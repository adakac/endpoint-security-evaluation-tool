'''
=====================================================================================
| IMPORTS                                                                           |
=====================================================================================
'''
from requests import get
import re, json
from flask import Flask, render_template, request, abort, redirect, url_for, jsonify
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

# Define table for the MITRE changes in an upgrade.
class MITREChange(Base):
    __tablename__ = "mitre_changes"
    change_id = Column(Integer, primary_key=True, autoincrement=True)
    mitre_id = Column(Text)
    technique_name = Column(Text)
    change_category = Column(Text)
    old_description = Column(Text)
    new_description = Column(Text)
    from_version = Column(Text)
    to_version = Column(Text)
    status = Column(Text, default="Not Done")

# Create the table.
Base.metadata.create_all(engine)

# Disable caching so the page is always reloaded and shows the most recent data.
# Else, if you change the status of something and go back, the change is not directly shown due to caching.
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expire"] = "0"
    return response



'''
=====================================================================================
| Custom Jinja filter for parsing Markdown text.                                    |
=====================================================================================
'''
@app.template_filter('markdown')
def markdown_filter(text):
    return markdown(text).strip()



'''
=====================================================================================
| This function gets all current MITRE versions available.                          |
=====================================================================================
'''
def get_mitre_versions():
    # Unfortunately, there is no API to get all MITRE versions, so we have to scrape the website.
    # We could use the GitHub API to get all releases, but this does not show all versions
    # (see https://github.com/mitre-attack/attack-stix-data/releases or https://github.com/mitre/cti/releases).
    # The official python API from MITRE also does not support the listing of versions (see https://github.com/mitre-attack/mitreattack-python).
    site = get("https://attack.mitre.org/resources/versions/").text

    # Extract the versions with Regex.
    pattern = r'v\d{1,2}\.\d(?!\.)'    
    versions = set(re.findall(pattern, site))

    # The MITRE website only lists the newest minor versions per major version, so we have to fill in the missing minor versions.
    # We have to iterate over a copy of the version set(), because we are changing it and it would throw an error if we use the original.
    for v in versions.copy():
        major, minor = map(int, v[1:].split('.'))

        # If the newest minor is 0, there are no other minor versions.
        if minor == 0:
            continue

        # Include all other minor versions.
        # E.g. if the newest minor version is 15.3, fill in 15.2, 15.1 and 15.0.
        else:
            for m in range(minor):
                versions.add(f"v{major}.{m}")

    # Return the versions as a list of strings and sorted.
    # Sort by major version first.
    # Else v10 comes right after v1 if you sort it by alphabet.
    def version_key(v):
        major_minor = v[1:].split('.')
        return tuple(map(int, major_minor))
    
    return sorted(versions, key=version_key)



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
    versions = get_mitre_versions()

    return render_template("homepage.html", versions=versions, upgrades=current_upgrades)




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
    # Get all versions.
    versions = get_mitre_versions()

    # Get the user selected version.
    from_version = request.form.get("version_select")
    
    # Get the next version.
    index = versions.index(from_version) + 1
    if index >= len(versions):
        return jsonify({"message": "You are already on the newest version"}),400
    
    to_version = versions[index]
        
    # Get the current upgrade from the database.
    mitre_changes = db.scalars(
        select(MITREChange) \
        .where(
            (MITREChange.from_version == from_version) &
            (MITREChange.to_version == to_version)
        )
    ).first()
    
    # If the current upgrade is already in progress, don't fetch the data again.
    if (mitre_changes):
        return jsonify({"message": "Upgrade already exists"}), 400
    
    # If the current upgrade does not exist, get it from the MITRE site, parse it and store it in the DB.
    else:
        # Works up from version 8.0.
        # Versions smaller than 8.0 have no JSON file for download.
        result = get(f"https://attack.mitre.org/docs/changelogs/{from_version}-{to_version}/changelog.json")
        print(f"https://attack.mitre.org/docs/changelogs/{from_version}-{to_version}/changelog.json")

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
                    from_version = from_version,
                    to_version = to_version
                )
                db.add(c)
        
        db.commit()
            
        return jsonify({
            "message": f"Successfully got the changelog from {from_version} to {to_version}. Click <a href=\"{url_for("upgrade", from_version=from_version, to_version=to_version)}\" target=\"_blank\">Link</a> to continue.",
            "url": url_for("upgrade", from_version=from_version, to_version=to_version),
            "url_text": f"{from_version} to {to_version}"
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
if __name__ == "__main__":
    app.run(debug=True, port=8000)