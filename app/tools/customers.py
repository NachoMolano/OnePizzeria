from langchain_core.tools import tool
from app.config import supabase

@tool
def find_customer(user_id: str) -> dict:
    """
    Busca un cliente por user_id en la tabla clientes.
    Retorna el primer registro encontrado o un diccionario vacío si no hay coincidencias.   
    """
    res = supabase.table("clientes").select("*").eq("user_id", user_id).limit(1).execute()
    return res.data[0] if res.data else {}

@tool
def create_customer(
    user_id: str,
    first_name: str = "",
    last_name: str = "",
    phone: str = "",
    email: str = "",
    direccion: str = ""
) -> dict:
    """
    Inserta un nuevo registro en la tabla clientes.
    """
    payload = {
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "email": email,
        "direccion": direccion
    }
    res = supabase.table("clientes").insert(payload).execute()
    return res.data[0]

@tool
def update_customer(
    user_id: str,
    first_name: str = None,
    last_name: str = None,
    phone: str = None,
    email: str = None,
    direccion: str = None,
    metadata: dict = None
) -> dict:
    """
    Actualiza campos proporcionados para el cliente con el user_id dado.
    Campos con valor None no se modifican.
    """
    updates = {}
    if first_name is not None:
        updates["first_name"] = first_name
    if last_name is not None:
        updates["last_name"] = last_name
    if phone is not None:
        updates["phone"] = phone
    if email is not None:
        updates["email"] = email
    if direccion is not None:
        updates["direccion"] = direccion
    if metadata is not None:
        updates["metadata"] = metadata
    if not updates:
        return find_customer(user_id)
    res = (
        supabase.table("clientes")
        .update(updates)
        .eq("user_id", user_id)
        .execute()
    )
    return res.data[0] if res.data else {}