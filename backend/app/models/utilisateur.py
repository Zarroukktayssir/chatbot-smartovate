# models/utilisateur.py — Entité Utilisateur
# Représente tout utilisateur du système (Client, Agent, Admin)

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RoleUtilisateur(str, Enum):
    """
    Rôles possibles dans le système — fidèles aux acteurs de la conception UML.
    """
    CLIENT = "client"
    AGENT_SUPPORT = "agent_support"
    ADMINISTRATEUR = "administrateur"


class Utilisateur(BaseModel):
    """
    Entité principale représentant un utilisateur du chatbot.
    Un utilisateur peut être un Client, un Agent Support ou un Administrateur.
    """
    id: str = Field(..., description="Identifiant unique de l'utilisateur")
    nom: str = Field(..., description="Nom complet de l'utilisateur")
    email: Optional[str] = Field(None, description="Adresse email")
    role: RoleUtilisateur = Field(RoleUtilisateur.CLIENT, description="Rôle dans le système")
    date_creation: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
