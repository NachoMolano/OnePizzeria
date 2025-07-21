"""
Smart Graph implementation for the pizzeria chatbot.
This version integrates with the SmartMemoryManager for intelligent conversation memory.
"""

import logging
from typing import Dict, Any
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from .state import ChatState
from .tools import ALL_TOOLS, get_menu
from .prompts import (
    SYSTEM_PROMPT, CONTEXT_NEW_CUSTOMER, CONTEXT_RETURNING_CUSTOMER,
    CONTEXT_MENU_INQUIRY, CONTEXT_ORDER_START, ERROR_GENERAL, CONTEXT_CONFUSION
)
from .smart_checkpointer import state_manager
from langgraph.checkpoint.memory import MemorySaver
from ..config import OPENAI_MODEL
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


# =============================================================================
# LLM SETUP
# =============================================================================

llm_with_tools = ChatOpenAI(
    model=OPENAI_MODEL,
    temperature=0.5,
    max_retries=3,
    timeout=10,
    max_tokens=2000 
).bind_tools(ALL_TOOLS)


llm_without_tools = ChatOpenAI(
    model=OPENAI_MODEL,
    temperature=0.5,
    max_retries=3,
    timeout=10,
    max_tokens=2000 
)

# =============================================================================
# SMART GRAPH NODES - Enhanced with memory integration
# =============================================================================

async def smart_load_state_node(state: ChatState) -> Dict[str, Any]:
    """
    Load complete conversation state including memory.
    ALWAYS checks if customer is registered at the start of any conversation.
    """
    user_id = state["user_id"]
    new_message = state["messages"][-1].content if state["messages"] else ""
    
    logger.info(f"Loading smart state for user: {user_id}")
    
    try:
        # CRITICAL: Always check if customer is registered first
        from .tools import get_customer
        customer = get_customer.invoke({"user_id": user_id})
        
        # Load complete state using our smart state manager
        complete_state = await state_manager.load_state_for_user(user_id, new_message)
        
        # Determine if this is a new conversation (no previous messages in memory)
        is_new_conversation = len(complete_state.get("messages", [])) == 0
        
        # IMPORTANT: Detect user intent to set correct current_step
        user_intent = _detect_user_intent(state)
        logger.info(f"User intent detected: {user_intent}")
        
        # Set current_step based on user intent
        if user_intent == "full_menu":
            current_step = "full_menu"
        elif user_intent == "menu":
            current_step = "menu"
        elif user_intent == "order":
            current_step = "order"
        elif user_intent == "confirmation":
            current_step = "confirmation"
        elif is_new_conversation:
            # This is the first interaction - start with greeting
            current_step = "greeting"
        else:
            # Continuing conversation - use general or detected intent
            current_step = user_intent if user_intent != "general" else "general"
        
        needs_customer_info = not customer or not customer.get("last_name")
        
        # Return the loaded state data
        return {
            "customer": customer,  # Always include customer data (empty dict if not found)
            "current_step": current_step,
            "active_order": complete_state.get("active_order", {}),
            "needs_customer_info": needs_customer_info,
            "ready_to_order": bool(customer and customer.get("last_name")),
            "messages": complete_state.get("messages", [])  # This includes conversation history
        }
        
    except Exception as e:
        logger.error(f"Error loading smart state for {user_id}: {e}")
        return {
            "customer": {},
            "current_step": "greeting",
            "active_order": {},
            "needs_customer_info": True,
            "ready_to_order": False
        }


def smart_conversation_node(state: ChatState) -> Dict[str, Any]:
    """
    Enhanced conversation node that uses conversation memory.
    Juan handles different types of interactions naturally.
    """
    current_step = state.get("current_step", "unknown")
    logger.info(f"Processing smart conversation for step: {current_step}")
    
    try:
        # Special handling for full menu requests
        if current_step == "full_menu":
            logger.info("DETECTED FULL_MENU REQUEST - Using send_full_menu tool directly")
            # For full menu requests, Juan should use send_full_menu tool
            from .tools import send_full_menu
            menu_response = send_full_menu.invoke({})
            
            # The send_full_menu tool returns JSON, so we need to return that directly
            # This will be processed by the parse_response_for_n8n function
            response = AIMessage(content=menu_response)
            
            # Log the action
            logger.info(f"Juan is sending full menu image to customer. Response: {menu_response}")
        else:
            logger.info(f"USING NORMAL LLM FLOW for step: {current_step}")
            # Build context for the AI using conversation history
            context = _build_smart_conversation_context(state)
            
            # Generate response using LLM with tools
            response = llm_with_tools.invoke(context)
            
            # Log tool calls for debugging
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"Generated {len(response.tool_calls)} tool calls: {[tc.get('name', 'unknown') for tc in response.tool_calls]}")
        
        # Update state based on response
        new_state = _update_state_from_response(state, response)
        new_state["messages"] = [response]
        
        return new_state
        
    except Exception as e:
        logger.error(f"Error in smart conversation node: {e}")
        error_message = AIMessage(content=ERROR_GENERAL)
        return {"messages": [error_message]}


