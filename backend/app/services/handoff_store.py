# services/handoff_store.py — Store en mémoire des HandoffRequests (simulation Sprint 3)
#
# Rôle : stocker et gérer les demandes de handoff actives en mémoire.
# Pas de base de données — simulation complète via des dicts Python.
# Partagé entre BotEngine (création) et routes/agent.py (consultation/mise à jour).
#
# Structure du store :
#   _handoff_requests : dict[conversation_id → HandoffRequest]
#   _agent_messages   : dict[conversation_id → list[dict]]  (messages agent → client)

from datetime import datetime
from typing import Optional
import uuid

from app.models.handoff_request import HandoffRequest, StatutHandoff, RaisonHandoff


# ── Stores en mémoire ─────────────────────────────────────────────────────────
# Clé : conversation_id  |  Valeur : HandoffRequest
_handoff_requests: dict[str, HandoffRequest] = {}

# Clé : conversation_id  |  Valeur : liste de messages {"agent_id", "contenu", "date"}
_agent_messages: dict[str, list] = {}


# ── Opérations sur les HandoffRequests ───────────────────────────────────────

def creer_handoff(
    conversation_id: str,
    utilisateur_id: str,
    raison: RaisonHandoff,
    score_confiance: Optional[float] = None,
) -> HandoffRequest:
    """
    Crée et enregistre une nouvelle HandoffRequest.
    Si une demande existe déjà pour cette conversation, elle est remplacée.
    """
    handoff = HandoffRequest(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        utilisateur_id=utilisateur_id,
        raison=raison,
        score_confiance_declencheur=score_confiance,
    )
    _handoff_requests[conversation_id] = handoff
    _agent_messages.setdefault(conversation_id, [])
    return handoff


def get_handoff(conversation_id: str) -> Optional[HandoffRequest]:
    """Retourne la HandoffRequest associée à une conversation, ou None."""
    return _handoff_requests.get(conversation_id)


def get_file_attente() -> list[HandoffRequest]:
    """Retourne toutes les HandoffRequests avec statut EN_ATTENTE."""
    return [
        h for h in _handoff_requests.values()
        if h.statut == StatutHandoff.EN_ATTENTE
    ]


def accepter_handoff(conversation_id: str, agent_id: str) -> Optional[HandoffRequest]:
    """
    Marque la HandoffRequest comme ACCEPTÉE et enregistre l'agent.
    Retourne la HandoffRequest mise à jour, ou None si introuvable.
    """
    handoff = _handoff_requests.get(conversation_id)
    if not handoff:
        return None
    handoff.statut = StatutHandoff.ACCEPTEE
    handoff.agent_id = agent_id
    handoff.date_prise_en_charge = datetime.utcnow()
    return handoff


def ajouter_message_agent(conversation_id: str, agent_id: str, contenu: str) -> dict:
    """
    Enregistre un message envoyé par l'agent au client.
    Retourne le message créé.
    """
    message = {
        "agent_id": agent_id,
        "contenu": contenu,
        "date": datetime.utcnow().isoformat(),
    }
    _agent_messages.setdefault(conversation_id, []).append(message)
    return message


def get_messages_agent(conversation_id: str) -> list:
    """Retourne tous les messages agent pour une conversation."""
    return _agent_messages.get(conversation_id, [])


def resoudre_handoff(conversation_id: str) -> Optional[HandoffRequest]:
    """
    Marque la HandoffRequest comme RÉSOLUE (conversation clôturée).
    Retourne la HandoffRequest mise à jour, ou None si introuvable.
    """
    handoff = _handoff_requests.get(conversation_id)
    if not handoff:
        return None
    handoff.statut = StatutHandoff.RESOLUE
    return handoff
