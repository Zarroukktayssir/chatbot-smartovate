# routes/bot_messages.py — Endpoint Bot Framework
#
# Rôle : exposer le point d'entrée POST /api/messages
#        que Azure Bot Service appelle pour chaque message utilisateur.
#
# C'est le seul endpoint que Azure Bot Service connaît.
# Il reçoit une "Activity" (objet JSON standardisé Bot Framework),
# l'authentifie, puis la passe à SmartovateBot pour traitement.

from fastapi import APIRouter, Request, Response, HTTPException
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity

from app.config import get_settings
from app.bot.smartovate_bot import SmartovateBot

router = APIRouter()
settings = get_settings()

# ─────────────────────────────────────────────────────────
# Initialisation de l'adaptateur Bot Framework
#
# BotFrameworkAdapter est le composant qui :
# - authentifie les requêtes venant d'Azure Bot Service
# - gère le protocole de communication Bot Framework
# - crée le TurnContext passé au bot
#
# MicrosoftAppId et MicrosoftAppPassword sont vides en développement local
# (Bot Framework Emulator fonctionne sans authentification en local)
# Ils seront remplis lors du déploiement sur Azure App Service
# ─────────────────────────────────────────────────────────
adapter_settings = BotFrameworkAdapterSettings(
    app_id=settings.microsoft_app_id,
    app_password=settings.microsoft_app_password,
)
adapter = BotFrameworkAdapter(adapter_settings)

# Instance unique du bot — créée une seule fois au démarrage
bot = SmartovateBot()


@router.post(
    "/messages",
    summary="Point d'entrée Bot Framework — Azure Bot Service",
    description=(
        "Endpoint principal appelé par Azure Bot Service pour chaque message utilisateur. "
        "Reçoit une Activity Bot Framework, l'authentifie et la passe au SmartovateBot."
    ),
)
async def bot_messages(request: Request):
    """
    Reçoit les Activity envoyées par Azure Bot Service (ou Bot Framework Emulator).

    Une Activity est un objet JSON standardisé qui peut représenter :
    - un message texte (type: 'message')
    - un événement système (type: 'conversationUpdate', 'event', etc.)

    En développement local : utiliser Bot Framework Emulator pointant sur http://localhost:8000/api/messages
    En production : Azure Bot Service appelle automatiquement cet endpoint
    """
    # Vérification du Content-Type
    if "application/json" not in request.headers.get("Content-Type", ""):
        raise HTTPException(status_code=415, detail="Content-Type application/json requis")

    # Désérialisation du corps de la requête en objet Activity
    body = await request.json()
    activity = Activity().deserialize(body)

    # Récupération du header d'authentification
    auth_header = request.headers.get("Authorization", "")

    # Réponse HTTP — le Bot Framework attend une réponse 200 vide
    # La vraie réponse est envoyée de manière asynchrone par l'adaptateur
    response = Response(status_code=201)

    async def call_bot(turn_context):
        await bot.on_turn(turn_context)

    try:
        await adapter.process_activity(activity, auth_header, call_bot)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Authentification Bot Framework échouée")
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur interne du bot")

    return response
