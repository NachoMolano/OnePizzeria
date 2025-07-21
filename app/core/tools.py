"""
Clean tools management for the pizzeria chatbot.
All tools are organized here for easy understanding and maintenance.
"""

import logging
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from ..config import supabase

logger = logging.getLogger(__name__)


# =============================================================================
# CUSTOMER MANAGEMENT TOOLS
# =============================================================================

@tool
def get_customer(user_id: str) -> Dict[str, Any]:
    """
    Get customer information from database by user_id.
    Returns customer data or empty dict if not found.
    """
    try:
        result = supabase.table("clientes").select("*").eq("user_id", user_id).limit(1).execute()
        if result.data:
            customer = result.data[0]
            logger.info(f"Customer found: {customer.get('first_name', 'Unknown')}")
            return customer
        else:
            logger.info(f"No customer found for user_id: {user_id}")
            return {}
    except Exception as e:
        logger.error(f"Error getting customer {user_id}: {e}")
        return {}


@tool
def create_customer(user_id: str, first_name: str, last_name: str, phone: str = "", email: str = "") -> Dict[str, Any]:
    """
    Create a new customer record in the database.
    If customer already exists, returns the existing customer.
    """
    try:
        logger.info(f"Creating customer with user_id: '{user_id}' (type: {type(user_id)})")
        logger.info(f"Customer name: {first_name} {last_name}")
        
        # First check if customer already exists
        existing_customer = get_customer(user_id)
        if existing_customer:
            logger.info(f"Customer with user_id '{user_id}' already exists. Returning existing customer.")
            return existing_customer
        
        customer_data = {
            "user_id": user_id,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "email": email
        }
        
        result = supabase.table("clientes").insert(customer_data).execute()
        if result.data:
            logger.info(f"Customer created successfully: {first_name} {last_name} with user_id: {user_id}")
            return result.data[0]
        else:
            logger.error("Failed to create customer - no data returned")
            return {}
    except Exception as e:
        # Check if this is a duplicate key error
        if "duplicate key value violates unique constraint" in str(e) and "clientes_user_id_key" in str(e):
            logger.warning(f"Customer with user_id '{user_id}' already exists. Retrieving existing customer.")
            # Return the existing customer instead of failing
            return get_customer(user_id)
        else:
            logger.error(f"Error creating customer: {e}")
            return {}


@tool
def update_customer(user_id: str, **updates) -> Dict[str, Any]:
    """
    Update customer information.
    Only updates fields that are provided.
    """
    try:
        # Remove None values
        clean_updates = {k: v for k, v in updates.items() if v is not None}
        
        if not clean_updates:
            return get_customer(user_id)
        
        result = supabase.table("clientes").update(clean_updates).eq("user_id", user_id).execute()
        if result.data:
            logger.info(f"Customer updated: {user_id}")
            return result.data[0]
        else:
            logger.error("Failed to update customer - no data returned")
            return {}
    except Exception as e:
        logger.error(f"Error updating customer {user_id}: {e}")
        return {}


# =============================================================================
# MENU MANAGEMENT TOOLS
# =============================================================================

@tool
def search_menu(query: str) -> List[Dict[str, Any]]:
    """
    Search menu items by name or description.
    """
    try:
        result = supabase.table("menu").select("*").eq("active", True).ilike("name", f"%{query}%").execute()
        if result.data:
            logger.info(f"Menu search '{query}': {len(result.data)} items found")
            return result.data
        else:
            logger.info(f"Menu search '{query}': No items found")
            return []
    except Exception as e:
        logger.error(f"Error searching menu with query '{query}': {e}")
        return []


@tool
def send_full_menu() -> str:
    """
    Send the complete menu image to the customer.
    Use this when customer asks for the full menu.
    Returns a JSON string that n8n can interpret to send image + text.
    """
    try:
        logger.info("Preparing to send full menu image to customer")
        # Return JSON format that n8n can parse
        import json
        response = {
            "type": "image",
            "image_path": "menu.webp",
            "text": "Te envío nuestro menú completo para que veas todas las opciones que tenemos",
            "has_image": True
        }
        return json.dumps(response)
    except Exception as e:
        logger.error(f"Error preparing menu image: {e}")
        return "Perdón, no pude cargar la imagen del menú. Te puedo ayudar con consultas específicas sobre nuestros productos."


# =============================================================================
# ORDER MANAGEMENT TOOLS
# =============================================================================

@tool
def get_active_order(user_id: str) -> Dict[str, Any]:
    """
    Get the active order for a customer.
    """
    try:
        # First get customer
        customer = get_customer(user_id)
        if not customer:
            return {}
        
        result = supabase.table("pedidos_activos").select("*").eq("cliente_id", customer["id"]).limit(1).execute()
        if result.data:
            logger.info(f"Active order found for customer {customer['first_name']}")
            return result.data[0]
        else:
            logger.info(f"No active order for customer {customer['first_name']}")
            return {}
    except Exception as e:
        logger.error(f"Error getting active order for {user_id}: {e}")
        return {}


