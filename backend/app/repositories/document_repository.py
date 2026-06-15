from sqlalchemy.orm import Session

from ..models.study_document import StudyDocument


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        plan_id: int,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> StudyDocument:
        doc = StudyDocument(
            plan_id=plan_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            status="processing",
            num_chunks=0,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_by_id(self, document_id: int) -> StudyDocument | None:
        return (
            self.db.query(StudyDocument)
            .filter(StudyDocument.id == document_id)
            .first()
        )

    def get_by_plan_id(self, plan_id: int) -> list[StudyDocument]:
        return (
            self.db.query(StudyDocument)
            .filter(StudyDocument.plan_id == plan_id)
            .order_by(StudyDocument.created_at)
            .all()
        )

    def mark_indexed(self, document_id: int, num_chunks: int) -> StudyDocument | None:
        doc = self.get_by_id(document_id)
        if not doc:
            return None
        doc.num_chunks = num_chunks
        doc.status = "indexed"
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def mark_failed(self, document_id: int) -> StudyDocument | None:
        doc = self.get_by_id(document_id)
        if not doc:
            return None
        doc.status = "failed"
        self.db.commit()
        self.db.refresh(doc)
        return doc
