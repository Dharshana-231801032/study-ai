import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import decode_token
from app.services.auth_service import get_user_by_email
from app.services.document_service import save_document, process_document, get_user_documents
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/documents", tags=["Documents"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    email = payload.get("sub")
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── Upload PDF ────────────────────────────────────────────
@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    subject: str = Form(None),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    # Verify user
    current_user = get_current_user(token, db)

    # Accept all supported formats
    allowed_extensions = [
        '.pdf', '.docx', '.doc',
        '.png', '.jpg', '.jpeg'
    ]
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Allowed: {', '.join(allowed_extensions)}"
        )

    # Validate file size (max 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File size exceeds 10MB limit"
        )

    # Save file to uploads folder
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    # Save to database
    doc = save_document(
        db=db,
        user_id=current_user.id,
        filename=unique_filename,
        original_filename=file.filename,
        subject=subject
    )

    # Process PDF immediately
    result = process_document(db, str(doc.id))

    return {
        "message": "PDF uploaded and processed successfully ✅",
        "document_id": str(doc.id),
        "filename": file.filename,
        "total_pages": result.get("total_pages"),
        "total_chars": result.get("total_chars"),
        "status": "processed"
    }


# ── Get All Documents ─────────────────────────────────────
@router.get("/")
def get_documents(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    docs = get_user_documents(db, current_user.id)
    return [
        {
            "id": str(doc.id),
            "filename": doc.original_filename,
            "subject": doc.subject,
            "processed": doc.processed,
            "upload_date": doc.upload_date
        }
        for doc in docs
    ]


# ── Get Single Document ───────────────────────────────────
@router.get("/{document_id}")
def get_document(
    document_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    from app.services.document_service import get_document_by_id
    doc = get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if str(doc.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    return {
        "id": str(doc.id),
        "filename": doc.original_filename,
        "subject": doc.subject,
        "processed": doc.processed,
        "upload_date": doc.upload_date
    }