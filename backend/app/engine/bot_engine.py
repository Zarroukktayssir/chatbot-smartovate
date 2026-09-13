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

# Confirmations courtes — détectées UNIQUEMENT après une proposition du bot.
_CONFIRMATIONS_HANDOFF = {
    "oui", "oui svp", "oui s'il vous plaît", "oui merci",
    "yes", "ok", "d'accord", "dacord", "bien sûr", "bien sur",
    "je veux", "je veux bien", "volontiers", "allez-y", "allons-y",
    "s'il vous plaît", "svp",
}

# Marker dans le message du BotEngine (pas d'OpenAI) indiquant une proposition de handoff.
# IMPORTANT : Ce marker doit être présent UNIQUEMENT dans les messages générés par le
# BotEngine lui-même (_MSG_PROPOSITION_HANDOFF), PAS dans les réponses OpenAI.
# Cela évite que la directive de refus d'OpenAI déclenche une fausse confirmation.
_BOT_PROPOSE_HANDOFF_MARKER = "souhaitez-vous être mis en relation"

# Message de proposition de mise en relation — généré par le BotEngine (pas OpenAI).
# Contient délibérément le marker pour que la confirmation "oui" soit détectée.
_MSG_PROPOSITION_HANDOFF = (
    "Je ne dispose pas d'informations suffisamment pertinentes pour répondre "
    "à votre question avec certitude.\n\n"
    "Souhaitez-vous être mis en relation avec un conseiller Smartovate ?"
)

# Message envoyé quand le handoff est déjà actif et que le client continue d'écrire.
_MSG_HANDOFF_DEJA_ACTIF = (
    "Votre demande a déjà été transmise à un conseiller. 🙏\n\n"
    "Merci de patienter, il prendra en charge votre conversation "
    "dans les plus brefs délais."
)

# Message d'attente envoyé après création du handoff.
_MSG_ATTENTE_AGENT = (
    "Votre demande de mise en relation a bien été enregistrée. 🙏\n\n"
    "Un conseiller Smartovate va prendre en charge votre conversation "
    "dans les plus brefs délais.\n\n"
    "**Merci de patienter** — vous serez notifié dès qu'un agent est disponible."
)


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions de détection
# ─────────────────────────────────────────────────────────────────────────────

def _is_commande_aide(message_normalise: str) -> bool:
    """Retourne True si le message est une commande d'aide."""
    if message_normalise in _COMMANDES_AIDE:
        return True
    return any(pattern in message_normalise for pattern in _PATTERNS_AIDE)


def _is_demande_handoff(message_normalise: str) -> bool:
    """Retourne True si le message exprime explicitement la volonté de parler
    à un agent humain (US 3.1 critère 1)."""
    return any(pattern in message_normalise for pattern in _PATTERNS_HANDOFF)


def _bot_vient_de_proposer_handoff(history: list) -> bool:
    """
    Retourne True si le dernier message de l'assistant dans l'historique
    était une proposition de mise en relation du BotEngine (pas d'OpenAI).

    On cherche spécifiquement le marker dans les messages du BotEngine.
    Les refus générés par OpenAI ("Je ne dispose pas de cette information...")
    ne contiennent PAS ce marker — ils utilisent une formulation différente
    sans "souhaitez-vous être mis en relation".
    """
    for msg in reversed(history):
        if msg.get("role") in ("assistant", "bot"):
            contenu = msg.get("content", "").lower()
            return _BOT_PROPOSE_HANDOFF_MARKER in contenu
    return False


def _is_confirmation_handoff(message_normalise: str, history: list) -> bool:
    """Retourne True si le message confirme une proposition de handoff du BotEngine."""
    return (
        message_normalise in _CONFIRMATIONS_HANDOFF
        and _bot_vient_de_proposer_handoff(history)
    )


def _handoff_deja_actif(conversation_id: str) -> bool:
    """
    Retourne True si un handoff EN_ATTENTE ou ACCEPTÉ existe déjà pour
    cette conversation.

    Évite de créer un doublon quand le client envoie un nouveau message
    après avoir déjà demandé un conseiller.
    """
    from app.services.handoff_store import get_handoff
    from app.models.handoff_request import StatutHandoff

    handoff = get_handoff(conversation_id)
    if not handoff:
        return False
    return handoff.statut in (StatutHandoff.EN_ATTENTE, StatutHandoff.ACCEPTEE)


# ─────────────────────────────────────────────────────────────────────────────
# BotEngine
# ─────────────────────────────────────────────────────────────────────────────

