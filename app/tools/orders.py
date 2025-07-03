from langchain_core.tools import tool
from app.config import supabase
from app.tools.customers import find_customer

@tool
def get_active_order(user_id: str) -> dict:
    """
    Busca en pedidos_activos por cliente_id y retorna el registro o {}.
    """
    customer = find_customer(user_id)
    if not customer:
        return {}
    res = (
        supabase.table("pedidos_activos")
        .select("*")
        .eq("cliente_id", customer["id"])
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else {}

@tool
def upsert_cart(user_id: str, cart: list[dict], subtotal: float) -> dict:
    """
    Si existe un pedido activo, actualiza cart y subtotal. Si no, crea uno nuevo.
    El parámetro 'cart' debe ser una lista de diccionarios, donde cada diccionario representa un ítem en el carrito.
    Cada ítem en el carrito debe tener las siguientes claves:
    - 'item_id': (str) El ID único del ítem.
    - 'name': (str) El nombre del ítem.
    - 'quantity': (int) La cantidad del ítem.
    - 'price': (float) El precio unitario del ítem.
    """
    customer = find_customer(user_id)
    if not customer:
        raise ValueError("Cliente no encontrado")
    cliente_id = customer["id"]
    existing = get_active_order(user_id)
    if existing:
        res = (
            supabase.table("pedidos_activos")
            .update({"cart": cart, "subtotal": subtotal, "updated_at": "now()"})
            .eq("id", existing["id"])
            .execute()
        )
    else:
        payload = {"cliente_id": cliente_id, "cart": cart, "subtotal": subtotal}
        res = supabase.table("pedidos_activos").insert(payload).execute()
    return res.data[0]