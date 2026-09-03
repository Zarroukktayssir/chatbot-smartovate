# bot/smartovate_bot.py — SmartovateBot
# Classe principale du Bot Framework SDK
#
# Rôle : recevoir les Activity (messages) envoyées par Azure Bot Service,
#        déléguer le traitement au BotEngine, et retourner la réponse.
#
# US 2.2 : message de bienvenue proactif via on_members_added_activity()
# US 2.1 : pipeline RAG via on_message_activity() → BotEngine.process_message()

from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import ChannelAccount

from app.engine.bot_engine import BotEngine


class SmartovateBot(ActivityHandler):
    """
    Bot principal Smartovate — hérite de ActivityHandler (Bot Framework SDK).

    Gestion des Activity :
    - on_message_activity       : message utilisateur → BotEngine → réponse
    - on_members_added_activity : nouveau membre → message de bienvenue (US 2.2)
    """

    def __init__(self):
        super().__init__()
        self.bot_engine = BotEngine()

    async def on_message_activity(self, turn_context: TurnContext):
        """
        Appelé à chaque message utilisateur.

        Délègue entièrement au BotEngine qui gère :
        - Les salutations (US 2.2) → réponse directe
        - La commande Aide/Help (US 2.2) → menu d'aide
        - Les questions normales (US 2.1) → pipeline RAG complet
        """
        user_message = turn_context.activity.text
        conversation_id = turn_context.activity.conversation.id

        if not user_message or not user_message.strip():
            await turn_context.send_activity(
                MessageFactory.text("Je n'ai pas reçu de message. Pouvez-vous reformuler ?")
            )
            return

        try:
            result = self.bot_engine.process_message(
                message=user_message.strip(),
                conversation_id=conversation_id,
                history=[],  # Historique géré à la persistance (Sprint ultérieur)
            )
            await turn_context.send_activity(
                MessageFactory.text(result["reponse"])
            )

        except Exception:
            await turn_context.send_activity(
                MessageFactory.text(
                    "Désolé, une erreur est survenue. Veuillez réessayer dans quelques instants."
                )
            )

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ):
        """
        Appelé quand un nouvel utilisateur rejoint la conversation (US 2.2).

        Envoie le message de bienvenue Smartovate — le contenu est centralisé
        dans BotEngine.get_welcome_message() pour rester cohérent avec la logique métier.
        """
        for member in members_added:
            # Ne pas envoyer le message de bienvenue au bot lui-même
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    MessageFactory.text(self.bot_engine.get_welcome_message())
                )
