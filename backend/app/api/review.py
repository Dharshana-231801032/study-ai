from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.database import get_db
from app.core.security import decode_token
from app.services.auth_service import get_user_by_email
from app.srs.fsrs_engine import (
    process_review,
    get_due_cards,
    get_overdue_cards,
    get_user_stats
)
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/review", tags=["Spaced Repetition"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class ReviewInput(BaseModel):
    question_id: str
    quality: int  # 1=Again, 2=Hard, 3=Good, 4=Easy


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


# ── Submit Review Rating ───────────────────────────────────
@router.post("/submit")
def submit_review(
    review: ReviewInput,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)

    if review.quality not in [1, 2, 3, 4]:
        raise HTTPException(
            status_code=400,
            detail="Quality must be 1 (Again), 2 (Hard), 3 (Good), or 4 (Easy)"
        )

    result = process_review(
        db=db,
        user_id=str(current_user.id),
        question_id=review.question_id,
        quality=review.quality
    )
    return result


# ── Get Due Cards for Today ───────────────────────────────
@router.get("/due/{syllabus_doc_id}")
def get_due(
    syllabus_doc_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    cards = get_due_cards(db, str(current_user.id), syllabus_doc_id)
    return {
        "total_due": len(cards),
        "cards": cards
    }


# ── Get Rapid Recall Cards ────────────────────────────────
@router.get("/rapid/{syllabus_doc_id}")
def get_rapid_recall(
    syllabus_doc_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    cards = get_overdue_cards(db, str(current_user.id), syllabus_doc_id)
    return {
        "total_overdue": len(cards),
        "cards": cards[:20]  # Max 20 for rapid recall
    }


# ── Get Dashboard Stats ───────────────────────────────────
@router.get("/stats/{syllabus_doc_id}")
def get_stats(
    syllabus_doc_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    stats = get_user_stats(db, str(current_user.id), syllabus_doc_id)
    return stats