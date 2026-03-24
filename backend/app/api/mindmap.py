from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import decode_token
from app.services.auth_service import get_user_by_email
from app.services.mindmap_service import (
    generate_mindmap,
    get_topic_mindmap
)
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/mindmap", tags=["Mind Map"])
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


# ── Full Syllabus Mind Map ────────────────────────────────
@router.get("/document/{syllabus_doc_id}")
def document_mindmap(
    syllabus_doc_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    result = generate_mindmap(db, syllabus_doc_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Single Topic Mind Map ─────────────────────────────────
@router.get("/topic/{topic_id}")
def topic_mindmap(
    topic_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    result = get_topic_mindmap(db, topic_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result