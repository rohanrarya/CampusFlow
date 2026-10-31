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

@router.get("/cloudinary-sign")
def get_cloudinary_signature():
    """
    Generate signature for direct client-to-Cloudinary upload.
    This bypasses Vercel/serverless payload limits (4.5MB).
    """
    if not CLOUDINARY_API_SECRET or not CLOUDINARY_API_KEY or not CLOUDINARY_CLOUD_NAME:
        raise HTTPException(status_code=500, detail="Cloudinary credentials not configured")

    timestamp = int(time.time())
    params = {"timestamp": timestamp}
    signature = cloudinary.utils.api_sign_request(params, CLOUDINARY_API_SECRET)

    return {
        "timestamp": timestamp,
        "signature": signature,
        "api_key": CLOUDINARY_API_KEY,
        "cloud_name": CLOUDINARY_CLOUD_NAME
    }

@router.post("/complaint")
async def create_complaint(
    request: Request,
    message: str = Form(...),
    photo: UploadFile | None = File(None),
    image_url: str | None = Form(None),
    submission_id: str = Form(...),
    college_id: str | None = Form(None),
    school_id: int | None = Form(None),
    token: str | None = Form(None),
    is_anonymous: str | bool | None = Form(False),
    db: Session = Depends(get_db)
):
    anonymous_flag = str(is_anonymous).lower() in ["true", "1", "yes", "on"]
    submitted_by = "Campus Member"
    user_college_id = None
    resolved_school_id = school_id or 1

    # Priority 1: Direct College ID verification from school spreadsheet / roster
    if college_id and college_id.strip():
        clean_cid = college_id.strip()
        member = get_member_by_college_id(db, clean_cid, school_id=school_id)
        if not member:
            raise HTTPException(
                status_code=400,
                detail=f"Verification failed: College ID '{clean_cid}' is not registered in this school's directory."
            )
        submitted_by = member.name
        user_college_id = member.college_id
        resolved_school_id = member.school_id or resolved_school_id

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
                submitted_by = payload.get("name", "Campus Member")
                user_college_id = payload.get("sub")
                if payload.get("school_id"):
                    resolved_school_id = payload.get("school_id")

    # If neither College ID nor token was provided, reject submission
    if not user_college_id:
        raise HTTPException(
            status_code=400,
            detail="College ID is required to submit a complaint. Please enter your registered ID."
        )

    exist_ticket = get_ticket_by_submission_id(db, submission_id)
    if exist_ticket:
        return {
            "message": "This complaint has already been submitted",
            "ticket": exist_ticket
        }

    analysis = analyze_complaint(message)
    department = find_department(analysis.category.lower())

    # Case 1: Image already uploaded directly to Cloudinary from client
    if image_url:
        try:
            req = urllib.request.Request(
                image_url,
                headers={"User-Agent": "CampusFlow/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                image_data = resp.read()
            moderation = moderate_image(image_data)
            if not moderation.allowed:
                raise HTTPException(
                    status_code=400,
                    detail="Image rejected: " + moderation.reason
                )
        except HTTPException:
            raise
        except Exception as img_err:
            print(f"Could not moderate client-uploaded image: {img_err}")

    # Case 2: Standard form-data file upload (fallback)
    elif photo:
        image_data = await photo.read()
        moderation = moderate_image(image_data)
        if not moderation.allowed:
            raise HTTPException(
                status_code=400,
                detail="Image rejected: " + moderation.reason
            )
        result = cloudinary.uploader.upload(image_data)
        image_url = result.get("secure_url")

    # Create ticket in database with synchronized ticket details and school scoping
    ticket = create_ticket(
        db,
        analysis=analysis,
        department=department,
        image_url=image_url,
        submission_id=submission_id,
        submitted_by=submitted_by,
        user_college_id=user_college_id,
        school_id=resolved_school_id,
        is_anonymous=anonymous_flag
    )

    return {
        "message": "Complaint received",
        "complaint": message,
        "analysis": analysis,
        "department": department,
        "ticket": ticket
    }
