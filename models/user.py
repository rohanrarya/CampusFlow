from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, DateTime, Integer, String
from core.database import Base

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.now(IST).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    college_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    user_type = Column(String, default="student")
    password_hash = Column(String, nullable=False)
    school_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=get_ist_now)
