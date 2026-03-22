from sqlalchemy.orm import Session
from app.models.models import Topic, Question, ReviewSchedule, PerformanceLog
from datetime import datetime, timezone, date, timedelta


def get_weak_areas(db: Session, user_id: str, syllabus_doc_id: str) -> list:
    """
    Detect weak areas based on FSRS review performance
    Weak = confidence < 60%
    """
    topics = db.query(Topic).filter(
        Topic.document_id == syllabus_doc_id
    ).all()

    weak_areas = []

    for topic in topics:
        questions = db.query(Question).filter(
            Question.topic_id == topic.id
        ).all()

        if not questions:
            continue

        q_ids = [q.id for q in questions]

        schedules = db.query(ReviewSchedule).filter(
            ReviewSchedule.user_id == user_id,
            ReviewSchedule.question_id.in_(q_ids)
        ).all()

        if not schedules:
            # Never reviewed = weak area
            weak_areas.append({
                "unit_number": topic.unit_number,
                "unit_title": topic.unit_title,
                "confidence": 0.0,
                "total_questions": len(questions),
                "reviewed": 0,
                "status": "🔴 Not Started",
                "priority": 1
            })
            continue

        # Calculate confidence from ratings
        logs = db.query(PerformanceLog).filter(
            PerformanceLog.user_id == user_id,
            PerformanceLog.question_id.in_(q_ids)
        ).all()

        if logs:
            avg_quality = sum(l.quality_rating for l in logs) / len(logs)
            confidence = (avg_quality / 4.0) * 100
        else:
            confidence = 0.0

        if confidence < 40:
            status = "🔴 Urgent Review Needed"
            priority = 1
        elif confidence < 60:
            status = "🟡 Needs Improvement"
            priority = 2
        elif confidence < 80:
            status = "🟢 Good Progress"
            priority = 3
        else:
            status = "⭐ Excellent"
            priority = 4

        weak_areas.append({
            "unit_number": topic.unit_number,
            "unit_title": topic.unit_title,
            "confidence": round(confidence, 1),
            "total_questions": len(questions),
            "reviewed": len(schedules),
            "status": status,
            "priority": priority
        })

    # Sort by priority (weakest first)
    weak_areas.sort(key=lambda x: x['priority'])

    return weak_areas


def get_confidence_dashboard(
    db: Session,
    user_id: str,
    syllabus_doc_id: str
) -> dict:
    """
    Full confidence dashboard with all metrics
    """
    topics = db.query(Topic).filter(
        Topic.document_id == syllabus_doc_id
    ).all()

    total_questions = 0
    total_reviewed = 0
    total_confidence = 0
    topic_confidences = []

    for topic in topics:
        questions = db.query(Question).filter(
            Question.topic_id == topic.id
        ).all()

        q_ids = [q.id for q in questions]
        total_questions += len(questions)

        schedules = db.query(ReviewSchedule).filter(
            ReviewSchedule.user_id == user_id,
            ReviewSchedule.question_id.in_(q_ids)
        ).all()

        total_reviewed += len(schedules)

        logs = db.query(PerformanceLog).filter(
            PerformanceLog.user_id == user_id,
            PerformanceLog.question_id.in_(q_ids)
        ).all()

        if logs:
            avg_quality = sum(l.quality_rating for l in logs) / len(logs)
            confidence = (avg_quality / 4.0) * 100
        else:
            confidence = 0.0

        total_confidence += confidence

        topic_confidences.append({
            "unit_number": topic.unit_number,
            "unit_title": topic.unit_title,
            "confidence": round(confidence, 1),
            "total_questions": len(questions),
            "reviewed": len(schedules),
            "pending": len(questions) - len(schedules)
        })

    # Overall confidence
    overall = total_confidence / max(len(topics), 1)

    # Readiness level
    if overall >= 80:
        readiness = "🎯 Exam Ready!"
        readiness_color = "green"
    elif overall >= 60:
        readiness = "📈 Good Progress"
        readiness_color = "blue"
    elif overall >= 40:
        readiness = "📚 Keep Studying"
        readiness_color = "yellow"
    else:
        readiness = "🚀 Just Getting Started"
        readiness_color = "red"

    # Progress percentage
    progress = (total_reviewed / max(total_questions, 1)) * 100

    return {
        "overall_confidence": round(overall, 1),
        "readiness": readiness,
        "readiness_color": readiness_color,
        "progress_percentage": round(progress, 1),
        "total_questions": total_questions,
        "total_reviewed": total_reviewed,
        "pending": total_questions - total_reviewed,
        "topic_confidences": topic_confidences
    }


def get_performance_history(
    db: Session,
    user_id: str,
    days: int = 7
) -> list:
    """
    Get review history for the last N days
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    logs = db.query(PerformanceLog).filter(
        PerformanceLog.user_id == user_id,
        PerformanceLog.reviewed_at >= since
    ).order_by(PerformanceLog.reviewed_at.asc()).all()

    # Group by date
    daily = {}
    for log in logs:
        day = log.reviewed_at.date().isoformat()
        if day not in daily:
            daily[day] = {
                "date": day,
                "reviews": 0,
                "avg_quality": 0,
                "total_quality": 0
            }
        daily[day]["reviews"] += 1
        daily[day]["total_quality"] += log.quality_rating

    # Calculate averages
    history = []
    for day, data in daily.items():
        data["avg_quality"] = round(
            data["total_quality"] / data["reviews"], 1
        )
        del data["total_quality"]
        history.append(data)

    return history