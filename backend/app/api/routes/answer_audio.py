# backend/app/api/routes/answer_audio.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import shutil
import uuid
import traceback

# we'll reuse the existing text-scoring endpoint function directly
from backend.app.api.routes.score_text import score_text_answer

router = APIRouter()

# lazy ASR pipeline singleton (import transformers inside function)
_asr = None
def get_asr_pipeline(model_name: str = "openai/whisper-small"):
    global _asr
    if _asr is None:
        # import inside function to avoid heavy import during FastAPI startup
        try:
            from transformers import pipeline as _pipeline
        except Exception as e:
            # provide a helpful message if transformers isn't importable
            raise RuntimeError(f"Failed to import transformers.pipeline: {e}")
        # this will download the model the first time it's called (may be slow)
        _asr = _pipeline("automatic-speech-recognition", model=model_name)
    return _asr

@router.post("/answer/audio")
async def answer_audio(session_id: str, question_id: str, file: UploadFile = File(...)):
    """
    Accept an uploaded audio file, save it, run ASR (Whisper), then call score_text_answer
    """
    try:
        BASE_DIR = Path(__file__).resolve().parents[4]
        STORAGE_DIR = BASE_DIR / "storage"
        session_dir = STORAGE_DIR / session_id
        if not session_dir.exists():
            raise HTTPException(status_code=404, detail="session_id not found")

        answers_dir = session_dir / "answers"
        answers_dir.mkdir(parents=True, exist_ok=True)

        # save uploaded file
        ext = Path(file.filename).suffix or ".wav"
        dest_name = f"{question_id}_{uuid.uuid4().hex}{ext}"
        dest_path = answers_dir / dest_name

        with dest_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        # run ASR (may be slow the first time while model downloads)
        try:
            asr = get_asr_pipeline()
            asr_result = asr(str(dest_path))
            transcript = asr_result.get("text") if isinstance(asr_result, dict) else str(asr_result)
            transcript = transcript.strip()
        except Exception as e:
            # catch everything and return a clear 500 with logs on server
            print("ASR error:", e)
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail="ASR failed. See server logs for details.")

        # call scoring logic
        payload = {
            "session_id": session_id,
            "question_id": question_id,
            "answer_text": transcript
        }

        scored = await score_text_answer(payload)

        # attach transcript + path
        scored["transcript"] = transcript
        scored["audio_path"] = str(dest_path)

        return scored

    except HTTPException:
        raise
    except Exception as e:
        print("Error in /answer/audio:", e)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
