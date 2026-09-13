# routes/admin.py — Routes Administration
# Endpoints accessibles par l'acteur Administrateur de la conception UML

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
import uuid

from app.services.azure_ai_search_service import AzureAISearchService
from app.services.handoff_store import _handoff_requests

router = APIRouter()


# ─────────────────────────────────────────────────────────
# Schéma pour l'indexation manuelle d'un document texte
# ─────────────────────────────────────────────────────────

class IndexDocumentRequest(BaseModel):
    """Corps de la requête POST /api/admin/documents/index."""
    contenu: str                          # Texte brut à indexer
    source: str                           # Nom du fichier source
    categorie: Optional[str] = "general" # Catégorie du document
    page: Optional[int] = 1              # Numéro de page


# ─────────────────────────────────────────────────────────
# POST /api/admin/documents/index — Indexation d'un document
# ─────────────────────────────────────────────────────────

@router.post(
    "/documents/index",
    summary="Indexer un document dans la base de connaissances",
    description=(
        "Indexe un nouveau document texte dans Azure AI Search. "
        "Génère automatiquement l'embedding via Azure OpenAI (text-embedding-3-large) "
        "et l'enregistre dans l'index smartovate-index."
    ),
)
def indexer_document(request: IndexDocumentRequest):
    """
    Indexe un chunk de texte dans Azure AI Search.

    Génère l'embedding du contenu fourni via AzureAISearchService,
    puis l'envoie dans l'index. Utilisé par l'Administrateur pour enrichir
    la base de connaissances sans relancer le script d'ingestion complet.
    """
    if not request.contenu.strip():
        raise HTTPException(status_code=400, detail="Le contenu du document ne peut pas être vide.")

    try:
        service = AzureAISearchService()

        # Génération de l'embedding via le client OpenAI du service
        embedding_response = service.openai_client.embeddings.create(
            input=[request.contenu],
            model=service.embedding_deployment,
        )
        embedding_vector = embedding_response.data[0].embedding

        doc_id = str(uuid.uuid4()).replace("-", "")

        document = {
            "id":        doc_id,
            "contenu":   request.contenu,
            "embedding": embedding_vector,
            "source":    request.source,
            "categorie": request.categorie,
            "page":      request.page,
        }

        success = service.index_document(document)

        if not success:
            raise HTTPException(
                status_code=502,
                detail="L'indexation a échoué dans Azure AI Search.",
            )

        return {
            "message": "Document indexé avec succès.",
            "id": doc_id,
            "source": request.source,
            "categorie": request.categorie,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'indexation du document. ({type(e).__name__})",
        )


# ─────────────────────────────────────────────────────────
# GET /api/admin/documents — Liste des documents indexés
# ─────────────────────────────────────────────────────────

@router.get(
    "/documents",
    summary="Lister les documents de la base de connaissances",
    description=(
        "Retourne les documents présents dans Azure AI Search "
        "via une recherche générique. Utile pour vérifier que l'ingestion "
        "s'est bien déroulée."
    ),
)
def lister_documents(top: int = 10):
    """
    Retourne les top N documents de l'index Azure AI Search.

    Effectue une recherche full-text vide (*) pour lister les documents
    récents. Le paramètre 'top' contrôle le nombre de résultats (max 50).
    """
    top = min(max(1, top), 50)  # Clamp entre 1 et 50

    try:
        service = AzureAISearchService()

        # Recherche générique sans filtre — retourne les premiers documents de l'index
        results = service.search_client.search(
            search_text="*",
            select=["id", "source", "categorie", "page"],
            top=top,
        )

        documents = [
            {
                "id":        r.get("id", ""),
                "source":    r.get("source", ""),
                "categorie": r.get("categorie", ""),
                "page":      r.get("page", 0),
            }
            for r in results
        ]

        return {
            "count": len(documents),
            "documents": documents,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération des documents. ({type(e).__name__})",
        )


# ─────────────────────────────────────────────────────────
# GET /api/admin/metrics — Métriques du chatbot
# ─────────────────────────────────────────────────────────

@router.get(
    "/metrics",
    summary="Métriques du chatbot",
    description=(
        "Retourne les métriques opérationnelles du chatbot : "
        "nombre de handoffs en attente, handoffs acceptés, et statut global."
    ),
)
def consulter_metriques():
    """
    Retourne les métriques en temps réel du chatbot.

    Les données sont issues du store en mémoire (handoff_store).
    En production, ces données seraient persistées en base de données.
    """
    from app.models.handoff_request import StatutHandoff

    all_handoffs = list(_handoff_requests.values())

    en_attente  = sum(1 for h in all_handoffs if h.statut == StatutHandoff.EN_ATTENTE)
    acceptes    = sum(1 for h in all_handoffs if h.statut == StatutHandoff.ACCEPTEE)
    resolus     = sum(1 for h in all_handoffs if h.statut == StatutHandoff.RESOLUE)
    rejetes     = sum(1 for h in all_handoffs if h.statut == StatutHandoff.REJETEE)

    from app.models.handoff_request import RaisonHandoff
    demandes_client  = sum(1 for h in all_handoffs if h.raison == RaisonHandoff.DEMANDE_CLIENT)
    conf_faible      = sum(1 for h in all_handoffs if h.raison == RaisonHandoff.CONFIANCE_FAIBLE)

    return {
        "handoffs": {
            "total":          len(all_handoffs),
            "en_attente":     en_attente,
            "acceptes":       acceptes,
            "resolus":        resolus,
            "rejetes":        rejetes,
        },
        "raisons_handoff": {
            "demande_client":  demandes_client,
            "confiance_faible": conf_faible,
        },
        "note": (
            "Métriques basées sur le store en mémoire. "
            "Les données sont réinitialisées au redémarrage du serveur."
        ),
    }
