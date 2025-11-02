# endpoint-security-evaluation-tool
A web-based tool to increase efficiency of ESE updates.

This tool provides a Web UI that guides users through the upgrade of ESE when a new MITRE version is released.

The backend is made with Python Flask to retrieve all changes that were made in the new MITRE version. The changes are then parsed and the needed information is extracted and written to a SQLite database to keep track of the upgrade progress and to be able to pause and continue later.

In the Web UI the progress is dynamically updated every time the status of a change has been changed.

## Libraries

Python:
- markdown
- sqlalchemy
- flask
- glom
- requests

JavaScript & CSS:
- Bootstrap 5.3.8
- Bootstrap Icons v1.13.1
- jQuery
- diff