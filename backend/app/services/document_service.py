from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..repositories.document_repository import DocumentRepository
from ..repositories.plan_repository import PlanRepository
from ..schemas.study_document import StudyDocumentRead
from ..utils.ai import vector_store
from ..utils.ai.document_loader import is_supported, load_and_split


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.repo = DocumentRepository(db)
        self.plan_repo = PlanRepository(db)

    def upload_document(self, plan_id: int, file: UploadFile) -> StudyDocumentRead:
        if not self.plan_repo.get_by_id(plan_id):
            raise HTTPException(status_code=404, detail="Plan not found")

        filename = file.filename or "upload"
        if not is_supported(filename, file.content_type):
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Upload a PDF, TXT, or Markdown file.",
            )

        file_bytes = file.file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        doc = self.repo.create(
            plan_id=plan_id,
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=len(file_bytes),
        )

        try:
            chunks = load_and_split(
                file_bytes, filename, file.content_type, plan_id, doc.id
            )
            if not chunks:
                raise ValueError("no extractable text")
            vector_store.add_documents(plan_id, chunks)
        except Exception as exc:  # noqa: BLE001 — record failure, surface as 422
            self.repo.mark_failed(doc.id)
            raise HTTPException(
                status_code=422,
                detail="Could not extract searchable text from the document",
            ) from exc

        updated = self.repo.mark_indexed(doc.id, len(chunks))
        return StudyDocumentRead.model_validate(updated)

    def list_documents(self, plan_id: int) -> list[StudyDocumentRead]:
        if not self.plan_repo.get_by_id(plan_id):
            raise HTTPException(status_code=404, detail="Plan not found")
        docs = self.repo.get_by_plan_id(plan_id)
        return [StudyDocumentRead.model_validate(d) for d in docs]
