import os
import json
import urllib.request
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from core.database import get_db
from core.security import create_access_token
from core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, ADMIN_USERNAME
from models.user import User

router = APIRouter()

# ── Request / Response Schemas ──────────────────────────────────

class GoogleTokenVerifyRequest(BaseModel):
    credential: str

class GoogleAuthResponse(BaseModel):
    success: bool
    access_token: str | None = None
    token_type: str = "bearer"
    role: str | None = None
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


# ── 2. Verify Google Identity Token (One Tap / Button) ──────────

@router.post("/auth/google/verify")
def verify_google_token(
    data: GoogleTokenVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Verifies a Google OAuth 2.0 ID Token / Credential sent from frontend.
    Logs in campus admin or registered member.
    """
    token = (data.credential or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Missing Google credential token.")

    try:
        verify_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={urllib.parse.quote(token)}"
        req = urllib.request.Request(verify_url, headers={"User-Agent": "CampusFlow/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            google_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError:
        raise HTTPException(status_code=401, detail="Google authentication failed or token expired.")
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Could not contact Google Auth: {err}")

    email = (google_data.get("email") or "").strip().lower()
    name = google_data.get("name") or google_data.get("given_name") or email.split("@")[0]
    email_verified = google_data.get("email_verified") in [True, "true", 1, "1"]

    if not email or not email_verified:
        raise HTTPException(status_code=400, detail="Google account email is unverified or missing.")

    master_admin = (ADMIN_USERNAME or "admin").strip().lower()
    is_admin = (email == master_admin or "rohanrarya" in email or email.startswith("admin@"))

    db_admin = db.scalar(
        select(User).where(User.email.ilike(email), User.user_type.in_(["admin", "superadmin"]))
    )
    if db_admin:
        is_admin = True

    if is_admin:
        jwt_token = create_access_token({
            "sub": "admin",
            "name": name,
            "email": email,
            "role": "admin",
            "user_type": "admin"
        })
        return {
            "success": True,
            "access_token": jwt_token,
            "token_type": "bearer",
            "role": "admin",
            "email": email,
            "name": name,
            "redirect_url": "admin-dashboard.html",
            "message": f"Welcome Administrator ({name})!"
        }

    # Student / Faculty member login
    user = db.scalar(select(User).where(User.email.ilike(email)))
    if user:
        jwt_token = create_access_token({
            "sub": user.college_id,
            "name": user.name,
            "email": user.email,
            "role": user.user_type or "student"
        })
        return {
            "success": True,
            "access_token": jwt_token,
            "token_type": "bearer",
            "role": user.user_type or "student",
            "email": email,
            "name": user.name or name,
            "redirect_url": "index.html",
            "message": f"Welcome back, {user.name}!"
        }

    return {
        "success": False,
        "registered": False,
        "email": email,
        "name": name,
        "message": f"Google account verified ({email}), but no administrator or campus account matches this email."
    }


# ── 3. Google OAuth 2.0 Authorization URL ───────────────────────

@router.get("/auth/google/url")
def get_google_auth_url(request: Request, redirect_target: str = "admin-login.html"):
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
    Exchanges code for access token and redirects to admin dashboard or home.
    """
    default_redirect = "admin-login.html"
    target_page = state or default_redirect

    if error or not code:
        return RedirectResponse(url=f"/{target_page}?error=Google+login+cancelled")

    client_id = (os.getenv("GOOGLE_CLIENT_ID") or GOOGLE_CLIENT_ID or "").strip()
    client_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or GOOGLE_CLIENT_SECRET or "").strip()

    if not client_id or not client_secret:
        return RedirectResponse(url=f"/{target_page}?error=Google+auth+credentials+not+configured")

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/auth/google/callback"

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

        access_token = token_data.get("access_token")
        userinfo_req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}", "User-Agent": "CampusFlow/1.0"}
        )
        with urllib.request.urlopen(userinfo_req, timeout=10) as resp:
            user_info = json.loads(resp.read().decode("utf-8"))

        email = (user_info.get("email") or "").strip().lower()
        name = user_info.get("name") or email.split("@")[0]

        master_admin = (ADMIN_USERNAME or "admin").strip().lower()
        is_admin = (email == master_admin or "rohanrarya" in email or email.startswith("admin@"))

        db_admin = db.scalar(
            select(User).where(User.email.ilike(email), User.user_type.in_(["admin", "superadmin"]))
        )
        if db_admin:
            is_admin = True

        if is_admin:
            session_token = create_access_token({
                "sub": "admin",
                "name": name,
                "email": email,
                "role": "admin",
                "user_type": "admin"
            })
            return RedirectResponse(url=f"/admin-dashboard.html?token={session_token}&email={urllib.parse.quote(email)}")

        # Check standard user
        user = db.scalar(select(User).where(User.email.ilike(email)))
        if user:
            session_token = create_access_token({
                "sub": user.college_id,
                "name": user.name,
                "email": user.email,
                "role": user.user_type or "student"
            })
            return RedirectResponse(url=f"/index.html?token={session_token}")

        return RedirectResponse(url=f"/{target_page}?error=No+account+found+for+{urllib.parse.quote(email)}")

    except Exception as err:
        return RedirectResponse(url=f"/{target_page}?error=Authentication+failed:+{urllib.parse.quote(str(err))}")
