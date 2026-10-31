import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from api.v1.api import api_router

app = FastAPI(
    title="CampusFlow",
    description="Campus Grievance Redressal System powered by Gemini AI",
    version="1.0.0"
)

# CORS middleware for local development and client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount Static Files & Templates ────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/css", StaticFiles(directory="static/css"), name="css")
app.mount("/js", StaticFiles(directory="static/js"), name="js")
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
templates = Jinja2Templates(directory="templates")

@app.get("/favicon.svg", include_in_schema=False)
@app.get("/favicon.ico", include_in_schema=False)
def get_favicon():
    from fastapi.responses import FileResponse
    return FileResponse("static/favicon.svg")

# ── Include API Routes ────────────────────────────────────────
# Expose at root (for frontend compatibility) and /api/v1 (standard versioning)
app.include_router(api_router)
app.include_router(api_router, prefix="/api/v1")


# ── Startup: Ensure Tables & Seed Members ─────────────────────
@app.on_event("startup")
def startup_db_init():
    try:
        from core.database import engine, Base
        import models
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Startup DB init warning: {e}")
@app.api_route("/health", methods=["GET", "HEAD", "OPTIONS"])
def health():
    return {"status": "ok", "message": "CampusFlow AI is running"}

# ── Frontend HTML Template Routes ─────────────────────────────
@app.get("/")
@app.get("/index.html")
def render_home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/complaints")
@app.get("/complaints.html")
def render_complaints(request: Request):
    return templates.TemplateResponse(request=request, name="complaints.html")

@app.get("/login")
@app.get("/login.html")
def render_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/register")
@app.get("/register.html")
def render_register(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")

@app.get("/admin-login")
@app.get("/admin-login.html")
def render_admin_login(request: Request):
    return templates.TemplateResponse(request=request, name="admin-login.html")

@app.get("/admin-dashboard")
@app.get("/admin-dashboard.html")
def render_admin_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="admin-dashboard.html")


@app.get("/subscribe")
@app.get("/subscribe.html")
def render_subscribe(request: Request):
    return templates.TemplateResponse(request=request, name="subscribe.html")