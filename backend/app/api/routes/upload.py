# backend/app/api/routes/upload.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from pathlib import Path
import shutil

router = APIRouter(tags=["Upload"])

class UploadResponse(BaseModel):
    filename: str
    saved_path: str
    session_id: str

@router.post("/upload/resume", response_model=UploadResponse)
async def upload_resume(session_id: str = Form(...), file: UploadFile = File(...)):
    base = Path.cwd() / "storage" / session_id / "resumes"
    if not base.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    out_path = base / file.filename
    with out_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"filename": file.filename, "saved_path": str(out_path), "session_id": session_id}
