from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from app.models.models import ReviewSchedule, Question, Topic, User
from typing import List, Dict


def get_due_reminders(
    db: Session,
    user_id: str,
    syllabus_doc_id: str
) -> dict:
    """
    Get reminder summary for a user's due cards
    Returns what to show as a notification/reminder
    """
    today = date.today()

    # Get all topics for this syllabus
    topics = db.query(Topic).filter(
        Topic.document_id == syllabus_doc_id
    ).all()
    topic_ids = [t.id for t in topics]

    # Get all questions
    questions = db.query(Question).filter(
        Question.topic_id.in_(topic_ids)
    ).all()
    question_ids = [q.id for q in questions]

    # Get overdue cards (past due date)
    overdue = db.query(ReviewSchedule).filter(
        ReviewSchedule.user_id == user_id,
        ReviewSchedule.question_id.in_(question_ids),
        ReviewSchedule.next_review_date < today
    ).count()

    # Get due today
    due_today = db.query(ReviewSchedule).filter(
        ReviewSchedule.user_id == user_id,
        ReviewSchedule.question_id.in_(question_ids),
        ReviewSchedule.next_review_date == today
    ).count()

    # Get never reviewed (new cards)
    reviewed_ids = db.query(ReviewSchedule.question_id).filter(
        ReviewSchedule.user_id == user_id,
        ReviewSchedule.question_id.in_(question_ids)
    ).all()
    reviewed_ids = [r[0] for r in reviewed_ids]
    new_cards = len([q for q in questions if q.id not in reviewed_ids])

    # Build reminder message
    total_urgent = overdue + due_today
    reminders = []

    if overdue > 0:
        reminders.append({
            "type": "overdue",
            "icon": "🔴",
            "title": f"{overdue} cards are overdue!",
            "message": "These cards have passed their review date. Review them now to prevent forgetting.",
            "priority": 1,
            "count": overdue
        })

    if due_today > 0:
        reminders.append({
            "type": "due_today",
            "icon": "🟡",
            "title": f"{due_today} cards due today",
            "message": "Complete today's review to stay on track with your spaced repetition schedule.",
            "priority": 2,
            "count": due_today
        })

    if new_cards > 0:
        reminders.append({
            "type": "new_cards",
            "icon": "🔵",
            "title": f"{new_cards} new cards to learn",
            "message": "Start learning new material to build your knowledge base.",
            "priority": 3,
            "count": new_cards
        })

    if total_urgent == 0 and new_cards == 0:
        reminders.append({
            "type": "all_done",
            "icon": "✅",
            "title": "All caught up!",
            "message": "No cards due right now. Great work! Check back later.",
            "priority": 4,
            "count": 0
        })

    return {
        "user_id": user_id,
        "date": str(today),
        "overdue": overdue,
        "due_today": due_today,
        "new_cards": new_cards,
        "total_urgent": total_urgent,
        "reminders": reminders,
        "should_study_now": total_urgent > 0
    }


def get_study_streak(
    db: Session,
    user_id: str
) -> dict:
    """
    Calculate study streak (consecutive days with reviews)
    """
    from app.models.models import PerformanceLog
    from datetime import timedelta

    logs = db.query(PerformanceLog).filter(
        PerformanceLog.user_id == user_id
    ).order_by(PerformanceLog.reviewed_at.desc()).all()

    if not logs:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "last_studied": None,
            "studied_today": False
        }

    # Get unique study days
    study_days = sorted(set([
        log.reviewed_at.date() for log in logs
    ]), reverse=True)

    today = date.today()
    studied_today = today in study_days

    # Calculate current streak
    current_streak = 0
    check_date = today if studied_today else today

    for i, day in enumerate(study_days):
        expected = today - __import__('datetime').timedelta(days=i)
        if day == expected:
            current_streak += 1
        else:
            break

    # Calculate longest streak
    longest_streak = 0
    temp_streak = 1

    for i in range(1, len(study_days)):
        diff = (study_days[i-1] - study_days[i]).days
        if diff == 1:
            temp_streak += 1
            longest_streak = max(longest_streak, temp_streak)
        else:
            temp_streak = 1

    longest_streak = max(longest_streak, current_streak)

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "last_studied": str(study_days[0]) if study_days else None,
        "studied_today": studied_today,
        "total_study_days": len(study_days)
    }


def get_full_notification_panel(
    db: Session,
    user_id: str,
    syllabus_doc_id: str
) -> dict:
    """
    Full notification panel data for frontend
    Combines reminders + streak + motivational message
    """
    reminders = get_due_reminders(db, user_id, syllabus_doc_id)
    streak = get_study_streak(db, user_id)

    # Motivational message based on streak
    if streak["current_streak"] >= 7:
        motivation = f"🔥 {streak['current_streak']} day streak! You're on fire!"
    elif streak["current_streak"] >= 3:
        motivation = f"⚡ {streak['current_streak']} days in a row! Keep it up!"
    elif streak["current_streak"] == 1:
        motivation = "🌱 Great start! Come back tomorrow to build your streak."
    else:
        motivation = "💪 Start your streak today — review at least one card!"

    return {
        "reminders": reminders,
        "streak": streak,
        "motivation": motivation,
        "timestamp": str(datetime.now(timezone.utc))
    }