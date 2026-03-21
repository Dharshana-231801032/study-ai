from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import decode_token
from app.services.auth_service import get_user_by_email
from app.services.question_service import (
    generate_questions_for_topic,
    generate_questions_for_document,
    get_questions_by_topic,
    get_questions_by_type
)
from app.services.topic_service import get_topic_by_id
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/questions", tags=["Questions"])
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


# ── Generate Questions for Single Topic ───────────────────
@router.post("/generate/topic/{topic_id}")
def generate_for_topic(
    topic_id: str,
    num_each: int = 3,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)

    result = generate_questions_for_topic(db, topic_id, num_each)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Generate Questions for ALL Topics in Document ─────────
@router.post("/generate/document/{syllabus_doc_id}")
def generate_for_document(
    syllabus_doc_id: str,
    num_each: int = 3,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)

    result = generate_questions_for_document(db, syllabus_doc_id, num_each)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Get All Questions for Topic ───────────────────────────
@router.get("/topic/{topic_id}")
def get_topic_questions(
    topic_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    questions = get_questions_by_topic(db, topic_id)
    return [
        {
            "id": str(q.id),
            "question_text": q.question_text,
            "answer_text": q.answer_text,
            "question_type": q.question_type,
            "difficulty": q.difficulty
        }
        for q in questions
    ]


# ── Get Questions by Type ─────────────────────────────────
@router.get("/topic/{topic_id}/type/{question_type}")
def get_questions_by_type_endpoint(
    topic_id: str,
    question_type: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    questions = get_questions_by_type(db, topic_id, question_type)
    return [
        {
            "id": str(q.id),
            "question_text": q.question_text,
            "answer_text": q.answer_text,
            "question_type": q.question_type,
            "difficulty": q.difficulty
        }
        for q in questions
    ]