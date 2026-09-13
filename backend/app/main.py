# main.py — Point d'entrée de l'application FastAPI Smartovate Chatbot
# Lance le serveur et enregistre toutes les routes

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import get_settings
from app.routes import chat, agent, admin
from app.routes import bot_messages
from app.routes import token as token_route

# ── Configuration du logging ─────────────────────────────────────────────────
# Le logger 'smartovate.search' est activé en DEBUG pour diagnostiquer le RAG.
# En production, passer le niveau à WARNING.
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logging.getLogger("smartovate.search").setLevel(logging.DEBUG)

# Chargement de la configuration
settings = get_settings()

# Initialisation de l'application FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API du chatbot conversationnel Smartovate — powered by Azure OpenAI + Azure AI Search",
    docs_url="/docs",       # Interface Swagger accessible à /docs
    redoc_url="/redoc",
)

# --- Middleware CORS ---
# Autorise les requêtes du frontend (localhost:5173 / 3000 en développement)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Enregistrement des routes API ---
# IMPORTANT : toutes les routes /api/* doivent être enregistrées AVANT
# le mount du frontend statique, sinon StaticFiles absorbe les requêtes.
app.include_router(chat.router,         prefix="/api/chat",  tags=["Chat — Client"])
app.include_router(agent.router,        prefix="/api/agent", tags=["Agent Support"])
app.include_router(admin.router,        prefix="/api/admin", tags=["Administration"])
app.include_router(bot_messages.router, prefix="/api",       tags=["Bot Framework"])
app.include_router(token_route.router,  prefix="/api/chat",  tags=["Web Chat — Token"])


@app.get("/api/health", tags=["Santé"])
def health_check():
    """Vérifie que le backend est opérationnel."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }


# --- Serving du frontend statique (US 3.2) ---
# DOIT être monté EN DERNIER — après toutes les routes /api/*
# main.py est dans backend/app/  →  frontend/ est à Chatbot-Smartovate/frontend/
_frontend_path = Path(__file__).parent.parent.parent / "frontend"
if _frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_path), html=True), name="frontend")
