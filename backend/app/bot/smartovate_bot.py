# bot/smartovate_bot.py — SmartovateBot
# Classe principale du Bot Framework SDK
#
# Rôle : recevoir les Activity (messages) envoyées par Azure Bot Service,
#        déléguer le traitement au BotEngine, et retourner la réponse.
#
# Position dans l'architecture :
#   Azure Bot Service
#       → POST /api/messages
#       → SmartovateBot.on_message_activity()
#       → BotEngine.process_message()
#       → AzureOpenAIService
#       → réponse au canal (Web Chat, Teams, etc.)

from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import ChannelAccount

from app.engine.bot_engine import BotEngine


class SmartovateBot(ActivityHandler):
    """
    Bot principal Smartovate — hérite de ActivityHandler (Bot Framework SDK).

    ActivityHandler est la classe de base fournie par le Bot Framework.
    Elle gère automatiquement le routing des différents types d'Activity :
    - on_message_activity     : quand un utilisateur envoie un message
    - on_members_added_activity : quand un utilisateur rejoint la conversation

    Le BotEngine est instancié une seule fois pour toute la durée de vie du bot.
    """

    def __init__(self):
        super().__init__()
        # BotEngine est l'orchestrateur — le bot ne parle jamais directement à Azure OpenAI
        self.bot_engine = BotEngine()

    async def on_message_activity(self, turn_context: TurnContext):
        """
        Appelé par le Bot Framework chaque fois qu'un utilisateur envoie un message.

        TurnContext contient :
        - turn_context.activity.text : le texte du message utilisateur
        - turn_context.activity.conversation.id : l'ID de la conversation
        - turn_context.activity.from_property.id : l'ID de l'utilisateur

        Flow complet :
        1. Extraire le message texte
        2. Passer au BotEngine pour traitement (OpenAI, plus tard RAG + handoff)
        3. Retourner la réponse via turn_context.send_activity()
        """
        user_message = turn_context.activity.text
        conversation_id = turn_context.activity.conversation.id

        if not user_message or not user_message.strip():
            await turn_context.send_activity(
                MessageFactory.text("Je n'ai pas reçu de message. Pouvez-vous reformuler ?")
            )
            return

        try:
            # Délégation au BotEngine — seul responsable du pipeline de traitement
            result = self.bot_engine.process_message(
                message=user_message.strip(),
                conversation_id=conversation_id,
                history=[],  # L'historique sera géré à l'étape de persistance
            )

            # Envoi de la réponse au canal via le Bot Framework
            await turn_context.send_activity(
                MessageFactory.text(result["reponse"])
            )

        except Exception:
            # Message d'erreur générique — aucune information sensible exposée
            await turn_context.send_activity(
                MessageFactory.text(
                    "Désolé, une erreur est survenue. Veuillez réessayer dans quelques instants."
                )
            )

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ):
        """
        Appelé quand un nouvel utilisateur rejoint la conversation.
        Envoie un message de bienvenue.
        """
        for member in members_added:
            # Ne pas envoyer le message de bienvenue au bot lui-même
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    MessageFactory.text(
                        "Bonjour ! Je suis l'assistant Smartovate. "
                        "Comment puis-je vous aider aujourd'hui ?"
                    )
                )
