# engine/bot_engine.py — BotEngine
# Orchestrateur central du chatbot Smartovate
# Pilote le pipeline complet : réception message → RAG → IA → réponse ou handoff

from app.config import get_settings
from app.services.azure_openai_service import AzureOpenAIService
from app.services.azure_ai_search_service import AzureAISearchService
from app.models.conversation import EtatConversation
from app.models.handoff_request import RaisonHandoff

settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Constantes US 2.2 — Salutations et commandes d'aide
# ─────────────────────────────────────────────────────────────────────────────

_SALUTATIONS = {"bonjour", "bonsoir", "salut", "hello", "hi", "hey", "coucou"}

_COMMANDES_AIDE = {"aide", "help", "?", "menu", "options"}

_PATTERNS_AIDE = (
    "que peux-tu",
    "qu'est-ce que tu peux",
    "que sais-tu",
    "quelles sont tes",
    "quels sont tes",
    "quels services proposes",
    "qu'est-ce que tu fais",
    "tu peux m'aider avec",
    "tu peux faire quoi",
)

_MSG_SALUTATION = (
    "Bonjour ! 👋 Je suis l'assistant virtuel de Smartovate.\n\n"
    "Comment puis-je vous aider aujourd'hui ?\n"
    "Tapez **Aide** pour voir les options disponibles."
)

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

# ─────────────────────────────────────────────────────────────────────────────
# Constantes US 3.1 — Détection d'intention de parler à un agent humain
# ─────────────────────────────────────────────────────────────────────────────

# Sous-chaînes déclenchant un handoff explicite demandé par le client.
# Ciblées sur les formulations claires de transfert — ne pas intercepter
# des questions RAG légitimes contenant le mot "agent" dans un autre contexte.
_PATTERNS_HANDOFF = (
    "parler à un agent",
    "parler à un humain",
    "parler à une personne",
    "je veux un agent",
    "je veux un humain",
    "je veux parler à",
    "transfert vers un agent",
    "transférer vers un agent",
    "mise en relation",
    "contacter un conseiller",
    "parler à un conseiller",
    "agent humain",
    "assistance humaine",
    "un humain s'il vous plaît",
    "un humain svp",
)

# Message d'attente envoyé au client après création du handoff
_MSG_ATTENTE_AGENT = (
    "Votre demande de mise en relation a bien été enregistrée. 🙏\n\n"
    "Un conseiller Smartovate va prendre en charge votre conversation "
    "dans les plus brefs délais.\n\n"
    "**Merci de patienter** — vous serez notifié dès qu'un agent est disponible."
)


def _is_commande_aide(message_normalise: str) -> bool:
    """
    Retourne True si le message est une commande d'aide (mot-clé exact ou
    formulation longue méta sur les capacités du bot).
    """
    if message_normalise in _COMMANDES_AIDE:
        return True
    return any(pattern in message_normalise for pattern in _PATTERNS_AIDE)


def _is_demande_handoff(message_normalise: str) -> bool:
    """
    Retourne True si le message exprime explicitement la volonté de parler
    à un agent humain (US 3.1 critère 1).

    Détection par sous-chaîne sur le message normalisé.
    Les patterns sont suffisamment spécifiques pour ne pas intercepter
    des questions RAG mentionnant le mot "agent" dans un autre contexte.
    """
    return any(pattern in message_normalise for pattern in _PATTERNS_HANDOFF)


