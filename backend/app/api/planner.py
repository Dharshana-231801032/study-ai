from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.database import get_db
from app.core.security import decode_token
from app.services.auth_service import get_user_by_email
from app.services.planner_service import (
    generate_study_plan,
    get_todays_plan
)
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/planner", tags=["Study Planner"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class PlanRequest(BaseModel):
    syllabus_doc_id: str
    exam_date: str  # Format: YYYY-MM-DD
    daily_hours: int = 3


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


# ── Generate Full Study Plan ──────────────────────────────
@router.post("/generate")
def generate_plan(
    request: PlanRequest,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)

    result = generate_study_plan(
        db=db,
        user_id=str(current_user.id),
        syllabus_doc_id=request.syllabus_doc_id,
        exam_date=request.exam_date,
        daily_hours=request.daily_hours
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ── Get Today's Plan ──────────────────────────────────────
@router.get("/today/{syllabus_doc_id}")
def todays_plan(
    syllabus_doc_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)

    result = get_todays_plan(
        db=db,
        user_id=str(current_user.id),
        syllabus_doc_id=syllabus_doc_id
    )

    return result