async def smart_save_state_node(state: ChatState) -> Dict[str, Any]:
    """
    Save conversation state to smart memory.
    """
    try:
        # Get the AI response (last message)
        ai_response = state["messages"][-1].content if state["messages"] else ""
        
        # Save state using our smart state manager
        await state_manager.save_state_for_user(state, ai_response)
        
        logger.info(f"Smart state saved for user: {state['user_id']}")
        return {}
        
    except Exception as e:
        logger.error(f"Error saving smart state: {e}")
        return {}


def _build_smart_conversation_context(state: ChatState) -> list:
    """
    Build conversation context using memory and current state.
    Juan always checks customer status and responds accordingly.
    """
    messages = []
    
    # Always start with Juan's system prompt
    messages.append(("system", SYSTEM_PROMPT))
    
    # CRITICAL: Add user_id to context so Juan knows which user_id to use for tools
    user_id = state["user_id"]
    messages.append(("system", f"IMPORTANTE: El user_id de este cliente es '{user_id}'. Usa SIEMPRE este user_id exacto cuando uses herramientas como get_customer, create_customer, etc. NO uses el nombre del cliente como user_id."))
    
    # Add situational context based on current step and customer info
    if state["current_step"] == "greeting":
        if state.get("customer") and state["customer"].get("first_name"):
            # Returning customer - greet by name
            customer_name = f"{state['customer'].get('first_name', '')} {state['customer'].get('last_name', '')}"
            context = CONTEXT_RETURNING_CUSTOMER.format(customer_name=customer_name.strip())
            messages.append(("system", context))
            messages.append(("system", f"IMPORTANTE: Este cliente se llama {customer_name.strip()}. Salúdalo por su nombre real."))
        else:
            # New customer - be cordial but don't ask for info unless ordering
            messages.append(("system", CONTEXT_NEW_CUSTOMER))
            messages.append(("system", "IMPORTANTE: Este cliente NO está registrado. NO inventes nombres. Salúdalo cordialmente sin usar nombres inventados."))
    
    elif state["current_step"] == "menu":
        messages.append(("system", CONTEXT_MENU_INQUIRY))
    
    elif state["current_step"] == "full_menu":
        messages.append(("system", CONTEXT_MENU_INQUIRY))
        messages.append(("system", "IMPORTANTE: El cliente pidió el MENÚ COMPLETO. Debes usar la herramienta send_full_menu para enviar la imagen del menú."))
    
    elif state["current_step"] == "order":
        messages.append(("system", CONTEXT_ORDER_START))
    
    elif state["current_step"] == "confirmation":
        messages.append(("system", CONTEXT_ORDER_CONFIRMATION))
    
    # Add customer context if available
    if state.get("customer") and state["customer"]:
        customer_info = f"Datos del cliente en la base de datos: {state['customer']}"
        messages.append(("system", customer_info))
    else:
        messages.append(("system", "IMPORTANTE: Este cliente NO está en la base de datos. NO inventes información sobre él."))
    
    # Add current order context if available
    if state.get("active_order") and state["active_order"]:
        order_info = f"Pedido activo actual: {state['active_order']}"
        messages.append(("system", order_info))
    
    # Add conversation history from smart memory
    conversation_messages = []
    for msg in state.get("messages", []):
        if isinstance(msg, HumanMessage):
            conversation_messages.append(("human", msg.content))
        elif isinstance(msg, AIMessage):
            conversation_messages.append(("assistant", msg.content))
    
    messages.extend(conversation_messages)
    
    return messages


