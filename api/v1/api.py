from fastapi import APIRouter
from .endpoints import complaints, tickets, admin, auth, members, schools, super_admin

api_router = APIRouter()
api_router.include_router(super_admin.router, tags=["super-admin"])
api_router.include_router(schools.router, tags=["schools"])
api_router.include_router(members.router, tags=["members"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(complaints.router, tags=["complaints"])
api_router.include_router(tickets.router, tags=["tickets"])
api_router.include_router(admin.router, tags=["admin"])
