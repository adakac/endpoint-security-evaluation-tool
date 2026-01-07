'''
=====================================================================================
| IMPORTS                                                                           |
=====================================================================================
'''
from flask import Flask, render_template, request, abort, url_for, jsonify
from sqlalchemy import select
from markdown import markdown
from table_definitions import *
from helper import *
from pathlib import Path
from os import path
from magic import from_buffer
import pyexcel



'''
=====================================================================================
| FLASK APP AND DATABASE SETUP                                                      |
=====================================================================================
'''
app = Flask(__name__)

# Create 'db' folder if it doesn't exist and 'sheets' for uploaded XLSX/ODS files.
Path("db").mkdir(exist_ok=True)
Path("sheets").mkdir(exist_ok=True)

db = get_db_connection()
create_tables()

# Get all versions and check if any new versions are released.
app.config["new_versions"] = get_mitre_versions_api(db)

# Disable caching so the page is always reloaded and shows the most recent data.
# Else, if you change the status of a Change and go back to Overview, the change is not directly shown due to caching.
# @app.after_request allows us to change the response before sending it to the user.
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expire"] = "0"
    return response



'''
=====================================================================================
| Custom Jinja filter for parsing Markdown text.                                    |
| Converts a markdown string to HTML.                                               |
=====================================================================================
'''
@app.template_filter('markdown')
def markdown_filter(text):
    return markdown(text).strip()



'''
=====================================================================================
| The homepage let's users choose their current version and let's them start the    |
| upgrade.                                                                          |
=====================================================================================
'''
@app.route("/")
def homepage():
    # Get all ongoing upgrades from the database.
    current_upgrades = db.execute(
        select(MITREChange.from_version, MITREChange.to_version) \
        .group_by(MITREChange.from_version, MITREChange.to_version)
    ).all()

    # Convert to dictionary.
    current_upgrades = [{"from_version": row[0], "to_version": row[1]} for row in current_upgrades]

    # Get all MITRE versions.
    versions = get_mitre_versions_db(db)

    return render_template("homepage.html", title="Home", versions=versions, upgrades=current_upgrades, new_versions=app.config["new_versions"])



'''
=====================================================================================
| This function initialises an upgrade by:                                          |
| - Getting all the changes from the JSON changelog on the MITRE website.           |
| - Parsing the JSON file.                                                          |
| - Storing all changes to database to be able to track the progress.               |
=====================================================================================
'''
@app.route("/upgrade/initiate", methods=['POST'])
def initiate_upgrade():
    # Get the user selected version.
    version_select = request.form.get("version_select")

    # If the current upgrade is already in progress, don't fetch the data again.
    if upgrade_exists(version_select, db):
        return jsonify({"message": "Upgrade already exists"}), 400
    
    try:
        # Get the user selected version and the next version from the DB.
        from_version, to_version = get_versions_db(version_select, db)

        # If the current upgrade does not exist, get it from the MITRE site, parse it and store it in the DB.
        result = parse_version_changes(from_version.name, to_version.name)
    except Exception as e:
        return jsonify({"message": e}),400
    
    # Iterate over all results and write them to DB.
    for c in result:
        db.add(c)

    db.commit()
    
    return jsonify({
        "message": f"Successfully got the changelog from {from_version.name} to {to_version.name}. Click <a href=\"{url_for("upgrade", from_version=from_version.name, to_version=to_version.name)}\" target=\"_blank\">Link</a> to continue.",
        "url": url_for("upgrade", from_version=from_version.name, to_version=to_version.name),
        "url_text": f"{from_version.name} to {to_version.name}"
    }), 200



# TODO: Read the excel file and complete the other fields in the MITREChange database.
# --> Especially the criticalities.
def read_excel():
    return ""




'''
====================================================================================
| Opens a current upgrade.                                                         |
====================================================================================
'''
@app.route("/upgrade/<from_version>-<to_version>")
def upgrade(from_version, to_version):
    mitre_changes = get_changes(from_version, to_version, db)

    if not mitre_changes:
        abort(404)

    # Exclude all techniques that have sub-techniques
    changes = [c for c in mitre_changes if c.nr_sub_techniques == 0]

    return render_template("changes.html", title=f"{from_version} to {to_version}", changes=changes, from_version=from_version, to_version=to_version)


'''
=====================================================================================
| Opens a change in an upgrade.                                                     |
=====================================================================================
'''
@app.route("/upgrade/<from_version>-<to_version>/<mitre_id>", methods=['GET', 'POST'])
def change(from_version, to_version, mitre_id):
    change = get_change(db, from_version, to_version, mitre_id)

    try:
        other_changes = json.loads(change.other_changes)
    except:
        other_changes = ""

    try:
        platforms = json.loads(change.platforms)
    except:
        platforms = ""

    return render_template('change.html', change=change, other_changes=other_changes, platforms=platforms, title=mitre_id)


# Returns the URLs of the previous and next change.
@app.route("/api/links", methods=['POST'])
def links():
    data = request.get_json()
    from_version = data.get("from_version")
    to_version = data.get("to_version")
    mitre_id = data.get("mitre_id")
    filter = data.get("filter")

    # Get the current change and determine the previous change based on the current change.
    current_change = get_change(db, from_version, to_version, mitre_id)
    prev_change = get_previous_change(db, current_change, filter)
    next_change = get_next_change(db, current_change, filter)

    # Determine the URL of the previous change according to alphabetical order.
    prev_url = url_for('change', from_version=prev_change.from_version, to_version=prev_change.to_version, mitre_id=prev_change.mitre_id) if prev_change else None
    next_url = url_for('change', from_version=next_change.from_version, to_version=next_change.to_version, mitre_id=next_change.mitre_id) if next_change else None
    
    return jsonify({
        "prev_url": prev_url,
        "next_url": next_url
    }),200


