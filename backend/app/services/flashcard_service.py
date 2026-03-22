import uuid
from sqlalchemy.orm import Session
from app.models.models import Topic, Document
from app.ai.flashcard_generator import (
    generate_flashcards_from_keywords,
    generate_topic_summary
)


def generate_flashcards_for_topic(
    db: Session,
    topic_id: str,
    num_cards: int = 10
) -> dict:
    """
    Generate flashcards for a topic using its keywords and mapped content
    """
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        return {"error": "Topic not found"}

    if not topic.mapped_content:
        return {"error": "No content mapped to this topic. Upload notes first."}

    if not topic.keywords:
        return {"error": "No keywords found for this topic."}

    # Generate flashcards
    flashcards = generate_flashcards_from_keywords(
        keywords=topic.keywords,
        mapped_content=topic.mapped_content,
        num_cards=num_cards
    )

    # Generate topic summary
    summary = generate_topic_summary(topic.mapped_content)

    # Save summary to topic
    topic.summary = summary
    db.commit()

    return {
        "status": "success",
        "topic": topic.unit_title,
        "unit_number": topic.unit_number,
        "summary": summary,
        "flashcards_generated": len(flashcards),
        "flashcards": flashcards
    }


def generate_flashcards_for_document(
    db: Session,
    syllabus_doc_id: str,
    num_cards: int = 10
) -> dict:
    """
    Generate flashcards for ALL topics in a document
    """
    topics = db.query(Topic).filter(
        Topic.document_id == syllabus_doc_id,
        Topic.mapped_content != None
    ).all()

    if not topics:
        return {"error": "No topics with content found."}

    all_results = []
    total_flashcards = 0

    for topic in topics:
        result = generate_flashcards_for_topic(
            db, str(topic.id), num_cards
        )
        if "error" not in result:
            total_flashcards += result["flashcards_generated"]
            all_results.append({
                "unit_number": topic.unit_number,
                "unit_title": topic.unit_title,
                "summary": result["summary"],
                "flashcards_generated": result["flashcards_generated"],
                "flashcards": result["flashcards"]
            })

    return {
        "status": "success",
        "total_flashcards": total_flashcards,
        "units_processed": len(all_results),
        "results": all_results
    }