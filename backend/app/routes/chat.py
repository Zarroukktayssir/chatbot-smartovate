# routes/chat.py — Routes Client (WebChat)
# Endpoints accessibles par l'acteur Client de la conception UML

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.services.azure_openai_service import AzureOpenAIService
from app.engine.bot_engine import BotEngine

router = APIRouter()


# ─────────────────────────────────────────────────────────
# Schémas de requête / réponse pour la route de test
# ─────────────────────────────────────────────────────────

class TestOpenAIRequest(BaseModel):
    """Corps de la requête pour le test Azure OpenAI."""
    message: str
    history: Optional[List[dict]] = []


class TestOpenAIResponse(BaseModel):
    """Réponse retournée par le test Azure OpenAI."""
    reponse: str
    modele: str
    tokens: dict


# ─────────────────────────────────────────────────────────
# Schémas US 2.1 — Critère 3 : historique de conversation
# ─────────────────────────────────────────────────────────

class MessageItem(BaseModel):
    """
    Représente un message de l'historique de conversation.
    Rôles acceptés : 'user', 'assistant', 'agent' — cohérent avec RoleMessage (models/message.py)
    et avec le filtre de _build_messages() dans AzureOpenAIService.
    """
    role: str       # "user" | "assistant" | "agent"
    content: str    # Texte du message


class ChatMessageRequest(BaseModel):
    """Corps de la requête POST /api/chat/message."""
    conversation_id: str
    message: str
    history: Optional[List[MessageItem]] = []
    utilisateur_id: Optional[str] = "anonymous"  # US 3.1 — identifiant client pour HandoffRequest


class ChatMessageResponse(BaseModel):
    """Corps de la réponse POST /api/chat/message."""
    conversation_id: str
    reponse: str
    sources: list
    tokens: dict
    type: str                        # "rag" | "salutation" | "aide" | "handoff_demande"
    etat: str
    handoff: bool = False            # True si handoff déclenché (score faible ou demande client)
    score_confiance: Optional[float] = None   # Score RAG (absent pour salutations/aide/handoff)
    handoff_id: Optional[str] = None          # ID de la HandoffRequest (présent si handoff=True)


# ─────────────────────────────────────────────────────────
# Route de test temporaire — Étape 2
# À désactiver après validation de la connexion Azure OpenAI
# ─────────────────────────────────────────────────────────

@router.post(
    "/test-openai",
    response_model=TestOpenAIResponse,
    summary="[TEST] Vérifier la connexion Azure OpenAI",
    description=(
        "Route temporaire pour tester la communication avec Azure OpenAI (gpt-4o). "
        "Appelle directement AzureOpenAIService sans passer par BotEngine ni RAG. "
        "À désactiver après validation."
    ),
)
def test_azure_openai(request: TestOpenAIRequest):
    """
    Envoie un message à Azure OpenAI et retourne la réponse.
    Utilisé uniquement pour valider la connexion à l'étape 2.
    La clé API n'apparaît jamais dans la réponse ni dans les logs.
    """
    try:
        service = AzureOpenAIService()
        result = service.generate_response(
            user_message=request.message,
            history=request.history,
        )
        return TestOpenAIResponse(
            reponse=result["reponse"],
            modele=result["modele"],
            tokens=result["tokens"],
        )
    except Exception as e:
        # Message d'erreur générique — la clé API n'est jamais exposée
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la communication avec Azure OpenAI. Vérifiez la configuration .env. ({type(e).__name__})",
        )


# ─────────────────────────────────────────────────────────
# Route principale — US 2.1 critère 3
# POST /api/chat/message — pipeline complet avec historique
# ─────────────────────────────────────────────────────────

@router.post(
    "/message",
    response_model=ChatMessageResponse,
    summary="Envoyer un message au chatbot",
    description=(
        "Envoie un message au chatbot Smartovate et reçoit une réponse IA. "
        "Pipeline complet : BotEngine → AzureAISearchService (RAG) → AzureOpenAIService (gpt-4o). "
        "L'historique de la conversation est transmis pour maintenir le contexte."
    ),
)
def envoyer_message(request: ChatMessageRequest):
    """
    Traite un message utilisateur via le BotEngine.

    Pipeline (US 2.1) :
    1. Convertit l'historique reçu en dicts compatibles avec _build_messages()
    2. Délègue au BotEngine.process_message()
    3. BotEngine appelle AzureAISearchService.search() → chunks RAG
    4. BotEngine appelle AzureOpenAIService.generate_response() → réponse gpt-4o
    5. Retourne la réponse avec ses sources, tokens et état

    Aucune clé API n'est manipulée dans cette route — tout passe par config.py.
    """
    try:
        engine = BotEngine()

        # Conversion des MessageItem en dicts attendus par BotEngine / _build_messages()
        # Format : [{"role": "user"|"assistant"|"agent", "content": "..."}]
        history = [
            {"role": item.role, "content": item.content}
            for item in request.history
        ]

        result = engine.process_message(
            message=request.message,
            conversation_id=request.conversation_id,
            history=history,
            utilisateur_id=request.utilisateur_id,
        )

        return ChatMessageResponse(
            conversation_id=request.conversation_id,
            reponse=result["reponse"],
            sources=result["sources"],
            tokens=result["tokens"],
            type=result["type"],
            etat=result["etat"],
            handoff=result.get("handoff", False),
            score_confiance=result.get("score_confiance"),
            handoff_id=result.get("handoff_id"),
        )

    except Exception as e:
        # Message d'erreur générique — aucune clé API ni donnée sensible exposée
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du traitement du message. ({type(e).__name__})",
        )


