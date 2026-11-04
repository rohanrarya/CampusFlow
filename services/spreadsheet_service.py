"""
CampusFlow — Spreadsheet Service (services/spreadsheet_service.py)
Simple, robust helper for managing campus members and syncing with Google Sheets / Excel.
"""

import csv
import io
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from models.member import Member, AppSetting

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_time():
    return datetime.now(IST).strftime("%Y-%m-%d %I:%M %p IST")


# ── Simple Settings Storage ──────────────────────────────────────

def get_setting(db: Session, key: str, default: str = "") -> str:
    """Read a setting from database."""
    item = db.scalar(select(AppSetting).where(AppSetting.key == key))
    return item.value if item and item.value else default

def set_setting(db: Session, key: str, value: str):
    """Save a setting to database."""
    item = db.scalar(select(AppSetting).where(AppSetting.key == key))
    if not item:
        item = AppSetting(key=key, value=value)
        db.add(item)
    else:
        item.value = value
    db.commit()


# ── Member Database Helpers ──────────────────────────────────────

def get_member_by_college_id(db: Session, college_id: str):
    """
    Search for a member by College ID (case-insensitive).
    """
    if not college_id:
        return None
    clean_id = college_id.strip()
    return db.scalar(
        select(Member).where(Member.college_id.ilike(clean_id))
    )

def get_all_members(db: Session, search: str = ""):
    """
    Get all registered college members, with optional search.
    """
    query = select(Member).order_by(Member.id.desc())
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            (Member.college_id.ilike(pattern)) |
            (Member.name.ilike(pattern)) |
            (Member.department.ilike(pattern)) |
            (Member.email.ilike(pattern))
        )
    return db.scalars(query).all()

def add_or_update_member(db: Session, college_id: str, name: str, department: str = "", email: str = "", role: str = "student"):
    """
    Add a new member or update an existing member.
    """
    clean_id = college_id.strip()
    existing = db.scalar(select(Member).where(Member.college_id.ilike(clean_id)))
    
    if existing:
        existing.name = name.strip()
        if department:
            existing.department = department.strip()
        if email:
            existing.email = email.strip()
        if role:
            existing.role = role.strip().lower()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        new_member = Member(
            college_id=clean_id,
            name=name.strip(),
            department=department.strip() if department else "General",
            email=email.strip() if email else None,
            role=role.strip().lower() if role else "student"
        )
        db.add(new_member)
        db.commit()
        db.refresh(new_member)
        return new_member

def delete_member_by_college_id(db: Session, college_id: str):
    """
    Delete a member by college ID.
    """
    clean_id = college_id.strip()
    member = db.scalar(select(Member).where(Member.college_id.ilike(clean_id)))
    if member:
        db.delete(member)
        db.commit()
        return True
    return False


# ── Google Sheets Integration Helpers ───────────────────────────

def extract_sheet_id(url_or_id: str) -> str:
    """
    Extract the Google Sheet ID from a full Google Sheets URL.
    Example: https://docs.google.com/spreadsheets/d/1BxiMVs.../edit -> 1BxiMVs...
    """
    if not url_or_id:
        return ""
    text = url_or_id.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", text)
    if match:
        return match.group(1)
    return text

