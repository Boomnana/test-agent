from typing import Optional, List
from sqlalchemy import String, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class DefectAnalysis(Base):
    __tablename__ = "defect_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"))
    testcase_id: Mapped[int] = mapped_column(Integer, ForeignKey("testcases.id"))
    
    # LLM Extracted
    phenomenon: Mapped[Optional[str]] = mapped_column(Text)
    observed_fact: Mapped[Optional[str]] = mapped_column(Text)
    hypothesis: Mapped[Optional[str]] = mapped_column(Text)
    evidence: Mapped[Optional[List[str]]] = mapped_column(JSON)
    repro_steps: Mapped[Optional[str]] = mapped_column(Text)
    severity_guess: Mapped[Optional[str]] = mapped_column(String)
    
    # Clustering
    cluster_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("defect_clusters.id"))
    
    job: Mapped["Job"] = relationship("Job", back_populates="defects")
    testcase: Mapped["TestCase"] = relationship("TestCase", back_populates="defect_analysis")
    cluster: Mapped[Optional["DefectCluster"]] = relationship("DefectCluster", back_populates="defects")

class DefectCluster(Base):
    __tablename__ = "defect_clusters"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"))
    
    # LLM Summarized
    cluster_name: Mapped[str] = mapped_column(String)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    risk_assessment: Mapped[Optional[str]] = mapped_column(Text)
    
    job: Mapped["Job"] = relationship("Job", back_populates="clusters")
    defects: Mapped[list["DefectAnalysis"]] = relationship("DefectAnalysis", back_populates="cluster")
