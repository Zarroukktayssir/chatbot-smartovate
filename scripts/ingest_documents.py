"""
scripts/ingest_documents.py — Script d'ingestion documentaire (US 1.2)
Pipeline RAG : documents → extraction texte → chunking → embeddings → Azure AI Search

Usage :
    cd Chatbot-Smartovate
    python scripts/ingest_documents.py

Toutes les clés sont lues depuis backend/.env — aucune valeur hardcodée.
"""

import os
import sys
import uuid
import time
import math
from pathlib import Path
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────
# Chargement du fichier .env depuis backend/
# ─────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENV_PATH = PROJECT_ROOT / "backend" / ".env"

if not ENV_PATH.exists():
    print(f"[ERREUR] Fichier .env introuvable : {ENV_PATH}")
    sys.exit(1)

load_dotenv(ENV_PATH)

# ─────────────────────────────────────────────────────────
# Lecture de la configuration depuis .env
# ─────────────────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT          = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY           = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION       = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")

AZURE_SEARCH_ENDPOINT          = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY           = os.getenv("AZURE_SEARCH_API_KEY", "")
AZURE_SEARCH_INDEX_NAME        = os.getenv("AZURE_SEARCH_INDEX_NAME", "smartovate-index")

# Validation des variables obligatoires
_required = {
    "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
    "AZURE_OPENAI_API_KEY": AZURE_OPENAI_API_KEY,
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    "AZURE_SEARCH_ENDPOINT": AZURE_SEARCH_ENDPOINT,
    "AZURE_SEARCH_API_KEY": AZURE_SEARCH_API_KEY,
    "AZURE_SEARCH_INDEX_NAME": AZURE_SEARCH_INDEX_NAME,
}
_missing = [k for k, v in _required.items() if not v]
if _missing:
    print(f"[ERREUR] Variables manquantes dans .env : {', '.join(_missing)}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────
# Imports des bibliothèques tierces
# ─────────────────────────────────────────────────────────
try:
    import pdfplumber
except ImportError:
    print("[ERREUR] pdfplumber non installé. Lancer : pip install pdfplumber==0.11.0")
    sys.exit(1)

try:
    from docx import Document as DocxDocument
except ImportError:
    print("[ERREUR] python-docx non installé. Lancer : pip install python-docx==1.1.2")
    sys.exit(1)

try:
    import tiktoken
except ImportError:
    print("[ERREUR] tiktoken non installé. Lancer : pip install tiktoken==0.7.0")
    sys.exit(1)

try:
    from openai import AzureOpenAI
except ImportError:
    print("[ERREUR] openai non installé. Lancer : pip install openai==1.30.1")
    sys.exit(1)

try:
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex,
        SearchField,
        SearchFieldDataType,
        SimpleField,
        SearchableField,
        VectorSearch,
        HnswAlgorithmConfiguration,
        VectorSearchProfile,
        SearchField as VectorField,
    )
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:
    print("[ERREUR] azure-search-documents non installé. Lancer : pip install 'azure-search-documents==11.6.0b4'")
    sys.exit(1)

# ─────────────────────────────────────────────────────────
# Configuration générale
# ─────────────────────────────────────────────────────────
DOCUMENTS_DIR   = PROJECT_ROOT / "documents"
CHUNK_SIZE      = 500      # Taille cible d'un chunk en tokens
CHUNK_OVERLAP   = 50       # Chevauchement entre chunks consécutifs
EMBEDDING_DIM   = 3072     # Dimensions de text-embedding-3-large
BATCH_EMBED     = 16       # Nombre de chunks par appel embedding
BATCH_INDEX     = 100      # Nombre de documents par upload vers Azure AI Search

# Encodeur tiktoken compatible avec les modèles OpenAI
TOKENIZER = tiktoken.get_encoding("cl100k_base")

# Clients Azure
openai_client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
)

search_credential   = AzureKeyCredential(AZURE_SEARCH_API_KEY)
index_client        = SearchIndexClient(AZURE_SEARCH_ENDPOINT, search_credential)
search_client       = SearchClient(AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX_NAME, search_credential)


# ═════════════════════════════════════════════════════════
# ÉTAPE 1 — Découverte des documents
# ═════════════════════════════════════════════════════════

