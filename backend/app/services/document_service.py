import os
import uuid
from sqlalchemy.orm import Session
from app.models.models import Document
from app.nlp.extractor import extract_text_from_pdf, clean_text

UPLOAD_DIR = "uploads"

def save_document(
    db: Session,
    user_id: str,
    filename: str,
    original_filename: str,
    subject: str = None
) -> Document:
    """Save document record to database"""
    doc = Document(
        id=uuid.uuid4(),
        user_id=user_id,
        filename=filename,
        original_filename=original_filename,
        subject=subject,
        processed=False
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def process_document(db: Session, document_id: str) -> dict:
    """Extract and clean text from uploaded PDF"""
    doc = db.query(Document).filter(
        Document.id == document_id
    ).first()

    if not doc:
        return {"error": "Document not found"}

    pdf_path = os.path.join(UPLOAD_DIR, doc.filename)

    if not os.path.exists(pdf_path):
        return {"error": "PDF file not found"}

    # Extract text using PyMuPDF
    extraction = extract_text_from_pdf(pdf_path)
    cleaned = clean_text(extraction["full_text"])

    # Mark as processed
    doc.processed = True
    db.commit()

    return {
        "document_id": str(doc.id),
        "filename": doc.original_filename,
        "total_pages": extraction["total_pages"],
        "total_chars": extraction["total_chars"],
        "cleaned_text": cleaned,
        "status": "processed"
    }


def get_user_documents(db: Session, user_id: str) -> list:
    """Get all documents for a user"""
    return db.query(Document).filter(
        Document.user_id == user_id
    ).all()


def get_document_by_id(db: Session, document_id: str) -> Document:
    """Get single document by ID"""
    return db.query(Document).filter(
        Document.id == document_id
    ).first()