# -*- coding: utf-8 -*-
"""
autoSaver – QGIS plugin

* Fixed-interval autosave with an infobar countdown (skip / postpone).
* Optional inactivity autosave (always to the *.bak.qgz backup file).
* Optional commit of modified layers in edit mode.
* Toolbar label showing the time left until the next autosave;
  clicking it resets both timers.

Runs on QGIS 3.16+ and QGIS 4 with either PyQt5 or PyQt6: only scoped enums
are used and Qt-version-specific imports are guarded.

User-facing strings are English; translations live in i18n/autoSaver_<lang>.qm
and are picked by the QGIS interface language (Hungarian included).
"""

import os

from qgis.PyQt.QtCore import QCoreApplication, QEvent, QLocale, QObject, QSettings, QTimer, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QApplication, QPushButton
try:
    from qgis.PyQt.QtGui import QAction        # Qt 6
except ImportError:
    from qgis.PyQt.QtWidgets import QAction    # Qt 5

from qgis.core import Qgis, QgsApplication, QgsProject, QgsVectorLayer

from .autosave_dialog import autoSaverDialog

PLUGIN_DIR = os.path.dirname(__file__)
SETTINGS_PREFIX = "autoSaver/"

# Setting keys are kept identical to earlier versions so existing users keep
# their configuration. Booleans are stored as "true"/"false" strings for the
# same reason.
DEFAULTS = {
    "enabled": False,             # fixed-interval autosave
    "interval": 15,               # minutes
    "alternateBak": True,         # write *.bak.qgz instead of the real project file
    "saveLayerInEditMode": False, # commit modified layers in edit mode
    "leadTimeSec": 10,            # infobar countdown before a scheduled save
    "postponeMin": 2,             # "postpone" button delay
    "enableInactivity": False,    # autosave after a period of no user activity
    "inactivityInterval": 3,      # minutes
}


def _to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def _to_int(value, default):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return number if number >= 1 else default


def load_settings():
    """Read all plugin settings, falling back to DEFAULTS for missing/invalid values."""
    store = QSettings()
    result = {}
    for key, default in DEFAULTS.items():
        raw = store.value(SETTINGS_PREFIX + key, None)
        if raw is None:
            result[key] = default
        elif isinstance(default, bool):
            result[key] = _to_bool(raw)
        else:
            result[key] = _to_int(raw, default)
    return result


def save_settings(values):
    store = QSettings()
    for key, default in DEFAULTS.items():
        value = values.get(key, default)
        if isinstance(default, bool):
            store.setValue(SETTINGS_PREFIX + key, "true" if value else "false")
        else:
            store.setValue(SETTINGS_PREFIX + key, str(int(value)))


