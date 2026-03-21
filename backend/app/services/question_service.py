import uuid
from sqlalchemy.orm import Session
from app.models.models import Question, Topic
from app.ai.question_generator import generate_all_questions


def generate_questions_for_topic(
    db: Session,
    topic_id: str,
    num_each: int = 3
) -> dict:
    """
    Generate questions for a single topic using mapped content
    """
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        return {"error": "Topic not found"}

    if not topic.mapped_content:
        return {"error": "No content mapped to this topic yet. Upload notes first."}

    # Generate all question types
    questions = generate_all_questions(topic.mapped_content, num_each)

    if not questions:
        return {"error": "Could not generate questions from this content"}

    # Save to database
    saved_questions = []
    for q in questions:
        question = Question(
            id=uuid.uuid4(),
            topic_id=topic_id,
            question_text=q["question_text"],
            answer_text=q["answer_text"],
            question_type=q["question_type"],
            marks=q.get("marks", 1),
            difficulty=q["difficulty"]
        )
        db.add(question)
        saved_questions.append({
            "id": str(question.id),
            "question_text": q["question_text"],
            "answer_text": q["answer_text"],
            "question_type": q["question_type"],
            "difficulty": q["difficulty"]
        })

    db.commit()

    return {
        "status": "success",
        "topic": topic.unit_title,
        "questions_generated": len(saved_questions),
        "questions": saved_questions
    }


def generate_questions_for_document(
    db: Session,
    syllabus_doc_id: str,
    num_each: int = 3
) -> dict:
    """
    Generate questions for ALL topics in a syllabus document
    """
    topics = db.query(Topic).filter(
        Topic.document_id == syllabus_doc_id,
        Topic.mapped_content != None
    ).all()

    if not topics:
        return {"error": "No topics with content found. Map notes first."}

    all_results = []
    total_questions = 0

    for topic in topics:
        result = generate_questions_for_topic(db, str(topic.id), num_each)
        if "error" not in result:
            total_questions += result["questions_generated"]
            all_results.append({
                "unit_number": topic.unit_number,
                "unit_title": topic.unit_title,
                "questions_generated": result["questions_generated"]
            })

    return {
        "status": "success",
        "total_questions_generated": total_questions,
        "units_processed": len(all_results),
        "results": all_results
    }


def get_questions_by_topic(db: Session, topic_id: str) -> list:
    """Get all questions for a topic"""
    return db.query(Question).filter(
        Question.topic_id == topic_id
    ).all()


def get_questions_by_type(
    db: Session,
    topic_id: str,
    question_type: str
) -> list:
    """Get questions filtered by type"""
    return db.query(Question).filter(
        Question.topic_id == topic_id,
        Question.question_type == question_type
    ).all()