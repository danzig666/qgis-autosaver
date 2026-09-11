autoSaver
=========

QGIS 3 plugin that saves the current project automatically.

Features
--------

* **Fixed interval** – every N minutes a countdown appears on the message bar
  with *Skip* and *Postpone* buttons; when it runs out the project is saved.
* **Backup file** – optionally the save goes to `<project>.bak.qgz` next to the
  project instead of overwriting it. The real project stays marked as unsaved,
  so QGIS still asks to save on exit. A new backup is only written when the
  project changed since the last one (QGIS 3.20 or newer; older versions
  write a backup on every interval).
* **Inactivity** – after N minutes without keyboard/mouse activity the project
  is backed up to `<project>.bak.qgz` (no prompt).
* **Layers in edit mode** – optionally modified layers are committed and put
  back into edit mode before the project is saved. Commit errors are reported.
* **Toolbar label** – shows the time left until the next autosave; clicking it
  resets both timers and cancels a pending countdown.

Nothing is saved while the project is clean, has never been saved to a file, or
is stored in a database (backup mode only).

Files
-----

* `__init__.py` – plugin entry point
* `autosave.py` – plugin logic
* `autosave_dialog.py` – settings dialog (built in code, no `.ui` file)
* `metadata.txt`, `icon.png`
