import os
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from pydantic import BaseModel
from core.database import get_db
from core.security import verify_password, create_access_token, decode_access_token
from models.user import User
from services.ticket_service import get_all_tickets

router = APIRouter()

class AdminLoginRequest(BaseModel):
    username: str
    password: str

@router.post("/admin/login")
def admin_login(data: AdminLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate administrator credentials against:
    1. Environment variables set on Vercel/system (ADMIN_USERNAME / ADMIN_PASSWORD)
    2. Neon Database 'users' table where user_type is 'admin'
    """
    clean_username = (data.username or "").strip()
    clean_password = (data.password or "").strip()

    if not clean_username or not clean_password:
        raise HTTPException(
            status_code=400,
            detail="Admin username and password are required."
        )

    # 1. Authenticate against Environment Variables (configured in Vercel or .env)
    env_admin_user = (os.getenv("ADMIN_USERNAME") or "admin").strip().strip('"\'')
    env_admin_pass = (os.getenv("ADMIN_PASSWORD") or "admin123").strip().strip('"\'')

    if env_admin_pass:
        is_user_match = secrets.compare_digest(clean_username.lower(), env_admin_user.lower())
        is_pass_match = secrets.compare_digest(clean_password, env_admin_pass)
        if is_user_match and is_pass_match:
            token = create_access_token({
                "sub": env_admin_user,
                "name": "Administrator",
                "role": "admin",
                "user_type": "admin"
            })
            return {
                "message": "Admin authentication successful",
                "token": token,
                "username": env_admin_user,
                "role": "admin"
            }

    # 2. Authenticate against Neon Database (User table where user_type == 'admin')
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
            if user_role in ["admin", "administrator", "staff", "superadmin"]:
                token = create_access_token({
                    "sub": user.college_id,
                    "name": user.name,
                    "email": user.email,
                    "role": "admin",
                    "user_type": "admin"
                })
                return {
                    "message": "Admin authentication successful",
                    "token": token,
                    "username": user.name or user.college_id,
                    "role": "admin"
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

    # 3. Reject invalid credentials with 401 Unauthorized
    raise HTTPException(
        status_code=401,
        detail="Invalid admin credentials. Please verify your username and password."
    )

@router.get("/admin/verify")
def verify_admin_session(request: Request):
    """
    Verify that the current session token belongs to an authorized administrator.
    """
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()

    if not token:
        raise HTTPException(status_code=401, detail="Missing admin authorization token.")

    payload = decode_access_token(token)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Invalid or expired admin session token.")

    return {"status": "ok", "admin": payload}

@router.get("/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    tickets = get_all_tickets(db)
    resolved = sum(1 for t in tickets if (t.get("status") or "").lower() == "resolved")
    pending = sum(1 for t in tickets if (t.get("status") or "").lower() != "resolved")
    high_urgency = sum(1 for t in tickets if (t.get("urgency") or "").lower() == "high")
    return {
        "total": len(tickets),
        "resolved": resolved,
        "pending": pending,
        "high_urgency": high_urgency
    }
