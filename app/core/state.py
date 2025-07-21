"""
Clean state definition for the pizzeria chatbot.
This defines what information flows through our conversation graph.
"""

from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any, List
from langchain_core.messages import BaseMessage


class ChatState(TypedDict):
    """
    Main state that flows through our conversation graph.
    
    Each key represents a piece of information that persists throughout the conversation.
    """
    
    # Core conversation data
    user_id: str                                    # Unique identifier for the user
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]  # Conversation history
    
    # Contextual information
    mensaje_dividido: Optional[List[Dict[str, str]]] = None
    tool_results: Optional[Dict[str, Any]]
    
    # Customer information
    customer: Optional[Dict[str, Any]]              # Customer data from database
    
    # Current conversation context
    current_step: str                               # What step we're in (greeting, menu, order, etc.)
    
    # Order management
    active_order: Optional[Dict[str, Any]]          # Current order being processed
    
    # System flags
    needs_customer_info: bool                       # True if we need to collect customer info
    ready_to_order: bool                           # True if customer is ready to place order