def discover_documents(root: Path) -> list[dict]:
    """
    Parcourt récursivement le dossier documents/ et retourne
    la liste de tous les fichiers PDF et DOCX avec leurs métadonnées.
    """
    supported = {".pdf", ".docx"}
    found = []

    for file_path in sorted(root.rglob("*")):
        if file_path.suffix.lower() in supported and file_path.is_file():
            # La catégorie est le nom du sous-dossier direct sous documents/
            try:
                categorie = file_path.relative_to(root).parts[0]
            except IndexError:
                categorie = "general"

            found.append({
                "path": file_path,
                "source": file_path.name,
                "categorie": categorie,
                "extension": file_path.suffix.lower(),
            })

    return found


# ═════════════════════════════════════════════════════════
# ÉTAPE 2 — Extraction du texte
# ═════════════════════════════════════════════════════════

def extract_text_pdf(file_path: Path) -> list[dict]:
    """
    Extrait le texte d'un fichier PDF page par page.
    Retourne une liste de dicts {texte, page}.
    """
    pages = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages.append({"texte": text.strip(), "page": i})
    return pages


def extract_text_docx(file_path: Path) -> list[dict]:
    """
    Extrait le texte d'un fichier DOCX paragraphe par paragraphe.
    Regroupe tout le contenu en une seule "page" (page=1).
    """
    doc = DocxDocument(str(file_path))
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(lines)
    if not full_text:
        return []
    return [{"texte": full_text, "page": 1}]


def extract_text(doc_info: dict) -> list[dict]:
    """Délègue l'extraction selon l'extension du fichier."""
    if doc_info["extension"] == ".pdf":
        return extract_text_pdf(doc_info["path"])
    elif doc_info["extension"] == ".docx":
        return extract_text_docx(doc_info["path"])
    return []


