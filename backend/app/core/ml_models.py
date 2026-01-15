"""
Centralized ML model loading and inference utilities.
All heavy models are loaded once and reused across requests.
"""

import threading
from typing import Union, List

from sentence_transformers import SentenceTransformer

# =========================
# Sentence Transformer
# =========================

_SENTENCE_MODEL_NAME = "all-MiniLM-L6-v2"
_sentence_model = None
_sentence_lock = threading.Lock()


def load_models():
    """
    Load all ML models at application startup.
    Called once via FastAPI lifespan.
    """
    global _sentence_model
    if _sentence_model is None:
        with _sentence_lock:
            if _sentence_model is None:
                print("📥 Loading SentenceTransformer...")
                _sentence_model = SentenceTransformer(_SENTENCE_MODEL_NAME)
                print("✅ SentenceTransformer loaded")


def get_sentence_transformer() -> SentenceTransformer:
    """
    Return the already-loaded SentenceTransformer.
    """
    if _sentence_model is None:
        raise RuntimeError(
            "SentenceTransformer not loaded. "
            "Did you forget to call load_models() in FastAPI lifespan?"
        )
    return _sentence_model


def encode_sentence(
    texts: Union[str, List[str]],
    convert_to_tensor: bool = True
):
    """
    Encode text(s) into embeddings using the shared SentenceTransformer.
    """
    model = get_sentence_transformer()
    return model.encode(texts, convert_to_tensor=convert_to_tensor)
