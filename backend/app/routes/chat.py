# routes/chat.py — Routes Client (WebChat)
# Endpoints accessibles par l'acteur Client de la conception UML

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.services.azure_openai_service import AzureOpenAIService

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
# Routes Client — à implémenter aux étapes suivantes
# ─────────────────────────────────────────────────────────

@router.post("/message")
def envoyer_message():
    """
    Envoie un message au chatbot et reçoit une réponse IA.
    Pipeline : BotEngine → AzureAISearchService → AzureOpenAIService → réponse
    TODO : implémenter lors de l'étape BotEngine complet.
    """
    return {"detail": "Route POST /api/chat/message — à implémenter"}


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
