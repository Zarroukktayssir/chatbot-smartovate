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


class ChatMessageResponse(BaseModel):
    """Corps de la réponse POST /api/chat/message."""
    conversation_id: str
    reponse: str
    sources: list
    tokens: dict
    type: str               # "rag" | "salutation" | "aide"
    etat: str
    handoff: bool = False   # True si score RAG < seuil de confiance (handoff Sprint 3)
    score_confiance: Optional[float] = None  # Meilleur score RAG (absent pour salutations/aide)


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
        )

    except Exception as e:
        # Message d'erreur générique — aucune clé API ni donnée sensible exposée
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du traitement du message. ({type(e).__name__})",
        )


# ─────────────────────────────────────────────────────────
# Routes Client — à implémenter aux étapes suivantes
# ─────────────────────────────────────────────────────────

@router.post("/handoff")
def demander_handoff():
    """
    Le Client demande explicitement à être transféré vers un Agent humain.
    TODO : implémenter lors de l'étape de gestion du handoff.
    """
    return {"detail": "Route POST /api/chat/handoff — à implémenter"}


@router.get("/conversation/{conversation_id}")
def get_conversation(conversation_id: str):
    """
    Récupère l'historique et l'état d'une conversation.
    TODO : implémenter lors de l'étape de persistance.
    """
    return {"detail": f"Route GET /api/chat/conversation/{conversation_id} — à implémenter"}
