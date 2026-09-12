# engine/bot_engine.py — BotEngine
# Orchestrateur central du chatbot Smartovate
# Pilote le pipeline complet : réception message → RAG → IA → réponse ou handoff

from app.config import get_settings
from app.services.azure_openai_service import AzureOpenAIService
from app.services.azure_ai_search_service import AzureAISearchService
from app.models.conversation import EtatConversation

settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Constantes US 2.2 — Salutations et commandes d'aide
# Centralisées ici pour faciliter les modifications futures
# ─────────────────────────────────────────────────────────────────────────────

# Mots déclenchant une réponse de salutation (sans appel Azure)
_SALUTATIONS = {"bonjour", "bonsoir", "salut", "hello", "hi", "hey", "coucou"}

# Mots déclenchant le menu d'aide (sans appel Azure)
_COMMANDES_AIDE = {"aide", "help", "?", "menu", "options"}

# Message de salutation
_MSG_SALUTATION = (
    "Bonjour ! 👋 Je suis l'assistant virtuel de Smartovate.\n\n"
    "Comment puis-je vous aider aujourd'hui ?\n"
    "Tapez **Aide** pour voir les options disponibles."
)

# Menu d'aide complet
_MSG_AIDE = (
    "Voici les sujets sur lesquels je peux vous aider :\n\n"
    "☁️  **Services Cloud** — catalogue et tarification\n"
    "🖥️  **Machines virtuelles Azure** — création et configuration\n"
    "🌐  **Réseau & infrastructure** — VNet, sous-réseaux, sécurité\n"
    "💾  **Stockage Azure** — Blob, File, configuration\n"
    "🔐  **Azure Active Directory** — gestion des identités\n"
    "💳  **Facturation & remboursements** — politique et procédures\n"
    "🚀  **Guide de démarrage rapide** — premiers pas avec Smartovate\n\n"
    "Posez-moi votre question directement ou choisissez un sujet ci-dessus."
)


