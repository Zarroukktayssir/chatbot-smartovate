# models/agent_humain.py — Entité AgentHumain
# Représente un Agent Support humain qui peut prendre en charge des conversations

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class StatutAgent(str, Enum):
    """
    Disponibilité de l'agent humain.
    """
    DISPONIBLE = "disponible"
    OCCUPE = "occupé"
    HORS_LIGNE = "hors_ligne"


class AgentHumain(BaseModel):
    """
    Entité représentant un Agent Support humain.
    Un agent peut consulter la file d'attente des handoffs,
    prendre en charge une conversation et répondre directement au client.
    """
    id: str = Field(..., description="Identifiant unique de l'agent")
    nom: str = Field(..., description="Nom complet de l'agent")
    email: str = Field(..., description="Email de l'agent")
    statut: StatutAgent = Field(
        default=StatutAgent.DISPONIBLE,
        description="Disponibilité actuelle de l'agent"
    )

    # IDs des conversations actuellement prises en charge
    conversations_actives: List[str] = Field(default_factory=list)

    date_creation: datetime = Field(default_factory=datetime.utcnow)
    derniere_activite: Optional[datetime] = Field(None)

    class Config:
        use_enum_values = True
