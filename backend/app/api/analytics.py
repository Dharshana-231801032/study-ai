from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import decode_token
from app.services.auth_service import get_user_by_email
from app.services.analytics_service import (
    get_weak_areas,
    get_confidence_dashboard,
    get_performance_history
)
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/analytics", tags=["Analytics"])
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


# ── Weak Area Detection ───────────────────────────────────
@router.get("/weak-areas/{syllabus_doc_id}")
def weak_areas(
    syllabus_doc_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    areas = get_weak_areas(db, str(current_user.id), syllabus_doc_id)
    return {
        "total_units": len(areas),
        "weak_areas": areas
    }


# ── Confidence Dashboard ──────────────────────────────────
@router.get("/dashboard/{syllabus_doc_id}")
def confidence_dashboard(
    syllabus_doc_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    dashboard = get_confidence_dashboard(
        db, str(current_user.id), syllabus_doc_id
    )
    return dashboard


# ── Performance History ───────────────────────────────────
@router.get("/history")
def performance_history(
    days: int = 7,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    history = get_performance_history(
        db, str(current_user.id), days
    )
    return {
        "days": days,
        "history": history
    }