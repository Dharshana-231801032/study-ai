from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.db.database import get_db
from app.core.security import decode_token
from app.services.auth_service import get_user_by_email
from app.services.document_service import get_document_by_id
from app.services.topic_service import (
    process_syllabus,
    map_notes_to_syllabus,
    get_topics_by_document,
    get_topic_by_id,
    create_manual_units,
    map_notes_to_manual_units
)
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/topics", tags=["Topics"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Schemas ───────────────────────────────────────────────
class UnitInput(BaseModel):
    unit_number: str
    unit_title: str
    sub_topics: Optional[List[str]] = []

class ManualSyllabusInput(BaseModel):
    subject: str
    units: List[UnitInput]


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


# ── METHOD 1: Process Digital Syllabus PDF/DOCX ───────────
@router.post("/syllabus/{document_id}")
def extract_syllabus_topics(
    document_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    doc = get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if str(doc.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = process_syllabus(db, document_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── METHOD 2: Manual Unit Input ───────────────────────────
@router.post("/manual")
def create_units_manually(
    data: ManualSyllabusInput,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    result = create_manual_units(
        db=db,
        user_id=str(current_user.id),
        subject=data.subject,
        units=data.units
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Map Notes to Syllabus (PDF syllabus) ──────────────────
@router.post("/map")
def map_notes(
    syllabus_doc_id: str,
    notes_doc_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    syllabus_doc = get_document_by_id(db, syllabus_doc_id)
    notes_doc = get_document_by_id(db, notes_doc_id)

    if not syllabus_doc or not notes_doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if str(syllabus_doc.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = map_notes_to_syllabus(db, syllabus_doc_id, notes_doc_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Map Notes to Manual Units ─────────────────────────────
@router.post("/map-manual")
def map_notes_to_manual(
    notes_doc_id: str,
    user_subject: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    notes_doc = get_document_by_id(db, notes_doc_id)
    if not notes_doc:
        raise HTTPException(status_code=404, detail="Notes document not found")
    if str(notes_doc.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = map_notes_to_manual_units(
        db=db,
        user_id=str(current_user.id),
        notes_doc_id=notes_doc_id,
        subject=user_subject
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Get All Topics for Document ───────────────────────────
@router.get("/{document_id}")
def get_topics(
    document_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    doc = get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if str(doc.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    topics = get_topics_by_document(db, document_id)
    return [
        {
            "id": str(topic.id),
            "unit_number": topic.unit_number,
            "unit_title": topic.unit_title,
            "sub_topics": topic.sub_topics,
            "keywords": topic.keywords,
            "mapped_content_length": len(topic.mapped_content) if topic.mapped_content else 0,
            "confidence_score": topic.confidence_score,
            "is_syllabus": topic.is_syllabus
        }
        for topic in topics
    ]


# ── Get Single Topic ──────────────────────────────────────
@router.get("/topic/{topic_id}")
def get_single_topic(
    topic_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    topic = get_topic_by_id(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    return {
        "id": str(topic.id),
        "unit_number": topic.unit_number,
        "unit_title": topic.unit_title,
        "sub_topics": topic.sub_topics,
        "keywords": topic.keywords,
        "mapped_content": topic.mapped_content,
        "confidence_score": topic.confidence_score,
        "is_syllabus": topic.is_syllabus
    }