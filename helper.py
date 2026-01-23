from table_definitions import *
from sqlalchemy import select, asc
from sqlalchemy.orm import Session
from requests import get
from glom import glom
import json, re
from os import path
from pathlib import Path
from werkzeug.datastructures import FileStorage
from magic import from_buffer
from constants import *
from ods import *
from xlsx import *


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

        # Get the whole Enterprise attack matrix.
        attack_data = get(f"https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-{to_version[1:]}.json", timeout=10)
        attack_data.raise_for_status()
        attack_data = attack_data.json()
    except:
        raise Exception("Request failed or timed out. Try again later.")

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
            old_description = glom(json_diff, "values_changed.root['description'].old_value", default="")
            new_description = glom(json_diff, "values_changed.root['description'].new_value", default=technique.get("description"))

            # Get the platforms of the technique in JSON format.
            platforms = json.dumps(technique.get("x_mitre_platforms"))

            # All other changes (except the description) will be stored as JSON in the database, since they are very dynamic.
            json_diff.get("values_changed", {}).pop("root['description']", None)
            
            changelog_mitigations = technique.get("changelog_mitigations")
            changelog_mitigations = {"changelog_mitigations": changelog_mitigations} if changelog_mitigations else {}

            changelog_detections = technique.get("changelog_datacomponent_detections")
            changelog_detections = {"changelog_detections": changelog_detections} if changelog_detections else {}

            changelog_detection_strategies = technique.get("changelog_detectionstrategy_detections")
            changelog_detection_strategies = {"changelog_detection_strategies": changelog_detection_strategies} if changelog_detection_strategies else {}

            # Put all dicts together and transform them to a JSON string.
            other_changes = json_diff | changelog_mitigations | changelog_detections | changelog_detection_strategies
            other_changes = json.dumps(other_changes)

            # A MITRE technique can belong to multiple tactics.
            # Extract MITRE tactic names from the array in the changelog and sort alphabetically.
            # Also transform the string from e.g. 'privilege-escalation' to 'Privilege Escalation'.
            tactics = technique.get("kill_chain_phases")
            tactics = sorted([t.get("phase_name").replace('-', ' ').title() for t in tactics])
            tactics = ", ".join(tactics)

            # Iterate over all references and extract the 'url' and 'external_id' (-> MITRE ID).
            # Default value is an empty string.
            url = next((ref.get("url") for ref in technique.get("external_references") if ref.get("source_name") == "mitre-attack"), "")
            mitre_id = next((ref.get("external_id") for ref in technique.get("external_references")if ref.get("source_name") == "mitre-attack"), "")

            # If sub-technique, get the name of the parent technique.
            if "." in mitre_id:
                parent_id = mitre_id.split('.')[0]
                parent_technique = next(
                    (
                        # Iterate over all objects (e.g. mitigations, techniques, sub-techniques, ...)
                        object for object in attack_data.get("objects")
                        
                        # Only select techniques and sub-techniques...
                        if object.get("type") == "attack-pattern"
                        
                        # ...and the technique that has the parent_id.
                        and any(ref.get("external_id") == parent_id for ref in object.get("external_references", []))
                    ), {})
                
                technique_name = parent_technique.get("name", "")
                sub_technique_name = technique.get("name")

                # Sub-Techniques don't have any further sub-techniques.
                sub_techniques = []
            
            # If not a sub-technique.
            else:
                technique_name = technique.get("name")
                sub_technique_name = ""
                # Check if a parent technique has any sub-techniques.
                sub_techniques = [
                    object for object in attack_data.get("objects", [])
                    if object.get("type") == "attack-pattern"
                    and any(f"{mitre_id}." in ref.get("external_id", "") for ref in object.get("external_references", []))
                ]

            # Fill out all necessary fields of the MITREChange object.
            change = MITREChange(
                mitre_id = mitre_id,
                url = url,
                tactics = tactics,
                technique = technique_name,
                sub_technique = sub_technique_name,
                nr_sub_techniques = len(sub_techniques),
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
| Small helper function that handles json.loads() errors and returns a default      |
| value on error.                                                                   |
=====================================================================================
'''
def load_json(json_string, default=None):
    try:
        return json.loads(json_string) if json_string else default
    except json.JSONDecodeError:
        return default



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
            (MITREChange.to_version == to_version) &
            (MITREChange.nr_sub_techniques == 0)
        ) \
        .order_by(
            asc(MITREChange.tactics),
            asc(MITREChange.technique),
            asc(MITREChange.sub_technique)
        )
    ).all()



'''
=====================================================================================
| Get one particular change from the DB.                                            |
=====================================================================================
'''
def get_change(db: Session, from_version: str, to_version: str, mitre_id: str) -> MITREChange:
    return db.scalar(
        select(MITREChange) \
        .where(
            (MITREChange.from_version == from_version) &
            (MITREChange.to_version == to_version) &
            (MITREChange.mitre_id == mitre_id)
        )
    )


'''
=====================================================================================
| Find out the change that comes before 'current_change' in the alphabetical order  |
| (tactics, techniques, sub-techniques in ascending order).                         |
=====================================================================================
'''
def get_previous_change(db: Session, current_change: MITREChange, filter: str) -> MITREChange:
    # If filer is "All" or there is no filter set, check all changes.
    if filter == "All" or not filter:
        query = select(MITREChange) \
        .where(
            (MITREChange.from_version == current_change.from_version) &
            (MITREChange.to_version == current_change.to_version) &
            (MITREChange.change_category == current_change.change_category) &
            (MITREChange.nr_sub_techniques == 0)
        ) \
        .order_by(
            asc(MITREChange.tactics),
            asc(MITREChange.technique),
            asc(MITREChange.sub_technique)
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
            asc(MITREChange.tactics),
            asc(MITREChange.technique),
            asc(MITREChange.sub_technique)
        )

    # Determine index of current change and subtract 1 to get previous change.
    results = db.scalars(query).all()
    index = next(
        i for i, r in enumerate(results)
        if r.mitre_id == current_change.mitre_id
    )

    # If index is 0, there is no previous change, so return 'None'.
    # Else return the previous change (-> 'results[index - 1]').
    return results[index - 1] if index != 0 else None



'''
=====================================================================================
| Find out the change that comes next to 'current_change' in the alphabetical order |
| (tactics, techniques, sub-techniques in ascending order).                         |
=====================================================================================
'''
def get_next_change(db: Session, current_change: MITREChange, filter: str) -> MITREChange:
    if filter == "All" or not filter:
        query = select(MITREChange) \
        .where(
            (MITREChange.from_version == current_change.from_version) &
            (MITREChange.to_version == current_change.to_version) &
            (MITREChange.change_category == current_change.change_category) &
            (MITREChange.nr_sub_techniques == 0)
        ) \
        .order_by(
            asc(MITREChange.tactics),
            asc(MITREChange.technique),
            asc(MITREChange.sub_technique)
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
            asc(MITREChange.tactics),
            asc(MITREChange.technique),
            asc(MITREChange.sub_technique)
        )
    
    # Determine index of current change and add 1 to get next change.
    results = db.scalars(query).all()
    index = next(
        i for i, r in enumerate(results)
        if r.mitre_id == current_change.mitre_id
        and r.tactics == current_change.tactics
    )
    
    # If 'current_change' is the last one in the results, return None.
    # Else, return the next change (-> 'results[index + 1]').
    return results[index + 1] if (index + 1) != len(results) else None



'''
=====================================================================================
| This function checks if the user has already uploaded a spreadsheet file for      |
| this upgrade. If yes, the function returns the filename and the extension.        |
=====================================================================================
'''
def get_spreadsheet_filename(from_version: str, to_version: str) -> str | None:
    # Check if there's already a file for this upgrade.
    file_name_ods = f"mitreattck_eval_{from_version}_{to_version}.ods"
    file_name_xlsx = f"mitreattck_eval_{from_version}_{to_version}.xlsx"
    file_path_ods = Path(path.join("sheets", file_name_ods))
    file_path_xlsx = Path(path.join("sheets", file_name_xlsx))

    if file_path_ods.exists():
        return file_name_ods
    elif file_path_xlsx.exists():
        return file_name_xlsx
    else:
        return None



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
    if change.client_criticality == 0:
        return 0

    sum = change.confidentiality + change.integrity + change.availability + change.client_criticality
    return sum



def infra_sum(change: MITREChange) -> int:
    if change.infra_criticality == 0:
        return 0

    sum = change.confidentiality + change.integrity + change.availability + change.infra_criticality
    return sum



def service_sum(change: MITREChange) -> int:
    if change.service_criticality == 0:
        return 0

    sum = change.confidentiality + change.integrity + change.availability + change.service_criticality
    return sum



'''
=====================================================================================
| Checks if a file type is valid (XLSX or ODS). The function checks both the file   |
| extension and the mimetype by reading the contents of the file.                   |
=====================================================================================
'''
# 
def is_xlsx_or_ods(file: FileStorage) -> Boolean:
    # Get the file extension.
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

    return file_ext in allowed_extensions and mimetype in allowed_mimetypes



'''
=====================================================================================
| This function constructs a unique filename, checks if the filetype is valid,      |
| removes any other spreadsheet files that may exist and saves it to local disk.    |
=====================================================================================
'''
def handle_upload(file: FileStorage, from_version: str, to_version: str):
    file_ext = file.filename.split(".")[-1]

    if not is_xlsx_or_ods(file):
        raise Exception("Unsupported Filetype")
    
    file_name = f"mitreattck_eval_{from_version}_{to_version}"
    file_path = path.join("sheets", f"{file_name}.{file_ext}")
    file.save(file_path)

    # If an ods file exists and a xlsx file is uploaded remove the ods file and vice versa.
    # If a xlsx file exists and a xlsx file is uploaded, it simply gets overwritten.
    if file_ext == "ods":
        file_remove_path = Path(path.join("sheets", f"{file_name}.xlsx"))
    elif file_ext == "xlsx":
        file_remove_path = Path(path.join("sheets", f"{file_name}.ods"))

    try:
        file_remove_path.unlink()
    except FileNotFoundError:
        pass

    return file_path



def import_file(file_path: str, from_version: str, to_version: str, db: Session):
    file_ext = file_path.split(".")[-1]
    sheet_name = "MITRE_ATT&CK"

    changes = get_changes(from_version, to_version, db)

    if file_ext == "xlsx":
        handler = XLSXHandler(file_path=file_path, sheet_name=sheet_name, db=db)
        handler.import_xlsx(changes)

    elif file_ext == "ods":
        handler = ODSHandler(file_path=file_path, sheet_name=sheet_name, db=db)
        handler.import_ods(changes)



def export_file(from_version: str, to_version: str, db: Session) -> str:
    # Get the current spreadsheet file for this upgrade.
    file_name = get_spreadsheet_filename(from_version, to_version)
    file_ext = file_name.split(".")[-1]
    file_path = path.join("sheets", file_name)
    sheet_name = "MITRE_ATT&CK"

    export_name = f"EXPORT_{file_name}"
    export_path = path.join("sheets", export_name)

    # Get all changes that were made during this upgrade.
    changes = get_changes(from_version, to_version, db)

    if file_ext == "xlsx":
        handler = XLSXHandler(file_path=file_path, sheet_name=sheet_name, db=db)
        handler.export_xlsx(file_path=export_path, changes=changes)
    elif file_ext == "ods":
        handler = ODSHandler(file_path=file_path, sheet_name=sheet_name, db=db)
        handler.export_ods(file_path=export_path, changes=changes)