class BotEngine:
    """
    Orchestrateur central du chatbot Smartovate.

    Le BotEngine est le seul composant qui pilote le pipeline de traitement.
    Aucune route ne contourne le BotEngine pour accéder directement aux services Azure.

    Pipeline complet (US 2.1 + US 2.2) :
    ┌─────────────────────────────────────────────────────────┐
    │  1. Réception du message utilisateur                    │
    │  2. Détection rapide (US 2.2)                          │
    │     - Salutation → réponse directe (pas d'appel Azure) │
    │     - Commande Aide → menu d'aide (pas d'appel Azure)  │
    │  3. Question normale → pipeline RAG (US 2.1)           │
    │     - AzureAISearchService.search() → documents        │
    │     - Évaluation score RAG vs seuil 0.7 (US 2.1 c.7)  │
    │       → score < 0.7 : handoff=True, pas d'appel OpenAI │
    │     - AzureOpenAIService.generate_response()           │
    │       → prompt expert cloud + RAG + historique         │
    │       → réponse gpt-4o (temperature=0.1)               │
    │  4. Handoff complet vers agent humain (Sprint 3)       │
    └─────────────────────────────────────────────────────────┘
    """

    def __init__(self):
        self.openai_service = AzureOpenAIService()
        self.search_service = AzureAISearchService()
        self.confidence_threshold = settings.app_confidence_threshold

    def get_welcome_message(self) -> str:
        """
        Retourne le message de bienvenue Smartovate.
        Appelé par SmartovateBot.on_members_added_activity() (US 2.2).
        """
        return (
            "Bonjour et bienvenue chez Smartovate ! 👋\n\n"
            "Je suis votre assistant virtuel spécialisé dans les services Cloud Microsoft Azure.\n\n"
            "Je peux vous aider avec :\n"
            "• ☁️  Les configurations Cloud et services Azure\n"
            "• 🖥️  Les machines virtuelles (VM)\n"
            "• 🌐  Le réseau et l'infrastructure\n"
            "• 💳  La facturation et les remboursements\n\n"
            "Tapez **Aide** pour voir toutes les options disponibles,\n"
            "ou posez-moi directement votre question."
        )

    def process_message(self, message: str, conversation_id: str, history: list) -> dict:
        """
        Traite un message entrant.

        Priorité de traitement (US 2.2 en premier, US 2.1 si question normale) :
          1. Salutation → réponse directe, pas d'appel Azure
          2. Commande Aide/Help → menu d'aide, pas d'appel Azure
          3. Question normale → pipeline RAG complet (US 2.1)

        Args:
            message         : texte du message utilisateur
            conversation_id : ID de la conversation en cours
            history         : historique des messages [{"role": ..., "content": ...}]

        Returns:
            dict avec :
            - 'reponse'        : texte de la réponse
            - 'etat'           : état de la conversation
            - 'handoff'        : True si score RAG < seuil (0.7), False sinon
            - 'sources'        : documents RAG utilisés (vide pour salutations/aide)
            - 'tokens'         : tokens consommés (vide si handoff ou salutation/aide)
            - 'type'           : 'salutation' | 'aide' | 'rag'
            - 'score_confiance': meilleur score RAG (absent pour salutations/aide)
        """
        message_normalise = message.strip().lower().rstrip("!?.")

        # ── Cas 2 : Salutation ───────────────────────────────────────────
        # Détection par mot-clé exact — évite un appel inutile à Azure
        if message_normalise in _SALUTATIONS:
            return {
                "reponse": _MSG_SALUTATION,
                "etat": EtatConversation.EN_ATTENTE_MESSAGE,
                "handoff": False,
                "sources": [],
                "tokens": {},
                "type": "salutation",
            }

        # ── Cas 3 : Commande Aide / Help ─────────────────────────────────
        # Détection par mot-clé exact — affiche le menu sans appel Azure
        if message_normalise in _COMMANDES_AIDE:
            return {
                "reponse": _MSG_AIDE,
                "etat": EtatConversation.EN_ATTENTE_MESSAGE,
                "handoff": False,
                "sources": [],
                "tokens": {},
                "type": "aide",
            }

        # ── Cas 4 : Question normale — pipeline RAG complet (US 2.1) ────
        context_documents = self.search_service.search(query=message, top_k=3)

        # ── Évaluation du seuil de confiance RAG (US 2.1 critère 7) ─────
        # Le meilleur score est celui du premier document retourné par Azure AI Search
        # (les résultats sont triés par score décroissant).
        # Si aucun document n'est trouvé, le score est 0.0 — en dessous du seuil.
        meilleur_score = context_documents[0]["score"] if context_documents else 0.0

        if self._should_trigger_handoff(meilleur_score):
            # Score insuffisant — on ne génère pas de réponse IA potentiellement non fiable.
            # Le vrai workflow de handoff vers un agent humain sera implémenté au Sprint 3.
            return {
                "reponse": (
                    "Je ne dispose pas d'informations suffisamment pertinentes pour répondre "
                    "à votre question avec certitude.\n\n"
                    "Souhaitez-vous être mis en relation avec un conseiller Smartovate ?"
                ),
                "etat": EtatConversation.EN_ATTENTE_AGENT,
                "handoff": True,
                "sources": context_documents,
                "tokens": {},
                "type": "rag",
                "score_confiance": meilleur_score,
            }

        result = self.openai_service.generate_response(
            user_message=message,
            history=history,
            context_documents=context_documents,
        )

        return {
            "reponse": result["reponse"],
            "etat": EtatConversation.EN_ATTENTE_MESSAGE,
            "handoff": False,
            "sources": context_documents,
            "tokens": result.get("tokens", {}),
            "type": "rag",
            "score_confiance": meilleur_score,
        }

    def request_handoff(self, conversation_id: str, utilisateur_id: str, raison: str) -> dict:
        """
        Crée une demande de HandoffRequest.
        TODO : implémenter au Sprint 3.
        """
        raise NotImplementedError("BotEngine.request_handoff sera implémenté au Sprint 3")

    def _should_trigger_handoff(self, score_confiance: float) -> bool:
        """
        Vérifie si le score de confiance déclenche un handoff.
        Sera utilisé dans process_message() au Sprint 3.
        """
        return score_confiance < self.confidence_threshold
