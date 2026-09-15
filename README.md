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
* **Toolbar countdown** – a small two-line button: time left until the next
  fixed-interval save on top, the inactivity countdown below (which restarts on
  every mouse/keyboard action, so it only counts down while you are not
  working). `—` means that timer is off or waiting. The tooltip lists both
  timers and the date and time of the last autosave. Left click resets both
  timers and cancels a pending countdown; right click opens the settings.

Nothing is saved while the project is clean, has never been saved to a file, or
is stored in a database (backup mode only).

Languages
---------

The interface follows the QGIS language setting (Settings → Options → General).
Source strings are English; Hungarian is provided in `i18n/autoSaver_hu.ts`.
Any other language falls back to English.

To add a language, copy `i18n/autoSaver_hu.ts` to `i18n/autoSaver_<lang>.ts`,
translate the `<translation>` entries, and compile it with Qt's `lrelease`
(for example `pyside6-lrelease autoSaver_<lang>.ts -qm autoSaver_<lang>.qm`).
The plugin loads `i18n/autoSaver_<lang>.qm` where `<lang>` is the two-letter
code of the QGIS locale.

Files
-----

* `__init__.py` – plugin entry point
* `autosave.py` – plugin logic
* `autosave_dialog.py` – settings dialog (built in code, no `.ui` file)
* `i18n/` – translation sources (`.ts`) and compiled files (`.qm`)
* `metadata.txt`, `icon.png`
