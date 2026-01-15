from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class TestCase(Base):
    __tablename__ = "testcases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"), index=True)
    
    # Original Fields
    case_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    case_name: Mapped[str] = mapped_column(Text)
    precondition: Mapped[Optional[str]] = mapped_column(Text)
    steps: Mapped[Optional[str]] = mapped_column(Text)
    expected: Mapped[Optional[str]] = mapped_column(Text)
    actual: Mapped[Optional[str]] = mapped_column(Text)
    
    # Execution Info
    test_result: Mapped[str] = mapped_column(String) # Original result string
    normalized_result: Mapped[str] = mapped_column(String) # Pass, Fail, Blocked, Skipped
    priority: Mapped[Optional[str]] = mapped_column(String)
    executor: Mapped[Optional[str]] = mapped_column(String)
    exec_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    
    # Analysis Info
    module: Mapped[Optional[str]] = mapped_column(String, index=True)
    module_confidence: Mapped[Optional[float]] = mapped_column(Float)
    
    # Source Info
    source_file: Mapped[str] = mapped_column(String)
    source_sheet: Mapped[str] = mapped_column(String)
    source_row: Mapped[int] = mapped_column(Integer)
    
    # Validation
    parse_warnings: Mapped[Optional[List[str]]] = mapped_column(JSON)
    
    # Audit Info (Result Consistency Check)
    audit_status: Mapped[Optional[str]] = mapped_column(String, default="Unchecked") # Unchecked, Pass, Flagged
    audit_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Defect Analysis (One-to-One or One-to-Many? usually One-to-One per execution)
    defect_analysis: Mapped[Optional["DefectAnalysis"]] = relationship("DefectAnalysis", back_populates="testcase", uselist=False)

    job: Mapped["Job"] = relationship("Job", back_populates="testcases")
