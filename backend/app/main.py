# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.session import router as session_router
from backend.app.api.routes.upload import router as upload_router
from backend.app.api.routes.answer import router as answer_router
from backend.app.api.routes.parse_resume import router as parse_router
from backend.app.api.routes.score_text import router as score_text_router


from backend.app.core import ml_models

@asynccontextmanager
async def lifespan(app: FastAPI):
    # preload models (runs before server accepts requests)
    await ml_models.load_models_async()
    yield
    # optional: cleanup here

app = FastAPI(title="Multimodal AI Interview Simulator", version="0.1.0", lifespan=lifespan)

# CORS etc...
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(answer_router, prefix="/api")
app.include_router(parse_router, prefix="/api")
app.include_router(score_text_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "AI Interview Backend is running"}
