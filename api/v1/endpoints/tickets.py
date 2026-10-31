from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from core.database import get_db
from core.security import decode_access_token
from services.ticket_service import get_all_tickets, get_ticket, update_ticket_status

router = APIRouter()

class StatusUpdate(BaseModel):
    status: str

@router.get("/tickets")
def list_tickets(
    request: Request,
    school_id: int | None = None,
    db: Session = Depends(get_db)
):
    """List tickets scoped to a school if authenticated or requested."""
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "").strip()
            payload = decode_access_token(token)
            if payload and payload.get("school_id"):
                school_id = payload.get("school_id")

        return get_all_tickets(db, school_id=school_id)
    except Exception as e:
        print(f"Database error in list_tickets: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database connection error. Please verify your Neon DATABASE_URL credentials."
        )

@router.get("/tickets/{ticket_id}")
def read_ticket(ticket_id: str, db: Session = Depends(get_db)):
    try:
        ticket = get_ticket(db, ticket_id)
    except Exception as e:
        print(f"Database error in read_ticket: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database connection error. Please verify your Neon DATABASE_URL credentials."
        )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@router.patch("/tickets/{ticket_id}")
def update_status(
    ticket_id: str,
    data: StatusUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    if data.status not in ["Pending", "In Progress", "Resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status.")

    school_id = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        payload = decode_access_token(token)
        if payload and payload.get("school_id"):
            school_id = payload.get("school_id")

    try:
        updated = update_ticket_status(db, ticket_id, data.status, school_id=school_id)
    except Exception as e:
        print(f"Database error in update_status: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database connection error. Please verify your Neon DATABASE_URL credentials."
        )

    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found or unauthorized")

    return {"message": "Ticket status updated"}