@tool
def create_or_update_order(user_id: str, items: List[Dict[str, Any]], subtotal: float, direccion: str = "", metodo_de_pago: str = "") -> Dict[str, Any]:
    """
    Create a new order or update existing active order.
    
    Args:
        user_id: Customer's user ID
        items: List of order items [{"name": "Pizza", "quantity": 1, "price": 25000}]
        subtotal: Total price
        direccion: Delivery address (required for new orders)
        metodo_de_pago: Payment method (required for new orders)
    """
    try:
        # Get customer
        customer = get_customer(user_id)
        if not customer:
            logger.error(f"Cannot create order: customer not found for {user_id}")
            return {}
        
        # Check for existing order
        existing_order = get_active_order(user_id)
        
        order_data = {
            "cart": items,
            "subtotal": subtotal,
            "updated_at": "now()"
        }
        
        if existing_order:
            # Update existing order - only update cart and subtotal
            result = supabase.table("pedidos_activos").update(order_data).eq("id", existing_order["id"]).execute()
            logger.info(f"Order updated for customer {customer['first_name']}")
        else:
            # Create new order - require direccion and metodo_de_pago
            if not direccion:
                logger.error(f"Cannot create order: direccion is required for new orders")
                return {"error": "Dirección de entrega es requerida para crear un pedido"}
            
            if not metodo_de_pago:
                logger.error(f"Cannot create order: metodo_de_pago is required for new orders")
                return {"error": "Método de pago es requerido para crear un pedido"}
            
            # Use correct column names from schema
            order_data.update({
                "cliente_id": customer["id"],
                "direccion": direccion,  # Note: with accent as in schema
                "metodo_de_pago": metodo_de_pago,  # Note: with underscores as in schema
                "status": "creado"
            })
            
            result = supabase.table("pedidos_activos").insert(order_data).execute()
            logger.info(f"New order created for customer {customer['first_name']} with address: {direccion}")
        
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"Error creating/updating order for {user_id}: {e}")
        return {"error": str(e)}


@tool
def finalize_order(user_id: str, total: float) -> Dict[str, Any]:
    """
    Move an active order to finalized orders.
    
    Args:
        user_id: Customer's user ID
        total: Final total including taxes, delivery, etc.
    """
    try:
        # Get customer
        customer = get_customer(user_id)
        if not customer:
            logger.error(f"Cannot finalize order: customer not found for {user_id}")
            return {}
        
        # Get active order
        active_order = get_active_order(user_id)
        if not active_order:
            logger.error(f"Cannot finalize order: no active order found for {user_id}")
            return {}
        
        # Create finalized order
        finalized_order_data = {
            "cliente_id": customer["id"],
            "cart": active_order["cart"],
            "subtotal": active_order["subtotal"],
            "total": total,
            "status": "completado"
        }
        
        # Insert into finalized orders
        result = supabase.table("pedidos_finalizados").insert(finalized_order_data).execute()
        
        if result.data:
            # Remove from active orders
            supabase.table("pedidos_activos").delete().eq("id", active_order["id"]).execute()
            logger.info(f"Order finalized for customer {customer['first_name']}")
            return result.data[0]
        else:
            logger.error("Failed to finalize order")
            return {}
            
    except Exception as e:
        logger.error(f"Error finalizing order for {user_id}: {e}")
        return {"error": str(e)}


@tool
def update_customer_address(user_id: str, direccion: str) -> Dict[str, Any]:
    """
    Update customer's address in the database.
    
    Args:
        user_id: Customer's user ID
        direccion: New address
    """
    try:
        result = supabase.table("clientes").update({"direccion": direccion}).eq("user_id", user_id).execute()
        if result.data:
            logger.info(f"Address updated for customer {user_id}")
            return result.data[0]
        else:
            logger.error("Failed to update address")
            return {}
    except Exception as e:
        logger.error(f"Error updating address for {user_id}: {e}")
        return {"error": str(e)}


# =============================================================================
# TOOL COLLECTIONS
# =============================================================================

# All available tools organized by category
CUSTOMER_TOOLS = [get_customer, create_customer, update_customer, update_customer_address]
MENU_TOOLS = [search_menu, send_full_menu]  # Removed get_menu - only use search_menu and send_full_menu
ORDER_TOOLS = [get_active_order, create_or_update_order, finalize_order]

# Complete tool list for the agent
ALL_TOOLS = CUSTOMER_TOOLS + MENU_TOOLS + ORDER_TOOLS 