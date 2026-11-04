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
    get_setting,
    set_setting,
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
def verify_college_id(college_id: str, db: Session = Depends(get_db)):
    """
    Auto-fetch verification for complaint submission form.
    Checks if the entered college_id exists in the admin roster/spreadsheet.
    """
    clean_id = (college_id or "").strip()
    if not clean_id:
        raise HTTPException(status_code=400, detail="College ID is required.")

    member = get_member_by_college_id(db, clean_id)
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
            "role": member.role or "student"
        }
    }


# ── Admin Endpoints: Member Management ──────────────────────────

@router.get("/admin/members")
def list_admin_members(
    request: Request,
    search: str = "",
    db: Session = Depends(get_db)
):
    """
    List all members in roster for Admin Dashboard.
    """
    require_admin(request)
    members = get_all_members(db, search=search)
    return [
        {
            "id": m.id,
            "college_id": m.college_id,
            "name": m.name,
            "department": m.department or "General",
            "email": m.email or "",
            "role": m.role or "student",
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
    Saves to database and sends to Google Sheets webhook if configured.
    """
    require_admin(request)

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
        role=data.role
    )

    webhook_url = get_setting(db, "google_sheet_webhook_url", "")
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
            "role": member.role
        },
        "sheet_pushed": sheet_pushed
    }


@router.delete("/admin/members/{college_id}")
def delete_admin_member(
    college_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Delete a member from campus roster.
    """
    require_admin(request)
    deleted = delete_member_by_college_id(db, college_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Member not found.")
    return {"success": True, "message": f"Member '{college_id}' removed."}


# ── Admin Endpoints: Spreadsheet Configuration & Sync ───────────

@router.get("/admin/spreadsheet/config")
def get_spreadsheet_config(request: Request, db: Session = Depends(get_db)):
    """
    Get current Google Sheet settings and sync statistics.
    """
    require_admin(request)
    sheet_url = get_setting(db, "google_sheet_url", "")
    webhook_url = get_setting(db, "google_sheet_webhook_url", "")
    last_synced_at = get_setting(db, "last_synced_at", "Never")
    total_members = db.scalar(select(func.count(Member.id))) or 0

    return {
        "google_sheet_url": sheet_url,
        "webhook_url": webhook_url,
        "last_synced_at": last_synced_at,
        "total_members": total_members
    }


@router.post("/admin/spreadsheet/config")
def save_spreadsheet_config(
    data: SpreadsheetConfigRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Save Google Sheet URL and Apps Script Webhook URL.
    """
    require_admin(request)
    set_setting(db, "google_sheet_url", data.google_sheet_url.strip())
    set_setting(db, "google_sheet_webhook_url", data.webhook_url.strip())
    return {"success": True, "message": "Spreadsheet configuration saved."}


@router.post("/admin/spreadsheet/sync")
def trigger_spreadsheet_sync(
    data: SyncRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Trigger on-demand sync from Google Sheet into local database.
    """
    require_admin(request)
    sheet_url = (
        (data.sheet_url or "").strip()
        or get_setting(db, "google_sheet_url", "")
        or get_setting(db, "google_sheet_webhook_url", "")
    )

    if not sheet_url:
        raise HTTPException(
            status_code=400,
            detail="No Google Sheet URL or Webhook found. Please click 'Sheet Settings' and paste your link first."
        )

    try:
        result = sync_from_google_sheet(db, sheet_url)
        return result
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Spreadsheet sync failed: {str(err)}")


@router.post("/webhook/sheet-sync")
@router.get("/webhook/sheet-sync")
def webhook_sheet_sync(db: Session = Depends(get_db)):
    """
    Public webhook endpoint callable by Google Apps Script onChange / onEdit trigger.
    Whenever a row is added, edited, or deleted in the Google Sheet,
    Google Apps Script pings this endpoint to instantly update CampusFlow's roster.
    """
    sheet_url = get_setting(db, "google_sheet_url", "") or get_setting(db, "google_sheet_webhook_url", "")
    if not sheet_url:
        return {"success": False, "message": "No sheet URL configured."}

    try:
        result = sync_from_google_sheet(db, sheet_url)
        return {"success": True, "sync": result}
    except Exception as err:
        return {"success": False, "error": str(err)}


@router.post("/admin/members/import-csv")
async def import_csv_members(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Bulk import students from a CSV file.
    """
    require_admin(request)

    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))

    added = 0
    for row in reader:
        row_clean = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items() if k}
        cid = row_clean.get("college_id") or row_clean.get("id") or row_clean.get("student_id") or row_clean.get("roll_no")
        name = row_clean.get("name") or row_clean.get("full_name") or row_clean.get("student_name")
        dept = row_clean.get("department") or row_clean.get("dept") or row_clean.get("branch") or "General"
        email = row_clean.get("email") or ""
        role = row_clean.get("role") or "student"

        if cid and name:
            add_or_update_member(db, college_id=cid, name=name, department=dept, email=email, role=role)
            added += 1

    return {"success": True, "message": f"Successfully imported {added} members from CSV."}


@router.get("/admin/members/export-csv")
def export_csv_members(request: Request, db: Session = Depends(get_db)):
    """
    Export all campus members as a downloadable CSV.
    """
    require_admin(request)
    members = get_all_members(db)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["College ID", "Full Name", "Department", "Role", "Email", "Date Added"])

    for m in members:
        writer.writerow([
            m.college_id,
            m.name,
            m.department or "",
            m.role or "student",
            m.email or "",
            m.created_at.strftime("%Y-%m-%d") if m.created_at else ""
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=campus_members_roster.csv"}
    )
