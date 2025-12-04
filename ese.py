'''
=====================================================================================
| IMPORTS                                                                           |
=====================================================================================
'''
from requests import get
import re, json
from flask import Flask, render_template, request, abort, redirect, url_for, jsonify, session
from sqlalchemy import Column, Integer, Text, create_engine, Boolean, and_, select
from sqlalchemy.orm import DeclarativeBase, Session, declarative_base
from markdown import markdown
from glom import glom



'''
=====================================================================================
| FLASK APP AND DATABASE SETUP                                                      |
=====================================================================================
'''
app = Flask(__name__)
Base = declarative_base()
engine = create_engine('sqlite:///db/mitre_changes.db', echo=False)
db = Session(engine)

# Setting global variables.
# app.config can be used for settings or static values that can be accessed anywhere in the app.
# If you don't use app.config for global variables, they are not available in routes.
# NEW_VERSIONS stores a string array of newly available versions.
# NEW_VERSIONS_AVAILABLE stores a bool value that indicates if a new MITRE version is available.
# app.config["NEW_VERSIONS"] = []
# app.config["NEW_VERSIONS_AVAILABLE"] = False

NEW_VERSIONS = []

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
| DATABASE SCHEME                                                                   |
=====================================================================================
'''
# The following table stores each upgrade. For each change in an upgrade there is a comparison between the new and old description.
# Changes can be tracked via a status.
class MITREChange(Base):
    __tablename__ = "mitre_changes"
    change_id = Column(Integer, primary_key=True, autoincrement=True)
    mitre_id = Column(Text)
    url = Column(Text)
    technique_name = Column(Text)
    technique_tactic = Column(Text)
    change_category = Column(Text)
    old_description = Column(Text)
    new_description = Column(Text)
    from_version = Column(Text)
    to_version = Column(Text)
    status = Column(Text, default="Not Done")
    client_criticality = Column(Integer)
    client_criticality_sum = Column(Integer)
    infra_criticality = Column(Integer)
    infra_criticality_sum = Column(Integer)
    service_criticality = Column(Integer)
    service_criticality_sum = Column(Integer)



# Table for all current MITRE versions to compare.
class MITREVersions(Base):
    __tablename__ = "mitre_versions"
    major = Column(Integer, primary_key=True)
    minor = Column(Integer, primary_key=True)
    name = Column(Text)

# Create the tables, if not already created.
Base.metadata.create_all(engine)



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
| This function gets all current MITRE versions available.                          |
| It stores versions that are not on the local DB to the local DB.                  |
| The function returns all new versions in a list.                                  |
=====================================================================================
'''
def get_mitre_versions_api():
    # To get the MITRE versions, we could either scrape the website which is not the most stable idea, but we can get all versions currently available. Also the website only lists the newest minor version per major version.
    # Alternatively, we can use the Github API to get all releases. But here we can only get MITRE versions from up to 8.0. Versions below were not pushed to Github.

    # Github API allows us to fetch all releases up from v8.0. Versions below were not pushed to Github by MITRE.
    req = get("https://api.github.com/repos/mitre/cti/releases")

    # If error, exit the function.
    # Happens mainly due to Githubs API rate limits.
    if req.status_code >= 400:
        return

    # Iterate over all versions search for key "tag_name" which looks like this: 'ATT&CK-v18.0'.
    # Then we extract the version like this: 'v18.0' and check if the version string matches the supplied regex.
    versions = req.json()
    versions = [t for v in versions if (t := str(v.get("tag_name").split('-')[1])) and re.search(r"^v\d{1,2}\.\d$", t)]

    # Check if new version and write any versions that are not in the database to the database.
    res = []
    for v in versions:
        # Split up into major and minor version and check DB.
        major, minor = map(int, v[1:].split('.'))
        v_db = db.scalars(select(MITREVersions).where((MITREVersions.major == major) & (MITREVersions.minor == minor))).all()

        # If new versions available, write to DB and set global variables.
        if not v_db:
            res.append(v)
            db.add(MITREVersions(major = major, minor = minor, name = v))
        
    db.commit()
    return res

# TODO: Use session['NEW_VERSIONS] = get_mitre_versions_api() for global access.
new_versions = get_mitre_versions_api()

