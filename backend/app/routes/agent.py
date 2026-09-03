# routes/agent.py — Routes Agent Support
# Endpoints accessibles par l'acteur Agent Support de la conception UML

from fastapi import APIRouter

router = APIRouter()


@router.get("/queue")
def get_file_attente():
    """
    Retourne la liste des HandoffRequests en attente d'un agent.
    L'Agent Support consulte cette file pour voir les conversations à prendre en charge.

    TODO : implémenter lors de l'étape de gestion du handoff.
    """
    return {"detail": "Route GET /api/agent/queue — à implémenter"}


@router.post("/takeover/{conversation_id}")
def prendre_en_charge(conversation_id: str):
    """
    L'Agent accepte une demande de handoff et prend en charge la conversation.
    La conversation passe en état PriseEnChargeAgent.

    TODO : implémenter lors de l'étape de gestion du handoff.
    """
    return {"detail": f"Route POST /api/agent/takeover/{conversation_id} — à implémenter"}


@router.post("/reply/{conversation_id}")
def repondre_client(conversation_id: str):
    """
    L'Agent envoie un message direct au Client dans la conversation.

    TODO : implémenter lors de l'étape de gestion du handoff.
    """
    return {"detail": f"Route POST /api/agent/reply/{conversation_id} — à implémenter"}
