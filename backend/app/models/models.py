from sqlalchemy import Column, String, Boolean, Float, Integer, DateTime, Text, ARRAY, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="owner")
    review_schedules = relationship("ReviewSchedule", back_populates="user")
    performance_logs = relationship("PerformanceLog", back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    subject = Column(String, nullable=True)

    owner = relationship("User", back_populates="documents")
    topics = relationship("Topic", back_populates="document")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    topic_name = Column(String, nullable=False)
    keywords = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0.0)
    unit_mapping = Column(String, nullable=True)

    document = relationship("Document", back_populates="topics")
    questions = relationship("Question", back_populates="topic")


class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)
    question_type = Column(String, default="open")
    difficulty = Column(String, default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)

    topic = relationship("Topic", back_populates="questions")
    review_schedules = relationship("ReviewSchedule", back_populates="question")
    performance_logs = relationship("PerformanceLog", back_populates="question")


class ReviewSchedule(Base):
    __tablename__ = "review_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    repetitions = Column(Integer, default=0)
    easiness = Column(Float, default=2.5)
    interval_days = Column(Integer, default=1)
    next_review_date = Column(Date, nullable=True)
    last_quality_rating = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="review_schedules")
    question = relationship("Question", back_populates="review_schedules")


class PerformanceLog(Base):
    __tablename__ = "performance_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    quality_rating = Column(Integer, nullable=False)
    reviewed_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="performance_logs")
    question = relationship("Question", back_populates="performance_logs")