'''
=====================================================================================
| IMPORTS                                                                           |
=====================================================================================
'''
from flask import Flask, render_template, request, abort, url_for, jsonify, send_file
from sqlalchemy import select
from markdown import markdown
from table_definitions import *
import helper as hp
from pathlib import Path
from os import path
from ods import ODSException
from xlsx import XLSXException



'''
=====================================================================================
| FLASK APP AND DATABASE SETUP                                                      |
=====================================================================================
'''
app = Flask(__name__)

# Create 'db' folder if it doesn't exist and 'sheets' for uploaded XLSX/ODS files.
Path("db").mkdir(exist_ok=True)
Path("sheets").mkdir(exist_ok=True)

# Get a DB session object and create all tables in the DB if not already happened.
db = get_db_connection()
create_tables()

# Get all versions and check if any new versions are released.
app.config["new_versions"] = hp.get_mitre_versions_api(db)

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
    upgrades = db.execute(
        select(MITREChange.from_version, MITREChange.to_version) \
        .group_by(MITREChange.from_version, MITREChange.to_version)
    ).all()

    # Convert to dictionary.
    upgrades = [{"from_version": row[0], "to_version": row[1]} for row in upgrades]

    # Get all MITRE versions.
    versions = hp.get_mitre_versions_db(db)

    return render_template(
        "homepage.html",
        title="Home",
        versions=versions,
        upgrades=upgrades,
        new_versions=app.config["new_versions"]
    )



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
    if hp.upgrade_exists(version_select, db):
        return jsonify({"message": "Upgrade already exists"}), 400
    
    try:
        # Get the user selected version and the next version from the DB.
        from_version, to_version = hp.get_versions_db(version_select, db)

        # If the current upgrade does not exist, get it from the MITRE site, parse it and store it in the DB.
        result = hp.parse_version_changes(from_version.name, to_version.name)
    except Exception as e:
        return jsonify({"message": "An Error occured while getting information from MITRE. Please make sure you have an internet connection."}), 400
    
    # Iterate over all results and write them to DB.
    for c in result:
        db.add(c)

    db.commit()
    
    return jsonify({
        "message": f"Successfully got the changelog from {from_version.name} to {to_version.name}. Click <a href=\"{url_for("upgrade", from_version=from_version.name, to_version=to_version.name)}\" target=\"_blank\">Link</a> to continue.",
        "url": url_for("upgrade", from_version=from_version.name, to_version=to_version.name),
        "url_text": f"{from_version.name} to {to_version.name}"
    }), 200



'''
====================================================================================
| Opens a current upgrade and displays all changes in an overview.                 |
====================================================================================
'''
@app.route("/upgrade/<from_version>-<to_version>")
def upgrade(from_version, to_version):
    changes = hp.get_changes(from_version, to_version, db)

    if not changes:
        abort(404)

    # Get spreadsheet file for this version if the user has uploaded one.
    file_name = hp.get_spreadsheet_filename(from_version, to_version)

    return render_template(
        "changes.html",
        title=f"{from_version} to {to_version}",
        changes=changes,
        from_version=from_version,
        to_version=to_version,
        file_name=file_name
    )



'''
=====================================================================================
| Opens a change in an upgrade.                                                     |
=====================================================================================
'''
@app.route("/upgrade/<from_version>-<to_version>/<mitre_id>")
def change(from_version, to_version, mitre_id):
    change = hp.get_change(db, from_version, to_version, mitre_id)

    other_changes = hp.load_json(change.other_changes)
    platforms = hp.load_json(change.platforms)

    # Links to the MITRE page for the old and new versions of the technique.
    mitre_link_old = f"https://attack.mitre.org/versions/{from_version.split(".")[0]}/techniques/{mitre_id.replace(".", "/")}" \
        if change.change_category != "additions" \
        else None
    
    mitre_link_new = f"https://attack.mitre.org/versions/{to_version.split(".")[0]}/techniques/{mitre_id.replace(".", "/")}"

    return render_template(
        "change.html",
        change=change,
        other_changes=other_changes,
        platforms=platforms,
        title=mitre_id,
        mitre_link_old=mitre_link_old,
        mitre_link_new=mitre_link_new
    )