def _detect_user_intent(state: ChatState) -> str:
    """
    Detect user intent based on their last message.
    Juan needs to distinguish between full menu requests vs specific queries.
    """
    if not state["messages"]:
        return "greeting"
    
    # Get the last human message
    last_human_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_human_message = msg.content.lower()
            break
    
    if not last_human_message:
        return "greeting"
    
    # Full menu request keywords (should send image)
    full_menu_keywords = [
        "menú completo", "menu completo", "el menú", "el menu", "ver el menú", "ver el menu",
        "muéstrame el menú", "muestrame el menu", "envíame el menú", "enviame el menu",
        "quiero ver el menú", "quiero ver el menu", "menú", "menu", "carta", "la carta",
        "qué tienen", "que tienen", "qué hay", "que hay", "qué venden", "que venden",
        "opciones", "productos", "comida", "pizzas tienen", "pizzas hay"
    ]
    
    # Specific menu queries (should use database)
    specific_menu_keywords = [
        "precio de", "precios de", "cuesta la", "cuánto cuesta", "cuanto cuesta", 
        "ingredientes de", "lleva la", "pizza de", "tamaño de", "tamaños de"
    ]
    
    # Order-related keywords
    order_keywords = [
        "pedido", "orden", "comprar", "quiero una", "me gustaría una", "voy a pedir",
        "hacer pedido", "ordenar", "pedir una"
    ]
    
    # Confirmation keywords
    confirmation_keywords = [
        "confirmar", "listo", "perfecto", "sí", "si", "ok", "está bien", "esta bien"
    ]
    
    # Check for specific menu queries first (more specific)
    if any(keyword in last_human_message for keyword in specific_menu_keywords):
        print(f"Detected menu")
        return "menu"
    
    # Check for full menu request
    if any(keyword in last_human_message for keyword in full_menu_keywords):
        print(f"Detected full menu")
        return "full_menu"
    
    # Check for order intent
    if any(keyword in last_human_message for keyword in order_keywords):
        print(f"Detected order")
        return "order"
    
    # Check for confirmation
    if any(keyword in last_human_message for keyword in confirmation_keywords):
        print(f"Detected confirmation")
        return "confirmation"
    
    print(f"Detected general")
    return "general"


def _update_state_from_response(state: ChatState, response: AIMessage) -> Dict[str, Any]:
    """
    Update state based on AI response.
    Juan's conversation flow management.
    """
    # Keep the current step as it was set by smart_load_state_node
    # The intent detection is now done there
    return {"current_step": state.get("current_step", "general")}


# =============================================================================
# ROUTING LOGIC
# =============================================================================

def should_use_tools(state: ChatState) -> str:
    """
    Determine if we should use tools or end the conversation.
    """
    if not state["messages"]:
        return "save_and_end"
    
    last_message = state["messages"][-1]
    
    # Check if the last message has tool calls
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "use_tools"
    else:
        return "save_and_end"


def smart_final_response_node(state: ChatState) -> Dict[str, Any]:
    """
    Generate a final response after using tools, without allowing more tool calls.
    """
    try:
        # Build conversation context
        raw_messages = _build_smart_conversation_context(state)
        
        # Convert tuple messages to proper LangChain message objects
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        
        # Combine all system messages into one
        system_content = []
        human_messages = []
        assistant_messages = []
        
        # Process messages and look for tool results
        for role, content in raw_messages:
            if role == "system":
                system_content.append(content)
            elif role == "human":
                human_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                assistant_messages.append(AIMessage(content=content))
        
        # Add instruction about using tool results that are already in the conversation
        system_content.append("IMPORTANTE: Las herramientas ya se ejecutaron y sus resultados están en la conversación anterior. Usa EXACTAMENTE esos resultados para responder. Sigue las reglas de formato del CONTEXT_MENU_INQUIRY para respuestas concisas y bien organizadas. NO ejecutes más herramientas. NO inventes información.")
        
        # Add final instruction to system content
        system_content.append("Genera una respuesta natural y humana basada en los resultados de las herramientas que ya se ejecutaron. Usa el formato optimizado para evitar respuestas muy largas. Si hay muchas pizzas, muestra solo algunos ejemplos y menciona que hay más opciones.")
        
        # Create final message list
        messages = [
            SystemMessage(content="\n".join(system_content))
        ]
        messages.extend(human_messages)
        messages.extend(assistant_messages)
        
        # Get AI response WITHOUT allowing tool calls
        response = llm_without_tools.invoke(messages)
        
        # Ensure response is properly formatted
        if hasattr(response, 'content'):
            response_content = response.content
            
            # Handle different response formats
            if isinstance(response_content, list):
                # If it's a list, join into a single coherent string
                if all(isinstance(item, str) for item in response_content):
                    response_content = " ".join(response_content).strip()
                else:
                    # Extract text from mixed content
                    text_parts = []
                    for item in response_content:
                        if isinstance(item, str):
                            text_parts.append(item)
                        elif hasattr(item, 'text'):
                            text_parts.append(item.text)
                        elif hasattr(item, 'content'):
                            text_parts.append(str(item.content))
                    response_content = " ".join(text_parts).strip()
            
            # Create a clean AIMessage with the formatted content
            response = AIMessage(content=response_content)
        
        # Add AI response to messages
        new_messages = list(state["messages"])
        if not isinstance(response, AIMessage):
            response = AIMessage(content=str(response))
        new_messages.append(response)
        
        return {
            "messages": new_messages
        }
        
    except Exception as e:
        logger.error(f"Error in smart_final_response_node: {e}")
        error_response = AIMessage(content=ERROR_GENERAL)
        messages_list = list(state["messages"])
        messages_list.append(error_response)
        return {
            "messages": messages_list
        }


