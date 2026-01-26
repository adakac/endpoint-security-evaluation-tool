from sqlalchemy import Column, Integer, Text, Boolean, create_engine
from sqlalchemy.orm import Session, declarative_base

Base = declarative_base()

# Establish connection to DB.
engine = create_engine("sqlite:///db/mitre_changes.db", echo=False)



'''
=====================================================================================
| Table for all changes in an upgrade.                                              |
=====================================================================================
'''
# The following table stores each upgrade. For each change in an upgrade there is a comparison between the new and old description.
# Changes can be tracked via a status.
class MITREChange(Base):
    __tablename__ = "mitre_changes"
    change_id = Column(Integer, primary_key=True, autoincrement=True)
    mitre_id = Column(Text)
    url = Column(Text)
    tactics = Column(Text)
    technique = Column(Text)
    sub_technique = Column(Text)
    nr_sub_techniques = Column(Integer, default=0)
    change_category = Column(Text)
    old_description = Column(Text)
    new_description = Column(Text)
    other_changes = Column(Text)
    from_version = Column(Text)
    to_version = Column(Text)
    status = Column(Text, default="Not Done")
    platforms = Column(Text)
    confidentiality = Column(Boolean, default=False)
    integrity = Column(Boolean, default=False)
    availability = Column(Boolean, default=False)
    client_criticality = Column(Integer, default=0)
    client_criticality_sum = Column(Integer, default=0)
    client_reasoning = Column(Text)
    client_measures = Column(Text)
    client_evaluation_status = Column(Text, default="n.a.")
    infra_criticality = Column(Integer, default=0)
    infra_criticality_sum = Column(Integer, default=0)
    infra_reasoning = Column(Text)
    infra_measures = Column(Text)
    infra_evaluation_status = Column(Text, default="n.a.")
    service_criticality = Column(Integer, default=0)
    service_criticality_sum = Column(Integer, default=0)
    service_reasoning = Column(Text)
    service_measures = Column(Text)
    service_evaluation_status = Column(Text, default="n.a.")



'''
=====================================================================================
| Table for all MITRE versions.                                                     |
=====================================================================================
'''
class MITREVersion(Base):
    __tablename__ = "mitre_versions"
    major = Column(Integer, primary_key=True)
    minor = Column(Integer, primary_key=True)
    name = Column(Text)



'''
=====================================================================================
| Returns a Session object that can be used to query the database.                  |
=====================================================================================
'''
def get_db_connection():
    return Session(engine)



'''
=====================================================================================
| Creates all tables, if they don't already exist.                                  |
=====================================================================================
'''
def create_tables():
    Base.metadata.create_all(engine)