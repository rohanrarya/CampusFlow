import time
import urllib.request
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
import cloudinary.uploader
import cloudinary.utils
from core.database import get_db
import core.cloudinary
from core.config import CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_CLOUD_NAME
from core.security import decode_access_token
from services.ai_service import analyze_complaint, moderate_image, find_department
from services.ticket_service import create_ticket, get_ticket_by_submission_id
from services.spreadsheet_service import get_member_by_college_id

router = APIRouter()

@router.get("/cloudinary-config")
def get_cloudinary_config():
    """Provides signature and timestamp for direct client-side uploads."""
    timestamp = int(time.time())
    params = {"timestamp": timestamp}
    signature = cloudinary.utils.api_sign_request(params, CLOUDINARY_API_SECRET)
    return {
        "cloud_name": CLOUDINARY_CLOUD_NAME,
        "api_key": CLOUDINARY_API_KEY,
        "timestamp": timestamp,
        "signature": signature
    }

@router.post("/complaint")
async def create_complaint(
    request: Request,
    message: str = Form(...),
    photo: UploadFile | None = File(None),
    image_url: str | None = Form(None),
    submission_id: str = Form(...),
    college_id: str | None = Form(None),
    token: str | None = Form(None),
    is_anonymous: str | bool | None = Form(False),
    school_id: int | None = Form(None),
    db: Session = Depends(get_db)
):
    anonymous_flag = str(is_anonymous).lower() in ["true", "1", "yes", "on"]
    submitted_by = "Campus Member"
    user_college_id = None

    # Priority 1: Direct College ID verification from campus spreadsheet / roster
    if college_id and college_id.strip():
        clean_cid = college_id.strip()
        member = get_member_by_college_id(db, clean_cid)
        if not member:
            raise HTTPException(
                status_code=400,
                detail=f"Verification failed: College ID '{clean_cid}' is not registered in the campus spreadsheet directory."
            )
        submitted_by = member.name
        user_college_id = member.college_id

    # Priority 2: Fallback to token if provided
    elif token or request.headers.get("Authorization"):
        user_token = token
        if not user_token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                user_token = auth_header.replace("Bearer ", "").strip()
        if user_token:
            payload = decode_access_token(user_token)
            if payload:
                submitted_by = payload.get("name") or payload.get("sub") or "Campus Member"
                user_college_id = payload.get("sub")

    # Idempotency check
    existing_ticket = get_ticket_by_submission_id(db, submission_id)
    if existing_ticket:
        return {
            "message": "Complaint already submitted",
            "complaint": message,
            "department": existing_ticket.get("department"),
            "ticket": existing_ticket
        }

    # AI complaint analysis
    analysis = analyze_complaint(message)
    department = find_department(analysis.category)

    # Handle image upload if attached
    if photo and photo.filename:
        image_data = await photo.read()
        moderation = moderate_image(image_data)
        if not moderation.allowed:
            raise HTTPException(
                status_code=400,
                detail="Image rejected: " + moderation.reason
            )
        result = cloudinary.uploader.upload(image_data)
        image_url = result.get("secure_url")

    # Create ticket in database
    ticket = create_ticket(
        db,
        analysis=analysis,
        department=department,
        image_url=image_url,
        submission_id=submission_id,
        submitted_by=submitted_by,
        user_college_id=user_college_id,
        is_anonymous=anonymous_flag
    )

    return {
        "message": "Complaint received",
        "complaint": message,
        "analysis": analysis,
        "department": department,
        "ticket": ticket
    }