class BotEngine:
    """
    Orchestrateur central du chatbot Smartovate.

    Pipeline complet (US 2.1 + US 2.2 + US 3.1) :
    ┌─────────────────────────────────────────────────────────┐
    │  0. Handoff déjà actif → message d'attente             │
    │  1. Salutation → réponse directe (pas d'appel Azure)   │
    │  2. Commande Aide → menu (pas d'appel Azure)           │
    │  3. Demande handoff explicite ou confirmation "oui"    │
    │     → HandoffRequest créée + message d'attente        │
    │  4. Question normale → pipeline RAG (US 2.1)           │
    │     - search() → chunks pertinents                    │
    │     - score < seuil → proposition handoff BotEngine   │
    │     - sinon → generate_response() OpenAI              │
    └─────────────────────────────────────────────────────────┘
    """

    def __init__(self):
        self.openai_service = AzureOpenAIService()
        self.search_service = AzureAISearchService()
        self.confidence_threshold = settings.app_confidence_threshold

    def get_welcome_message(self) -> str:
        """Retourne le message de bienvenue Smartovate (US 2.2)."""
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

        Priorité :
          0. Handoff déjà actif    → rappel d'attente, pas de traitement
          1. Salutation            → réponse directe (US 2.2)
          2. Commande Aide         → menu d'aide (US 2.2)
          3. Demande handoff       → HandoffRequest + attente (US 3.1)
          4. Question normale      → pipeline RAG complet (US 2.1)
        """
        message_normalise = message.strip().lower().rstrip("!?.")

        # ── Cas 0 : Handoff déjà actif ───────────────────────────────────
        # Si un conseiller est déjà assigné ou en attente pour cette conversation,
        # on ne relance pas de nouveau pipeline RAG — on rappelle juste que
        # la demande est en cours.
        if _handoff_deja_actif(conversation_id):
            from app.services.handoff_store import get_handoff
            handoff = get_handoff(conversation_id)
            return {
                "reponse": _MSG_HANDOFF_DEJA_ACTIF,
                "etat": EtatConversation.EN_ATTENTE_AGENT,
                "handoff": True,
                "sources": [],
                "tokens": {},
                "type": "handoff_actif",
                "handoff_id": handoff.id if handoff else None,
            }

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

        # ── Cas 3 : Handoff — formulation directe ou confirmation "oui" ──
        # - Formulation directe : "je veux parler à un agent"
        # - Confirmation : "oui" / "ok" APRÈS que le BotEngine a proposé
        #   (_MSG_PROPOSITION_HANDOFF contient le marker).
        #   Les refus OpenAI ("Je ne dispose pas...") ne contiennent PAS
        #   le marker → ne déclenchent pas de fausse confirmation.
        if _is_demande_handoff(message_normalise) or _is_confirmation_handoff(message_normalise, history):
            raison = (
                RaisonHandoff.DEMANDE_CLIENT
                if _is_demande_handoff(message_normalise)
                else RaisonHandoff.CONFIANCE_FAIBLE
            )
            handoff = self.request_handoff(
                conversation_id=conversation_id,
                utilisateur_id=utilisateur_id,
                raison=raison,
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
        context_documents = self.search_service.search(query=message, top_k=5)
        meilleur_score = context_documents[0]["score"] if context_documents else 0.0

        if self._should_trigger_handoff(meilleur_score):
            # Score insuffisant — proposition BotEngine (avec marker) sans créer le handoff.
            # Si l'utilisateur répond "oui", le Cas 3 créera le handoff.
            return {
                "reponse": _MSG_PROPOSITION_HANDOFF,
                "etat": EtatConversation.EN_ATTENTE_MESSAGE,
                "handoff": False,
                "sources": context_documents,
                "tokens": {},
                "type": "rag",
                "score_confiance": meilleur_score,
            }

        # Pipeline OpenAI — gpt-4o répond ou retourne ##HORS_SUJET## si hors scope.
        result = self.openai_service.generate_response(
            user_message=message,
            history=history,
            context_documents=context_documents,
        )

        reponse_texte = result["reponse"].strip()

        # ── Détection tag hors sujet retourné par OpenAI ────────────────
        # Si gpt-4o retourne ##HORS_SUJET##, le BotEngine prend la main
        # et envoie _MSG_PROPOSITION_HANDOFF (avec le bon marker).
        # Cela évite que OpenAI génère lui-même le message de refus
        # et déclenche un faux handoff automatique.
        if "##HORS_SUJET##" in reponse_texte:
            return {
                "reponse": _MSG_PROPOSITION_HANDOFF,
                "etat": EtatConversation.EN_ATTENTE_MESSAGE,
                "handoff": False,
                "sources": [],
                "tokens": result.get("tokens", {}),
                "type": "hors_sujet",
                "score_confiance": meilleur_score,
            }

        return {
            "reponse": reponse_texte,
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
        """Crée une HandoffRequest dans le store en mémoire (US 3.1)."""
        from app.services.handoff_store import creer_handoff

        handoff = creer_handoff(
            conversation_id=conversation_id,
            utilisateur_id=utilisateur_id,
            raison=raison,
            score_confiance=score_confiance,
        )
        return handoff.model_dump()

    def _should_trigger_handoff(self, score_confiance: float) -> bool:
        """Retourne True si le score RAG est sous le seuil configuré."""
        return score_confiance < self.confidence_threshold
