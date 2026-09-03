# routes/admin.py — Routes Administration
# Endpoints accessibles par l'acteur Administrateur de la conception UML

from fastapi import APIRouter

router = APIRouter()


@router.post("/documents/index")
def indexer_document():
    """
    Indexe un nouveau document dans Azure AI Search.
    Utilisé par l'Administrateur pour alimenter la base de connaissances (RAG).
    Appelle AzureAISearchService.index_document() via le BotEngine.

    TODO : implémenter lors de l'étape de connexion Azure AI Search.
    """
    return {"detail": "Route POST /api/admin/documents/index — à implémenter"}


@router.get("/documents")
def lister_documents():
    """
    Liste tous les documents indexés dans la base de connaissances.

    TODO : implémenter lors de l'étape de connexion Azure AI Search.
    """
    return {"detail": "Route GET /api/admin/documents — à implémenter"}


@router.get("/metrics")
def consulter_metriques():
    """
    Retourne les métriques du chatbot (conversations, handoffs, scores, etc.)
    Accessible uniquement par l'Administrateur.

    TODO : implémenter lors de l'étape des métriques.
    """
    return {"detail": "Route GET /api/admin/metrics — à implémenter"}