class BotEngine:
    """
    Orchestrateur central du chatbot Smartovate.

    Pipeline complet (US 2.1 + US 2.2 + US 3.1) :
    ┌─────────────────────────────────────────────────────────┐
    │  1. Réception du message utilisateur                    │
    │  2. Détection rapide (US 2.2)                          │
    │     - Salutation → réponse directe (pas d'appel Azure) │
    │     - Commande Aide → menu d'aide (pas d'appel Azure)  │
    │  3. Détection handoff explicite (US 3.1)               │
    │     - Intention agent humain → HandoffRequest créée    │
    │       message d'attente, etat=EN_ATTENTE_AGENT         │
    │  4. Question normale → pipeline RAG (US 2.1)           │
    │     - AzureAISearchService.search() → documents        │
    │     - score < seuil → handoff automatique (confiance)  │
    │     - AzureOpenAIService.generate_response()           │
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

    def process_message(
        self,
        message: str,
        conversation_id: str,
        history: list,
        utilisateur_id: str = "anonymous",
    ) -> dict:
        """
        Traite un message entrant.

        Priorité de traitement :
          1. Salutation       → réponse directe, pas d'appel Azure  (US 2.2)
          2. Commande Aide    → menu d'aide, pas d'appel Azure       (US 2.2)
          3. Demande handoff  → HandoffRequest créée + message attente (US 3.1)
          4. Question normale → pipeline RAG complet                 (US 2.1)

        Args:
            message         : texte du message utilisateur
            conversation_id : ID de la conversation en cours
            history         : historique [{"role": ..., "content": ...}]
            utilisateur_id  : ID de l'utilisateur (optionnel, défaut "anonymous")

        Returns:
            dict avec :
            - 'reponse'        : texte de la réponse
            - 'etat'           : état de la conversation (EtatConversation)
            - 'handoff'        : True si handoff déclenché
            - 'sources'        : documents RAG (vide si hors pipeline RAG)
            - 'tokens'         : tokens consommés (vide si hors pipeline RAG)
            - 'type'           : 'salutation'|'aide'|'handoff_demande'|'rag'
            - 'score_confiance': score RAG (absent pour salutations/aide/handoff)
            - 'handoff_id'     : ID de la HandoffRequest (présent si handoff)
        """
        message_normalise = message.strip().lower().rstrip("!?.")

        # ── Cas 1 : Salutation ───────────────────────────────────────────
        if message_normalise in _SALUTATIONS:
            return {
                "reponse": _MSG_SALUTATION,
                "etat": EtatConversation.EN_ATTENTE_MESSAGE,
                "handoff": False,
                "sources": [],
                "tokens": {},
                "type": "salutation",
            }

        # ── Cas 2 : Commande Aide / Help ─────────────────────────────────
        if _is_commande_aide(message_normalise):
            return {
                "reponse": _MSG_AIDE,
                "etat": EtatConversation.EN_ATTENTE_MESSAGE,
                "handoff": False,
                "sources": [],
                "tokens": {},
                "type": "aide",
            }

        # ── Cas 3 : Demande explicite de handoff (US 3.1) ────────────────
        # Le client exprime sa volonté de parler à un agent humain.
        # On crée la HandoffRequest et on retourne un message d'attente.
        # Aucun appel Azure OpenAI ni Azure AI Search.
        if _is_demande_handoff(message_normalise):
            handoff = self.request_handoff(
                conversation_id=conversation_id,
                utilisateur_id=utilisateur_id,
                raison=RaisonHandoff.DEMANDE_CLIENT,
            )
            return {
                "reponse": _MSG_ATTENTE_AGENT,
                "etat": EtatConversation.EN_ATTENTE_AGENT,
                "handoff": True,
                "sources": [],
                "tokens": {},
                "type": "handoff_demande",
                "handoff_id": handoff["id"],
            }

        # ── Cas 4 : Question normale — pipeline RAG complet (US 2.1) ────
        context_documents = self.search_service.search(query=message, top_k=3)

        meilleur_score = context_documents[0]["score"] if context_documents else 0.0

        if self._should_trigger_handoff(meilleur_score):
            # Score insuffisant — handoff automatique (confiance faible)
            handoff = self.request_handoff(
                conversation_id=conversation_id,
                utilisateur_id=utilisateur_id,
                raison=RaisonHandoff.CONFIANCE_FAIBLE,
                score_confiance=meilleur_score,
            )
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
                "handoff_id": handoff["id"],
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

    def request_handoff(
        self,
        conversation_id: str,
        utilisateur_id: str,
        raison: RaisonHandoff,
        score_confiance: float = None,
    ) -> dict:
        """
        Crée une HandoffRequest dans le store en mémoire (US 3.1).

        Args:
            conversation_id : ID de la conversation
            utilisateur_id  : ID de l'utilisateur demandeur
            raison          : DEMANDE_CLIENT ou CONFIANCE_FAIBLE
            score_confiance : score RAG déclencheur (si CONFIANCE_FAIBLE)

        Returns:
            dict avec les champs de la HandoffRequest créée.
        """
        from app.services.handoff_store import creer_handoff  # import local — évite la circularité

        handoff = creer_handoff(
            conversation_id=conversation_id,
            utilisateur_id=utilisateur_id,
            raison=raison,
            score_confiance=score_confiance,
        )
        return handoff.model_dump()

    def _should_trigger_handoff(self, score_confiance: float) -> bool:
        """Retourne True si le score de confiance est en dessous du seuil configuré."""
        return score_confiance < self.confidence_threshold
