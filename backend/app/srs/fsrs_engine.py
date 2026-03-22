from fsrs import Scheduler, Card, Rating, State
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.models import ReviewSchedule, PerformanceLog, Question
import uuid

# Initialize FSRS scheduler
scheduler = Scheduler()


def rating_from_quality(quality: int) -> Rating:
    """
    Convert 1-4 quality rating to FSRS Rating
    1 = Again (forgot completely)
    2 = Hard (remembered with difficulty)
    3 = Good (remembered with hesitation)
    4 = Easy (remembered perfectly)
    """
    mapping = {
        1: Rating.Again,
        2: Rating.Hard,
        3: Rating.Good,
        4: Rating.Easy
    }
    return mapping.get(quality, Rating.Good)


def get_or_create_card(
    db: Session,
    user_id: str,
    question_id: str
) -> ReviewSchedule:
    """
    Get existing review schedule or create new one
    """
    schedule = db.query(ReviewSchedule).filter(
        ReviewSchedule.user_id == user_id,
        ReviewSchedule.question_id == question_id
    ).first()

    if not schedule:
        # Create new schedule
        schedule = ReviewSchedule(
            id=uuid.uuid4(),
            user_id=user_id,
            question_id=question_id,
            repetitions=0,
            easiness=2.5,
            interval_days=1,
            next_review_date=datetime.now(timezone.utc).date(),
            last_quality_rating=None
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)

    return schedule


def process_review(
    db: Session,
    user_id: str,
    question_id: str,
    quality: int
) -> dict:
    """
    Process a review rating and update FSRS schedule
    quality: 1=Again, 2=Hard, 3=Good, 4=Easy
    """
    # Get or create card
    schedule = get_or_create_card(db, user_id, question_id)

    # Create FSRS card from current state
    card = Card()
    card.due = datetime.combine(
        schedule.next_review_date,
        datetime.min.time()
    ).replace(tzinfo=timezone.utc) if schedule.next_review_date else datetime.now(timezone.utc)

    # Get FSRS rating
    rating = rating_from_quality(quality)

    # Process review
    card, review_log = scheduler.review_card(card, rating)

    # Get retrievability (probability of remembering)
    retrievability = scheduler.get_card_retrievability(card)

    # Update schedule in database
    schedule.repetitions = card.reps if hasattr(card, 'reps') else schedule.repetitions + 1
    schedule.interval_days = card.scheduled_days if hasattr(card, 'scheduled_days') else 1
    schedule.next_review_date = card.due.date() if card.due else None
    schedule.last_quality_rating = quality
    schedule.easiness = float(retrievability)

    # Log performance
    log = PerformanceLog(
        id=uuid.uuid4(),
        user_id=user_id,
        question_id=question_id,
        quality_rating=quality,
        reviewed_at=datetime.now(timezone.utc)
    )
    db.add(log)
    db.commit()

    return {
        "question_id": question_id,
        "quality": quality,
        "next_review_date": str(schedule.next_review_date),
        "interval_days": schedule.interval_days,
        "retrievability": round(float(retrievability) * 100, 1),
        "status": get_card_status(quality)
    }


def get_card_status(quality: int) -> str:
    """Get human readable status"""
    if quality == 1:
        return "Again — Review tomorrow"
    elif quality == 2:
        return "Hard — Review in 2-3 days"
    elif quality == 3:
        return "Good — Review scheduled"
    else:
        return "Easy — Long interval set"


