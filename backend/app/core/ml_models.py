# backend/app/core/ml_models.py
import asyncio
from sentence_transformers import SentenceTransformer
from typing import Optional

MODEL_NAME = "all-MiniLM-L6-v2"
_model: Optional[SentenceTransformer] = None

async def load_models_async():
    """
    Called during app lifespan. Uses run_in_executor to avoid blocking the event loop
    while the SentenceTransformer downloads / initializes.
    """
    global _model
    if _model is not None:
        return
    loop = asyncio.get_running_loop()
    # run the blocking model init in a thread
    _model = await loop.run_in_executor(None, lambda: SentenceTransformer(MODEL_NAME))

def get_model():
    """
    Synchronous accessor to the loaded model. Raises if not loaded.
    Use this in endpoints (and offload heavy .encode calls to executor).
    """
    if _model is None:
        raise RuntimeError("Model not loaded. Ensure app was started with lifespan that calls load_models_async().")
    return _model
