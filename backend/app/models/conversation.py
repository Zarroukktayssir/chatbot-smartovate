# models/conversation.py — Entité Conversation + Machine à états
# Les états respectent exactement la conception UML

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class EtatConversation(str, Enum):
    """
    États possibles d'une conversation — définis dans la conception UML.
    La machine à états est pilotée par le BotEngine.

    Transitions prévues :
      Initiée
        → EnAttenteMessage  (conversation ouverte, attente du premier message)
        → EnTraitement      (message reçu, pipeline RAG+IA en cours)
        → EnAttenteAgent    (handoff demandé ou confiance trop faible)
        → PriseEnChargeAgent (un agent humain a accepté la conversation)
        → Clôturée          (conversation terminée)
    """
    INITIEE = "Initiée"
    EN_ATTENTE_MESSAGE = "EnAttenteMessage"
    EN_TRAITEMENT = "EnTraitement"
    EN_ATTENTE_AGENT = "EnAttenteAgent"
    PRISE_EN_CHARGE_AGENT = "PriseEnChargeAgent"
    CLOTUREE = "Clôturée"


class Conversation(BaseModel):
    """
    Entité représentant une session de conversation entre un utilisateur et le chatbot.
    Chaque conversation possède un état géré par le BotEngine.
    """
    id: str = Field(..., description="Identifiant unique de la conversation")
    utilisateur_id: str = Field(..., description="ID de l'utilisateur (Client) initiateur")
    etat: EtatConversation = Field(
        default=EtatConversation.INITIEE,
        description="État actuel dans la machine à états"
    )
    agent_id: Optional[str] = Field(
        None,
        description="ID de l'agent humain si la conversation est prise en charge"
    )
    # Les IDs des messages sont stockés ici ; les objets Message sont dans models/message.py
    message_ids: List[str] = Field(default_factory=list)

    date_creation: datetime = Field(default_factory=datetime.utcnow)
    date_derniere_activite: datetime = Field(default_factory=datetime.utcnow)
    date_cloture: Optional[datetime] = Field(None)

    class Config:
        use_enum_values = True
