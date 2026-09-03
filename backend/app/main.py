# main.py — Point d'entrée de l'application FastAPI Smartovate Chatbot
# Lance le serveur et enregistre toutes les routes

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import chat, agent, admin
from app.routes import bot_messages

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
# Autorise les requêtes du frontend React (localhost:5173 en développement)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Enregistrement des routes ---
app.include_router(chat.router,         prefix="/api/chat",  tags=["Chat — Client"])
app.include_router(agent.router,        prefix="/api/agent", tags=["Agent Support"])
app.include_router(admin.router,        prefix="/api/admin", tags=["Administration"])
app.include_router(bot_messages.router, prefix="/api",       tags=["Bot Framework"])


@app.get("/api/health", tags=["Santé"])
def health_check():
    """Vérifie que le backend est opérationnel."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }
