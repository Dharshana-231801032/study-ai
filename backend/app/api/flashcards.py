from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import decode_token
from app.services.auth_service import get_user_by_email
from app.services.flashcard_service import (
    generate_flashcards_for_topic,
    generate_flashcards_for_document
)
from app.services.topic_service import get_topic_by_id
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])
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


# ── Generate Flashcards for Single Topic ──────────────────
@router.post("/generate/topic/{topic_id}")
def generate_topic_flashcards(
    topic_id: str,
    num_cards: int = 10,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)

    result = generate_flashcards_for_topic(db, topic_id, num_cards)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Generate Flashcards for ALL Topics ───────────────────
@router.post("/generate/document/{syllabus_doc_id}")
def generate_document_flashcards(
    syllabus_doc_id: str,
    num_cards: int = 10,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)

    result = generate_flashcards_for_document(db, syllabus_doc_id, num_cards)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Get Topic Summary ─────────────────────────────────────
@router.get("/summary/{topic_id}")
def get_topic_summary(
    topic_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)

    topic = get_topic_by_id(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    return {
        "topic_id": topic_id,
        "unit_number": topic.unit_number,
        "unit_title": topic.unit_title,
        "summary": topic.summary,
        "keywords": topic.keywords
    }