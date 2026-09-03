# models/handoff_request.py — Entité HandoffRequest
# Représente une demande de transfert vers un agent humain
# Entité distincte — définie explicitement dans la conception UML

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class StatutHandoff(str, Enum):
    """
    États possibles d'une demande de handoff.
    - EN_ATTENTE       : demande créée, aucun agent n'a encore accepté
    - ACCEPTEE         : un agent a pris en charge la conversation
    - REJETEE          : demande rejetée (aucun agent disponible, etc.)
    - RESOLUE          : la conversation a été clôturée après handoff
    """
    EN_ATTENTE = "en_attente"
    ACCEPTEE = "acceptée"
    REJETEE = "rejetée"
    RESOLUE = "résolue"


class RaisonHandoff(str, Enum):
    """
    Raison ayant déclenché la demande de handoff — fidèle à la conception UML.
    """
    DEMANDE_CLIENT = "demande_client"       # Le Client a explicitement demandé un agent
    CONFIANCE_FAIBLE = "confiance_faible"   # Le score de confiance IA est trop faible


class HandoffRequest(BaseModel):
    """
    Entité représentant une demande de transfert (handoff) vers un agent humain.
    Créée par le BotEngine quand :
      - Le client demande explicitement à parler à un agent
      - Le score de confiance de la réponse IA est inférieur au seuil configuré
    """
    id: str = Field(..., description="Identifiant unique de la demande de handoff")
    conversation_id: str = Field(..., description="ID de la conversation concernée")
    utilisateur_id: str = Field(..., description="ID du client qui demande le transfert")

    raison: RaisonHandoff = Field(..., description="Raison du déclenchement du handoff")
    statut: StatutHandoff = Field(
        default=StatutHandoff.EN_ATTENTE,
        description="Statut actuel de la demande"
    )

    agent_id: Optional[str] = Field(
        None,
        description="ID de l'agent ayant accepté la demande (renseigné après acceptation)"
    )

    # Score de confiance ayant déclenché le handoff (si raison = CONFIANCE_FAIBLE)
    score_confiance_declencheur: Optional[float] = Field(None)

    date_creation: datetime = Field(default_factory=datetime.utcnow)
    date_prise_en_charge: Optional[datetime] = Field(None)

    class Config:
        use_enum_values = True