# =============================================================================
# SMART GRAPH CREATION
# =============================================================================

def create_smart_graph():
    """
    Create and compile the smart conversation graph with memory.
    """
    # Create the graph
    workflow = StateGraph(ChatState)
    
    # Add nodes
    workflow.add_node("load_state", smart_load_state_node)
    workflow.add_node("conversation", smart_conversation_node)
    workflow.add_node("tools", ToolNode(ALL_TOOLS))
    workflow.add_node("final_response", smart_final_response_node)
    workflow.add_node("save_state", smart_save_state_node)
    
    # Set entry point
    workflow.set_entry_point("load_state")
    
    # Add edges
    workflow.add_edge("load_state", "conversation")
    workflow.add_conditional_edges(
        "conversation",
        should_use_tools,
        {
            "use_tools": "tools",
            "save_and_end": "save_state"
        }
    )
    # After tools, generate final response then end
    workflow.add_edge("tools", "final_response")
    workflow.add_edge("final_response", "save_state")
    workflow.add_edge("save_state", END)
    
    # Compile with memory checkpointer
    return workflow.compile(checkpointer=MemorySaver())


# Create the smart graph
smart_graph = create_smart_graph()

logger.info("Smart LangGraph with memory compiled successfully!")


# =============================================================================
# SMART INTERFACE - Enhanced process_message function
# =============================================================================

async def smart_process_message(user_id: str, message: str) -> str:
    """
    Enhanced message processing with smart memory.
    Now handles special image commands for Telegram integration.
    
    Args:
        user_id: Unique identifier for the user
        message: User's message
        
    Returns:
        AI response as string (may include special image commands)
    """
    try:
        # Log the incoming user_id for debugging
        logger.info(f"Processing message for user_id: '{user_id}' (type: {type(user_id)})")
        logger.info(f"Message content: '{message}'")
        
        # Create initial state - we only need user_id and the new message
        # The smart_load_state_node will handle loading the complete state
        from langchain_core.messages import HumanMessage
        
        initial_state = ChatState(
            user_id=user_id,
            messages=[HumanMessage(content=message)],
            customer=None,  # Will be loaded by smart_load_state_node
            current_step="unknown",  # Will be determined by smart_load_state_node
            active_order=None,  # Will be loaded by smart_load_state_node
            needs_customer_info=True,  # Will be determined by smart_load_state_node
            ready_to_order=False  # Will be determined by smart_load_state_node
        )
        
        # Process through smart graph
        config = {"configurable": {"thread_id": user_id}}
        final_state = await smart_graph.ainvoke(initial_state, config=config)
        
        # Extract response - handle different content formats
        if final_state and "messages" in final_state and final_state["messages"]:
            # Find the last AI message
            for msg in reversed(final_state["messages"]):
                if isinstance(msg, AIMessage) and msg.content:
                    content = msg.content
                    
                    # Handle different content formats
                    if isinstance(content, str):
                        # Check if this is an image command
                        if "[SEND_IMAGE:" in content:
                            logger.info(f"Image command detected for {user_id}")
                        
                        logger.info(f"Smart response generated for {user_id}")
                        return content
                    elif isinstance(content, list):
                        # List content - join into a single string
                        if all(isinstance(item, str) for item in content):
                            # List of strings
                            response = " ".join(content).strip()
                            
                            # Check for image commands in the joined response
                            if "[SEND_IMAGE:" in response:
                                logger.info(f"Image command detected in list response for {user_id}")
                            
                            logger.info(f"Smart response generated for {user_id} (from list)")
                            return response
                        else:
                            # Mixed content - extract text parts
                            text_parts = []
                            for item in content:
                                if isinstance(item, str):
                                    text_parts.append(item)
                                elif hasattr(item, 'text'):
                                    text_parts.append(item.text)
                                elif hasattr(item, 'content'):
                                    text_parts.append(str(item.content))
                            
                            if text_parts:
                                response = " ".join(text_parts).strip()
                                
                                # Check for image commands
                                if "[SEND_IMAGE:" in response:
                                    logger.info(f"Image command detected in mixed content for {user_id}")
                                
                                logger.info(f"Smart response generated for {user_id} (from mixed content)")
                                return response
                    else:
                        # Other content types - convert to string
                        response = str(content).strip()
                        
                        # Check for image commands
                        if "[SEND_IMAGE:" in response:
                            logger.info(f"Image command detected in converted content for {user_id}")
                        
                        logger.info(f"Smart response generated for {user_id} (converted to string)")
                        return response
        
        logger.warning(f"No valid response generated for {user_id}")
        return ERROR_GENERAL
        
    except Exception as e:
        logger.error(f"Error in smart message processing for {user_id}: {e}")
        return ERROR_GENERAL 