# ═════════════════════════════════════════════════════════
# ÉTAPE 3 — Chunking
# ═════════════════════════════════════════════════════════

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Découpe un texte en chunks de ~chunk_size tokens avec chevauchement.

    Stratégie :
    - Tokenisation avec tiktoken (cl100k_base)
    - Fenêtre glissante : avance de (chunk_size - overlap) tokens à chaque pas
    - Retourne les chunks sous forme de texte décodé
    """
    tokens = TOKENIZER.encode(text)
    total  = len(tokens)

    if total == 0:
        return []

    step   = chunk_size - overlap
    chunks = []

    for start in range(0, total, step):
        end        = min(start + chunk_size, total)
        chunk_tok  = tokens[start:end]
        chunk_text = TOKENIZER.decode(chunk_tok)
        if chunk_text.strip():
            chunks.append(chunk_text.strip())
        if end == total:
            break

    return chunks


def build_chunks(doc_info: dict, pages: list[dict]) -> list[dict]:
    """
    Construit la liste de chunks pour un document.
    Chaque chunk contient : id, contenu, source, categorie, page.
    """
    all_chunks = []
    source_stem = Path(doc_info["source"]).stem.lower().replace(" ", "_")

    for page_data in pages:
        text_chunks = chunk_text(page_data["texte"])
        for idx, chunk in enumerate(text_chunks):
            chunk_id = f"{source_stem}_p{page_data['page']}_c{idx:04d}"
            all_chunks.append({
                "id":        chunk_id,
                "contenu":   chunk,
                "source":    doc_info["source"],
                "categorie": doc_info["categorie"],
                "page":      page_data["page"],
            })

    return all_chunks


# ═════════════════════════════════════════════════════════
# ÉTAPE 4 — Génération des embeddings
# ═════════════════════════════════════════════════════════

def generate_embeddings(chunks: list[dict]) -> list[dict]:
    """
    Génère les embeddings pour une liste de chunks.
    Traitement par lots de BATCH_EMBED pour respecter les limites Azure OpenAI.
    Chaque chunk reçoit un champ 'embedding' (vecteur de 3072 floats).
    """
    total_batches = math.ceil(len(chunks) / BATCH_EMBED)

    for batch_num in range(total_batches):
        start  = batch_num * BATCH_EMBED
        end    = min(start + BATCH_EMBED, len(chunks))
        batch  = chunks[start:end]
        texts  = [c["contenu"] for c in batch]

        print(f"    Embeddings lot {batch_num + 1}/{total_batches} ({len(texts)} chunks)...")

        try:
            response = openai_client.embeddings.create(
                input=texts,
                model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,  # text-embedding-3-large depuis .env
            )
            for i, embedding_data in enumerate(response.data):
                batch[i]["embedding"] = embedding_data.embedding

        except Exception as e:
            print(f"    [ERREUR] Lot {batch_num + 1} : {type(e).__name__} — {str(e)[:100]}")
            raise

        # Pause courte pour éviter les rate limits
        if batch_num < total_batches - 1:
            time.sleep(0.5)

    return chunks


# ═════════════════════════════════════════════════════════
# ÉTAPE 5 — Création de l'index Azure AI Search
# ═════════════════════════════════════════════════════════

def create_index_if_not_exists():
    """
    Crée l'index smartovate-index dans Azure AI Search s'il n'existe pas déjà.

    Schéma de l'index :
    - id          : clé unique (string)
    - contenu     : texte du chunk — champ de recherche full-text
    - embedding   : vecteur 3072 dimensions — champ de recherche vectorielle
    - source      : nom du fichier source (filtrable)
    - categorie   : catégorie du document (filtrable)
    - page        : numéro de page (filtrable)
    """
    try:
        index_client.get_index(AZURE_SEARCH_INDEX_NAME)
        print(f"  Index '{AZURE_SEARCH_INDEX_NAME}' existe déjà — pas de recréation.")
        return
    except ResourceNotFoundError:
        print(f"  Index '{AZURE_SEARCH_INDEX_NAME}' introuvable — création en cours...")

    # Configuration de la recherche vectorielle (algorithme HNSW)
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(name="hnsw-config"),
        ],
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw-config",
            )
        ],
    )

    # Définition des champs de l'index
    fields = [
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SearchableField(
            name="contenu",
            type=SearchFieldDataType.String,
            analyzer_name="fr.microsoft",  # Analyseur français
        ),
        VectorField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIM,       # 3072 pour text-embedding-3-large
            vector_search_profile_name="vector-profile",
        ),
        SimpleField(
            name="source",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SimpleField(
            name="categorie",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SimpleField(
            name="page",
            type=SearchFieldDataType.Int32,
            filterable=True,
        ),
    ]

    index = SearchIndex(
        name=AZURE_SEARCH_INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
    )

    index_client.create_index(index)
    print(f"  Index '{AZURE_SEARCH_INDEX_NAME}' créé avec succès.")


# ═════════════════════════════════════════════════════════
# ÉTAPE 5 (suite) — Indexation des chunks
# ═════════════════════════════════════════════════════════

def index_chunks(chunks: list[dict]):
    """
    Uploade les chunks dans Azure AI Search par lots de BATCH_INDEX.
    """
    total_batches = math.ceil(len(chunks) / BATCH_INDEX)

    for batch_num in range(total_batches):
        start = batch_num * BATCH_INDEX
        end   = min(start + BATCH_INDEX, len(chunks))
        batch = chunks[start:end]

        # Format attendu par Azure AI Search
        documents = [
            {
                "id":        c["id"],
                "contenu":   c["contenu"],
                "embedding": c["embedding"],
                "source":    c["source"],
                "categorie": c["categorie"],
                "page":      c["page"],
            }
            for c in batch
        ]

        print(f"    Upload lot {batch_num + 1}/{total_batches} ({len(documents)} docs)...")
        result = search_client.upload_documents(documents=documents)

        failed = [r for r in result if not r.succeeded]
        if failed:
            print(f"    [ATTENTION] {len(failed)} documents échoués dans le lot {batch_num + 1}")


# ═════════════════════════════════════════════════════════
# ÉTAPE 6 — Test de recherche vectorielle
# ═════════════════════════════════════════════════════════

def test_vector_search(query: str = "Comment configurer une machine virtuelle Azure ?"):
    """
    Teste la recherche vectorielle sur l'index créé.
    Génère l'embedding de la requête et retourne les 3 résultats les plus pertinents.
    """
    print(f"\n{'='*60}")
    print(f"TEST DE RECHERCHE VECTORIELLE")
    print(f"Requête : '{query}'")
    print(f"{'='*60}")

    # Génération de l'embedding de la requête
    response = openai_client.embeddings.create(
        input=[query],
        model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    )
    query_embedding = response.data[0].embedding

    # Recherche vectorielle dans Azure AI Search
    from azure.search.documents.models import VectorizedQuery

    vector_query = VectorizedQuery(
        vector=query_embedding,
        k_nearest_neighbors=3,
        fields="embedding",
    )

    results = search_client.search(
        search_text=None,
        vector_queries=[vector_query],
        select=["id", "contenu", "source", "categorie", "page"],
        top=3,
    )

    print(f"\nRésultats (top 3) :\n")
    for i, result in enumerate(results, start=1):
        print(f"  Résultat #{i}")
        print(f"  Source    : {result.get('source', 'N/A')}")
        print(f"  Catégorie : {result.get('categorie', 'N/A')}")
        print(f"  Page      : {result.get('page', 'N/A')}")
        print(f"  Extrait   : {result.get('contenu', '')[:200]}...")
        print(f"  Score     : {result.get('@search.score', 'N/A'):.4f}")
        print()


# ═════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ═════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("SMARTOVATE — INGESTION DOCUMENTAIRE (US 1.2)")
    print("=" * 60)
    print(f"Dossier source    : {DOCUMENTS_DIR}")
    print(f"Index cible       : {AZURE_SEARCH_INDEX_NAME}")
    print(f"Modèle embedding  : {AZURE_OPENAI_EMBEDDING_DEPLOYMENT}")
    print(f"Taille chunk      : {CHUNK_SIZE} tokens (overlap: {CHUNK_OVERLAP})")
    print()

    # ── Étape 1 : Découverte ──────────────────────────────
    print("ÉTAPE 1 — Découverte des documents...")
    documents = discover_documents(DOCUMENTS_DIR)
    if not documents:
        print(f"[ERREUR] Aucun document PDF/DOCX trouvé dans {DOCUMENTS_DIR}")
        sys.exit(1)
    print(f"  {len(documents)} documents trouvés :")
    for doc in documents:
        print(f"    [{doc['categorie']}] {doc['source']}")
    print()

    # ── Étape 5a : Création de l'index ───────────────────
    print("ÉTAPE 5a — Vérification/Création de l'index Azure AI Search...")
    create_index_if_not_exists()
    print()

    # ── Traitement document par document ─────────────────
    all_chunks_with_embeddings = []

    for doc_idx, doc_info in enumerate(documents, start=1):
        print(f"[{doc_idx}/{len(documents)}] Traitement : {doc_info['source']}")

        # Étape 2 : Extraction
        print("  Étape 2 — Extraction du texte...")
        pages = extract_text(doc_info)
        if not pages:
            print(f"  [ATTENTION] Aucun texte extrait de {doc_info['source']} — ignoré.")
            continue
        total_chars = sum(len(p["texte"]) for p in pages)
        print(f"  {len(pages)} page(s) extraite(s) — {total_chars} caractères")

        # Étape 3 : Chunking
        print("  Étape 3 — Découpage en chunks...")
        chunks = build_chunks(doc_info, pages)
        print(f"  {len(chunks)} chunk(s) créé(s)")

        # Étape 4 : Embeddings
        print("  Étape 4 — Génération des embeddings...")
        chunks_with_embeddings = generate_embeddings(chunks)
        all_chunks_with_embeddings.extend(chunks_with_embeddings)
        print(f"  OK — {len(chunks_with_embeddings)} embeddings générés")
        print()

    # ── Étape 5b : Indexation ────────────────────────────
    print(f"ÉTAPE 5b — Indexation de {len(all_chunks_with_embeddings)} chunks...")
    index_chunks(all_chunks_with_embeddings)
    print(f"  Indexation terminée.")
    print()

    # ── Étape 6 : Test de recherche ──────────────────────
    print("ÉTAPE 6 — Test de recherche vectorielle...")
    time.sleep(2)  # Délai pour que l'index soit prêt
    test_vector_search("Comment configurer une machine virtuelle Azure ?")

    print("=" * 60)
    print("INGESTION TERMINÉE AVEC SUCCÈS")
    print(f"Total chunks indexés : {len(all_chunks_with_embeddings)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
