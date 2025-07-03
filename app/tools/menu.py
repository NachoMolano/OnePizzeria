from langchain_core.tools import tool
from app.config import supabase

@tool
def get_menu() -> list:
    """
    Consulta la tabla menu y retorna todos los registros con active = true.
    """
    res = (
        supabase.table("menu")
        .select("*")
        .eq("active", True)
        .execute()
    )
    return res.data