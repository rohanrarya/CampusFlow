import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from pydantic import BaseModel
from core.database import get_db
from core.security import hash_password
from models.school import School
from models.user import User

router = APIRouter()

class SchoolSubscriptionRequest(BaseModel):
    school_name: str
    school_code: str
    admin_email: str
    admin_username: str
    password: str
    plan: str = "Standard"

@router.post("/schools/subscribe")
def subscribe_school(data: SchoolSubscriptionRequest, db: Session = Depends(get_db)):
    """
    Onboard a new school with a subscription:
    1. Creates dedicated School record in DB.
    2. Creates school admin user account in DB scoped to that school.
    3. Provides isolated spreadsheet configuration instructions.
    """
    school_name = (data.school_name or "").strip()
    raw_code = (data.school_code or "").strip()
    admin_email = (data.admin_email or "").strip().lower()
    admin_username = (data.admin_username or "").strip().upper()
    password = (data.password or "").strip()
    plan = (data.plan or "Standard").strip()

    if not school_name:
        raise HTTPException(status_code=400, detail="School name is required.")
    if not raw_code:
        raise HTTPException(status_code=400, detail="School code is required.")
    if not admin_email or "@" not in admin_email:
        raise HTTPException(status_code=400, detail="A valid admin email address is required.")
    if not admin_username:
        raise HTTPException(status_code=400, detail="Admin username is required.")
    if not password or len(password) < 5:
        raise HTTPException(status_code=400, detail="Password must be at least 5 characters long.")

    # Format code: alphanumeric + dashes only
    clean_code = re.sub(r"[^A-Za-z0-9_-]", "", raw_code).upper()
    if len(clean_code) < 2:
        raise HTTPException(status_code=400, detail="School code must be at least 2 alphanumeric characters.")

    # 1. Check if School Code is already taken
    existing_school = db.scalar(select(School).where(School.code == clean_code))
    if existing_school:
        raise HTTPException(
            status_code=400,
            detail=f"School code '{clean_code}' is already registered. Please choose a different unique code."
        )

    # 2. Check if username or email already exists in users table
    existing_user = db.scalar(
        select(User).where(
            or_(
                User.college_id == admin_username,
                User.email == admin_email
            )
        )
    )
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail=f"An account with username '{admin_username}' or email '{admin_email}' already exists."
        )

    try:
        # 3. Create School entity
        new_school = School(
            name=school_name,
            code=clean_code,
            admin_email=admin_email,
            subscription_status="active",
            plan=plan,
            google_sheet_url=None,
            google_sheet_webhook_url=None
        )
        db.add(new_school)
        db.flush()

        # 4. Create School Admin user account
        hashed_pwd = hash_password(password)
        new_admin = User(
            college_id=admin_username,
            name=f"{school_name} Admin",
            email=admin_email,
            user_type="admin",
            password_hash=hashed_pwd,
            school_id=new_school.id
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_school)

        return {
            "success": True,
            "message": f"Subscription activated successfully for {school_name}!",
            "school": {
                "id": new_school.id,
                "name": new_school.name,
                "code": new_school.code,
                "plan": new_school.plan,
                "admin_username": admin_username,
                "admin_email": admin_email
            },
            "login_url": "admin-login.html",
            "sheet_setup": {
                "columns": ["College ID", "Name", "Department", "Role", "Email"],
                "note": "Log in to your Admin Portal, open 'Sheet Settings', and link your school's private Google Sheet Webhook."
            }
        }
    except Exception as err:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create school subscription: {err}")

@router.get("/schools/list")
def list_schools(db: Session = Depends(get_db)):
    """
    Public endpoint to list active schools for students to pick when submitting complaints.
    """
    schools = db.scalars(
        select(School)
        .where(School.subscription_status == "active")
        .order_by(School.id.asc())
    ).all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "plan": s.plan
        }
        for s in schools
    ]

@router.get("/schools/info/{code_or_id}")
def get_school_info(code_or_id: str, db: Session = Depends(get_db)):
    """
    Get public school details by ID or code.
    """
    clean_val = code_or_id.strip()
    if clean_val.isdigit():
        school = db.scalar(select(School).where(School.id == int(clean_val)))
    else:
        school = db.scalar(select(School).where(School.code.ilike(clean_val)))

    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    return {
        "id": school.id,
        "name": school.name,
        "code": school.code
    }
