# -*- coding: utf-8 -*-
"""
autoSaverDialog – settings dialog, built in code with layouts and spin boxes
so every value is guaranteed to be an integer within range.
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)


class autoSaverDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AutoSaver")

        # --- fixed-interval autosave ---
        self.enableAutoSave = QGroupBox(self.tr("Mentés rögzített időközönként"))
        self.enableAutoSave.setCheckable(True)
        fixedForm = QFormLayout(self.enableAutoSave)

        self.interval = self._spin(1, 1440, self.tr(" perc"))
        fixedForm.addRow(self.tr("Időköz:"), self.interval)

        self.enableAlternate = QCheckBox(self.tr("Külön biztonsági fájlba (*.bak.qgz) a projektfájl helyett"))
        fixedForm.addRow(self.enableAlternate)

        self.leadTimeSec = self._spin(1, 600, self.tr(" mp"))
        self.leadTimeSec.setToolTip(self.tr("Visszaszámlálás hossza az infósávon a mentés előtt."))
        fixedForm.addRow(self.tr("Figyelmeztetés a mentés előtt:"), self.leadTimeSec)

        self.postponeMin = self._spin(1, 1440, self.tr(" perc"))
        self.postponeMin.setToolTip(self.tr("A „Halasztás” gomb ennyivel tolja el a mentést."))
        fixedForm.addRow(self.tr("Halasztás hossza:"), self.postponeMin)

        # --- inactivity autosave ---
        self.enableInactivity = QGroupBox(self.tr("Mentés inaktivitás esetén"))
        self.enableInactivity.setCheckable(True)
        inactivityForm = QFormLayout(self.enableInactivity)

        self.inactivityInterval = self._spin(1, 1440, self.tr(" perc"))
        inactivityForm.addRow(self.tr("Inaktivitási idő:"), self.inactivityInterval)

        note = QLabel(self.tr("Az inaktivitási mentés mindig a biztonsági fájlba (*.bak.qgz) történik."))
        note.setWordWrap(True)
        inactivityForm.addRow(note)

        # --- common ---
        self.enableSaveLayers = QCheckBox(self.tr("Szerkesztés alatt álló rétegek módosításainak mentése is"))
        self.enableSaveLayers.setToolTip(self.tr("A módosított rétegeket rögzíti (commit), majd újra szerkesztő módba teszi."))

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.enableAutoSave)
        layout.addWidget(self.enableInactivity)
        layout.addWidget(self.enableSaveLayers)
        layout.addStretch(1)
        layout.addWidget(self.buttonBox)

    def tr(self, message):
        return QCoreApplication.translate("autoSaverDialog", message)

    def _spin(self, minimum, maximum, suffix):
        box = QSpinBox(self)
        box.setRange(minimum, maximum)
        box.setSuffix(suffix)
        return box

    # ------------------------------------------------------------------ values

    def setValues(self, values):
        self.enableAutoSave.setChecked(values["enabled"])
        self.interval.setValue(values["interval"])
        self.enableAlternate.setChecked(values["alternateBak"])
        self.leadTimeSec.setValue(values["leadTimeSec"])
        self.postponeMin.setValue(values["postponeMin"])
        self.enableInactivity.setChecked(values["enableInactivity"])
        self.inactivityInterval.setValue(values["inactivityInterval"])
        self.enableSaveLayers.setChecked(values["saveLayerInEditMode"])

    def values(self):
        return {
            "enabled": self.enableAutoSave.isChecked(),
            "interval": self.interval.value(),
            "alternateBak": self.enableAlternate.isChecked(),
            "leadTimeSec": self.leadTimeSec.value(),
            "postponeMin": self.postponeMin.value(),
            "enableInactivity": self.enableInactivity.isChecked(),
            "inactivityInterval": self.inactivityInterval.value(),
            "saveLayerInEditMode": self.enableSaveLayers.isChecked(),
        }
