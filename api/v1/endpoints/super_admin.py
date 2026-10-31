import os
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from pydantic import BaseModel
from core.database import get_db
from core.security import hash_password, create_access_token, decode_access_token
from models.school import School
from models.user import User
from models.ticket import Ticket
from models.member import Member

router = APIRouter()

# ── Dependency: Require Super Admin Token ───────────────────────

def require_super_admin(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()

    if not token:
        raise HTTPException(status_code=401, detail="Missing Super Admin authorization token.")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")

    # Only super_admin or master admin
    role = payload.get("role") or payload.get("user_type")
    is_super = role in ["super_admin", "superadmin"] or payload.get("is_super_admin") is True
    # If the user is the master env admin (ADMIN_USERNAME), also grant access
    env_admin = (os.getenv("ADMIN_USERNAME") or "admin").strip()
    if payload.get("sub") == env_admin:
        is_super = True

    if not is_super:
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Super Administrator privileges required."
        )

    return payload


# ── Request Models ──────────────────────────────────────────────

class SuperAdminLoginRequest(BaseModel):
    username: str
    password: str

class UpdateSchoolStatusRequest(BaseModel):
    status: str  # "active", "suspended", "cancelled"

class ResetPasswordRequest(BaseModel):
    new_password: str


# ── Super Admin Login ───────────────────────────────────────────

@router.post("/super-admin/login")
def super_admin_login(data: SuperAdminLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate exclusively for the platform owner (Super Admin).
    Accepts:
    1. Master environment credentials (ADMIN_USERNAME / ADMIN_PASSWORD)
    2. Users table accounts with role 'super_admin'
    """
    clean_user = (data.username or "").strip()
    clean_pass = (data.password or "").strip()

    if not clean_user or not clean_pass:
        raise HTTPException(status_code=400, detail="Username and password are required.")

    # 1. Master environment credentials
    env_admin_user = (os.getenv("ADMIN_USERNAME") or "admin").strip().strip('"\'')
    env_admin_pass = (os.getenv("ADMIN_PASSWORD") or "admin123").strip().strip('"\'')

    if env_admin_pass:
        is_user_match = secrets.compare_digest(clean_user.lower(), env_admin_user.lower())
        is_pass_match = secrets.compare_digest(clean_pass, env_admin_pass)
        if is_user_match and is_pass_match:
            token = create_access_token({
                "sub": env_admin_user,
                "name": "Platform Super Administrator",
                "role": "super_admin",
                "user_type": "super_admin",
                "is_super_admin": True
            })
            return {
                "message": "Super Admin authenticated successfully",
                "token": token,
                "username": env_admin_user,
                "role": "super_admin"
            }

    # 2. Database lookup for super_admin
    user = db.scalar(
        select(User).where(
            User.college_id.ilike(clean_user),
            User.user_type.in_(["super_admin", "superadmin"])
        )
    )
    if user:
        from core.security import verify_password
        if verify_password(clean_pass, user.password_hash):
            token = create_access_token({
                "sub": user.college_id,
                "name": user.name,
                "role": "super_admin",
                "user_type": "super_admin",
                "is_super_admin": True
            })
            return {
                "message": "Super Admin authenticated successfully",
                "token": token,
                "username": user.college_id,
                "role": "super_admin"
            }

    raise HTTPException(
        status_code=401,
        detail="Invalid Super Admin credentials."
    )


# ── Super Admin Dashboard Stats ─────────────────────────────────

@router.get("/super-admin/stats")
def get_super_admin_stats(request: Request, db: Session = Depends(get_db)):
    """Platform-wide system metrics for Super Admin."""
    require_super_admin(request)

    total_schools = db.scalar(select(func.count(School.id))) or 0
    active_schools = db.scalar(select(func.count(School.id)).where(School.subscription_status == "active")) or 0
    total_students = db.scalar(select(func.count(Member.id))) or 0
    total_tickets = db.scalar(select(func.count(Ticket.id))) or 0

    return {
        "total_schools": total_schools,
        "active_schools": active_schools,
        "total_students": total_students,
        "total_tickets": total_tickets
    }


# ── School Management Endpoints ─────────────────────────────────

@router.get("/super-admin/schools")
def list_all_schools(request: Request, db: Session = Depends(get_db)):
    """List all registered schools with subscription details and counts."""
    require_super_admin(request)

    schools = db.scalars(select(School).order_by(School.id.desc())).all()
    results = []

    for s in schools:
        mem_count = db.scalar(select(func.count(Member.id)).where(Member.school_id == s.id)) or 0
        tkt_count = db.scalar(select(func.count(Ticket.id)).where(Ticket.school_id == s.id)) or 0

        # Find admin username
        admin_user = db.scalar(select(User).where(User.school_id == s.id))
        admin_username = admin_user.college_id if admin_user else "N/A"

        results.append({
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "admin_email": s.admin_email,
            "admin_username": admin_username,
            "subscription_status": s.subscription_status,
            "plan": s.plan or "Standard",
            "google_sheet_url": s.google_sheet_url or "",
            "google_sheet_webhook_url": s.google_sheet_webhook_url or "",
            "members_count": mem_count,
            "tickets_count": tkt_count,
            "created_at": s.created_at.strftime("%Y-%m-%d %I:%M %p") if s.created_at else "N/A"
        })

    return results


@router.patch("/super-admin/schools/{school_id}/status")
def update_school_status(
    school_id: int,
    data: UpdateSchoolStatusRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Change school subscription status: active, suspended, cancelled."""
    require_super_admin(request)

    school = db.scalar(select(School).where(School.id == school_id))
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    new_status = data.status.strip().lower()
    if new_status not in ["active", "suspended", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status. Choose active, suspended, or cancelled.")

    school.subscription_status = new_status
    db.commit()

    return {
        "success": True,
        "message": f"School '{school.name}' subscription status updated to '{new_status}'."
    }


@router.post("/super-admin/schools/{school_id}/reset-password")
def reset_school_admin_password(
    school_id: int,
    data: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Reset the school administrator's login password."""
    require_super_admin(request)

    school = db.scalar(select(School).where(School.id == school_id))
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    new_pwd = (data.new_password or "").strip()
    if len(new_pwd) < 5:
        raise HTTPException(status_code=400, detail="Password must be at least 5 characters.")

    # Find admin user
    admin_user = db.scalar(select(User).where(User.school_id == school_id))
    if not admin_user:
        raise HTTPException(status_code=404, detail="No admin account found for this school.")

    admin_user.password_hash = hash_password(new_pwd)
    db.commit()

    return {
        "success": True,
        "message": f"Password for {school.name} admin ({admin_user.college_id}) has been reset successfully."
    }


@router.delete("/super-admin/schools/{school_id}")
def delete_school(
    school_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Delete a school and its associated data.
    Protected: Cannot delete Default School (ID: 1).
    """
    require_super_admin(request)

    if school_id == 1:
        raise HTTPException(status_code=400, detail="Default campus school cannot be deleted.")

    school = db.scalar(select(School).where(School.id == school_id))
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    school_name = school.name

    # Cascade delete tickets, members, and users for this school
    db.query(Ticket).filter(Ticket.school_id == school_id).delete()
    db.query(Member).filter(Member.school_id == school_id).delete()
    db.query(User).filter(User.school_id == school_id).delete()
    db.delete(school)
    db.commit()

    return {
        "success": True,
        "message": f"School '{school_name}' and all associated records have been deleted."
    }
