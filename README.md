# Endpoint Security Evaluation Helper Tool
<a href="https://github.com/adakac/endpoint-security-evaluation-tool/releases/latest"><img src="https://img.shields.io/github/v/release/adakac/endpoint-security-evaluation-tool?label=Release&color=brightgreen&cacheSeconds=3600" alt="Release"/></a>
<a href="./LICENSE.txt">[![CC BY 4.0][cc-by-shield]][cc-by]</a>

A web-based tool to increase efficiency of [ESE](https://github.com/adakac/endpoint-security-evaluation-spreadsheet) updates.

## Introduction
The backend is made with Python Flask to retrieve all changes that were made in the new MITRE version. The changes are then parsed and the needed information is extracted and written to a SQLite database to keep track of the upgrade progress and to be able to pause and continue later.

In the Web UI the progress is dynamically updated every time the status of a change has been changed.

## Goal
This is a web-based tool to increase efficiency of ESE updates.

The current update process from one MITRE version to the next was very tedious:
- No tracking of the status.
- MITRE doesn't highlight the differences between two versions very well.
- No integration of the ESE spreadsheet. Everything must be written into the spreadsheet manually.

This tool provides a Web UI that guides users through the upgrade of ESE when a new MITRE version is released.

The following features help the user making more efficient upgrades:
- All important information can be seen on a single, nice formatted webpage (e.g. technique, tactics, what exactly changed, platforms, ...).
- The differences between the old and the new description of a technique are highlighted, so you can immediately see what exactly changed.
- User can easily skip to the next or previous change.
- Users can track their status. The status is dynamically updated once a change is set to "Done".
- Users can filter by status (e.g. all changes that are "Done", "In Progress" or "Not Done").
- Integration of ESE:
  - Users can directly classify the criticality of the technique during the upgrade process.
  - A criticality score is calculated dynamically and displayed for the user.
  - Users can directly document which measures they have already taken to mitigate the risk and which measures could be done further.
  - Users can set the status of the measures (e.g. partial, completed).
  - Users can import and export an existing ESE spreadsheet.

## Tech Stack

Backend:
- Python Flask
- SQLAlchemy
- Jinja2 Templating Engine
- SQLite DB
- openpyxl for reading/writing xlsx files
- odfpy for reading/writing ods files

Frontend:
- jQuery
- Bootstrap 5.3.8
- Bootstrap Icons v1.13.1
- HTML
- CSS
- [jsdiff](https://github.com/kpdecker/jsdiff)

## Installation

### Python Version

This project has been developed with Python version 3.13.9.

### Running with Python from Source code

```
git clone https://github.com/adakac/endpoint-security-evaluation-tool.git
pip install markdown sqlalchemy flask glom requests openpyxl odfpy
python ese.py
```

This automatically starts the web UI on port 8000. Then simply go to [http://localhost:8000](http://localhost:8000).

A SQLite database is automatically created in ```./db```.

### Creating an executable file with PyInstaller

** Windows: **
```
pip install pyinstaller
python -m PyInstaller --onefile --add-data "templates;templates" --add-data "static;static" ese.py
```

** Linux: **
```
pip install pyinstaller
python -m PyInstaller --onefile --add-data "templates:templates" --add-data "static:static" ese.py
```

The executable file will be created in ```./dist```. You can delete the ```*.spec``` file afterwards.

### Running directly from the provided executable files

See Releases.

## Thanks
- Thanks to [mani5789](https://github.com/mani5789) for creating the [ESE Helper Tool](https://github.com/adakac/endpoint-security-evaluation-tool) with us.

## Disclaimer
This project has NO affiliation with, sponsorship, or endorsement by MITRE. This project does NOT represent the views and opinions of MITRE or MITRE personnel.

## Licensing
[![CC BY 4.0][cc-by-shield]][cc-by]

This work is licensed under a
[Creative Commons Attribution 4.0 International License][cc-by].

[![CC BY 4.0][cc-by-image]][cc-by]

[cc-by]: http://creativecommons.org/licenses/by/4.0/
[cc-by-image]: https://i.creativecommons.org/l/by/4.0/88x31.png
[cc-by-shield]: https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg

You are free to:
* Share — copy and redistribute the material in any medium or format for any purpose, even commercially.
* Adapt — remix, transform, and build upon the material for any purpose, even commercially.
* The licensor cannot revoke these freedoms as long as you follow the license terms.

Under the following terms:
* Attribution — You must give appropriate credit , provide a link to the license, and indicate if changes were made . You may do so in any reasonable manner, but not in any way that suggests the licensor endorses you or your use.
* No additional restrictions — You may not apply legal terms or technological measures that legally restrict others from doing anything the license permits.