'''
=====================================================================================
| Changes the status of a change.                                                   |
=====================================================================================
'''
@app.route("/api/change-status", methods=['POST'])
def change_status():
    data = request.get_json()
    from_version = data.get("from_version")
    to_version = data.get("to_version")
    mitre_id = data.get("mitre_id")
    status = data.get("status")

    # Get the object from database and change it.
    change = get_change(db, from_version, to_version, mitre_id)

    if not change:
        abort(404)

    change.status = status
    db.commit()

    return "",204



'''
=====================================================================================
| Changes the classification of a change and calculates all metrics                 |
| (e.g. criticality)                                                                |
=====================================================================================
'''
@app.route("/api/change-classification", methods=['POST'])
def change_classification():
    data = request.get_json()
    from_version = data.get("from_version")
    to_version = data.get("to_version")
    mitre_id = data.get("mitre_id")
    target = data.get("target")

    # Get the change from the DB.
    change = get_change(db, from_version, to_version, mitre_id)

    if not change:
        abort(404)

    if target == "client-criticality":
        change.client_criticality = int(data.get("value"))
    elif target == "infra-criticality":
        change.infra_criticality = int(data.get("value"))
    elif target == "service-criticality":
        change.service_criticality = int(data.get("value"))
    elif target == "confidentiality":
        change.confidentiality = not change.confidentiality
    elif target == "integrity":
        change.integrity = not change.integrity
    elif target == "availability":
        change.availability = not change.availability

    # After each change, calculate the sums again.
    change.client_criticality_sum = client_sum(change)
    change.infra_criticality_sum = infra_sum(change)
    change.service_criticality_sum = service_sum(change)
    db.commit()

    return jsonify({
        "message": "Updated database",
        "client_criticality_sum": change.client_criticality_sum,
        "infra_criticality_sum": change.infra_criticality_sum,
        "service_criticality_sum": change.service_criticality_sum
    }),200



@app.route("/api/upload-file", methods=['POST'])
def upload_file():
    file = request.files.get("file")
    file_ext = file.filename.lower().split(".")[-1]

    # Find out mimetype by reading the contents of the file.
    file_bytes = file.read()
    file.seek(0)
    mimetype = from_buffer(file_bytes, mime=True)

    # Check the file. Only ods and xlsx is allowed.
    allowed_extensions = ["ods", "xlsx"]
    allowed_mimetypes = [
        # ODS
        "application/vnd.oasis.opendocument.spreadsheet",
        # XLSX
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        # XLSX files are basically ZIP files and are sometimes detected as application/zip.
        "application/zip"
    ]

    if file_ext not in allowed_extensions or mimetype not in allowed_mimetypes:
        return jsonify({"message": "Unsupported Filetype"}),400

    # Get all data and construct a filename.
    from_version = request.form.get("from_version")
    to_version = request.form.get("to_version")
    file_name = f"mitreattck_eval_{from_version}_{to_version}.{file_ext}"
    file_path = path.join("sheets", file_name)
    
    # Save the file to disk.
    file.save(file_path)


    # Open excel with pyexcel
    workbook = pyexcel.get_book(file_name=file_path, name_columns_by_row=0)
    sheet = workbook["MITRE_ATT&CK"]

    # First row are the headers, everything else is the data.
    rows = sheet.to_array() # one array per row
    headers = rows[0]
    data = rows[1:]

    # Convert array to dict (one dict per row).
    sheet_dict = [dict(zip(headers, row)) for row in data]

    # Read the excel and fill out the database.
    for c in get_changes(from_version, to_version, db):
        row = next(
            (
                r for r in sheet_dict
                if r["MITREID"] == c.mitre_id
            )
        , {})

        if not row:
            continue

        c.client_criticality = 0 if row["Client Criticality"] == "n.a." else row["Client Criticality"]
        c.client_criticality_sum = 0 if row["Sum Criticality (Client)"] == "n.a." else row["Sum Criticality (Client)"]

        c.infra_criticality = 0 if row["Infrastructure Criticality"] == "n.a." else row["Infrastructure Criticality"]
        c.infra_criticality_sum = 0 if row["Sum Criticality (Infra)"] == "n.a." else row["Sum Criticality (Infra)"]

        c.service_criticality = 0 if row["Service Criticality"] == "n.a." else row["Service Criticality"]
        c.service_criticality_sum = 0 if row["Sum Criticality (Service)"] == "n.a." else row["Sum Criticality (Service)"]

        c.confidentiality = True if row["Confidentiality"] == "x" else False
        c.integrity = True if row["Integrity"] == "x" else False
        c.availability = True if row["Availability"] == "x" else False

    db.commit()

    return jsonify({
        "message": "Successfully loaded and read file. Database is updated. Refresh the site to see the changes."
    }),200




'''
=====================================================================================
| Start the flask server in debug mode and on port 8000.                            |
=====================================================================================
'''
# TODO: Remove Debugging mode when going productive.
if __name__ == "__main__":
    app.run(debug=True, port=8000)