def sync_from_google_sheet(db: Session, sheet_url: str):
    """
    Fetch members from Google Sheets (via CSV export or Apps Script Webhook).
    Parses rows, updates the database roster, and prunes deleted records.
    """
    if not sheet_url or not sheet_url.strip():
        raise ValueError("Please provide a Google Sheet URL or Webhook in Sheet Settings.")

    url = sheet_url.strip()
    rows = []

    try:
        # 1. If it's a Google Apps Script Webhook (ends in /exec)
        if "script.google.com" in url or "/exec" in url:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "CampusFlow/1.0", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_body = resp.read().decode("utf-8")
                try:
                    data = json.loads(raw_body)
                except Exception:
                    data = []
                if isinstance(data, list):
                    rows = data
                elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                    rows = data["data"]

        # 2. Direct Google Sheets CSV export
        else:
            sheet_id = extract_sheet_id(url)
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
            req = urllib.request.Request(csv_url, headers={"User-Agent": "CampusFlow/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_bytes = resp.read()
                content = raw_bytes.decode("utf-8-sig", errors="replace")
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)

    except urllib.error.HTTPError as http_err:
        if http_err.code in [401, 403]:
            raise ValueError("Access Denied: In your Google Apps Script, set 'Who has access' to 'Anyone' and redeploy. For Google Sheet, set sharing to 'Anyone with link can view'.")
        elif http_err.code == 404:
            raise ValueError("Google Sheet not found. Please verify the sheet link in Sheet Settings.")
        else:
            raise ValueError(f"HTTP error connecting to Google Sheets ({http_err.code}): {http_err.reason}")
    except urllib.error.URLError as url_err:
        raise ValueError(f"Network error connecting to Google Sheets: {url_err.reason}")

    # If sheet is empty (or all rows were deleted): prune all members
    if not rows:
        all_members = db.scalars(select(Member)).all()
        pruned_count = len(all_members)
        for m in all_members:
            db.delete(m)
        db.commit()
        set_setting(db, "google_sheet_url", sheet_url)
        set_setting(db, "last_synced_at", get_ist_time())
        return {
            "success": True,
            "added": 0,
            "updated": 0,
            "pruned": pruned_count,
            "total_synced": 0,
            "message": f"Sync complete: 0 rows found in sheet (pruned {pruned_count} deleted members).",
            "timestamp": get_ist_time()
        }

    # Match flexible column names and save into database
    added_count = 0
    updated_count = 0
    sheet_ids = set()

    for row in rows:
        normalized = {}
        for k, v in row.items():
            if k:
                clean_key = re.sub(r"[^a-zA-Z0-9]", "", k.lower())
                normalized[clean_key] = str(v).strip() if v else ""

        college_id = (
            normalized.get("collegeid") or
            normalized.get("studentid") or
            normalized.get("id") or
            normalized.get("rollno") or
            normalized.get("rollnumber")
        )

        name = (
            normalized.get("name") or
            normalized.get("fullname") or
            normalized.get("studentname") or
            normalized.get("membername")
        )

        if not college_id or not name:
            continue

        clean_cid = college_id.strip()
        sheet_ids.add(clean_cid.upper())

        department = normalized.get("department") or normalized.get("dept") or normalized.get("branch") or "General"
        email = normalized.get("email") or normalized.get("emailid") or normalized.get("mail") or ""
        role = normalized.get("role") or normalized.get("type") or normalized.get("designation") or "student"

        existing = db.scalar(select(Member).where(Member.college_id.ilike(clean_cid)))
        if existing:
            existing.name = name
            existing.department = department
            if email:
                existing.email = email
            existing.role = role.lower()
            updated_count += 1
        else:
            new_mem = Member(
                college_id=clean_cid,
                name=name,
                department=department,
                email=email if email else None,
                role=role.lower()
            )
            db.add(new_mem)
            added_count += 1

    # Prune members that are no longer in the spreadsheet
    deleted_count = 0
    all_members = db.scalars(select(Member)).all()
    for m in all_members:
        if m.college_id.strip().upper() not in sheet_ids:
            db.delete(m)
            deleted_count += 1

    db.commit()

    # Save last sync time and sheet url
    set_setting(db, "google_sheet_url", sheet_url)
    set_setting(db, "last_synced_at", get_ist_time())

    return {
        "success": True,
        "added": added_count,
        "updated": updated_count,
        "pruned": deleted_count,
        "total_synced": added_count + updated_count,
        "timestamp": get_ist_time()
    }


def push_student_to_spreadsheet_webhook(webhook_url: str, member_data: dict) -> bool:
    """
    If admin set up a Google Apps Script Webhook, send the new member
    so Google Sheets automatically appends a new row.
    """
    if not webhook_url or not webhook_url.startswith("http"):
        return False
    try:
        payload = json.dumps(member_data).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CampusFlow/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status in [200, 201]
    except Exception as err:
        print(f"Warning: could not push to Google Sheets webhook: {err}")
        return False
