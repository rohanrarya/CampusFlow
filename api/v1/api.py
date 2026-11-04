from fastapi import APIRouter
from .endpoints import complaints, tickets, admin, auth, members, google_auth

api_router = APIRouter()
api_router.include_router(google_auth.router, tags=["google-auth"])
api_router.include_router(members.router, tags=["members"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(complaints.router, tags=["complaints"])
api_router.include_router(tickets.router, tags=["tickets"])
api_router.include_router(admin.router, tags=["admin"])
