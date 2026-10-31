from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, DateTime, Integer, String, Text
from core.database import Base

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.now(IST).replace(tzinfo=None)

class Member(Base):
    """
    Stores genuine college members (students, faculty, staff)
    synced from the admin spreadsheet or added via Admin UI.
    Scoped by school_id for multi-school isolation.
    """
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    college_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    department = Column(String, nullable=True)
    role = Column(String, default="student")
    school_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=get_ist_now)

class AppSetting(Base):
    """
    Simple key-value table to save spreadsheet settings.
    """
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)
