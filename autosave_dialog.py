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
        self.enableAutoSave = QGroupBox(self.tr("Save at a fixed interval"))
        self.enableAutoSave.setCheckable(True)
        fixedForm = QFormLayout(self.enableAutoSave)

        self.interval = self._spin(1, 1440, self.tr(" min"))
        fixedForm.addRow(self.tr("Interval:"), self.interval)

        self.enableAlternate = QCheckBox(self.tr("Save to a separate backup file (*.bak.qgz) instead of the project file"))
        fixedForm.addRow(self.enableAlternate)

        self.leadTimeSec = self._spin(1, 600, self.tr(" s"))
        self.leadTimeSec.setToolTip(self.tr("Length of the countdown shown on the message bar before saving."))
        fixedForm.addRow(self.tr("Warning before saving:"), self.leadTimeSec)

        self.postponeMin = self._spin(1, 1440, self.tr(" min"))
        self.postponeMin.setToolTip(self.tr("The \"Postpone\" button delays the save by this much."))
        fixedForm.addRow(self.tr("Postpone length:"), self.postponeMin)

        # --- inactivity autosave ---
        self.enableInactivity = QGroupBox(self.tr("Save on inactivity"))
        self.enableInactivity.setCheckable(True)
        inactivityForm = QFormLayout(self.enableInactivity)

        self.inactivityInterval = self._spin(1, 1440, self.tr(" min"))
        inactivityForm.addRow(self.tr("Inactivity time:"), self.inactivityInterval)

        note = QLabel(self.tr("Inactivity saves always go to the backup file (*.bak.qgz)."))
        note.setWordWrap(True)
        inactivityForm.addRow(note)

        # --- common ---
        self.enableSaveLayers = QCheckBox(self.tr("Also save changes of layers in edit mode"))
        self.enableSaveLayers.setToolTip(self.tr("Commits modified layers, then puts them back into edit mode."))

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
