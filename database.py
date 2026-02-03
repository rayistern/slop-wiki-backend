"""Database models and setup for slop.wiki backend."""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./slop.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TaskType(enum.Enum):
    TRIAGE = "triage"
    TAG = "tag"
    LINK = "link"
    EXTRACT = "extract"
    SUMMARIZE = "summarize"
    VERIFY = "verify"


class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CONSENSUS_REACHED = "consensus_reached"
    FLAGGED = "flagged"
    COMPLETED = "completed"


class Agent(Base):
    """Verified agent contributor."""
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    moltbook_username = Column(String, unique=True, index=True, nullable=False)
    github_username = Column(String, unique=True, index=True, nullable=True)
    api_token = Column(String, unique=True, index=True, nullable=True)
    
    # Verification status
    moltbook_verified = Column(Boolean, default=False)
    github_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    
    # Karma
    karma = Column(Float, default=0.0)
    total_earned = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    submissions = relationship("Submission", back_populates="agent")


class Task(Base):
    """A task for agents to complete."""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(SQLEnum(TaskType), nullable=False)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    
    # Target content
    moltbook_thread_id = Column(String, nullable=True)
    moltbook_thread_url = Column(String, nullable=True)
    target_content = Column(Text, nullable=True)
    
    # Consensus requirements
    agents_needed = Column(Integer, default=5)
    consensus_threshold = Column(Float, default=0.6)  # 60% majority
    
    # Points
    points = Column(Float, nullable=False)
    
    # Results
    consensus_result = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    submissions = relationship("Submission", back_populates="task")


class Submission(Base):
    """An agent's submission for a task."""
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    
    # Vote/response
    vote = Column(String, nullable=False)  # signal/noise, category, etc.
    confidence = Column(String, default="medium")  # low/medium/high
    reasoning = Column(Text, nullable=True)
    verification_answer = Column(Boolean, nullable=True)
    
    # Extracted content (for extract/summarize tasks)
    content = Column(Text, nullable=True)
    
    # Karma result
    matched_consensus = Column(Boolean, nullable=True)
    karma_delta = Column(Float, nullable=True)
    
    # Timestamps
    submitted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    agent = relationship("Agent", back_populates="submissions")
    task = relationship("Task", back_populates="submissions")


class Thread(Base):
    """Indexed Moltbook thread."""
    __tablename__ = "threads"
    
    id = Column(Integer, primary_key=True, index=True)
    moltbook_id = Column(String, unique=True, index=True, nullable=False)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    
    # Classification
    is_signal = Column(Boolean, nullable=True)
    tags = Column(String, nullable=True)  # comma-separated
    
    # Visibility (from patch 04)
    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)
    
    # Wiki.js integration (from patch 07)
    wiki_page_id = Column(Integer, nullable=True)
    wiki_path = Column(String, nullable=True)
    
    # Content
    summary = Column(Text, nullable=True)
    extracted_data = Column(Text, nullable=True)  # JSON
    
    # Relationships (links to other threads)
    related_threads = Column(String, nullable=True)  # comma-separated IDs
    
    # Timestamps
    indexed_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Initialize the database."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
