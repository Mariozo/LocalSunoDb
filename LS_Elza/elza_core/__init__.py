"""Host-neutral Elza Core contracts."""

ELZA_CORE_VERSION = "1.0.0"

from .context import ElzaContext
from .conversation import ConversationService
from .model import Conversation, Message, MessageState, Reaction, Turn

__all__ = [
    "ELZA_CORE_VERSION",
    "Conversation",
    "ConversationService",
    "ElzaContext",
    "Message",
    "MessageState",
    "Reaction",
    "Turn",
]