'''
=====================================================================================
| This function receives a change from the frontend and returns the previous and    |
| next changes in alphabetical order (-> tactics, techniques and sub-techniques in  |
| ascending order). The function then returns the links to the next and the previous|
| changes. Users in the frontend can then easily skip to next and previous changes. |
=====================================================================================
'''
# Returns the URLs of the previous and next change.
@app.route("/api/links", methods=['POST'])
def links():
    # Get all data from the frontend.
    data = request.get_json()
    from_version = data.get("from_version")
    to_version = data.get("to_version")
    mitre_id = data.get("mitre_id")
    filter = data.get("filter")

    # Get the current change and determine the previous change based on the current change.
    current_change = hp.get_change(db, from_version, to_version, mitre_id)
    prev_change = hp.get_previous_change(db, current_change, filter)
    next_change = hp.get_next_change(db, current_change, filter)

    # Determine the URL of the previous and next change.
    prev_url = url_for('change', from_version=prev_change.from_version, to_version=prev_change.to_version, mitre_id=prev_change.mitre_id) if prev_change else None
    next_url = url_for('change', from_version=next_change.from_version, to_version=next_change.to_version, mitre_id=next_change.mitre_id) if next_change else None
    
    return jsonify({
        "prev_url": prev_url,
        "next_url": next_url
    }), 200



'''
=====================================================================================
| This function changes the status of a change (e.g. Done, In Progress, Not Done).  |
=====================================================================================
'''
@app.route("/api/change-status", methods=['POST'])
def change_status():
    # Get the data from the frontend.
    data = request.get_json()
    from_version = data.get("from_version")
    to_version = data.get("to_version")
    mitre_id = data.get("mitre_id")
    status = data.get("status")

    # Get the object from database and change it.
    change = hp.get_change(db, from_version, to_version, mitre_id)

    if not change:
        abort(404)

    change.status = status
    db.commit()
    return "", 204



'''
=====================================================================================
| Changes the classification of a change and calculates all metrics                 |
| (e.g. client/infrastructure/service criticality).                                 |
=====================================================================================
'''
@app.route("/api/change-classification", methods=['POST'])
def change_classification():
    # Get the data from the frontend.
    data = request.get_json()
    from_version = data.get("from_version")
    to_version = data.get("to_version")
    mitre_id = data.get("mitre_id")
    target = data.get("target")

    # Get the change from the DB.
    change = hp.get_change(db, from_version, to_version, mitre_id)

    if not change:
        abort(404)

    # Update the according metric and write to the DB.
    if target == "client-criticality":
        change.client_criticality = int(data.get("value"))
    elif target == "infra-criticality":
        change.infra_criticality = int(data.get("value"))
    elif target == "service-criticality":
        change.service_criticality = int(data.get("value"))
    elif target == "confidentiality":
        # Boolean value. If clicked change it to the opposite.
        change.confidentiality = not change.confidentiality
    elif target == "integrity":
        change.integrity = not change.integrity
    elif target == "availability":
        change.availability = not change.availability

    # After each change, calculate the sums again.
    change.client_criticality_sum = hp.client_sum(change)
    change.infra_criticality_sum = hp.infra_sum(change)
    change.service_criticality_sum = hp.service_sum(change)
    db.commit()

    return jsonify({
        "client_criticality_sum": change.client_criticality_sum,
        "infra_criticality_sum": change.infra_criticality_sum,
        "service_criticality_sum": change.service_criticality_sum
    }), 200



