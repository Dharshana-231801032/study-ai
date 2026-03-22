from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models.models import Topic, Question, ReviewSchedule, PerformanceLog
import heapq


def generate_study_plan(
    db: Session,
    user_id: str,
    syllabus_doc_id: str,
    exam_date: str,
    daily_hours: int = 3
) -> dict:
    """
    Generate AI study plan based on:
    - Exam date
    - Weak areas
    - FSRS due dates
    - Daily available hours
    """
    exam = date.fromisoformat(exam_date)
    today = date.today()
    days_left = (exam - today).days

    if days_left <= 0:
        return {"error": "Exam date must be in the future"}

    # Get all topics
    topics = db.query(Topic).filter(
        Topic.document_id == syllabus_doc_id
    ).all()

    # Calculate priority score for each topic
    priority_queue = []

    for topic in topics:
        questions = db.query(Question).filter(
            Question.topic_id == topic.id
        ).all()

        q_ids = [q.id for q in questions]

        # Get review logs for confidence
        logs = db.query(PerformanceLog).filter(
            PerformanceLog.user_id == user_id,
            PerformanceLog.question_id.in_(q_ids)
        ).all()

        if logs:
            avg_quality = sum(l.quality_rating for l in logs) / len(logs)
            confidence = (avg_quality / 4.0) * 100
        else:
            confidence = 0.0

        # Priority = inverse of confidence
        # Lower confidence = higher priority
        priority = 100 - confidence

        # Boost priority for topics with many questions
        priority += len(questions) * 0.1

        heapq.heappush(
            priority_queue,
            (-priority, topic.unit_number, topic.unit_title, confidence, len(questions))
        )

    # Build day-by-day plan
    plan = {}
    current_day = today
    topics_list = []

    while priority_queue:
        neg_priority, unit_num, unit_title, confidence, num_questions = heapq.heappop(priority_queue)
        topics_list.append({
            "unit_number": unit_num,
            "unit_title": unit_title,
            "confidence": confidence,
            "num_questions": num_questions,
            "priority": -neg_priority
        })

    # Distribute topics across days
    # Each topic gets multiple revision slots based on confidence
    schedule = []
    day_index = 0

    for topic in topics_list:
        # Low confidence topics get more days
        if topic['confidence'] < 30:
            revision_days = 3
        elif topic['confidence'] < 60:
            revision_days = 2
        else:
            revision_days = 1

        for rev in range(revision_days):
            if day_index >= days_left:
                break

            plan_date = today + timedelta(days=day_index)
            day_label = plan_date.strftime("%A, %d %b %Y")

            # Determine activity based on revision number
            if rev == 0:
                activity = f"📖 Study {topic['unit_title']}"
                action = "First study"
            elif rev == 1:
                activity = f"🔄 Revise {topic['unit_title']}"
                action = "Revision"
            else:
                activity = f"✅ Final Review {topic['unit_title']}"
                action = "Final review"

            schedule.append({
                "date": str(plan_date),
                "day_label": day_label,
                "unit_number": topic['unit_number'],
                "unit_title": topic['unit_title'],
                "activity": activity,
                "action": action,
                "confidence": topic['confidence'],
                "estimated_hours": min(daily_hours, 2)
            })

            day_index += 1

    # Add exam day
    exam_label = exam.strftime("%A, %d %b %Y")
    schedule.append({
        "date": str(exam),
        "day_label": exam_label,
        "unit_number": "ALL",
        "unit_title": "All Units",
        "activity": "🎯 EXAM DAY — Best of luck!",
        "action": "Exam",
        "confidence": 0,
        "estimated_hours": 0
    })

    # Summary stats
    weak_units = [t for t in topics_list if t['confidence'] < 60]
    strong_units = [t for t in topics_list if t['confidence'] >= 60]

    return {
        "status": "success",
        "exam_date": exam_date,
        "days_left": days_left,
        "total_study_days": len(schedule) - 1,
        "daily_hours": daily_hours,
        "weak_units": len(weak_units),
        "strong_units": len(strong_units),
        "summary": f"{days_left} days until exam. Focus on {len(weak_units)} weak units first.",
        "schedule": schedule
    }


def get_todays_plan(
    db: Session,
    user_id: str,
    syllabus_doc_id: str
) -> dict:
    """
    Get what the student should study TODAY
    based on weak areas and due cards
    """
    today = date.today()

    topics = db.query(Topic).filter(
        Topic.document_id == syllabus_doc_id
    ).all()

    todays_tasks = []

    for topic in topics:
        questions = db.query(Question).filter(
            Question.topic_id == topic.id
        ).all()
        q_ids = [q.id for q in questions]

        # Count due cards
        due_count = db.query(ReviewSchedule).filter(
            ReviewSchedule.user_id == user_id,
            ReviewSchedule.question_id.in_(q_ids),
            ReviewSchedule.next_review_date <= today
        ).count()

        # Count never reviewed
        reviewed_ids = db.query(ReviewSchedule.question_id).filter(
            ReviewSchedule.user_id == user_id,
            ReviewSchedule.question_id.in_(q_ids)
        ).all()
        reviewed_ids = [r[0] for r in reviewed_ids]
        new_count = len([q for q in questions if q.id not in reviewed_ids])

        if due_count > 0 or new_count > 0:
            todays_tasks.append({
                "unit_number": topic.unit_number,
                "unit_title": topic.unit_title,
                "due_cards": due_count,
                "new_cards": min(new_count, 10),
                "total_to_review": due_count + min(new_count, 10),
                "estimated_minutes": (due_count + min(new_count, 10)) * 2
            })

    # Sort by most urgent (most due cards first)
    todays_tasks.sort(key=lambda x: x['total_to_review'], reverse=True)

    total_cards = sum(t['total_to_review'] for t in todays_tasks)
    total_minutes = sum(t['estimated_minutes'] for t in todays_tasks)

    return {
        "date": str(today),
        "total_cards_today": total_cards,
        "estimated_minutes": total_minutes,
        "tasks": todays_tasks
    }