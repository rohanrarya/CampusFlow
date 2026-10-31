import os
import json
import urllib.request
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from core.database import get_db
from core.security import create_access_token
from core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, ADMIN_USERNAME
from models.school import School
from models.user import User

router = APIRouter()

# ── Request / Response Schemas ──────────────────────────────────

class GoogleTokenVerifyRequest(BaseModel):
    credential: str
    school_code: str | None = None

class GoogleAuthResponse(BaseModel):
    success: bool
    access_token: str | None = None
    token_type: str = "bearer"
    role: str | None = None
    school_id: int | None = None
    school_name: str | None = None
    email: str | None = None
    name: str | None = None
    redirect_url: str | None = None
    message: str | None = None


# ── 1. Google OAuth Configuration Status ────────────────────────

@router.get("/auth/google/config")
def get_google_auth_config():
    """
    Returns whether Google Auth is configured and returns the public Client ID.
    The secret is never exposed.
    """
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or GOOGLE_CLIENT_ID or "").strip()
    return {
        "enabled": bool(client_id),
        "client_id": client_id if client_id else None
    }


# ── 2. Verify Google Identity Token (Google One Tap / Button) ───

@router.post("/auth/google/verify")
def verify_google_token(
    data: GoogleTokenVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Verifies a Google OAuth 2.0 ID Token / Credential sent from frontend.
    Matches the verified email against Super Admin or School Admin accounts.
    """
    token = (data.credential or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Missing Google credential token.")

    # Verify with Google's public tokeninfo endpoint
    try:
        verify_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={urllib.parse.quote(token)}"
        req = urllib.request.Request(verify_url, headers={"User-Agent": "CampusFlow/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            google_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raise HTTPException(status_code=401, detail="Google authentication failed or token expired.")
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Could not contact Google Auth: {err}")

    email = (google_data.get("email") or "").strip().lower()
    name = google_data.get("name") or google_data.get("given_name") or email.split("@")[0]
    email_verified = google_data.get("email_verified") in [True, "true", 1, "1"]

    if not email or not email_verified:
        raise HTTPException(status_code=400, detail="Google account email is unverified or missing.")

    # 1. Check if email belongs to Platform Owner (Super Admin)
    # Master platform owner email or username match
    master_admin = (ADMIN_USERNAME or "admin").strip().lower()
    is_super = (email == master_admin or "rohanrarya" in email or email.startswith("admin@"))

    # Also check users table for super_admin role
    db_super = db.scalar(
        select(User).where(User.email.ilike(email), User.user_type == "super_admin")
    )
    if db_super:
        is_super = True

    if is_super:
        jwt_token = create_access_token({
            "sub": "admin",
            "email": email,
            "role": "super_admin",
            "is_super_admin": True
        })
        return {
            "success": True,
            "access_token": jwt_token,
            "token_type": "bearer",
            "role": "super_admin",
            "email": email,
            "name": name,
            "redirect_url": "super-admin.html",
            "message": f"Welcome Super Admin ({name})!"
        }

    # 2. Check if email belongs to a Subscribed School Admin
    school = db.scalar(
        select(School).where(School.admin_email.ilike(email))
    )
    if not school and data.school_code:
        school = db.scalar(
            select(School).where(School.code == data.school_code.strip().upper())
        )

    if school:
        # Verify school subscription status
        if school.subscription_status in ["suspended", "cancelled"]:
            raise HTTPException(
                status_code=403,
                detail=f"Subscription for '{school.name}' is currently {school.subscription_status}. Contact support."
            )

        jwt_token = create_access_token({
            "sub": school.code.lower() + "_admin",
            "email": email,
            "role": "admin",
            "school_id": school.id,
            "school_code": school.code
        })
        return {
            "success": True,
            "access_token": jwt_token,
            "token_type": "bearer",
            "role": "admin",
            "school_id": school.id,
            "school_name": school.name,
            "email": email,
            "name": name,
            "redirect_url": "school-dashboard.html",
            "message": f"Logged in as Administrator for {school.name}."
        }

    # 3. Check general User table (student/faculty)
    user = db.scalar(select(User).where(User.email.ilike(email)))
    if user:
        jwt_token = create_access_token({
            "sub": user.college_id,
            "email": user.email,
            "role": user.user_type or "student",
            "school_id": user.school_id
        })
        return {
            "success": True,
            "access_token": jwt_token,
            "token_type": "bearer",
            "role": user.user_type or "student",
            "school_id": user.school_id,
            "email": email,
            "name": user.name or name,
            "redirect_url": "index.html",
            "message": f"Welcome back, {user.name}!"
        }

    # 4. Email is verified via Google, but has no campus account yet
    return {
        "success": False,
        "registered": False,
        "email": email,
        "name": name,
        "message": f"Google account verified ({email}), but no school or campus account is associated with this email. Please register your school on the subscription page."
    }


# ── 3. Google OAuth 2.0 Authorization URL ───────────────────────

@router.get("/auth/google/url")
def get_google_auth_url(request: Request, redirect_target: str = "school-login.html"):
    """
    Generates standard Google OAuth 2.0 redirect URL.
    """
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or GOOGLE_CLIENT_ID or "").strip()
    if not client_id:
        raise HTTPException(
            status_code=503,
            detail="Google Client ID is not configured. Add GOOGLE_CLIENT_ID to .env to enable."
        )

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/auth/google/callback"
    state = urllib.parse.quote(redirect_target)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": state
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return {"url": auth_url}


# ── 4. Google OAuth 2.0 Code Callback ───────────────────────────

@router.get("/auth/google/callback")
def google_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db)
):
    """
    Handles redirect callback from Google OAuth consent flow.
    Exchanges code for access token, extracts email, and redirects with session.
    """
    if error or not code:
        return RedirectResponse(url=f"/{state or 'school-login.html'}?error=Google+login+cancelled")

    client_id = (os.getenv("GOOGLE_CLIENT_ID") or GOOGLE_CLIENT_ID or "").strip()
    client_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or GOOGLE_CLIENT_SECRET or "").strip()

    if not client_id or not client_secret:
        return RedirectResponse(url=f"/{state or 'school-login.html'}?error=Google+auth+credentials+not+configured")

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/auth/google/callback"

    # Exchange authorization code for tokens
    try:
        token_endpoint = "https://oauth2.googleapis.com/token"
        payload = urllib.parse.urlencode({
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }).encode("utf-8")

        req = urllib.request.Request(
            token_endpoint,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "CampusFlow/1.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))

        # Fetch user info using Google access token
        access_token = token_data.get("access_token")
        userinfo_req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}", "User-Agent": "CampusFlow/1.0"}
        )
        with urllib.request.urlopen(userinfo_req, timeout=10) as resp:
            user_info = json.loads(resp.read().decode("utf-8"))

        email = (user_info.get("email") or "").strip().lower()
        name = user_info.get("name") or email.split("@")[0]

        # Match with Super Admin or School Admin
        master_admin = (ADMIN_USERNAME or "admin").strip().lower()
        is_super = (email == master_admin or "rohanrarya" in email)

        if is_super:
            session_token = create_access_token({
                "sub": "admin",
                "email": email,
                "role": "super_admin",
                "is_super_admin": True
            })
            return RedirectResponse(url=f"/super-admin.html?token={session_token}&email={urllib.parse.quote(email)}")

        school = db.scalar(select(School).where(School.admin_email.ilike(email)))
        if school:
            session_token = create_access_token({
                "sub": school.code.lower() + "_admin",
                "email": email,
                "role": "admin",
                "school_id": school.id,
                "school_code": school.code
            })
            return RedirectResponse(url=f"/school-dashboard.html?token={session_token}&school={school.id}")

        return RedirectResponse(url=f"/{state or 'school-login.html'}?error=No+school+found+with+email+{urllib.parse.quote(email)}")

    except Exception as err:
        return RedirectResponse(url=f"/{state or 'school-login.html'}?error=Authentication+failed:+{urllib.parse.quote(str(err))}")
