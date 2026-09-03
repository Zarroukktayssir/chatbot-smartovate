# services/azure_ai_search_service.py — AzureAISearchService
# Responsable de la recherche de documents pertinents dans Azure AI Search
# Ce service est appelé par le BotEngine EN PREMIER, avant Azure OpenAI (pipeline RAG)

from app.config import get_settings

settings = get_settings()


class AzureAISearchService:
    """
    Service d'intégration avec Azure AI Search.

    Responsabilités :
    - Initialiser le client Azure AI Search (à partir des variables d'environnement)
    - Rechercher des documents pertinents à partir d'une requête utilisateur
    - Retourner les chunks de documents pour enrichir le prompt Azure OpenAI

    Position dans le pipeline RAG :
      BotEngine → AzureAISearchService (ici) → AzureOpenAIService

    Configuration (via .env) :
    - AZURE_SEARCH_ENDPOINT   : endpoint de la ressource Azure AI Search
    - AZURE_SEARCH_API_KEY    : clé API (jamais hardcodée)
    - AZURE_SEARCH_INDEX_NAME : nom de l'index de documents
    """

    def __init__(self):
        # Les paramètres viennent tous de la configuration (.env)
        self.endpoint = settings.azure_search_endpoint
        self.index_name = settings.azure_search_index_name
        self.client = None  # Sera initialisé lors de l'étape de connexion Azure

    def search(self, query: str, top_k: int = 5) -> list:
        """
        Recherche les documents les plus pertinents pour une requête donnée.

        Args:
            query : question ou message de l'utilisateur
            top_k : nombre maximum de documents à retourner (défaut: 5)

        Returns:
            Liste de documents pertinents (dicts avec 'contenu', 'titre', 'score', etc.)

        Note: La logique complète sera implémentée lors de l'étape de connexion Azure.
        """
        # TODO : implémenter lors de l'étape de connexion Azure AI Search
        raise NotImplementedError("AzureAISearchService.search sera implémenté à l'étape Azure")

    def index_document(self, document: dict) -> bool:
        """
        Indexe un document dans Azure AI Search.
        Appelé par les routes Admin lors de l'ajout de nouveaux documents.

        Args:
            document : dict contenant les champs du document à indexer

        Returns:
            True si l'indexation a réussi, False sinon

        Note: La logique complète sera implémentée lors de l'étape de connexion Azure.
        """
        # TODO : implémenter lors de l'étape de connexion Azure AI Search
        raise NotImplementedError("AzureAISearchService.index_document sera implémenté à l'étape Azure")
