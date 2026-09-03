# models/document.py — Entité Document
# Représente un document indexé dans Azure AI Search pour le pipeline RAG

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class Document(BaseModel):
    """
    Entité représentant un document de la base de connaissances.
    Ces documents sont indexés dans Azure AI Search et utilisés
    par AzureAISearchService pour enrichir les réponses IA (pipeline RAG).
    """
    id: str = Field(..., description="Identifiant unique du document")
    titre: str = Field(..., description="Titre du document")
    contenu: str = Field(..., description="Contenu textuel du document")
    source: Optional[str] = Field(None, description="Origine du document (URL, fichier, etc.)")

    # Métadonnées pour le filtrage et la recherche
    tags: List[str] = Field(default_factory=list, description="Étiquettes thématiques")
    categorie: Optional[str] = Field(None, description="Catégorie du document")

    # Statut d'indexation dans Azure AI Search
    indexe: bool = Field(default=False, description="True si le document a été indexé dans Azure AI Search")
    date_indexation: Optional[datetime] = Field(None)

    date_creation: datetime = Field(default_factory=datetime.utcnow)
    date_modification: Optional[datetime] = Field(None)
