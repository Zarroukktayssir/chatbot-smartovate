# config.py — Chargement centralisé de toutes les variables d'environnement
# Toutes les valeurs sensibles sont lues depuis le fichier .env (jamais hardcodées)

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Paramètres de l'application chargés depuis les variables d'environnement.
    Utilise pydantic-settings pour la validation automatique des types.
    """

    # --- Azure OpenAI ---
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-02-01"
    azure_openai_deployment: str = "gpt-4o"                          # Deployment chat
    azure_openai_embedding_deployment: str = "text-embedding-3-large"  # Deployment embedding (RAG)
    azure_openai_temperature: float = 0.1        # Température prévue dans la conception UML

    # --- Azure AI Search ---
    azure_search_endpoint: str = ""
    azure_search_api_key: str = ""
    azure_search_index_name: str = ""

    # --- Azure Bot Service / Bot Framework ---
    # Laisser vides en développement local (Bot Framework Emulator n'exige pas d'auth)
    # À remplir lors de la création de la ressource Azure Bot Service sur le portail Azure
    microsoft_app_id: str = ""
    microsoft_app_password: str = ""

    # --- Application ---
    app_name: str = "Smartovate Chatbot"
    app_version: str = "1.0.0"
    debug: bool = False

    # Seuil de confiance en dessous duquel un handoff vers un agent humain est déclenché
    app_confidence_threshold: float = 0.7

    class Config:
        # Lecture automatique depuis le fichier .env à la racine du backend
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Retourne une instance unique des paramètres (singleton via cache).
    À utiliser avec l'injection de dépendances FastAPI : Depends(get_settings)
    """
    return Settings()
