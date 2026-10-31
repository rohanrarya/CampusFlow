import os
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from pydantic import BaseModel
from core.database import get_db
from core.security import verify_password, create_access_token, decode_access_token
from models.user import User
from models.school import School
from services.ticket_service import get_all_tickets

router = APIRouter()

class AdminLoginRequest(BaseModel):
    username: str
    password: str

@router.post("/admin/login")
def admin_login(data: AdminLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate administrator credentials:
    1. Check against DB 'users' table (supports multi-school admin accounts)
    2. Check against environment variables (ADMIN_USERNAME / ADMIN_PASSWORD)
    """
    clean_username = (data.username or "").strip()
    clean_password = (data.password or "").strip()

    if not clean_username or not clean_password:
        raise HTTPException(
            status_code=400,
            detail="Admin username and password are required."
        )

    # 1. Authenticate against Neon Database (User table where user_type == 'admin')
    try:
        user = db.scalars(
            select(User).where(
                or_(
                    User.college_id.ilike(clean_username),
                    User.email.ilike(clean_username),
                    User.name.ilike(clean_username)
                )
            )
        ).first()

        if user and verify_password(clean_password, user.password_hash):
            user_role = (user.user_type or "").strip().lower()
            if user_role in ["admin", "administrator", "staff", "superadmin", "school_admin"]:
                school_id = getattr(user, "school_id", 1) or 1
                school = db.scalar(select(School).where(School.id == school_id))
                school_name = school.name if school else "Main Campus"
                school_code = school.code if school else "DEFAULT"

                token = create_access_token({
                    "sub": user.college_id,
                    "name": user.name,
                    "email": user.email,
                    "role": "admin",
                    "user_type": "admin",
                    "school_id": school_id,
                    "school_name": school_name,
                    "school_code": school_code
                })
                return {
                    "message": "Admin authentication successful",
                    "token": token,
                    "username": user.name or user.college_id,
                    "role": "admin",
                    "school_id": school_id,
                    "school_name": school_name,
                    "school_code": school_code
                }
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. Your account does not have administrator privileges."
                )
    except HTTPException:
        raise
    except Exception as db_err:
        print(f"Database lookup during admin login failed: {db_err}")

    # 2. Authenticate against Environment Variables (fallback default master)
    env_admin_user = (os.getenv("ADMIN_USERNAME") or "admin").strip().strip('"\'')
    env_admin_pass = (os.getenv("ADMIN_PASSWORD") or "admin123").strip().strip('"\'')

    if env_admin_pass:
        is_user_match = secrets.compare_digest(clean_username.lower(), env_admin_user.lower())
        is_pass_match = secrets.compare_digest(clean_password, env_admin_pass)
        if is_user_match and is_pass_match:
            default_school = db.scalar(select(School).where(School.id == 1))
            school_name = default_school.name if default_school else "Main Campus"
            school_code = default_school.code if default_school else "DEFAULT"
            token = create_access_token({
                "sub": env_admin_user,
                "name": "Administrator",
                "role": "admin",
                "user_type": "admin",
                "school_id": 1,
                "school_name": school_name,
                "school_code": school_code
            })
            return {
                "message": "Admin authentication successful",
                "token": token,
                "username": env_admin_user,
                "role": "admin",
                "school_id": 1,
                "school_name": school_name,
                "school_code": school_code
            }

    # 3. Reject invalid credentials with 401 Unauthorized
    raise HTTPException(
        status_code=401,
        detail="Invalid admin credentials. Please verify your username and password."
    )

@router.get("/admin/verify")
def verify_admin_session(request: Request, db: Session = Depends(get_db)):
    """Verify admin JWT session and return admin + school profile."""
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()

    if not token:
        raise HTTPException(status_code=401, detail="Session expired or invalid token.")

    payload = decode_access_token(token)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Session expired or invalid token.")

    school_id = payload.get("school_id") or 1
    school = db.scalar(select(School).where(School.id == school_id))

    return {
        "status": "valid",
        "username": payload.get("sub", "Admin"),
        "role": payload.get("role", "admin"),
        "school_id": school_id,
        "school_name": school.name if school else payload.get("school_name", "Main Campus"),
        "school_code": school.code if school else payload.get("school_code", "DEFAULT")
    }

@router.get("/admin/feed")
def get_admin_feed(request: Request, db: Session = Depends(get_db)):
    """Public/Admin feed of recent complaints, filtered by school."""
    auth_header = request.headers.get("Authorization", "")
    school_id = None
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        payload = decode_access_token(token)
        if payload and payload.get("role") == "admin":
            school_id = payload.get("school_id")

    # If no token, check query params
    if not school_id and request.query_params.get("school_id"):
        try:
            school_id = int(request.query_params.get("school_id"))
        except ValueError:
            pass

    return get_all_tickets(db, school_id=school_id)
