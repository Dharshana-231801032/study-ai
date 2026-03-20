import uuid
from sqlalchemy.orm import Session
from app.models.models import Topic, Document
from app.nlp.syllabus_extractor import extract_units_from_syllabus, map_content_to_units
from app.nlp.keyword_extractor import extract_keywords
from app.nlp.extractor import extract_text, extract_text_from_pdf, clean_text
import os

UPLOAD_DIR = "uploads"


def process_syllabus(db: Session, document_id: str) -> dict:
    """Extract units from digital syllabus PDF and save as topics"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        return {"error": "Document not found"}

    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if not os.path.exists(file_path):
        return {"error": "File not found"}

    extraction = extract_text(file_path)

    if extraction.get("is_scanned"):
        return {"error": "This is a scanned PDF. Please use manual unit input instead via POST /topics/manual"}

    if extraction.get("total_chars", 0) < 100:
        return {"error": "Could not extract text. Please use manual unit input instead."}

    cleaned = clean_text(extraction["full_text"])
    units = extract_units_from_syllabus(cleaned)

    if not units:
        return {"error": "No units found in syllabus. Make sure it has UNIT-I, UNIT-II format or use manual input."}

    topics_created = []
    for unit in units:
        topic = Topic(
            id=uuid.uuid4(),
            document_id=document_id,
            unit_number=unit['unit_number'],
            unit_title=unit['unit_title'],
            sub_topics='\n'.join(unit['sub_topics']),
            keywords=None,
            mapped_content=None,
            is_syllabus=True,
            confidence_score=0.0
        )
        db.add(topic)
        topics_created.append({
            "unit_number": unit['unit_number'],
            "unit_title": unit['unit_title'],
            "sub_topics": unit['sub_topics'][:5]
        })

    db.commit()

    return {
        "status": "success",
        "units_extracted": len(topics_created),
        "topics": topics_created
    }


def create_manual_units(
    db: Session,
    user_id: str,
    subject: str,
    units: list
) -> dict:
    """Create topics from manually entered unit names"""
    import uuid as uuid_lib

    doc = Document(
        id=uuid_lib.uuid4(),
        user_id=user_id,
        filename=f"manual_syllabus_{subject}.txt",
        original_filename=f"Manual Syllabus - {subject}",
        subject=subject,
        doc_type="syllabus",
        processed=True
    )
    db.add(doc)
    db.flush()

    topics_created = []
    for unit in units:
        topic = Topic(
            id=uuid_lib.uuid4(),
            document_id=doc.id,
            unit_number=unit.unit_number,
            unit_title=unit.unit_title,
            sub_topics='\n'.join(unit.sub_topics) if unit.sub_topics else '',
            keywords=None,
            mapped_content=None,
            is_syllabus=True,
            confidence_score=0.0
        )
        db.add(topic)
        topics_created.append({
            "unit_number": unit.unit_number,
            "unit_title": unit.unit_title,
            "sub_topics": unit.sub_topics
        })

    db.commit()

    return {
        "status": "success",
        "syllabus_document_id": str(doc.id),
        "subject": subject,
        "units_created": len(topics_created),
        "topics": topics_created
    }


def map_notes_to_syllabus(
    db: Session,
    syllabus_doc_id: str,
    notes_doc_id: str
) -> dict:
    """Map notes content to syllabus units"""
    syllabus_topics = db.query(Topic).filter(
        Topic.document_id == syllabus_doc_id,
        Topic.is_syllabus == True
    ).all()

    if not syllabus_topics:
        return {"error": "No syllabus topics found. Upload syllabus first"}

    notes_doc = db.query(Document).filter(
        Document.id == notes_doc_id
    ).first()
    if not notes_doc:
        return {"error": "Notes document not found"}

    file_path = os.path.join(UPLOAD_DIR, notes_doc.filename)
    extraction = extract_text(file_path)
    cleaned_notes = clean_text(extraction["full_text"])

    units = [
        {
            "unit_number": t.unit_number,
            "unit_title": t.unit_title,
            "sub_topics": t.sub_topics.split('\n') if t.sub_topics else [],
            "topic_id": str(t.id)
        }
        for t in syllabus_topics
    ]

    mapped_units = map_content_to_units(units, cleaned_notes)

    updated = []
    for unit in mapped_units:
        topic = db.query(Topic).filter(
            Topic.id == unit['topic_id']
        ).first()

        if topic and unit.get('mapped_content'):
            keywords = extract_keywords(unit['mapped_content'], top_n=10)
            topic.mapped_content = unit['mapped_content']
            topic.keywords = ', '.join(keywords)
            topic.confidence_score = 0.5
            updated.append({
                "unit_number": unit['unit_number'],
                "unit_title": unit['unit_title'],
                "keywords": keywords[:5],
                "content_length": len(unit['mapped_content'])
            })

    db.commit()

    return {
        "status": "success",
        "units_mapped": len(updated),
        "mapping": updated
    }


def map_notes_to_manual_units(
    db: Session,
    user_id: str,
    notes_doc_id: str,
    subject: str
) -> dict:
    """Map notes to manually created units for a subject"""
    manual_doc = db.query(Document).filter(
        Document.user_id == user_id,
        Document.subject == subject,
        Document.doc_type == "syllabus"
    ).first()

    if not manual_doc:
        return {"error": f"No syllabus found for subject '{subject}'. Create manual units first."}

    return map_notes_to_syllabus(db, str(manual_doc.id), notes_doc_id)


def get_topics_by_document(db: Session, document_id: str) -> list:
    """Get all topics for a document"""
    return db.query(Topic).filter(
        Topic.document_id == document_id
    ).all()


def get_topic_by_id(db: Session, topic_id: str) -> Topic:
    """Get single topic by ID"""
    return db.query(Topic).filter(
        Topic.id == topic_id
    ).first()