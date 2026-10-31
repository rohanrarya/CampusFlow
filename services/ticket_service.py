from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from models.ticket import Ticket

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.now(IST).replace(tzinfo=None)

def ticket_to_dict(ticket: Ticket) -> dict:
    if not ticket:
        return None
    return {
        "id": ticket.id,
        "ticket_id": ticket.ticket_id,
        "created_at": (ticket.created_at.isoformat() + "+05:30") if ticket.created_at else None,
        "resolved_at": (ticket.resolved_at.isoformat() + "+05:30") if ticket.resolved_at else None,
        "status": ticket.status,
        "department": ticket.department,
        "category": ticket.category,
        "location": ticket.location,
        "problem": ticket.problem,
        "urgency": ticket.urgency,
        "image_url": ticket.image_url,
        "submitted_by": "Anonymous Student" if getattr(ticket, "is_anonymous", False) else getattr(ticket, "submitted_by", None),
        "user_college_id": getattr(ticket, "user_college_id", None),
        "school_id": getattr(ticket, "school_id", 1) or 1,
        "is_anonymous": bool(getattr(ticket, "is_anonymous", False)),
        "rating": getattr(ticket, "rating", None),
        "feedback": getattr(ticket, "feedback", None)
    }

def create_ticket(
    session: Session,
    analysis,
    department: str,
    image_url: str = None,
    submission_id: str = None,
    submitted_by: str = None,
    user_college_id: str = None,
    school_id: int = 1,
    is_anonymous: bool = False
) -> dict:
    display_submitter = "Anonymous Student" if is_anonymous else submitted_by
    db_ticket = Ticket(
        status="Pending",
        department=department,
        category=analysis.category,
        location=analysis.location,
        problem=analysis.problem,
        urgency=analysis.urgency,
        image_url=image_url,
        submission_id=submission_id,
        submitted_by=display_submitter,
        user_college_id=user_college_id,
        school_id=school_id or 1,
        is_anonymous=is_anonymous
    )

    try:
        session.add(db_ticket)
        session.flush()
        ticket_id = f"TKT-{db_ticket.id:03d}"
        db_ticket.ticket_id = ticket_id
        session.commit()
        session.refresh(db_ticket)
        return ticket_to_dict(db_ticket)
    except Exception:
        session.rollback()
        raise

def get_ticket_by_submission_id(session: Session, submission_id: str):
    statement = select(Ticket).where(Ticket.submission_id == submission_id)
    ticket = session.scalars(statement).first()
    return ticket_to_dict(ticket) if ticket else None

def get_ticket(session: Session, ticket_id: str, school_id: int | None = None):
    statement = select(Ticket).where(Ticket.ticket_id == ticket_id)
    if school_id:
        statement = statement.where(Ticket.school_id == school_id)
    ticket = session.scalars(statement).first()
    return ticket_to_dict(ticket) if ticket else None

def get_all_tickets(session: Session, school_id: int | None = None):
    statement = select(Ticket).order_by(Ticket.id.desc())
    if school_id:
        statement = statement.where(Ticket.school_id == school_id)
    tickets = session.scalars(statement).all()
    return [ticket_to_dict(t) for t in tickets]

def update_ticket_status(session: Session, ticket_id: str, new_status: str, school_id: int | None = None) -> bool:
    statement = select(Ticket).where(Ticket.ticket_id == ticket_id)
    if school_id:
        statement = statement.where(Ticket.school_id == school_id)
    ticket = session.scalars(statement).first()
    if not ticket:
        return False
    ticket.status = new_status
    if new_status.lower() in ["resolved", "closed"]:
        if not ticket.resolved_at:
            ticket.resolved_at = get_ist_now()
    else:
        ticket.resolved_at = None
    session.commit()
    return True

def record_ticket_feedback(session: Session, ticket_id: str, rating: int, feedback: str = None) -> bool:
    statement = select(Ticket).where(Ticket.ticket_id == ticket_id)
    ticket = session.scalars(statement).first()
    if not ticket:
        return False
    ticket.rating = max(1, min(5, int(rating)))
    if feedback:
        ticket.feedback = feedback.strip()
    session.commit()
    return True
