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
    - Générer une réponse à partir d'un message utilisateur et d'un historique
    - Retourner la réponse textuelle

    Configuration lue depuis .env (jamais hardcodée) :
    - AZURE_OPENAI_ENDPOINT
    - AZURE_OPENAI_API_KEY
    - AZURE_OPENAI_API_VERSION
    - AZURE_OPENAI_DEPLOYMENT  (ex: gpt-4o)
    - AZURE_OPENAI_TEMPERATURE (0.1 selon la conception UML)
    """

    def __init__(self):
        # Initialisation du client Azure OpenAI avec les paramètres depuis .env
        # La clé API est passée directement au client — elle n'est jamais loguée
        self.client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self.deployment = settings.azure_openai_deployment      # ex: "gpt-4o"
        self.temperature = settings.azure_openai_temperature    # 0.1 selon conception UML

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
                                représentant l'historique de la conversation
            context_documents : documents RAG fournis par AzureAISearchService
                                (sera utilisé à l'étape RAG — ignoré pour l'instant)

        Returns:
            dict avec :
            - "reponse"  : texte de la réponse générée par gpt-4o
            - "modele"   : nom du deployment utilisé
            - "tokens"   : nombre de tokens consommés (utile pour les métriques)
        """
        if history is None:
            history = []

        # Construction des messages à envoyer à Azure OpenAI
        messages = self._build_messages(user_message, history, context_documents)

        # Appel à Azure OpenAI — la clé API est dans le client, jamais dans la requête
        response = self.client.chat.completions.create(
            model=self.deployment,          # Nom du deployment depuis .env
            messages=messages,
            temperature=self.temperature,   # 0.1 depuis .env
        )

        reponse_texte = response.choices[0].message.content

        return {
            "reponse": reponse_texte,
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
        context_documents: list = None,
    ) -> list:
        """
        Construit la liste de messages pour l'API Azure OpenAI.

        Structure :
        1. Message système (system prompt Smartovate)
        2. Historique de la conversation
        3. Message utilisateur courant

        Note : l'injection des documents RAG sera ajoutée à l'étape Azure AI Search.
        """
        # Message système — définit le comportement du chatbot
        system_message = {
            "role": "system",
            "content": (
                "Tu es un assistant conversationnel intelligent pour Smartovate. "
                "Tu réponds aux questions des utilisateurs de manière claire, précise et professionnelle. "
                "Si tu ne connais pas la réponse, dis-le honnêtement plutôt que d'inventer."
            ),
        }

        messages = [system_message]

        # Ajout de l'historique de la conversation (pour maintenir le contexte)
        for msg in history:
            if msg.get("role") in ("user", "assistant", "agent"):
                messages.append({
                    "role": msg["role"] if msg["role"] != "agent" else "assistant",
                    "content": msg["content"],
                })

        # Message courant de l'utilisateur
        messages.append({"role": "user", "content": user_message})

        return messages
