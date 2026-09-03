# models/message.py — Entité Message
# Représente un message individuel dans une conversation

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RoleMessage(str, Enum):
    """
    Émetteur possible d'un message.
    - user      : message envoyé par le Client
    - assistant : réponse générée par Azure OpenAI via BotEngine
    - agent     : message envoyé par un Agent Support humain
    """
    USER = "user"
    ASSISTANT = "assistant"
    AGENT = "agent"


class Message(BaseModel):
    """
    Entité représentant un message dans une conversation.
    Contient le contenu textuel, le rôle de l'émetteur et des métadonnées.
    """
    id: str = Field(..., description="Identifiant unique du message")
    conversation_id: str = Field(..., description="ID de la conversation parente")
    role: RoleMessage = Field(..., description="Émetteur du message")
    contenu: str = Field(..., description="Texte du message")

    # Métadonnées IA — renseignées uniquement pour les messages de type 'assistant'
    score_confiance: Optional[float] = Field(
        None,
        description="Score de confiance de la réponse IA (0.0 à 1.0)"
    )
    sources_documents: Optional[list] = Field(
        None,
        description="Liste des documents sources utilisés par Azure AI Search (RAG)"
    )

    date_creation: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
