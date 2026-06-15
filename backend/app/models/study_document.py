from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class StudyDocument(Base):
    __tablename__ = "study_documents"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("study_plans.id"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    num_chunks = Column(Integer, nullable=False, default=0)
    # processing -> indexed -> failed
    status = Column(String, nullable=False, default="processing")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    plan = relationship("StudyPlan", back_populates="documents")
