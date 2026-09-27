import hashlib
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError

from api.deps import get_session_dao
from backend.config import SESSION_UPLOADS_SUBDIR
from backend.temporal.client import get_temporal_client
from backend.temporal.workflows.doc_ingest_workflow import ProcessSessionDocumentsWorkflow
from backend.models.pydantic_models import FileInfo, FileUploadResponse
from database.session_dao import SessionDAO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

_DATA = Path(__file__).resolve().parents[2] / "data"

_OPENAPI_FILE_UPLOAD = {
    "requestBody": {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["session_id", "files"],
                    "properties": {
                        "session_id": {"type": "string"},
                        "files": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                        },
                    },
                }
            }
        }
    }
}


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="upload_files",
    openapi_extra=_OPENAPI_FILE_UPLOAD,
)
async def upload_files(
    session_uuid: uuid.UUID = Form(..., alias="session_id"),
    files: list[UploadFile] = File(...),
    session_dao: SessionDAO = Depends(get_session_dao),
) -> FileUploadResponse:
    """Accept multipart uploads for an existing session and persist file metadata in the database.

    Args:
        session_uuid: Client session id from form field session_id (must already exist in the sessions table).
        files: One or more file parts to store under data/<session_id>/uploads/.
        session_dao: Injected DAO used to append FileInfo rows to JSONB.

    Returns:
        Session id and a list of generated file ids with original filenames.
    """
    session_id = str(session_uuid)
    session_dir = _DATA / session_id / SESSION_UPLOADS_SUBDIR
    session_dir.mkdir(parents=True, exist_ok=True)

    uploaded_files: list[FileInfo] = []
    for file in files:
        file_id = str(uuid.uuid4())
        file_path = session_dir / file.filename
        file_bytes = await file.read()
        file_path.write_bytes(file_bytes)
        uploaded_files.append(
            FileInfo(
                file_id=file_id,
                filename=file.filename,
                content_hash=hashlib.sha256(file_bytes).hexdigest(),
            )
        )

    try:
        await session_dao.append_uploaded_files(session_id, uploaded_files)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        ) from None
    except SQLAlchemyError as e:
        logger.exception(f"upload_files database error session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from e

    try:
        temporal_client = await get_temporal_client()
        await temporal_client.start_workflow(
            ProcessSessionDocumentsWorkflow.run,
            args=[session_id, SESSION_UPLOADS_SUBDIR],
            id=f"doc-ingest:{session_id}:{uuid.uuid4()}",
            task_queue=os.environ["TEMPORAL_TASK_QUEUE"],
        )
    except Exception as e:
        logger.exception(f"upload_files temporal enqueue failed session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document processing unavailable",
        ) from e

    logger.info(f"Files uploaded count={len(uploaded_files)} session_id={session_id}")
    return FileUploadResponse(session_id=session_id, files=uploaded_files)
