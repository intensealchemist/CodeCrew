from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from codecrew.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    jobs = relationship("Job", back_populates="owner")


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True) # E.g., job-a1b2c3d4
    user_id = Column(Integer, ForeignKey("users.id"))
    task_prompt = Column(String)
    llm_provider = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    owner = relationship("User", back_populates="jobs")