class autoSaver(QObject):
    """QGIS plugin implementation."""

    ACTIVITY_EVENTS = (
        QEvent.Type.KeyPress,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseMove,
        QEvent.Type.Wheel,
    )

    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.menu = "AutoSaver"
        self.action = None          # settings entry in the Plugins menu
        self.statusAction = None    # toolbar countdown label
        self.dlg = None             # settings dialog, created on first use

        self.translator = None
        self._installTranslator()

        self.settings = load_settings()
        self.defaultIntervalMs = 0

        # Fixed cadence timer
        self.cron = QTimer(self)
        self.cron.timeout.connect(self._onCronTimeout)

        # Toolbar refresh timer (10 s normally, 1 s below one minute)
        self.uiTicker = QTimer(self)
        self.uiTicker.setInterval(10000)
        self.uiTicker.timeout.connect(self._refreshToolbarCountdown)

        # Inactivity timer: single shot, restarted on every user activity
        self.inactivityTimer = QTimer(self)
        self.inactivityTimer.setSingleShot(True)
        self.inactivityTimer.timeout.connect(self._onInactivityTimeout)

        # Pre-save countdown
        self.pendingTimer = QTimer(self)
        self.pendingTimer.setSingleShot(True)
        self.pendingTimer.timeout.connect(self._performAutosaveIfStillPending)
        self.pendingWidget = None
        self.pendingForceBackup = False

        self._saving = False
        self._filterInstalled = False
        self._warnedNoFileName = False
        self._warnedDbProject = False

        # True when the project changed since the last *.bak.qgz backup.
        # Without this a backup would be rewritten every interval, because a
        # backup leaves the real project file unsaved (and therefore dirty).
        self._changedSinceBackup = True
        self._dirtySetConnected = False
        project = QgsProject.instance()
        try:
            project.dirtySet.connect(self._onProjectDirtySet)
            self._dirtySetConnected = True
        except AttributeError:
            pass  # QGIS < 3.20: backups are written on every interval instead
        for signal_name in ("readProject", "cleared"):
            try:
                getattr(project, signal_name).connect(self._onProjectReplaced)
            except AttributeError:
                pass

    # ------------------------------------------------------------------ lifecycle

    def tr(self, message):
        return QCoreApplication.translate("autoSaver", message)

    def _installTranslator(self):
        """Load i18n/autoSaver_<lang>.qm for the QGIS UI language, if present.

        Source strings are English; without a matching .qm the UI stays English.
        """
        try:
            locale = QgsApplication.locale()
        except AttributeError:
            locale = ""
        if not locale:
            store = QSettings()
            if _to_bool(store.value("locale/overrideFlag", False)):
                locale = str(store.value("locale/userLocale", ""))
            else:
                locale = QLocale.system().name()
        lang = str(locale).replace("-", "_").split("_")[0].lower()
        qm = os.path.join(PLUGIN_DIR, "i18n", "autoSaver_{0}.qm".format(lang))
        if not os.path.exists(qm):
            return
        translator = QTranslator()
        if translator.load(qm) and QCoreApplication.installTranslator(translator):
            self.translator = translator

    def initGui(self):
        icon = QIcon(os.path.join(PLUGIN_DIR, "icon.png"))
        self.action = QAction(icon, self.tr("AutoSaver settings…"), self.iface.mainWindow())
        self.action.setObjectName("autoSaverSettingsAction")
        self.action.setStatusTip(self.tr("Configure AutoSaver"))
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(self.menu, self.action)

        self.statusAction = QAction("AS: —", self.iface.mainWindow())
        self.statusAction.setObjectName("autoSaverStatusAction")
        self.statusAction.setToolTip(self.tr("Click to reset the autosave timer"))
        self.statusAction.triggered.connect(self._onStatusClicked)
        self.iface.addToolBarIcon(self.statusAction)

        self._applySettings()

    def unload(self):
        self._clearPendingPrompt()
        self.cron.stop()
        self.uiTicker.stop()
        self.inactivityTimer.stop()
        self._setActivityMonitoring(False)

        project = QgsProject.instance()
        if self._dirtySetConnected:
            try:
                project.dirtySet.disconnect(self._onProjectDirtySet)
            except (AttributeError, TypeError):
                pass
        for signal_name in ("readProject", "cleared"):
            try:
                getattr(project, signal_name).disconnect(self._onProjectReplaced)
            except (AttributeError, TypeError):
                pass

        if self.action:
            self.iface.removePluginMenu(self.menu, self.action)
            self.action = None
        if self.statusAction:
            self.iface.removeToolBarIcon(self.statusAction)
            self.statusAction = None
        if self.dlg is not None:
            self.dlg.close()
            self.dlg.deleteLater()
            self.dlg = None
        if self.translator is not None:
            QCoreApplication.removeTranslator(self.translator)
            self.translator = None

    # ------------------------------------------------------------------ settings

    def run(self):
        """Open the settings dialog; apply and persist on OK, discard on Cancel."""
        if self.dlg is None:
            self.dlg = autoSaverDialog(self.iface.mainWindow())
        self.dlg.setValues(self.settings)
        if self.dlg.exec():
            self.settings = self.dlg.values()
            save_settings(self.settings)
            self._applySettings()

    def _applySettings(self):
        """(Re)start timers and activity monitoring from self.settings."""
        self._clearPendingPrompt()

        if self.settings["enabled"]:
            self.defaultIntervalMs = self.settings["interval"] * 60000
            self.cron.start(self.defaultIntervalMs)
        else:
            self.defaultIntervalMs = 0
            self.cron.stop()

        self.inactivityTimer.stop()
        self.inactivityTimer.setInterval(self.settings["inactivityInterval"] * 60000)
        if self.settings["enableInactivity"]:
            self._setActivityMonitoring(True)
            self.inactivityTimer.start()
        else:
            self._setActivityMonitoring(False)

        self._syncUiTicker()

    # ------------------------------------------------------------------ activity monitoring

    def _setActivityMonitoring(self, enabled):
        app = QApplication.instance()
        if app is None:
            return
        if enabled and not self._filterInstalled:
            app.installEventFilter(self)
            self._filterInstalled = True
        elif not enabled and self._filterInstalled:
            app.removeEventFilter(self)
            self._filterInstalled = False

    def eventFilter(self, obj, event):
        try:
            if event.type() in self.ACTIVITY_EVENTS:
                self._noteUserActivity()
        except Exception:
            pass
        return False  # never consume the event

    def _noteUserActivity(self):
        timer = self.inactivityTimer
        if timer.interval() <= 0:
            return
        # Mouse moves arrive continuously; restarting more than once a second
        # is pointless and would also spam the toolbar refresh.
        if timer.isActive() and timer.interval() - timer.remainingTime() < 1000:
            return
        timer.start()
        if not self.uiTicker.isActive():
            self._syncUiTicker()

    # ------------------------------------------------------------------ project signals

    def _onProjectDirtySet(self):
        self._changedSinceBackup = True

    def _onProjectReplaced(self, *args):
        self._changedSinceBackup = True
        self._warnedNoFileName = False
        self._warnedDbProject = False

    # ------------------------------------------------------------------ timers

    def _onCronTimeout(self):
        # A postponed (shorter) interval must not become the permanent cadence.
        if self.defaultIntervalMs > 0 and self.cron.interval() != self.defaultIntervalMs:
            self.cron.start(self.defaultIntervalMs)
        self._autosaveCheck(force_backup=False, prompt=True)

    def _onInactivityTimeout(self):
        # Single shot: the timer restarts on the next user activity.
        self._autosaveCheck(force_backup=True, prompt=False,
                            reason=self.tr("Inactivity detected, autosaving…"))
        self._syncUiTicker()

    def _isPromptPending(self):
        return self.pendingTimer.isActive() or self.pendingWidget is not None

    def _autosaveCheck(self, force_backup, prompt, reason=None):
        """Decide whether anything needs saving; prompt or save accordingly."""
        if self._isPromptPending() or self._saving:
            return False

        needs_project, needs_layers = self._whatNeedsSaving(force_backup)
        if not needs_project and not needs_layers:
            return False

        if reason:
            self.iface.messageBar().pushMessage(
                "AutoSaver", reason, level=Qgis.MessageLevel.Info, duration=3)

        if prompt:
            self._promptAutosaveCountdown(force_backup)
        else:
            self._performAutosaveNow(force_backup)
        return True

    def _whatNeedsSaving(self, force_backup):
        """Returns (project_needs_save, layers_need_save).

        Only things the plugin will actually write count, so the user is never
        prompted for a save that would then do nothing.
        """
        needs_layers = bool(self.settings["saveLayerInEditMode"] and self._modifiedEditableLayers())

        project = QgsProject.instance()
        needs_project = False
        if project.isDirty():
            if not project.fileName():
                self._warnOnce("_warnedNoFileName", self.tr(
                    "The project has not been saved to a file yet, so it cannot be "
                    "autosaved. Save it manually once."))
            else:
                self._warnedNoFileName = False
                if force_backup or self.settings["alternateBak"]:
                    if self._backupFileName() is None:
                        self._warnOnce("_warnedDbProject", self.tr(
                            "Project stored in a database: saving to a separate "
                            "backup file (*.bak.qgz) is not supported."))
                    else:
                        needs_project = self._changedSinceBackup
                else:
                    needs_project = True
        return needs_project, needs_layers

    def _warnOnce(self, flag_name, text):
        if getattr(self, flag_name):
            return
        setattr(self, flag_name, True)
        self.iface.messageBar().pushMessage("AutoSaver", text,
                                            level=Qgis.MessageLevel.Warning, duration=10)

    # ------------------------------------------------------------------ pre-save prompt

    def _promptAutosaveCountdown(self, force_backup):
        lead_sec = self.settings["leadTimeSec"]
        postpone_min = self.settings["postponeMin"]
        self.pendingForceBackup = force_backup

        msg = self.tr("Autosave in {0} seconds…").format(lead_sec)
        if force_backup:
            msg += self.tr(" (backup copy)")
        bar = self.iface.messageBar()
        widget = bar.createMessage("AutoSaver", msg)

        btnSkip = QPushButton(self.tr("Skip this time"), widget)
        btnSkip.clicked.connect(self._skipThisAutosave)
        widget.layout().addWidget(btnSkip)

        btnPost = QPushButton(self.tr("Postpone {0} min").format(postpone_min), widget)
        btnPost.clicked.connect(self._postponeAutosave)
        widget.layout().addWidget(btnPost)

        self.pendingWidget = widget
        # duration=0: the message stays until we pop it ourselves, so the
        # widget cannot be auto-deleted underneath us.
        bar.pushWidget(widget, Qgis.MessageLevel.Info, 0)
        self.pendingTimer.start(lead_sec * 1000)

    def _clearPendingPrompt(self):
        self.pendingTimer.stop()
        widget, self.pendingWidget = self.pendingWidget, None
        if widget is not None:
            try:
                self.iface.messageBar().popWidget(widget)
            except Exception:
                pass  # the user already closed it

    def _skipThisAutosave(self):
        self._clearPendingPrompt()
        self._restartCronDefault()
        self.iface.messageBar().pushMessage("AutoSaver", self.tr("Autosave skipped."),
                                            level=Qgis.MessageLevel.Info, duration=4)

    def _postponeAutosave(self):
        self._clearPendingPrompt()
        postpone_min = self.settings["postponeMin"]
        self.cron.start(postpone_min * 60000)
        self._syncUiTicker()
        self.iface.messageBar().pushMessage(
            "AutoSaver", self.tr("Autosave postponed by {0} minutes.").format(postpone_min),
            level=Qgis.MessageLevel.Info, duration=4)

    def _performAutosaveIfStillPending(self):
        self._clearPendingPrompt()
        self._performAutosaveNow(self.pendingForceBackup)
        self._restartCronDefault()

    # ------------------------------------------------------------------ saving

    def _performAutosaveNow(self, force_backup):
        if self._saving:
            return
        self._saving = True
        try:
            self.iface.messageBar().pushMessage("AutoSaver", self.tr("Autosaving…"),
                                                level=Qgis.MessageLevel.Info, duration=3)
            QApplication.processEvents()
            if self.settings["saveLayerInEditMode"]:
                self._saveLayersInEditMode()
            self._saveCurrentProject(force_backup)
        finally:
            self._saving = False

    @staticmethod
    def _modifiedEditableLayers():
        """All modified vector layers in edit mode, hidden ones included."""
        return [
            layer for layer in QgsProject.instance().mapLayers().values()
            if isinstance(layer, QgsVectorLayer) and layer.isEditable() and layer.isModified()
        ]

    def _saveLayersInEditMode(self):
        bar = self.iface.messageBar()
        for layer in self._modifiedEditableLayers():
            if layer.commitChanges():
                layer.startEditing()
                bar.pushMessage("AutoSaver", self.tr("Layer saved: {0}").format(layer.name()),
                                level=Qgis.MessageLevel.Success, duration=3)
            else:
                # On failure the layer stays in edit mode with its changes intact.
                errors = "; ".join(layer.commitErrors()) or self.tr("unknown error")
                bar.pushMessage("AutoSaver",
                                self.tr("Failed to save layer {0}: {1}").format(layer.name(), errors),
                                level=Qgis.MessageLevel.Warning, duration=10)

    @staticmethod
    def _backupFileName():
        """*.bak.qgz path next to the project file, or None if not file-based."""
        project = QgsProject.instance()
        storage = getattr(project, "projectStorage", None)
        if storage is not None and storage() is not None:
            return None  # stored in GeoPackage / PostgreSQL etc.
        file_name = project.fileName()
        if not file_name:
            return None
        base, _ext = os.path.splitext(file_name)
        return base + ".bak.qgz"

    def _saveCurrentProject(self, force_backup):
        project = QgsProject.instance()
        if not project.isDirty():
            return
        original = project.fileName()
        if not original:
            return  # already warned in _whatNeedsSaving

        bar = self.iface.messageBar()
        use_bak = force_backup or self.settings["alternateBak"]
        if use_bak:
            target = self._backupFileName()
            if target is None:
                return  # already warned
            project.setFileName(target)
            try:
                ok = project.write()
            finally:
                project.setFileName(original)
                # The real project file is still unsaved: keep QGIS aware of it
                # so it asks to save on exit.
                project.setDirty(True)
            if ok:
                # Without the dirtySet signal we cannot tell when the next
                # change happens, so keep backing up every interval.
                self._changedSinceBackup = not self._dirtySetConnected
        else:
            target = original
            ok = project.write()

        if ok:
            bar.pushMessage("AutoSaver", self.tr("Project saved to: {0}").format(target),
                            level=Qgis.MessageLevel.Success, duration=3)
        else:
            bar.pushMessage("AutoSaver",
                            self.tr("Failed to save project: {0}").format(project.error()),
                            level=Qgis.MessageLevel.Critical, duration=10)

    # ------------------------------------------------------------------ toolbar countdown

    def _syncUiTicker(self):
        if self.cron.isActive() or self.inactivityTimer.isActive():
            if not self.uiTicker.isActive():
                self.uiTicker.start()
        else:
            self.uiTicker.stop()
        self._refreshToolbarCountdown()

    def _setStatusTextIdle(self):
        if self.statusAction:
            self.statusAction.setText("AS: —")
            self.statusAction.setToolTip(self.tr("Click to reset the autosave timer"))

    def _refreshToolbarCountdown(self):
        """Minutes (rounded up) when >= 60 s, seconds when < 60 s."""
        if not self.statusAction:
            return

        candidates = []
        if self.cron.isActive() and self.defaultIntervalMs > 0:
            candidates.append((self.cron.remainingTime(), self.tr("fixed interval")))
        if self.inactivityTimer.isActive():
            candidates.append((self.inactivityTimer.remainingTime(), self.tr("inactivity")))
        candidates = [c for c in candidates if c[0] >= 0]

        if not candidates:
            self._setStatusTextIdle()
            self.uiTicker.stop()
            return

        ms, source = min(candidates, key=lambda c: c[0])

        # Adaptive refresh: 1 s ticks below one minute, otherwise 10 s.
        wanted = 1000 if ms < 60000 else 10000
        if self.uiTicker.interval() != wanted:
            self.uiTicker.setInterval(wanted)

        if ms < 60000:
            text = "AS: {0}s".format((ms + 999) // 1000)
        else:
            text = "AS: {0}m".format((ms + 59999) // 60000)
        self.statusAction.setText(text)
        self.statusAction.setToolTip(
            self.tr("Click to reset the autosave timer")
            + " ({0} s, {1})".format(ms // 1000, source))

    def _onStatusClicked(self):
        """Reset both timers to their full intervals; cancel a pending prompt."""
        self._clearPendingPrompt()
        self._restartCronDefault()
        if self.settings["enableInactivity"]:
            self.inactivityTimer.start()
        self._syncUiTicker()
        self.iface.messageBar().pushMessage("AutoSaver", self.tr("Autosave timer reset."),
                                            level=Qgis.MessageLevel.Info, duration=3)

    def _restartCronDefault(self):
        if self.defaultIntervalMs > 0:
            self.cron.start(self.defaultIntervalMs)
        else:
            self.cron.stop()
        self._syncUiTicker()
