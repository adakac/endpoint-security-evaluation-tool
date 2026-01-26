# endpoint-security-evaluation-tool

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

The backend is made with Python Flask to retrieve all changes that were made in the new MITRE version. The changes are then parsed and the needed information is extracted and written to a SQLite database to keep track of the upgrade progress and to be able to pause and continue later.

In the Web UI the progress is dynamically updated every time the status of a change has been changed.

## Installation

```
git clone https://github.com/adakac/endpoint-security-evaluation-tool.git
pip install markdown sqlalchemy flask glom requests openpyxl odfpy
python ese.py
```

This automatically starts the web UI on port 8000. Then simply go to [http://localhost:8000](http://localhost:8000).

A SQLite database is automatically created in ```./db```.