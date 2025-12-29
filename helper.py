from table_definitions import *
from sqlalchemy import select, asc, desc
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
    try:
        changelog = get(f"https://attack.mitre.org/docs/changelogs/{from_version}-{to_version}/changelog.json", timeout=10)
        changelog.raise_for_status()
        attack_data = get(f"https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-{to_version[1:]}.json", timeout=10)
        attack_data.raise_for_status()
        attack_data = attack_data.json()
    except:
        print("TIMEOUT")
        return

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
    for change_category in modified_techniques:

        # Iterate through all techniques in the category.
        for technique in modified_techniques[change_category]:

            # The text in detailed_diff is JSON formatted, but is interpreted by python as a string, so we have to parse it manually (no idea why).
            json_diff = json.loads(technique.get("detailed_diff", "{}"))

            # If key "values_changed" doesn't exist (e.g. technique is a new addition), then use the "description" key.
            # Glom is great for deeply nested JSON.
            old_description = glom(json_diff, "values_changed.root['description'].old_value", default="N/A")
            new_description = glom(json_diff, "values_changed.root['description'].new_value", default=technique.get("description"))

            # Get the platforms of the technique in JSON format.
            platforms = json.dumps(technique.get("x_mitre_platforms"))

            # All other changes (except the description) will be stored as JSON in the database, since they are very dynamic.
            json_diff.get("values_changed", {}).pop("root['description']", None)
            other_changes = json.dumps(json_diff)

            # Category = MITRE Tactic
            # A MITRE technique can belong to multiple tactics.
            # Each combination of tactic and technique has it's own entry in the database.
            # Depending on the tactic the scores can be different.
            categories = technique.get("kill_chain_phases")

            # Iterate over all references and extract the 'url' and 'external_id' (-> MITRE ID).
            # Default value is None.
            url = next((ref.get("url") for ref in technique.get("external_references") if ref.get("source_name") == "mitre-attack"), "")

            mitre_id = next((ref.get("external_id") for ref in technique.get("external_references")if ref.get("source_name") == "mitre-attack"), "")

            # If sub-technique, get the name of the parent technique (-> sub_category).
            if "." in mitre_id:
                parent_id = mitre_id.split('.')[0]
                parent_technique = next((object for object in attack_data.get("objects") if object.get("type") == "attack-pattern" and any(ref.get("external_id") == parent_id for ref in object.get("external_references", []))), {})
                sub_category = parent_technique.get("name", "")
                technique_name = technique.get("name")
                print(f"MITREID: {mitre_id} -- ParentID: {parent_id} -- Sub-Category: {sub_category} -- Technique: {technique_name}")
            
            # If not a sub-technique, then the technique name is the sub-category.
            else:
                sub_category = technique.get("name")
                technique_name = ""


            for c in categories:
                # Get the name of the tactic/category.
                category = c.get("phase_name")

                # Fill out all necessary fields of the MITREChange object.
                change = MITREChange(
                    mitre_id = mitre_id,
                    url = url,
                    technique = technique_name,
                    category = category,
                    sub_category = sub_category,
                    old_description = old_description,
                    new_description = new_description,
                    other_changes = other_changes,
                    change_category = change_category,
                    from_version = from_version,
                    to_version = to_version,
                    platforms = platforms
                )

                result.append(change)
    
    return result


'''
=====================================================================================
| The function is given a version and determines which version is next.             |
| It then returns the current and the next version as database objects.             |
=====================================================================================
'''
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



'''
=====================================================================================
| Checks if an upgrade is already in progress.                                      |
=====================================================================================
'''
def upgrade_exists(from_version: str, db: Session) -> bool:
    res = db.scalar(select(MITREChange).where(MITREChange.from_version == from_version))
    
    # Returns True if 'res' is not empty.
    return (res is not None)



'''
=====================================================================================
| Get all changes from a specific upgrade.                                          |
=====================================================================================
'''
def get_changes(from_version: str, to_version: str, db: Session):
    return db.scalars(
        select(MITREChange) \
        .where(
            (MITREChange.from_version == from_version) &
            (MITREChange.to_version == to_version)
        ) \
        .order_by(
            asc(MITREChange.category),
            asc(MITREChange.sub_category),
            asc(MITREChange.technique)
        )
    ).all()



# get one particular change from db.
def get_change(db: Session, from_version: str, to_version: str, category: str, mitre_id: str) -> MITREChange:
    return db.scalar(
        select(MITREChange) \
        .where(
            (MITREChange.from_version == from_version) &
            (MITREChange.to_version == to_version) &
            (MITREChange.category == category) &
            (MITREChange.mitre_id == mitre_id)
        )
    )



def get_previous_change(db: Session, current_change: MITREChange, filter: str) -> MITREChange:
    # If filer is "All" or there is no filter set, check all changes.
    if filter == "All" or not filter:
        query = select(MITREChange) \
        .where(
            (MITREChange.from_version == current_change.from_version) &
            (MITREChange.to_version == current_change.to_version) &
            (MITREChange.change_category == current_change.change_category)
        ) \
        .order_by(
            asc(MITREChange.category),
            asc(MITREChange.sub_category),
            asc(MITREChange.technique)
        )
    
    # If filter is "Done", "In Progress" or "Not Done", only get the specific records from DB.
    else:
        query = select(MITREChange) \
        .where(
            (MITREChange.from_version == current_change.from_version) &
            (MITREChange.to_version == current_change.to_version) &
            (MITREChange.change_category == current_change.change_category) &
            (MITREChange.status == filter)
        ) \
        .order_by(
            asc(MITREChange.category),
            asc(MITREChange.sub_category),
            asc(MITREChange.technique)
        )

    # Determine index of current change and subtract 1 to get previous change.
    results = db.scalars(query).all()
    index = next(
        i for i, r in enumerate(results)
        if r.mitre_id == current_change.mitre_id
        and r.category == current_change.category
    )

    # If index is 0, there is no previous change, so return 'None'.
    # Else return the previous change (-> 'results[index - 1]').
    return results[index - 1] if index != 0 else None





def get_next_change(db: Session, current_change: MITREChange, filter: str) -> MITREChange:
    if filter == "All" or not filter:
        query = select(MITREChange) \
        .where(
            (MITREChange.from_version == current_change.from_version) &
            (MITREChange.to_version == current_change.to_version) &
            (MITREChange.change_category == current_change.change_category)
        ) \
        .order_by(
            asc(MITREChange.category),
            asc(MITREChange.sub_category),
            asc(MITREChange.technique)
        )
    
    else:
        query = select(MITREChange) \
        .where(
            (MITREChange.from_version == current_change.from_version) &
            (MITREChange.to_version == current_change.to_version) &
            (MITREChange.change_category == current_change.change_category) &
            (MITREChange.status == filter)
        ) \
        .order_by(
            asc(MITREChange.category),
            asc(MITREChange.sub_category),
            asc(MITREChange.technique)
        )
    
    # Determine index of current change and add 1 to get next change.
    results = db.scalars(query).all()
    index = next(
        i for i, r in enumerate(results)
        if r.mitre_id == current_change.mitre_id
        and r.category == current_change.category
    )
    
    # If 'current_change' is the last one in the results, return None.
    # Else, return the next change (-> 'results[index + 1]').
    return results[index + 1] if (index + 1) != len(results) else None



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