'''
=====================================================================================
| Get all MITRE versions from the DB in a descending order.                         |
=====================================================================================
'''
def get_mitre_versions_db():
    return db.scalars(
        select(MITREVersions).order_by(
            MITREVersions.major.desc(),
            MITREVersions.minor.desc()
        )
    ).all()

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
    versions = get_mitre_versions_db()

    # TODO: Show notification when new MITRE version releases.
    return render_template("homepage.html", versions=versions, upgrades=current_upgrades, new_versions="")




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
    print(version_select)
    
    # Get the user selected version from DB.
    from_version = db.scalar(select(MITREVersions).where(MITREVersions.name == version_select))
    print(from_version.name)

    # Check if the next version is a minor version.
    to_version = db.scalar(
        select(MITREVersions) \
        .where(
            (MITREVersions.major == from_version.major) &
            (MITREVersions.minor == (from_version.minor + 1)))
    )

    # If not, next version must be a major version.
    if not to_version:
        to_version = db.scalar(
            select(MITREVersions) \
            .where(
                (MITREVersions.major == from_version.major + 1) &
                (MITREVersions.minor == 0)
            )
        )

    # If still nothing was found, the user must be on the newest version.    
    if not to_version:
        return jsonify({"message": "You are already on the newest version"}),400
    
    print(to_version.name)

    # Get the current upgrade from the database.
    mitre_changes = db.scalars(
        select(MITREChange) \
        .where(
            (MITREChange.from_version == from_version.name) &
            (MITREChange.to_version == to_version.name)
        )
    ).first()
    
    # If the current upgrade is already in progress, don't fetch the data again.
    if (mitre_changes):
        return jsonify({"message": "Upgrade already exists"}), 400
    
    # If the current upgrade does not exist, get it from the MITRE site, parse it and store it in the DB.
    else:
        # Works up from version 8.0.
        # Versions smaller than 8.0 have no JSON file for download.
        result = get(f"https://attack.mitre.org/docs/changelogs/{from_version.name}-{to_version.name}/changelog.json")

        # If a JSON changelog file does not exist:
        if not result:
            return jsonify({"message": "Version not supported."}),404

        # Get all modified enterprise techniques from the changelog, if available.
        modified_techniques = glom(result.json(), "enterprise-attack.techniques", default=None)
            
        # In some minor updates, there are no changes to any techniques.
        if not modified_techniques:
            return jsonify({"message": "No changes to any techniques."}),404

        # Parse the JSON file.
        # The techniques in the changelog are categorized (e.g. major change, addition, deletion, minor change, ...).
        # Iterate through all categories.
        for category in modified_techniques:
            # Iterate through all techniques in the category.
            for technique in modified_techniques[category]:
                # The text in detailed_diff is JSON formatted, but is interpreted by python as a string, so we have to parse it manually (no idea why).
                json_diff = json.loads(technique.get("detailed_diff", "{}"))
                  
                # If key "values_changed" doesn't exist (e.g. technique is a new addition), then use the "description" key.
                # Glom is great for deeply nested JSON.
                old_description = glom(json_diff, "values_changed.root['description'].old_value", default="NA")
                new_description = glom(json_diff, "values_changed.root['description'].new_value", default=technique.get("description"))

                # Add the change to the database.
                c = MITREChange(
                    mitre_id = technique["external_references"][0]["external_id"],
                    technique_name = technique.get("name"),
                    old_description = old_description,
                    new_description = new_description,
                    change_category = category,
                    from_version = from_version.name,
                    to_version = to_version.name
                )
                db.add(c)

        db.commit()
    
        return jsonify({
            "message": f"Successfully got the changelog from {from_version.name} to {to_version.name}. Click <a href=\"{url_for("upgrade", from_version=from_version.name, to_version=to_version.name)}\" target=\"_blank\">Link</a> to continue.",
            "url": url_for("upgrade", from_version=from_version.name, to_version=to_version.name),
            "url_text": f"{from_version.name} to {to_version.name}"
        }), 200



'''
====================================================================================
| Opens a current upgrade.                                                           |
====================================================================================
'''
@app.route("/upgrade/<from_version>-<to_version>")
def upgrade(from_version, to_version):
    query = select(MITREChange).where((MITREChange.from_version == from_version) & (MITREChange.to_version == to_version))

    if (not db.scalars(query).first()):
        abort(404)

    else:
        mitre_changes = db.scalars(query).all()
        return render_template("changes.html", changes=mitre_changes, from_version=from_version, to_version=to_version)



'''
=====================================================================================
| Opens a change in an upgrade.                                                     |
=====================================================================================
'''
@app.route("/upgrade/<from_version>-<to_version>/<mitre_id>")
def change(from_version, to_version, mitre_id):
    query = select(MITREChange).where((MITREChange.from_version == from_version) & (MITREChange.to_version == to_version) & (MITREChange.mitre_id == mitre_id))
    change = db.scalar(query)

    # Get the previous and next change item of the current upgrade.
    # Then get the URL of that item.
    prev_change = db.scalar(
        select(MITREChange) \
        .where(
            (MITREChange.from_version == from_version) &
            (MITREChange.to_version == to_version) &
            (MITREChange.change_id == change.change_id - 1)
        )        
    )
    prev_change_url = url_for('change', from_version=prev_change.from_version, to_version=prev_change.to_version, mitre_id=prev_change.mitre_id) if prev_change else ""
    
    next_change = db.scalar(
        select(MITREChange) \
        .where(
            (MITREChange.from_version == from_version) & 
            (MITREChange.to_version == to_version) & 
            (MITREChange.change_id == change.change_id + 1)
        )
    )
    next_change_url = url_for('change', from_version=next_change.from_version, to_version=next_change.to_version, mitre_id=next_change.mitre_id) if next_change else ""

    return render_template("change.html", change=change, prev_change=prev_change_url, next_change=next_change_url)



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
    query = select(MITREChange).where((MITREChange.from_version == from_version) & (MITREChange.to_version == to_version) & (MITREChange.mitre_id == mitre_id))
    change = db.scalar(query)
    change.status = status
    db.commit()

    return "",204



'''
=====================================================================================
| Start the flask server in debug mode and on port 8000.                            |
=====================================================================================
'''
# TODO: Remove Debugging mode when going productive.
if __name__ == "__main__":
    app.run(debug=True, port=8000)