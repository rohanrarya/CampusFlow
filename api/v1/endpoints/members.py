import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from core.database import get_db
from core.security import decode_access_token
from models.member import Member
from services.spreadsheet_service import (
    get_member_by_college_id,
    get_all_members,
    add_or_update_member,
    delete_member_by_college_id,
    get_school_spreadsheet_config,
    set_school_spreadsheet_config,
    sync_from_google_sheet,
    push_student_to_spreadsheet_webhook
)

router = APIRouter()


# ── Dependency: Verify Admin Token ──────────────────────────────

def require_admin(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()

    if not token:
        raise HTTPException(status_code=401, detail="Missing admin authorization token.")

    payload = decode_access_token(token)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Invalid or unauthorized admin session.")

    return payload


# ── Pydantic Request Models ─────────────────────────────────────

class AddMemberRequest(BaseModel):
    college_id: str
    name: str
    department: str = "General"
    email: str = ""
    role: str = "student"

class SpreadsheetConfigRequest(BaseModel):
    google_sheet_url: str = ""
    webhook_url: str = ""

class SyncRequest(BaseModel):
    sheet_url: str = ""


# ── Public Endpoint: Verify College ID ──────────────────────────

@router.get("/members/verify/{college_id}")
def verify_college_id(
    college_id: str,
    school_id: int | None = None,
    db: Session = Depends(get_db)
):
    """
    Auto-fetch verification for complaint submission form.
    Checks if the entered college_id exists in the school's spreadsheet roster.
    """
    clean_id = (college_id or "").strip()
    if not clean_id:
        raise HTTPException(status_code=400, detail="College ID is required.")

    member = get_member_by_college_id(db, clean_id, school_id=school_id)
    if not member:
        return {
            "verified": False,
            "message": f"College ID '{clean_id}' was not found in the campus spreadsheet roster."
        }

    return {
        "verified": True,
        "member": {
            "college_id": member.college_id,
            "name": member.name,
            "department": member.department or "General",
            "email": member.email or "",
            "role": member.role or "student",
            "school_id": member.school_id
        }
    }


# ── Admin Endpoints: Member Management (Scoped by School) ───────

@router.get("/admin/members")
def list_admin_members(
    request: Request,
    search: str = "",
    db: Session = Depends(get_db)
):
    """
    List all members in the school's roster for Admin Dashboard.
    """
    payload = require_admin(request)
    school_id = payload.get("school_id") or 1
    members = get_all_members(db, search=search, school_id=school_id)

    return [
        {
            "id": m.id,
            "college_id": m.college_id,
            "name": m.name,
            "department": m.department or "General",
            "email": m.email or "",
            "role": m.role or "student",
            "school_id": m.school_id,
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
        for m in members
    ]


@router.post("/admin/members")
def add_admin_member(
    data: AddMemberRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Add a new student or faculty member via Admin UI.
    Saves to the school's roster and pushes to the school's Google Sheet webhook.
    """
    payload = require_admin(request)
    school_id = payload.get("school_id") or 1

    if not data.college_id or not data.college_id.strip():
        raise HTTPException(status_code=400, detail="College ID is required.")
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="Member name is required.")

    member = add_or_update_member(
        db=db,
        college_id=data.college_id,
        name=data.name,
        department=data.department,
        email=data.email,
        role=data.role,
        school_id=school_id
    )

    # Push to school's private Google Apps Script Webhook
    cfg = get_school_spreadsheet_config(db, school_id=school_id)
    webhook_url = cfg.get("google_sheet_webhook_url", "")
    sheet_pushed = False
    if webhook_url:
        sheet_pushed = push_student_to_spreadsheet_webhook(
            webhook_url,
            {
                "college_id": member.college_id,
                "name": member.name,
                "department": member.department,
                "email": member.email or "",
                "role": member.role
            }
        )

    return {
        "success": True,
        "message": f"Member {member.name} ({member.college_id}) saved successfully.",
        "member": {
            "id": member.id,
            "college_id": member.college_id,
            "name": member.name,
            "department": member.department,
            "email": member.email or "",
            "role": member.role,
            "school_id": member.school_id
        },
        "sheet_pushed": sheet_pushed
    }


@router.delete("/admin/members/{college_id}")
def delete_admin_member(
    college_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete a member from the school's campus roster."""
    payload = require_admin(request)
    school_id = payload.get("school_id") or 1
    deleted = delete_member_by_college_id(db, college_id, school_id=school_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Member not found.")
    return {"success": True, "message": f"Member '{college_id}' removed."}


# ── Admin Endpoints: Spreadsheet Configuration & Sync ───────────

@router.get("/admin/spreadsheet/config")
def get_spreadsheet_config(request: Request, db: Session = Depends(get_db)):
    """Get current school's Google Sheet settings and sync statistics."""
    payload = require_admin(request)
    school_id = payload.get("school_id") or 1
    cfg = get_school_spreadsheet_config(db, school_id=school_id)

    total_count = db.scalar(
        select(func.count(Member.id)).where(Member.school_id == school_id)
    ) or 0

    return {
        "google_sheet_url": cfg.get("google_sheet_url", ""),
        "google_sheet_webhook_url": cfg.get("google_sheet_webhook_url", ""),
        "last_synced_at": cfg.get("last_synced_at", "Never"),
        "total_members": total_count,
        "school_id": school_id,
        "school_name": cfg.get("school_name", "Main Campus"),
        "school_code": cfg.get("school_code", "DEFAULT")
    }


@router.post("/admin/spreadsheet/config")
def save_spreadsheet_config(
    data: SpreadsheetConfigRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Save Google Sheet link and Webhook URL for the current school."""
    payload = require_admin(request)
    school_id = payload.get("school_id") or 1

    set_school_spreadsheet_config(
        db,
        school_id=school_id,
        sheet_url=data.google_sheet_url.strip(),
        webhook_url=data.webhook_url.strip()
    )

    return {
        "success": True,
        "message": "Spreadsheet configuration saved for your school.",
        "google_sheet_url": data.google_sheet_url.strip(),
        "google_sheet_webhook_url": data.webhook_url.strip()
    }


@router.post("/admin/spreadsheet/sync")
def trigger_spreadsheet_sync(
    data: SyncRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Trigger on-demand sync from Google Sheet for the current school."""
    payload = require_admin(request)
    school_id = payload.get("school_id") or 1

    cfg = get_school_spreadsheet_config(db, school_id=school_id)
    target_url = (
        data.sheet_url.strip() or
        cfg.get("google_sheet_url", "") or
        cfg.get("google_sheet_webhook_url", "")
    )

    if not target_url:
        raise HTTPException(
            status_code=400,
            detail="No Google Sheet URL or Webhook configured for your school. Please configure it in Sheet Settings."
        )

    try:
        result = sync_from_google_sheet(db, target_url, school_id=school_id)
        return result
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Sync failed: {err}")


# ── CSV Import & Export (Scoped by School) ───────────────────────

@router.get("/admin/members/export-csv")
def export_members_csv(request: Request, db: Session = Depends(get_db)):
    """Export the school's members roster as a downloadable CSV."""
    payload = require_admin(request)
    school_id = payload.get("school_id") or 1
    members = get_all_members(db, school_id=school_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["College ID", "Name", "Department", "Role", "Email"])

    for m in members:
        writer.writerow([
            m.college_id,
            m.name,
            m.department or "General",
            m.role or "student",
            m.email or ""
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=campus_roster_school_{school_id}.csv"}
    )


@router.post("/admin/members/import-csv")
async def import_members_csv(
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Upload and bulk import members for the school via CSV."""
    payload = require_admin(request)
    school_id = payload.get("school_id") or 1

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a valid .csv file.")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        imported_count = 0
        for row in reader:
            normalized = {k.strip().lower().replace(" ", "").replace("_", ""): v.strip() for k, v in row.items() if k}
            cid = normalized.get("collegeid") or normalized.get("studentid") or normalized.get("id")
            name = normalized.get("name") or normalized.get("fullname")
            if cid and name:
                dept = normalized.get("department") or normalized.get("dept") or "General"
                email = normalized.get("email") or ""
                role = normalized.get("role") or "student"
                add_or_update_member(db, cid, name, dept, email, role, school_id=school_id)
                imported_count += 1

        return {
            "success": True,
            "message": f"Successfully imported {imported_count} members.",
            "count": imported_count
        }
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {err}")


# ── Webhook: Real-Time Auto Sync from Google Sheets ──────────────

@router.post("/webhook/sheet-sync/{school_id}")
@router.get("/webhook/sheet-sync/{school_id}")
def webhook_sheet_sync(
    school_id: int,
    db: Session = Depends(get_db)
):
    """
    Public webhook endpoint callable by Google Apps Script onChange / onEdit trigger.
    Whenever a row is added, edited, or deleted in the Google Sheet,
    Google Apps Script pings this endpoint to instantly update CampusFlow's roster.
    """
    cfg = get_school_spreadsheet_config(db, school_id=school_id)
    target_url = cfg.get("google_sheet_url") or cfg.get("google_sheet_webhook_url")
    if not target_url:
        return {"success": False, "message": f"No sheet URL configured for school {school_id}"}

    try:
        result = sync_from_google_sheet(db, target_url, school_id=school_id)
        return {"success": True, "school_id": school_id, "sync": result}
    except Exception as err:
        return {"success": False, "error": str(err)}
