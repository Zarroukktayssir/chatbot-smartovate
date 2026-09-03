# services/azure_ai_search_service.py — AzureAISearchService
# Responsable de la recherche vectorielle dans Azure AI Search (pipeline RAG)
# Appelé par le BotEngine EN PREMIER, avant Azure OpenAI

from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential

from app.config import get_settings

settings = get_settings()


class AzureAISearchService:
    """
    Service d'intégration avec Azure AI Search.

    Pipeline RAG :
      BotEngine
        → AzureAISearchService.search(query)   ← CE FICHIER
            → génère l'embedding de la requête (text-embedding-3-large)
            → recherche vectorielle dans smartovate-index
            → retourne les chunks pertinents
        → AzureOpenAIService.generate_response(message + chunks)

    Configuration lue depuis .env (jamais hardcodée) :
    - AZURE_SEARCH_ENDPOINT
    - AZURE_SEARCH_API_KEY
    - AZURE_SEARCH_INDEX_NAME
    - AZURE_OPENAI_ENDPOINT             (pour générer l'embedding de la requête)
    - AZURE_OPENAI_API_KEY
    - AZURE_OPENAI_EMBEDDING_DEPLOYMENT (text-embedding-3-large)
    """

    def __init__(self):
        # ── Client Azure AI Search ──────────────────────────────────────
        # Utilise AzureKeyCredential — la clé vient du .env via config.py
        self.search_client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_api_key),
        )

        # ── Client Azure OpenAI pour les embeddings ─────────────────────
        # On réutilise la même ressource OpenAI que pour gpt-4o
        self.openai_client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self.embedding_deployment = settings.azure_openai_embedding_deployment

    def search(self, query: str, top_k: int = 5) -> list:
        """
        Recherche les documents les plus pertinents pour une requête donnée.

        Étapes internes :
        1. Générer l'embedding vectoriel de la requête (text-embedding-3-large)
        2. Lancer une recherche vectorielle sur smartovate-index (HNSW)
        3. Retourner les top_k chunks les plus proches sémantiquement

        Args:
            query : question ou message de l'utilisateur
            top_k : nombre maximum de documents à retourner (défaut: 5)

        Returns:
            Liste de dicts, chacun contenant :
            - 'contenu'   : texte du chunk
            - 'source'    : nom du fichier PDF d'origine
            - 'categorie' : catégorie du document (ex: services_cloud)
            - 'page'      : numéro de page dans le PDF
            - 'score'     : score de pertinence vectorielle
        """
        # ── Étape 1 : Générer l'embedding de la requête ─────────────────
        embedding_response = self.openai_client.embeddings.create(
            input=[query],
            model=self.embedding_deployment,  # text-embedding-3-large depuis .env
        )
        query_vector = embedding_response.data[0].embedding

        # ── Étape 2 : Recherche vectorielle dans Azure AI Search ─────────
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="embedding",       # Champ vectoriel défini lors de l'ingestion
        )

        results = self.search_client.search(
            search_text=None,         # Recherche purement vectorielle (pas full-text)
            vector_queries=[vector_query],
            select=["id", "contenu", "source", "categorie", "page"],
            top=top_k,
        )

        # ── Étape 3 : Formater et retourner les résultats ────────────────
        documents = []
        for result in results:
            documents.append({
                "contenu":   result.get("contenu", ""),
                "source":    result.get("source", ""),
                "categorie": result.get("categorie", ""),
                "page":      result.get("page", 0),
                "score":     result.get("@search.score", 0.0),
            })

        return documents

    def index_document(self, document: dict) -> bool:
        """
        Indexe un document dans Azure AI Search.
        Appelé par les routes Admin lors de l'ajout de nouveaux documents.

        Args:
            document : dict avec les champs : id, contenu, embedding, source, categorie, page

        Returns:
            True si l'indexation a réussi, False sinon
        """
        try:
            result = self.search_client.upload_documents(documents=[document])
            return all(r.succeeded for r in result)
        except Exception:
            return False