def get_due_cards(
    db: Session,
    user_id: str,
    syllabus_doc_id: str
) -> list:
    """
    Get all questions due for review today
    """
    from datetime import date
    from app.models.models import Topic

    today = date.today()

    # Get all topics for this syllabus
    topics = db.query(Topic).filter(
        Topic.document_id == syllabus_doc_id
    ).all()
    topic_ids = [t.id for t in topics]

    # Get all questions for these topics
    questions = db.query(Question).filter(
        Question.topic_id.in_(topic_ids)
    ).all()
    question_ids = [q.id for q in questions]

    # Get due review schedules
    due_schedules = db.query(ReviewSchedule).filter(
        ReviewSchedule.user_id == user_id,
        ReviewSchedule.question_id.in_(question_ids),
        ReviewSchedule.next_review_date <= today
    ).all()

    # Get questions with no schedule (never reviewed)
    scheduled_ids = [s.question_id for s in due_schedules]
    unscheduled = [
        q for q in questions
        if q.id not in scheduled_ids
    ]

    # Build due cards list
    due_cards = []

    # Add overdue/due cards
    for schedule in due_schedules:
        question = next(
            (q for q in questions if q.id == schedule.question_id),
            None
        )
        if question:
            due_cards.append({
                "question_id": str(question.id),
                "question_text": question.question_text,
                "answer_text": question.answer_text,
                "question_type": question.question_type,
                "marks": question.marks,
                "difficulty": question.difficulty,
                "next_review_date": str(schedule.next_review_date),
                "interval_days": schedule.interval_days,
                "retrievability": round(schedule.easiness * 100, 1),
                "is_new": False
            })

    # Add new unreviewed cards (max 20 new per session)
    for question in unscheduled[:20]:
        due_cards.append({
            "question_id": str(question.id),
            "question_text": question.question_text,
            "answer_text": question.answer_text,
            "question_type": question.question_type,
            "marks": question.marks,
            "difficulty": question.difficulty,
            "next_review_date": str(today),
            "interval_days": 0,
            "retrievability": 100.0,
            "is_new": True
        })

    return due_cards


def get_overdue_cards(
    db: Session,
    user_id: str,
    syllabus_doc_id: str
) -> list:
    """
    Get cards sorted by most forgotten (lowest retrievability)
    for Rapid Recall mode
    """
    all_due = get_due_cards(db, user_id, syllabus_doc_id)

    # Sort by retrievability (lowest first = most forgotten)
    overdue = sorted(
        [c for c in all_due if not c['is_new']],
        key=lambda x: x['retrievability']
    )

    return overdue


def get_user_stats(
    db: Session,
    user_id: str,
    syllabus_doc_id: str
) -> dict:
    """
    Get overall study statistics for dashboard
    """
    from app.models.models import Topic
    from datetime import date

    today = date.today()

    # Get all topics
    topics = db.query(Topic).filter(
        Topic.document_id == syllabus_doc_id
    ).all()
    topic_ids = [t.id for t in topics]

    # Get all questions
    total_questions = db.query(Question).filter(
        Question.topic_id.in_(topic_ids)
    ).count()

    # Get review schedules
    schedules = db.query(ReviewSchedule).filter(
        ReviewSchedule.user_id == user_id
    ).all()

    reviewed = len(schedules)
    due_today = len([
        s for s in schedules
        if s.next_review_date and s.next_review_date <= today
    ])

    # Calculate average confidence
    if schedules:
        avg_confidence = sum(
            s.easiness for s in schedules
        ) / len(schedules) * 100
    else:
        avg_confidence = 0

    # Get performance logs for streak
    logs = db.query(PerformanceLog).filter(
        PerformanceLog.user_id == user_id
    ).order_by(PerformanceLog.reviewed_at.desc()).all()

    # Calculate topic confidence scores
    topic_stats = []
    for topic in topics:
        topic_questions = db.query(Question).filter(
            Question.topic_id == topic.id
        ).all()
        topic_q_ids = [q.id for q in topic_questions]

        topic_schedules = [
            s for s in schedules
            if s.question_id in topic_q_ids
        ]

        if topic_schedules:
            topic_confidence = sum(
                s.easiness for s in topic_schedules
            ) / len(topic_schedules) * 100
        else:
            topic_confidence = 0

        topic_stats.append({
            "unit_number": topic.unit_number,
            "unit_title": topic.unit_title,
            "total_questions": len(topic_questions),
            "reviewed": len(topic_schedules),
            "confidence": round(topic_confidence, 1)
        })

    return {
        "total_questions": total_questions,
        "reviewed": reviewed,
        "pending": total_questions - reviewed,
        "due_today": due_today,
        "avg_confidence": round(avg_confidence, 1),
        "total_reviews": len(logs),
        "topic_stats": topic_stats
    }