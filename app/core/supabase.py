import os

from supabase import Client, create_client

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)

# PEDIDOS

def get_orders() -> list[dict]:
    return supabase.table("pedidos_activos").select("*").execute().data

def get_order_by_id(id: int) -> dict:
    return supabase.table("pedidos_activos").select("*").eq("id", id).execute().data[0]

def get_order_by_client_id(client_id: int) -> list[dict]:
    return supabase.table("pedidos_activos").select("*").eq("cliente_id", client_id).execute().data

def create_order(order: dict) -> None:
    supabase.table("pedidos_activos").insert(order).execute()

def update_order(order: dict) -> None:
    supabase.table("pedidos_activos").update(order).eq("id", order["id"]).execute()

def delete_order(order: dict) -> None:
    supabase.table("pedidos_activos").delete().eq("id", order["id"]).execute()
    
def finish_order(order: dict) -> None:
    supabase.table("pedidos_activos").delete().eq("id", order["id"]).execute()
    supabase.table("pedidos_finalizados").insert(order).execute()


# CLIENTES

def get_client_by_phone_number(phone_number: str) -> dict:
    return supabase.table("clientes").select("*").eq("id", phone_number).execute().data[0]

def get_client_by_full_name(full_name: str) -> dict:
    return supabase.table("clientes").select("*").eq("nombre_completo", full_name).execute().data[0]

def create_client(client: dict) -> None:
    supabase.table("clientes").insert(client).execute()

def update_client(client: dict) -> None:
    supabase.table("clientes").update(client).eq("id", client["id"]).execute()

#def delete_client(client: dict) -> None:
#    supabase.table("clientes").delete().eq("id", client["id"]).execute()

# PIZZAS

def get_pizzas() -> list[dict]:
    return supabase.table("pizzas_armadas").select("*").execute().data

def get_pizzas_by_all_ingredients(ingredients: list[str]) -> list[dict]:
    # First get the ingredient IDs that match any of the input ingredient names
    ingredient_ids = supabase.table("ingredientes") \
        .select("id") \
        .or_(f"name.ilike.%{ingredient}%" for ingredient in ingredients) \
        .execute().data
    
    # Extract just the IDs
    ids = [ing["id"] for ing in ingredient_ids]
    
    # Get pizzas that contain ALL the specified ingredients
    # We use a subquery to count matches and ensure all ingredients are present
    pizzas = supabase.table("pizzas_armadas") \
        .select("*") \
        .in_("id", 
            supabase.table("ingredientes_pizzas") \
            .select("pizza_id") \
            .in_("ingrediente_id", ids) \
            .group("pizza_id") \
            .gte("count", len(ids)) \
            .execute().data
        ) \
        .execute().data
    
    return pizzas

def get_pizza_by_name(name: str) -> dict:
    return supabase.table("pizzas_armadas").select("*").eq("nombre", name).execute().data[0]

def get_pizzas_by_type(type: str) -> list[dict]:
    return supabase.table("pizzas_armadas").select("*").eq("tipo", type).execute().data

# COMBOS

def get_combos() -> list[dict]:
    return supabase.table("combos").select("*").execute().data

def get_combo_by_name(name: str) -> dict:
    return supabase.table("combos").select("*").eq("nombre", name).execute().data[0]

# BEBIDAS

def get_beverages() -> list[dict]:
    return supabase.table("bebidas").select("*").execute().data

def get_beverage_by_name(name: str) -> dict:
    return supabase.table("bebidas").select("*").eq("nombre_producto", name).execute().data[0]

def get_beverages_by_sugar(sugar: bool) -> list[dict]:
    return supabase.table("bebidas").select("*").eq("azucar", sugar).execute().data

def get_beverages_by_alcohol(alcohol: bool) -> list[dict]:
    return supabase.table("bebidas").select("*").eq("alcohol", alcohol).execute().data

# ADICIONES

def get_aditions() -> list[dict]:
    return supabase.table("adiciones").select("*").execute().data

def get_adition_by_name(name: str) -> dict:
    return supabase.table("adiciones").select("*").eq("nombre", name).execute().data[0]

# BORDES

def get_borders() -> list[dict]:
    return supabase.table("bordes").select("*").execute().data

def get_border_by_name(name: str) -> dict:
    return supabase.table("bordes").select("*").eq("nombre", name).execute().data[0]