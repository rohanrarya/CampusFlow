from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, DateTime, Integer, String, Text
from core.database import Base

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.now(IST).replace(tzinfo=None)

class School(Base):
    """
    Represents an independent school or college subscribed to CampusFlow.
    Each school owns its private member roster, complaint tickets, and Google Spreadsheet.
    """
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)
    admin_email = Column(String, nullable=False)
    subscription_status = Column(String, default="active")
    plan = Column(String, default="Standard")
    google_sheet_url = Column(Text, nullable=True)
    google_sheet_webhook_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_ist_now)
