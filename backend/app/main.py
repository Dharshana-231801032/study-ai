from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import engine, Base
from app.models import models
from app.api import auth, upload, topics, questions, flashcards

# Create all tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Study-AI API",
    description="Intelligent Active Learning System for Exam Preparation",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(topics.router)
app.include_router(questions.router)
app.include_router(flashcards.router)

@app.get("/")
async def root():
    return {
        "message": "Study-AI API is running ✅",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}