'''
=====================================================================================
| Handles the upload of the XLSX/ODS file that contains all techniques. The         |
| function imports all data from the file to the SQLite DB (but only if the         |
| according technique is part of the DB).                                           |
=====================================================================================
'''
@app.route("/api/upload-file", methods=['POST'])
def upload_file():
    # Get the file object from the frontend.
    file = request.files.get("file")

    # Get all data.
    from_version = request.form.get("from_version")
    to_version = request.form.get("to_version")
    
    # Upload the file and get the file_path.
    try:
        file_path = hp.handle_upload(file, from_version, to_version)
    except Exception as e:
        return jsonify({"message": "Upload failed. Please make sure that the file is either a .ods or .xlsx file."}), 400

    # Import the file into the DB.
    try:
        hp.import_file(file_path, from_version, to_version, db)
    except Exception as e:
        return jsonify({"message": str(e)}), 400

    return jsonify({
        "message": "Successfully loaded and read file. Database is updated. Refresh the site to see the changes."
    }), 200



'''
=====================================================================================
| Handles the export of the SQLite database. All changes are exported to their      |
| respective spreadsheet file (.ods or .xlsx). When the export file is created      |
| a download link is returned to the user.                                          |
=====================================================================================
'''
@app.route("/api/export-file", methods=['POST'])
def export_file():
    data = request.get_json()
    from_version = data.get("from_version")
    to_version = data.get("to_version")

    # Export spreadsheet file of a specific upgrade.
    try:
        hp.export_file(from_version, to_version, db)
    except (XLSXException, ODSException) as e:
        return jsonify({"message": str(e)}), 400

    return jsonify({
        "message": "File has been successfully exported.",
        "download_url": url_for('download_exported_file', from_version=from_version, to_version=to_version)
    })



'''
=====================================================================================
| Returns the exported file to the user for download.                               |
=====================================================================================
'''
@app.route("/api/download-file/<from_version>-<to_version>")
def download_exported_file(from_version, to_version):
    file = Path(path.join("sheets", f"EXPORT_{hp.get_spreadsheet_filename(from_version, to_version)}"))

    if (not file.exists()):
        abort(404)

    return send_file(file, as_attachment=True)



'''
=====================================================================================
| Changes the Client/Service/Infrastructure evaluation status of a technique.       |
=====================================================================================
'''
@app.route("/api/change-evaluation-status", methods=['POST'])
def change_evaluation_status():
    data = request.get_json()
    from_version = data.get("from_version")
    to_version = data.get("to_version")
    mitre_id = data.get("mitre_id")
    target = data.get("target")
    value = data.get("value")
    change = hp.get_change(db, from_version, to_version, mitre_id)

    if not change:
        abort(404)

    if target == "client-status":
        change.client_evaluation_status = value
    elif target == "infra-status":
        change.infra_evaluation_status = value
    elif target == "service-status":
        change.service_evaluation_status = value
    else:
        return "", 400

    db.commit()
    return "", 204



'''
=====================================================================================
| Changes the Client/Service/Infrastructure Reasoning or Measures of a technique.   |
=====================================================================================
'''
@app.route("/api/change-reasoning-and-measures", methods=['POST'])
def change_reasoning_and_measures():
    data = request.get_json()
    from_version = data.get("from_version")
    to_version = data.get("to_version")
    mitre_id = data.get("mitre_id")
    target = data.get("target")
    text = data.get("text")
    change = hp.get_change(db, from_version, to_version, mitre_id)

    if not change:
        abort(404)

    if target == "client-reasoning":
        change.client_reasoning = text
    elif target == "client-measures":
        change.client_measures = text
    elif target == "infra-reasoning":
        change.infra_reasoning = text
    elif target == "infra-measures":
        change.infra_measures = text
    elif target == "service-reasoning":
        change.service_reasoning = text
    elif target == "service-measures":
        change.service_measures = text
    else:
        return jsonify({"message": "Invalid target."}), 400
    
    db.commit()
    return jsonify({"message": "Saved!"}), 200



'''
=====================================================================================
| Start the flask server in debug mode and on port 8000.                            |
=====================================================================================
'''
# TODO: Remove Debugging mode when going productive.
if __name__ == "__main__":
    app.run(debug=True, port=8000)