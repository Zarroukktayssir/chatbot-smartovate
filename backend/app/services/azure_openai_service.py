# services/azure_openai_service.py — AzureOpenAIService
# Responsable de la communication avec Azure OpenAI (gpt-4o)
# Toutes les valeurs de configuration viennent du fichier .env — aucune clé hardcodée

from openai import AzureOpenAI
from app.config import get_settings

settings = get_settings()


class AzureOpenAIService:
    """
    Service d'intégration avec Azure OpenAI.

    Responsabilités :
    - Initialiser le client AzureOpenAI via le SDK officiel openai (v1.x)
    - Construire le prompt avec les documents RAG + historique + message
    - Générer une réponse contextualisée et anti-hallucination

    Configuration lue depuis .env (jamais hardcodée) :
    - AZURE_OPENAI_ENDPOINT
    - AZURE_OPENAI_API_KEY
    - AZURE_OPENAI_API_VERSION
    - AZURE_OPENAI_DEPLOYMENT  (gpt-4o)
    - AZURE_OPENAI_TEMPERATURE (0.1 — valeur très basse pour réduire les hallucinations)
    """

    # Nombre maximum de documents RAG injectés dans le prompt
    MAX_CONTEXT_DOCS = 3

    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self.deployment = settings.azure_openai_deployment      # gpt-4o
        self.temperature = settings.azure_openai_temperature    # 0.1

    def generate_response(
        self,
        user_message: str,
        history: list = None,
        context_documents: list = None,
    ) -> dict:
        """
        Génère une réponse en appelant Azure OpenAI (gpt-4o).

        Args:
            user_message      : message de l'utilisateur
            history           : liste de dicts {"role": ..., "content": ...}
            context_documents : chunks RAG fournis par AzureAISearchService
                                [{"contenu": ..., "source": ..., "score": ...}, ...]

        Returns:
            dict avec :
            - "reponse"  : texte de la réponse générée par gpt-4o
            - "modele"   : nom du deployment utilisé
            - "tokens"   : tokens consommés (prompt, completion, total)
        """
        if history is None:
            history = []
        if context_documents is None:
            context_documents = []

        messages = self._build_messages(user_message, history, context_documents)

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            temperature=self.temperature,   # 0.1 — réduit les hallucinations
        )

        return {
            "reponse": response.choices[0].message.content,
            "modele": self.deployment,
            "tokens": {
                "prompt": response.usage.prompt_tokens,
                "completion": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            },
        }

    def _build_messages(
        self,
        user_message: str,
        history: list,
        context_documents: list,
    ) -> list:
        """
        Construit la liste de messages pour l'API Azure OpenAI.

        Structure du prompt :
        1. System message — persona expert cloud + documents RAG + directive anti-hallucination
        2. Historique de la conversation (maintien du contexte)
        3. Message utilisateur courant

        Les documents RAG sont injectés dans le system message pour forcer gpt-4o
        à répondre uniquement à partir des informations de la base de connaissances.
        """

        # ── Construction du bloc de contexte documentaire ───────────────
        if context_documents:
            docs_text = "\n\n".join([
                f"[Source: {doc.get('source', 'N/A')} | Page: {doc.get('page', '?')}]\n"
                f"{doc.get('contenu', '')}"
                for doc in context_documents[:self.MAX_CONTEXT_DOCS]
            ])
            contexte_section = (
                "\n\n---\n"
                "DOCUMENTS DE RÉFÉRENCE (base de connaissances Smartovate) :\n\n"
                f"{docs_text}"
                "\n---"
            )
        else:
            contexte_section = ""

        # ── System prompt professionnel Smartovate ───────────────────────
        # Directive stricte : répondre uniquement depuis les documents fournis.
        # Si l'information n'est pas disponible, retourner le tag HORS_SUJET
        # que le BotEngine intercepte pour proposer le handoff proprement.
        # Temperature=0.1 renforce cette directive côté modèle.
        system_content = (
            "Tu es l'assistant virtuel officiel de Smartovate, entreprise experte en conseil "
            "et solutions cloud Microsoft Azure.\n\n"
            "Ton rôle est d'aider les clients et collaborateurs de Smartovate avec :\n"
            "- La configuration et l'utilisation des services Azure (VM, réseau, stockage, Azure AD)\n"
            "- Les questions de facturation et de politique de remboursement\n"
            "- La prise en main rapide des outils et services Smartovate\n\n"
            "RÈGLES STRICTES :\n"
            "1. Tu réponds UNIQUEMENT à partir des documents de référence fournis ci-dessous.\n"
            "2. Si la question ne concerne pas Smartovate ou les services Azure, "
            "ou si la réponse ne se trouve pas dans les documents fournis, "
            "réponds UNIQUEMENT avec le mot-clé exact (sans rien ajouter) : ##HORS_SUJET##\n"
            "3. Tu ne dois jamais inventer de prix, de caractéristiques ou de procédures "
            "qui ne figurent pas dans les documents.\n"
            "4. Tu répondras toujours en français, de manière claire, concise et professionnelle.\n"
            "5. Si la question est ambiguë, demande une clarification avant de répondre."
            f"{contexte_section}"
        )

        messages = [{"role": "system", "content": system_content}]

        # ── Ajout de l'historique de la conversation ─────────────────────
        for msg in history:
            if msg.get("role") in ("user", "assistant", "agent"):
                messages.append({
                    "role": "assistant" if msg["role"] == "agent" else msg["role"],
                    "content": msg["content"],
                })

        # ── Message courant de l'utilisateur ────────────────────────────
        messages.append({"role": "user", "content": user_message})

        return messages
