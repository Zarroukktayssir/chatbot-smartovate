# routes/agent.py — Routes Agent Support (US 3.1)
# Endpoints accessibles par l'acteur Agent Support de la conception UML.
#
# Interface de simulation Sprint 3 :
# - Consulter la file d'attente des handoffs
# - Accepter (takeover) une conversation
# - Envoyer un message au client

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services import handoff_store

router = APIRouter()


# ─────────────────────────────────────────────────────────
# Schémas US 3.1
# ─────────────────────────────────────────────────────────

class TakeoverRequest(BaseModel):
    """Corps de la requête POST /api/agent/takeover/{conversation_id}."""
    agent_id: str   # Identifiant de l'agent qui accepte la conversation


class ReplyRequest(BaseModel):
    """Corps de la requête POST /api/agent/reply/{conversation_id}."""
    agent_id: str   # Identifiant de l'agent qui envoie le message
    contenu: str    # Texte du message envoyé au client


# ─────────────────────────────────────────────────────────
# GET /api/agent/queue — File d'attente des handoffs
# ─────────────────────────────────────────────────────────

@router.get(
    "/queue",
    summary="Consulter la file d'attente des handoffs",
    description=(
        "Retourne toutes les HandoffRequests avec statut EN_ATTENTE. "
        "Permet à l'agent de voir quelles conversations nécessitent une prise en charge."
    ),
)
def get_file_attente():
    """
    Liste toutes les demandes de handoff en attente (US 3.1).

    Retourne :
    - count   : nombre de demandes en attente
    - handoffs : liste des HandoffRequests sérialisées
    """
    demandes = handoff_store.get_file_attente()
    return {
        "count": len(demandes),
        "handoffs": [h.model_dump() for h in demandes],
    }


# ─────────────────────────────────────────────────────────
# POST /api/agent/takeover/{conversation_id} — Prise en charge
# ─────────────────────────────────────────────────────────

@router.post(
    "/takeover/{conversation_id}",
    summary="Prendre en charge une conversation",
    description=(
        "L'agent accepte une HandoffRequest. "
        "Le statut passe à ACCEPTÉE et l'agent est associé à la conversation."
    ),
)
def prendre_en_charge(conversation_id: str, request: TakeoverRequest):
    """
    Accepte la HandoffRequest pour une conversation donnée (US 3.1).

    - Marque la HandoffRequest comme ACCEPTÉE.
    - Enregistre l'agent_id dans la HandoffRequest.
    - Retourne la HandoffRequest mise à jour.
    """
    handoff = handoff_store.accepter_handoff(
        conversation_id=conversation_id,
        agent_id=request.agent_id,
    )
    if not handoff:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune HandoffRequest trouvée pour la conversation '{conversation_id}'.",
        )
    return {
        "message": f"Conversation '{conversation_id}' prise en charge par l'agent '{request.agent_id}'.",
        "handoff": handoff.model_dump(),
    }


# ─────────────────────────────────────────────────────────
# POST /api/agent/reply/{conversation_id} — Réponse agent
# ─────────────────────────────────────────────────────────

@router.post(
    "/reply/{conversation_id}",
    summary="Envoyer un message au client",
    description=(
        "L'agent envoie un message texte au client dans la conversation. "
        "Le message est stocké en mémoire et consultable par le client."
    ),
)
def repondre_client(conversation_id: str, request: ReplyRequest):
    """
    Enregistre un message de l'agent dans la conversation (US 3.1).

    Vérifie que la HandoffRequest existe avant d'accepter le message.
    """
    handoff = handoff_store.get_handoff(conversation_id)
    if not handoff:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune HandoffRequest trouvée pour la conversation '{conversation_id}'.",
        )

    message = handoff_store.ajouter_message_agent(
        conversation_id=conversation_id,
        agent_id=request.agent_id,
        contenu=request.contenu,
    )
    return {
        "message": "Message envoyé au client.",
        "detail": message,
    }


# ─────────────────────────────────────────────────────────
# GET /api/agent/messages/{conversation_id} — Messages agent
# ─────────────────────────────────────────────────────────

@router.get(
    "/messages/{conversation_id}",
    summary="Lire les messages agent d'une conversation",
    description=(
        "Retourne tous les messages envoyés par l'agent au client "
        "pour une conversation donnée."
    ),
)
def get_messages_agent(conversation_id: str):
    """
    Retourne l'historique des messages agent pour une conversation (US 3.1).
    Utilisé par le client pour récupérer les réponses de l'agent.
    """
    messages = handoff_store.get_messages_agent(conversation_id)
    return {
        "conversation_id": conversation_id,
        "count": len(messages),
        "messages": messages,
    }
