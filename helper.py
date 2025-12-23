from table_definitions import *
from sqlalchemy import select
from sqlalchemy.orm import Session
from requests import get
from glom import glom
import json, re

'''
=====================================================================================
| This function parses the JSON changelog and fills all fields of the MITREChange   |
| object. The function then returns a list of MITREChange objects.                  |
=====================================================================================
'''
def parse_version_changes(from_version: str, to_version: str) -> list:
    result = []
    changelog = get(f"https://attack.mitre.org/docs/changelogs/{from_version}-{to_version}/changelog.json")

    # A JSON changelog is only available for versions greater than v8.0.
    if not changelog:
        raise Exception("Version not supported!")

    # Get all modified enterprise techniques from the changelog if available.
    modified_techniques = glom(changelog.json(), "enterprise-attack.techniques", default=None)

    # If no changes were made.
    if not modified_techniques:
        raise Exception("No changes to any techniques.")

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
            old_description = glom(json_diff, "values_changed.root['description'].old_value", default="N/A")
            new_description = glom(json_diff, "values_changed.root['description'].new_value", default=technique.get("description"))

            # All other changes (except the description) will be stored as JSON in the database, since they are very dynamic.
            json_diff.get("values_changed", {}).pop("root['description']", None)
            other_changes = json.dumps(json_diff)

            # Fill out all necessary fields of the MITREChange object.
            change = MITREChange(
                mitre_id = technique["external_references"][0]["external_id"],
                url = technique["external_references"][0]["url"],
                technique_name = technique.get("name"),
                old_description = old_description,
                new_description = new_description,
                other_changes = other_changes,
                change_category = category,
                from_version = from_version,
                to_version = to_version
            )

            result.append(change)
    
    return result



# The function is given a version and determines which version is next.
# It then returns the current and the next version as database objects.
def get_versions_db(current_version: str, db: Session) -> tuple[MITREVersion, MITREVersion]:
    
    # Get current version from DB.
    current_version = db.scalar(select(MITREVersion).where(MITREVersion.name == current_version))

    # Check if the next version is a minor version.
    next_version = db.scalar(
        select(MITREVersion) \
        .where(
            (MITREVersion.major == current_version.major) &
            (MITREVersion.minor == (current_version.minor + 1))
        )
    )

    # If the next version is not a minor version, it must be a major version.
    if not next_version:
        next_version = db.scalar(
            select(MITREVersion) \
            .where(
                (MITREVersion.major == (current_version.major + 1)) &
                (MITREVersion.minor == 0)
            )
        )

    if not next_version:
        raise Exception("You are already on the newest version!")

    # If there is no next version the variable 'next_version' is None.
    return current_version, next_version
        

# Get an existing update from the DB.
def get_upgrade_db(from_version: str, to_version: str):
    return ""






# Checks if an upgrade is already in progress.
def upgrade_exists(from_version: str, db: Session) -> bool:
    res = db.scalar(select(MITREChange).where(MITREChange.from_version == from_version))
    
    # Returns True if 'res' is not empty.
    return (res is not None)

# Get all changes for a specific upgrade.
def get_changes(from_version: str, to_version: str, db: Session):
    return db.scalars(
        select(MITREChange).where(
            (MITREChange.from_version == from_version) &
            (MITREChange.to_version == to_version)
        )
    ).all()



'''
=====================================================================================
| Get all MITRE versions from the DB in a descending order.                         |
=====================================================================================
'''
def get_mitre_versions_db(db: Session):
    return db.scalars(
        select(MITREVersion).order_by(
            MITREVersion.major.desc(),
            MITREVersion.minor.desc()
        )
    ).all()







'''
=====================================================================================
| This function gets all current MITRE versions available using the Github API.     |
| It stores versions that are not on the local DB to the local DB.                  |
| The function returns a list of the new versions                                   |
=====================================================================================
'''
def get_mitre_versions_api(db: Session):
    # To get the MITRE versions, we could either scrape the website which is not the most stable idea, but we can get all versions currently available. Also the website only lists the newest minor version per major version.
    # Alternatively, we can use the Github API to get all releases. But here we can only get MITRE versions from up to 8.0. Versions below were not pushed to Github.

    # Github API allows us to fetch all releases up from v8.0. Versions below were not pushed to Github by MITRE.
    req = get("https://api.github.com/repos/mitre/cti/releases")

    # If error, exit the function. Happens mainly due to Githubs API rate limits.
    if req.status_code >= 400:
        return

    # Iterate over all versions in json format and search for key "tag_name" which looks like this: 'ATT&CK-v18.0'.
    # Then we extract the version like this: 'v18.0' and check if the version string matches the supplied regex.
    versions = req.json()
    versions = [t for v in versions if (t := str(v.get("tag_name").split('-')[1])) and re.search(r"^v\d{1,2}\.\d$", t)]

    # Check if new version and write any versions that are not in the database to the database.
    res = []
    for v in versions:
        # Split up into major and minor version and check DB.
        major, minor = map(int, v[1:].split('.'))
        version_db = db.scalars(select(MITREVersion).where((MITREVersion.major == major) & (MITREVersion.minor == minor))).all()

        # If new versions available, write to DB and set global variables.
        if not version_db:
            res.append(v)
            db.add(MITREVersion(major = major, minor = minor, name = v))
        
    db.commit()
    return res



'''
=====================================================================================
| The following functions calculate the client, infrastructure and service          |
| criticality sum.                                                                  |
=====================================================================================
'''
def client_sum(change: MITREChange) -> int:
    sum = change.confidentiality + change.integrity + change.availability + change.client_criticality
    return sum

def infra_sum(change: MITREChange) -> int:
    sum = change.confidentiality + change.integrity + change.availability + change.infra_criticality
    return sum

def service_sum(change: MITREChange) -> int:
    sum = change.confidentiality + change.integrity + change.availability + change.service_criticality
    return sum





# Used for storing variables that need to be accessed globally.
class AppState():
    def __init__(self):
        self.cache = {}