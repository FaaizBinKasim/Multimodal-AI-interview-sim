# backend/app/api/routes/answer.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from pathlib import Path
import shutil
import uuid
import json

router = APIRouter(tags=["Answer"])

class TextAnswerIn(BaseModel):
    session_id: str
    question_id: str
    answer_text: str

class TextAnswerOut(BaseModel):
    id: str
    session_id: str
    question_id: str
    saved_path: str

@router.post("/answer/text", response_model=TextAnswerOut)
async def submit_text_answer(payload: TextAnswerIn):
    base = Path.cwd() / "storage" / payload.session_id / "text_answers"
    if not base.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    aid = str(uuid.uuid4())
    out_file = base / f"{payload.question_id}_{aid}.json"
    out_data = {
        "id": aid,
        "session_id": payload.session_id,
        "question_id": payload.question_id,
        "answer_text": payload.answer_text
    }
    with out_file.open("w", encoding="utf8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)
    return {"id": aid, "session_id": payload.session_id, "question_id": payload.question_id, "saved_path": str(out_file)}

class AudioAnswerOut(BaseModel):
    id: str
    session_id: str
    question_id: str
    saved_path: str

@router.post("/answer/audio", response_model=AudioAnswerOut)
async def submit_audio_answer(session_id: str = Form(...), question_id: str = Form(...), file: UploadFile = File(...)):
    base = Path.cwd() / "storage" / session_id / "audio"
    if not base.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    aid = str(uuid.uuid4())
    filename = f"{question_id}_{aid}_{file.filename}"
    out_path = base / filename
    with out_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    # Dummy placeholder for ASR/transcription step: we will replace with real ASR later
    return {"id": aid, "session_id": session_id, "question_id": question_id, "saved_path": str(out_path)}
