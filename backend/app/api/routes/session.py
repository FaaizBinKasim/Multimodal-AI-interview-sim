# backend/app/api/routes/session.py
from fastapi import APIRouter
from pydantic import BaseModel
import uuid
import os
from pathlib import Path
from typing import List

router = APIRouter(tags=["Session"])

STORAGE_ROOT = Path.cwd() / "storage"

class SessionCreateResponse(BaseModel):
    session_id: str
    storage_path: str

@router.post("/session/create", response_model=SessionCreateResponse)
async def create_session():
    sid = str(uuid.uuid4())
    session_dir = STORAGE_ROOT / sid
    os.makedirs(session_dir, exist_ok=True)
    # create subfolders
    (session_dir / "resumes").mkdir(exist_ok=True)
    (session_dir / "audio").mkdir(exist_ok=True)
    (session_dir / "text_answers").mkdir(exist_ok=True)
    return {"session_id": sid, "storage_path": str(session_dir)}
