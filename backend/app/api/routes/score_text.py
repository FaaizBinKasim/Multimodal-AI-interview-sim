# backend/app/api/routes/score_text.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json, traceback
from sentence_transformers import util
from backend.app.core.ml_models import get_model
import asyncio
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import torch

router = APIRouter()

MODEL_NAME = "all-MiniLM-L6-v2"
_model = None


def load_parsed_and_plan(storage_dir: Path, session_id: str):
    parsed_path = storage_dir / session_id / "parsed_resume.json"
    plan_path = storage_dir / session_id / "interview_plan.json"
    if not parsed_path.exists():
        raise FileNotFoundError(f"parsed_resume.json not found at {parsed_path}")
    if not plan_path.exists():
        raise FileNotFoundError(f"interview_plan.json not found at {plan_path}")
    parsed = json.loads(
        parsed_path.read_text(encoding="utf-8", errors="ignore")
    )
    plan = json.loads(
        plan_path.read_text(encoding="utf-8", errors="ignore")
    )
    return parsed, plan

def build_reference_text(parsed: dict, plan: dict, question_obj: dict):
    if question_obj.get("type") == "technical":
        skill = question_obj.get("skill") or question_obj.get("question", "")
        resume_summary = parsed.get("summary", "")
        projects = parsed.get("projects", []) or []
        project_snippet = (projects[0][:800]) if projects else ""
        ref = (
            f"Describe your experience with {skill}. Mention projects using {skill}, tools/frameworks, "
            "your role, responsibilities, and any concrete results or metrics. "
            f"Resume summary: {resume_summary}. Example project excerpt: {project_snippet}"
        )
        return ref
    else:
        resume_summary = parsed.get("summary", "")
        return (
            f"Answer: {question_obj.get('question')}. Include role, duration, achievements. "
            f"Resume summary: {resume_summary}"
        )

def compute_top_matches(reference: str, answer: str, top_k=6):
    """
    Explainability helper: compute TF-IDF on [reference, answer] and return tokens that
    are present in both with their TF-IDF weight from reference (higher => more important).
    """
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1,2), max_features=2000)
        docs = [reference, answer]
        X = vec.fit_transform(docs)  # shape (2, n_features)
        feature_names = np.array(vec.get_feature_names_out())
        ref_vec = X[0].toarray().ravel()
        ans_vec = X[1].toarray().ravel()
        # tokens present in both
        common_mask = (ref_vec > 0) & (ans_vec > 0)
        if not np.any(common_mask):
            return []
        common_scores = ref_vec * common_mask  # use ref tfidf weight as importance
        idx = np.argsort(common_scores)[::-1]
        top_idx = [i for i in idx if common_mask[i]][:top_k]
        matches = [{"token": feature_names[i], "ref_tfidf": float(round(ref_vec[i], 4))} for i in top_idx]
        return matches
    except Exception:
        return []

@router.post("/score/text")
async def score_text_answer(payload: dict):
    try:
        session_id = payload.get("session_id")
        question_id = payload.get("question_id")
        answer_text = payload.get("answer_text", "")

        if not (session_id and question_id and answer_text is not None):
            raise HTTPException(status_code=400, detail="session_id, question_id and answer_text required")

        BASE_DIR = Path(__file__).resolve().parents[4]
        STORAGE_DIR = BASE_DIR / "storage"

        # load parsed and plan -> can raise FileNotFoundError
        parsed, plan = load_parsed_and_plan(STORAGE_DIR, session_id)

        # find question object
        q_obj = next((q for q in plan.get("questions", []) if q.get("id") == question_id), None)
        if q_obj is None:
            raise HTTPException(status_code=404, detail="question_id not found in interview_plan.json")

        # build reference
        ref_text = build_reference_text(parsed, plan, q_obj)

        # load model (already preloaded during lifespan)
        model = get_model()

        # offload CPU / IO-heavy encoding to threadpool to avoid blocking uvicorn event loop
        loop = asyncio.get_running_loop()
        def encode_pair():
            # encode in same thread (so model internal caching/device handling is consistent)
            emb_r = model.encode(ref_text, convert_to_tensor=True)
            emb_a = model.encode(answer_text, convert_to_tensor=True)
            return emb_r, emb_a

        emb_ref, emb_ans = await loop.run_in_executor(None, encode_pair)

        # compute cosine similarity in executor as well (torch ops)
        sim = await loop.run_in_executor(None, lambda: util.cos_sim(emb_ref, emb_ans).item())


        sim_clamped = max(min(sim, 1.0), -1.0)
        score_0_10 = round(((sim_clamped + 1.0) / 2.0) * 10.0, 2)

        # per-question min_score (if specified in plan, add "min_score": 6.0 for the question)
        default_min = 5.0
        min_score = q_obj.get("min_score", plan.get("default_min_score", default_min))

        needs_human_review = score_0_10 < float(min_score)

        # top matches (explainability)
        top_matches = compute_top_matches(ref_text, answer_text, top_k=6)

        score_obj = {
            "question_id": question_id,
            "session_id": session_id,
            "similarity": float(sim_clamped),
            "score": float(score_0_10),
            "min_score": float(min_score),
            "needs_human_review": bool(needs_human_review),
            "reference_snippet": ref_text[:1200],
            "answer_excerpt": answer_text[:1200],
            "top_matches": top_matches
        }

        out_dir = STORAGE_DIR / session_id / "scores"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{question_id}.json"
        out_file.write_text(json.dumps(score_obj, indent=2, ensure_ascii=False))

        return {"status": "ok", "question_id": question_id, "similarity": sim_clamped, "score": score_0_10, "needs_human_review": needs_human_review, "score_path": str(out_file)}

    except HTTPException:
        # re-raise HTTP errors so FastAPI handles them properly
        raise
    except FileNotFoundError as e:
        # provide helpful message
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # catch-all with a readable message and server trace in logs
        tb = traceback.format_exc()
        # Log to server console
        print("Error in /score/text:", e)
        print(tb)
        # Return a friendly 500 with short message
        raise HTTPException(status_code=500, detail=f"Internal error scoring answer: {str(e)}")
    
    except RuntimeError as e:
        # common OOM or device errors
        if "out of memory" in str(e).lower():
            raise HTTPException(status_code=503, detail="Server out of memory while processing embeddings.")
        raise
