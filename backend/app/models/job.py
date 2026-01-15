from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True) # UUID
    status: Mapped[str] = mapped_column(String, default="pending") # pending, processing, completed, failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Stage Progress
    stage_status: Mapped[Dict[str, str]] = mapped_column(JSON, default={})
    stage_artifacts: Mapped[Dict[str, Any]] = mapped_column(JSON, default={})
    
    # Results pointers
    stats: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    validation_report: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    testcases: Mapped[list["TestCase"]] = relationship("TestCase", back_populates="job", cascade="all, delete-orphan")
    defects: Mapped[list["DefectAnalysis"]] = relationship("DefectAnalysis", back_populates="job", cascade="all, delete-orphan")
    clusters: Mapped[list["DefectCluster"]] = relationship("DefectCluster", back_populates="job", cascade="all, delete-orphan")