# ─────────────────────────────────────────────────────────
# Schéma US 2.2 — Réponse du message de bienvenue
# ─────────────────────────────────────────────────────────

class WelcomeResponse(BaseModel):
    """Réponse retournée par GET /api/chat/start."""
    message: str    # Texte du message de bienvenue (BotEngine.get_welcome_message())
    type: str       # Toujours "welcome"


# ─────────────────────────────────────────────────────────
# Route US 2.2 — Démarrage de conversation
# GET /api/chat/start — message de bienvenue proactif
# ─────────────────────────────────────────────────────────

@router.get(
    "/start",
    response_model=WelcomeResponse,
    summary="Démarrer une conversation — message de bienvenue",
    description=(
        "Retourne le message de bienvenue Smartovate à afficher à l'ouverture du chat. "
        "Aucun appel à Azure OpenAI ni à Azure AI Search n'est effectué. "
        "Le contenu est fourni par BotEngine.get_welcome_message()."
    ),
)
def demarrer_conversation():
    """
    Retourne le message de bienvenue proactif (US 2.2).

    Appelé par le frontend à l'ouverture de la fenêtre de chat,
    avant tout message utilisateur. Ne consomme aucun token Azure.
    """
    engine = BotEngine()
    return WelcomeResponse(
        message=engine.get_welcome_message(),
        type="welcome",
    )


# ─────────────────────────────────────────────────────────
# Routes Client — à implémenter aux étapes suivantes
# ─────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────
# Schéma US 3.1 — Requête handoff explicite
# ─────────────────────────────────────────────────────────

class HandoffRequest(BaseModel):
    """Corps de la requête POST /api/chat/handoff."""
    conversation_id: str
    utilisateur_id: Optional[str] = "anonymous"
    raison: Optional[str] = "Le client souhaite parler à un agent humain."


class HandoffResponse(BaseModel):
    """Réponse retournée par POST /api/chat/handoff."""
    conversation_id: str
    handoff_id: str
    message: str        # Message d'attente à afficher au client
    etat: str           # "EnAttenteAgent"
    handoff: bool       # Toujours True


# ─────────────────────────────────────────────────────────
# Route US 3.1 — Handoff explicite demandé par le client
# POST /api/chat/handoff
# ─────────────────────────────────────────────────────────

@router.post(
    "/handoff",
    response_model=HandoffResponse,
    summary="Demander un transfert vers un agent humain",
    description=(
        "Le client demande explicitement à être mis en relation avec un agent humain. "
        "Crée une HandoffRequest dans la file d'attente et retourne un message d'attente. "
        "Aucun appel Azure OpenAI ni Azure AI Search n'est effectué."
    ),
)
def demander_handoff(request: HandoffRequest):
    """
    Crée une HandoffRequest via BotEngine.request_handoff() (US 3.1).

    Le frontend peut appeler cet endpoint directement (bouton "Parler à un agent")
    ou il est déclenché automatiquement via process_message() quand l'intention
    est détectée dans le message.
    """
    from app.models.handoff_request import RaisonHandoff

    try:
        engine = BotEngine()
        handoff = engine.request_handoff(
            conversation_id=request.conversation_id,
            utilisateur_id=request.utilisateur_id,
            raison=RaisonHandoff.DEMANDE_CLIENT,
        )
        return HandoffResponse(
            conversation_id=request.conversation_id,
            handoff_id=handoff["id"],
            message=(
                "Votre demande de mise en relation a bien été enregistrée. 🙏\n\n"
                "Un conseiller Smartovate va prendre en charge votre conversation "
                "dans les plus brefs délais."
            ),
            etat="EnAttenteAgent",
            handoff=True,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la création de la demande de handoff. ({type(e).__name__})",
        )


@router.get("/conversation/{conversation_id}")
def get_conversation(conversation_id: str):
    """
    Récupère l'historique et l'état d'une conversation.
    TODO : implémenter lors de l'étape de persistance.
    """
    return {"detail": f"Route GET /api/chat/conversation/{conversation_id} — à implémenter"}
