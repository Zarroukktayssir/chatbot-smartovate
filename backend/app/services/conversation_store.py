# services/conversation_store.py — Store en mémoire des conversations et messages
#
# Rôle : stocker l'historique des conversations et des messages pendant la session.
# Pas de base de données — simulation complète via des dicts Python.
#
# Structure :
#   _conversations : dict[conversation_id → Conversation]
#   _messages      : dict[conversation_id → list[Message]]

from datetime import datetime
from typing import Optional
import uuid

from app.models.conversation import Conversation, EtatConversation
from app.models.message import Message, RoleMessage


# ── Stores en mémoire ─────────────────────────────────────────────────────────
_conversations: dict[str, Conversation] = {}
_messages: dict[str, list] = {}     # liste de dicts sérialisables


def get_or_create_conversation(conversation_id: str, utilisateur_id: str = "anonymous") -> Conversation:
    """
    Retourne la conversation existante ou en crée une nouvelle.
    """
    if conversation_id not in _conversations:
        conv = Conversation(
            id=conversation_id,
            utilisateur_id=utilisateur_id,
            etat=EtatConversation.EN_ATTENTE_MESSAGE,
        )
        _conversations[conversation_id] = conv
        _messages[conversation_id] = []
    return _conversations[conversation_id]


def update_conversation_state(conversation_id: str, etat: EtatConversation):
    """Met à jour l'état d'une conversation."""
    conv = _conversations.get(conversation_id)
    if conv:
        conv.etat = etat
        conv.date_derniere_activite = datetime.utcnow()


def add_message(
    conversation_id: str,
    role: str,
    contenu: str,
    score_confiance: Optional[float] = None,
    sources_documents: Optional[list] = None,
) -> dict:
    """
    Enregistre un message dans la conversation.
    Retourne le message créé sous forme de dict.
    """
    msg = {
        "id":                str(uuid.uuid4()),
        "conversation_id":   conversation_id,
        "role":              role,
        "contenu":           contenu,
        "score_confiance":   score_confiance,
        "sources_documents": sources_documents or [],
        "date_creation":     datetime.utcnow().isoformat(),
    }
    _messages.setdefault(conversation_id, []).append(msg)

    # Mettre à jour la date de dernière activité
    conv = _conversations.get(conversation_id)
    if conv:
        conv.date_derniere_activite = datetime.utcnow()

    return msg


def get_conversation_history(conversation_id: str) -> list:
    """Retourne l'historique des messages d'une conversation."""
    return _messages.get(conversation_id, [])


def get_conversation(conversation_id: str) -> Optional[Conversation]:
    """Retourne la Conversation ou None si elle n'existe pas."""
    return _conversations.get(conversation_id)
