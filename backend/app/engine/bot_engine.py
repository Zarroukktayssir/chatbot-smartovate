# engine/bot_engine.py — BotEngine
# Orchestrateur central du chatbot Smartovate
# Pilote le pipeline complet : réception message → RAG → IA → réponse ou handoff

from app.config import get_settings
from app.services.azure_openai_service import AzureOpenAIService
from app.services.azure_ai_search_service import AzureAISearchService
from app.models.conversation import EtatConversation

settings = get_settings()


class BotEngine:
    """
    Orchestrateur central du chatbot Smartovate.

    Le BotEngine est le seul composant qui pilote le pipeline de traitement.
    Aucune route ne contourne le BotEngine pour accéder directement aux services Azure.

    Pipeline de traitement d'un message (défini dans la conception UML) :
    ┌─────────────────────────────────────────────────────────┐
    │  1. Réception du message utilisateur                    │
    │  2. Changement d'état → EnTraitement                   │
    │  3. AzureAISearchService.search() → documents          │
    │  4. AzureOpenAIService.generate_response() → réponse   │
    │  5. Évaluation du score de confiance                   │
    │     - Score < seuil → créer HandoffRequest             │
    │     - Score >= seuil → retourner réponse au Client     │
    │  6. Changement d'état → EnAttenteMessage ou EnAttenteAgent
    └─────────────────────────────────────────────────────────┘

    Gestion du Handoff :
    - Déclenché si l'utilisateur le demande explicitement
    - Déclenché si le score de confiance est inférieur à APP_CONFIDENCE_THRESHOLD
    """

    def __init__(self):
        # AzureOpenAIService : opérationnel depuis l'étape 2
        self.openai_service = AzureOpenAIService()

        # AzureAISearchService : squelette — sera activé à l'étape RAG
        self.search_service = AzureAISearchService()

        # Seuil de confiance pour déclencher le handoff (configurable via .env)
        self.confidence_threshold = settings.app_confidence_threshold

    def process_message(self, message: str, conversation_id: str, history: list) -> dict:
        """
        Traite un message entrant.

        Pipeline actuel (étape Bot Framework — sans RAG) :
          1. Réception du message
          2. Appel direct à AzureOpenAIService (gpt-4o)
          3. Retour de la réponse

        Pipeline futur (après étape RAG) :
          1. Réception du message
          2. AzureAISearchService.search() → documents pertinents
          3. AzureOpenAIService.generate_response(message + documents)
          4. Évaluation du score de confiance → handoff si nécessaire
          5. Retour de la réponse

        Args:
            message         : texte du message utilisateur
            conversation_id : ID de la conversation en cours
            history         : historique des messages de la conversation

        Returns:
            dict avec :
            - 'reponse'         : texte de la réponse générée
            - 'etat'            : état de la conversation (EnAttenteMessage pour l'instant)
            - 'handoff'         : False (sera évalué à l'étape handoff)
            - 'sources'         : [] (sera rempli à l'étape RAG)
        """
        # Appel à Azure OpenAI via AzureOpenAIService — sans documents RAG pour l'instant
        result = self.openai_service.generate_response(
            user_message=message,
            history=history,
            context_documents=[],  # Sera rempli par AzureAISearchService à l'étape RAG
        )

        return {
            "reponse": result["reponse"],
            "etat": EtatConversation.EN_ATTENTE_MESSAGE,
            "handoff": False,       # Sera évalué à l'étape handoff
            "sources": [],          # Sera rempli à l'étape RAG
            "tokens": result.get("tokens", {}),
        }

    def request_handoff(self, conversation_id: str, utilisateur_id: str, raison: str) -> dict:
        """
        Crée une demande de HandoffRequest et change l'état de la conversation.

        Déclenché par :
        - Demande explicite du client
        - Score de confiance trop faible (appelé automatiquement par process_message)

        Args:
            conversation_id : ID de la conversation à transférer
            utilisateur_id  : ID du client demandant le transfert
            raison          : 'demande_client' ou 'confiance_faible'

        Returns:
            dict avec l'ID du HandoffRequest créé et le nouvel état

        Note: La logique complète sera implémentée lors de l'étape de handoff.
        """
        # TODO : implémenter lors de l'étape de gestion du handoff
        raise NotImplementedError("BotEngine.request_handoff sera implémenté à l'étape handoff")

    def _should_trigger_handoff(self, score_confiance: float) -> bool:
        """
        Vérifie si le score de confiance est inférieur au seuil configuré.
        Méthode interne utilisée par process_message.

        Args:
            score_confiance : score retourné par AzureOpenAIService (0.0 à 1.0)

        Returns:
            True si un handoff doit être déclenché
        """
        return score_confiance < self.confidence_threshold
