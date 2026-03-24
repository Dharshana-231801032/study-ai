from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import decode_token
from app.services.auth_service import get_user_by_email
from app.services.reminder_service import (
    get_due_reminders,
    get_study_streak,
    get_full_notification_panel
)
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/reminders", tags=["Smart Reminders"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    email = payload.get("sub")
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── Get Due Reminders ─────────────────────────────────────
@router.get("/due/{syllabus_doc_id}")
def due_reminders(
    syllabus_doc_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    result = get_due_reminders(db, str(current_user.id), syllabus_doc_id)
    return result


# ── Get Study Streak ──────────────────────────────────────
@router.get("/streak")
def study_streak(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    result = get_study_streak(db, str(current_user.id))
    return result


# ── Full Notification Panel ───────────────────────────────
@router.get("/panel/{syllabus_doc_id}")
def notification_panel(
    syllabus_doc_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    result = get_full_notification_panel(
        db, str(current_user.id), syllabus_doc_id
    )
    return result