# services/azure_ai_search_service.py — AzureAISearchService
# Responsable de la recherche hybride (vectorielle + keyword) dans Azure AI Search
# Appelé par le BotEngine EN PREMIER, avant Azure OpenAI

import logging
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential

from app.config import get_settings

settings = get_settings()

# Logger dédié au service de recherche — activé en DEBUG pour diagnostiquer le RAG
logger = logging.getLogger("smartovate.search")


class AzureAISearchService:
    """
    Service d'intégration avec Azure AI Search.

    Pipeline RAG :
      BotEngine
        → AzureAISearchService.search(query)   ← CE FICHIER
            → génère l'embedding de la requête (text-embedding-3-large)
            → recherche HYBRIDE : keyword BM25 + vectorielle HNSW
            → retourne les chunks les plus pertinents (score RRF)
        → AzureOpenAIService.generate_response(message + chunks)

    Pourquoi la recherche hybride ?
    - La recherche vectorielle pure est bonne pour les reformulations sémantiques,
      mais son score cosinus brut est souvent compris entre 0.5 et 0.7 pour des
      passages proches mais non identiques. Le seuil de 0.7 les élimine.
    - La recherche hybride (BM25 + vecteur) utilise le Reciprocal Rank Fusion (RRF)
      d'Azure, qui combine les deux signaux et produit un score normalisé plus stable,
      permettant de retrouver les bonnes reformulations.

    Configuration lue depuis .env :
    - AZURE_SEARCH_ENDPOINT
    - AZURE_SEARCH_API_KEY
    - AZURE_SEARCH_INDEX_NAME
    - AZURE_OPENAI_ENDPOINT
    - AZURE_OPENAI_API_KEY
    - AZURE_OPENAI_EMBEDDING_DEPLOYMENT (text-embedding-3-large)
    """

    def __init__(self):
        # ── Client Azure AI Search ──────────────────────────────────────
        self.search_client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_api_key),
        )

        # ── Client Azure OpenAI pour les embeddings ─────────────────────
        # Même modèle que l'ingestion : text-embedding-3-large
        self.openai_client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self.embedding_deployment = settings.azure_openai_embedding_deployment

    def search(self, query: str, top_k: int = 5) -> list:
        """
        Recherche hybride (keyword BM25 + vectorielle HNSW) pour une requête donnée.

        Étapes :
        1. Générer l'embedding de la requête (même modèle que l'ingestion)
        2. Lancer une recherche hybride : BM25 sur le champ 'contenu' + HNSW sur 'embedding'
        3. Azure AI Search combine les deux via Reciprocal Rank Fusion (RRF)
        4. Retourner les top_k résultats avec leur score RRF

        Pourquoi hybride plutôt que vectorielle pure :
        - Vectorielle pure : capte la similarité sémantique mais score souvent < 0.7
          pour des reformulations ("signer contrat" ≈ "activer compte")
        - BM25 keyword : capte les correspondances lexicales exactes
        - Hybride RRF : combine les deux, score plus stable entre 0.01 et 1.0

        Args:
            query : question ou message de l'utilisateur
            top_k : nombre maximum de résultats (défaut: 5)

        Returns:
            Liste de dicts : contenu, source, categorie, page, score
        """
        logger.debug("─" * 60)
        logger.debug(f"[SEARCH] Requête : '{query}'")
        logger.debug(f"[SEARCH] Modèle embedding : {self.embedding_deployment}")
        logger.debug(f"[SEARCH] top_k : {top_k}")

        # ── Étape 1 : Embedding de la requête ───────────────────────────
        # CRITIQUE : utiliser le MÊME modèle que lors de l'ingestion
        # (text-embedding-3-large via AZURE_OPENAI_EMBEDDING_DEPLOYMENT)
        embedding_response = self.openai_client.embeddings.create(
            input=[query],
            model=self.embedding_deployment,
        )
        query_vector = embedding_response.data[0].embedding
        logger.debug(f"[SEARCH] Embedding généré ({len(query_vector)} dimensions)")

        # ── Étape 2 : Recherche hybride ──────────────────────────────────
        # search_text = requête BM25 keyword sur le champ 'contenu' (analyseur fr.microsoft)
        # vector_queries = recherche vectorielle HNSW sur le champ 'embedding'
        # Azure AI Search combine automatiquement via RRF quand les deux sont fournis.
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="embedding",
        )

        results = self.search_client.search(
            search_text=query,          # BM25 keyword — NOUVEAU (était None avant)
            vector_queries=[vector_query],
            select=["id", "contenu", "source", "categorie", "page"],
            top=top_k,
        )

        # ── Étape 3 : Formater et logger les résultats ───────────────────
        documents = []
        for i, result in enumerate(results):
            score = result.get("@search.score", 0.0)
            doc = {
                "contenu":   result.get("contenu", ""),
                "source":    result.get("source", ""),
                "categorie": result.get("categorie", ""),
                "page":      result.get("page", 0),
                "score":     score,
            }
            documents.append(doc)

            # Logs de diagnostic — visibles si le niveau DEBUG est activé
            logger.debug(f"[SEARCH] Résultat #{i+1}")
            logger.debug(f"  Source    : {doc['source']}")
            logger.debug(f"  Page      : {doc['page']}")
            logger.debug(f"  Score RRF : {score:.4f}")
            logger.debug(f"  Extrait   : {doc['contenu'][:120]}…")

        if documents:
            logger.debug(f"[SEARCH] Meilleur score : {documents[0]['score']:.4f}")
        else:
            logger.debug("[SEARCH] Aucun résultat retourné par Azure AI Search")

        logger.debug("─" * 60)
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
