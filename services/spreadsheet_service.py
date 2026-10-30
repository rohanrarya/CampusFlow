"""
CampusFlow — Spreadsheet Service (services/spreadsheet_service.py)
Simple, clean helper for managing campus members and syncing with Google Sheets.
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
    return text  # Already plain ID

def sync_from_google_sheet(db: Session, sheet_url: str):
    """
    Fetch members from Google Sheets (via CSV export or Apps Script Webhook).
    Parses rows and saves them into the database roster.
    """
    if not sheet_url or not sheet_url.strip():
        raise ValueError("Google Sheet URL is required.")

    url = sheet_url.strip()
    rows = []

    # 1. If it's a Google Apps Script Webhook (ends in /exec)
    if "script.google.com" in url:
        req = urllib.request.Request(url, headers={"User-Agent": "CampusFlow/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                rows = data["data"]

    # 2. If it's a standard Google Sheets URL, fetch direct CSV export
    else:
        sheet_id = extract_sheet_id(url)
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        req = urllib.request.Request(csv_url, headers={"User-Agent": "CampusFlow/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            csv_content = resp.read().decode("utf-8", errors="ignore")
            reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(reader)

    if not rows:
        raise ValueError("No rows found in spreadsheet. Ensure sheet is not empty and shared properly.")

    # 3. Match flexible column names and save into database
    added_count = 0
    updated_count = 0

    for row in rows:
        # Standardize keys to lowercase without spaces/underscores
        normalized = {}
        for k, v in row.items():
            if k:
                clean_key = re.sub(r"[^a-zA-Z0-9]", "", k.lower())
                normalized[clean_key] = str(v).strip() if v else ""

        # Find College ID
        college_id = (
            normalized.get("collegeid") or
            normalized.get("studentid") or
            normalized.get("id") or
            normalized.get("rollno") or
            normalized.get("rollnumber")
        )

        # Find Name
        name = (
            normalized.get("name") or
            normalized.get("fullname") or
            normalized.get("studentname") or
            normalized.get("membername")
        )

        if not college_id or not name:
            continue

        department = normalized.get("department") or normalized.get("dept") or normalized.get("branch") or "General"
        email = normalized.get("email") or normalized.get("emailid") or normalized.get("mail") or ""
        role = normalized.get("role") or normalized.get("type") or normalized.get("designation") or "student"

        existing = db.scalar(select(Member).where(Member.college_id.ilike(college_id)))
        if existing:
            existing.name = name
            existing.department = department
            if email:
                existing.email = email
            existing.role = role.lower()
            updated_count += 1
        else:
            new_mem = Member(
                college_id=college_id,
                name=name,
                department=department,
                email=email if email else None,
                role=role.lower()
            )
            db.add(new_mem)
            added_count += 1

    db.commit()

    # Save last sync time and sheet url
    set_setting(db, "google_sheet_url", sheet_url)
    set_setting(db, "last_synced_at", get_ist_time())

    return {
        "success": True,
        "added": added_count,
        "updated": updated_count,
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


def seed_sample_members_if_empty(db: Session):
    """
    Add a few default sample college IDs so testing works immediately.
    """
    count = db.scalar(select(Member).limit(1))
    if not count:
        sample_members = [
            Member(college_id="STD202601", name="Rohan Sharma", department="Computer Science & Eng", email="rohan@campus.edu", role="student"),
            Member(college_id="STD202602", name="Ananya Patel", department="Electronics & Comm", email="ananya@campus.edu", role="student"),
            Member(college_id="STD202603", name="Vikram Singh", department="Mechanical Engineering", email="vikram@campus.edu", role="student"),
            Member(college_id="FAC9901", name="Dr. Rajesh Kumar", department="Computer Science & Eng", email="rajesh.kumar@campus.edu", role="faculty"),
            Member(college_id="FAC9902", name="Prof. Sunita Verma", department="Information Technology", email="sverma@campus.edu", role="faculty"),
        ]
        db.add_all(sample_members)
        db.commit()
        set_setting(db, "last_synced_at", get_ist_time() + " (Initial Seed)")
