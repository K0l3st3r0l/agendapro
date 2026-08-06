from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from app.api import auth, curriculum, events, ai_constructor, settings
import app.models  # noqa - ensure all models are registered
import os

Base.metadata.create_all(bind=engine)

os.makedirs("/app/static/images", exist_ok=True)

app = FastAPI(
    title="AgendaPro API",
    description="Plataforma pedagógica de agenda y construcción de material educativo con IA",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(ai_constructor.router)
app.include_router(settings.router)
app.include_router(curriculum.router)

app.mount("/static", StaticFiles(directory="/app/static"), name="static")

@app.get("/")
def root():
    return {"status": "ok", "app": "AgendaPro API", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy"}
