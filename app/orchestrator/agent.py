import logging
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool

from ..config import LLM_MODEL, supabase, GOOGLE_API_KEY
from ..memory import PersistedBufferMemory

# Importar las funciones que crean las herramientas de los sub-agentes
from ..sub_agents.customer_agent.agent import create_customer_agent_tool
from ..sub_agents.menu_agent.agent import create_menu_agent_tool
from ..sub_agents.order_agent.agent import create_order_agent_tool
from ..sub_agents.general_agent.agent import create_general_agent_tool

# Importar el prompt del orquestador
from .prompts import ORCHESTRATOR_PROMPT

logger = logging.getLogger(__name__)

# Configurar el LLM para el orquestador y los sub-agentes
llm = ChatGoogleGenerativeAI(
    model=LLM_MODEL,
    temperature=0.6
)

# Configurar memoria (la misma instancia para todos los agentes)
summary_memory = PersistedBufferMemory(
    supabase_client=supabase,
    llm=llm,
    memory_key="chat_history",
    input_key="input",
    output_key="output",
    max_token_limit=1500,
)

# Inicializar las funciones que actúan como herramientas de los sub-agentes
customer_agent_tool_instance = create_customer_agent_tool(llm)
menu_agent_tool_instance = create_menu_agent_tool(llm)
order_agent_tool_instance = create_order_agent_tool(llm)
general_agent_tool_instance = create_general_agent_tool(llm)

# Definir las herramientas del orquestador (que son las funciones de los sub-agentes)
@tool
def customer_agent(query: str, user_id: str) -> str:
    """
    Gestiona la información del cliente (crear, buscar, actualizar). Es la primera herramienta que debe ser invocada al inicio de una nueva conversación o cuando se necesite identificar/registrar al usuario.
    Útil cuando el usuario quiere registrarse, actualizar sus datos personales, o si el sistema necesita buscar un cliente.
    Recibe la consulta del usuario y el user_id.
    Retorna un resumen de la operación para que el orquestador genere la respuesta final.
    """
    return customer_agent_tool_instance(query, user_id)

@tool
def menu_agent(query: str, user_id: str) -> str:
    """
    Responde preguntas sobre el menú, precios, ingredientes y productos.
    Útil cuando el usuario pregunta sobre qué pizzas hay, qué ingredientes tienen, precios, etc.
    Recibe la consulta del usuario y el user_id.
    Retorna un resumen de la información del menú para que el orquestador genere la respuesta final.
    """
    return menu_agent_tool_instance(query, user_id)

@tool
def order_agent(query: str, user_id: str) -> str:
    """
    Toma y gestiona pedidos de pizza, incluyendo la consulta de su estado.
    Útil cuando el usuario quiere hacer un pedido, añadir ítems al carrito, modificar un pedido existente, finalizar un pedido o consultar el estado de su pedido.
    Recibe la consulta del usuario y el user_id.
    Retorna un resumen de la operación del pedido para que el orquestador genere la respuesta final.
    """
    return order_agent_tool_instance(query, user_id)

@tool
def general_agent(query: str, user_id: str) -> str:
    """
    Responde preguntas generales o si la intención del usuario no encaja en ninguna de las categorías anteriores.
    Útil para preguntas como horarios, ubicación, métodos de contacto, etc.
    Recibe la consulta del usuario y el user_id.
    Retorna una respuesta general o un resumen para que el orquestador genere la respuesta final.
    """
    return general_agent_tool_instance(query, user_id)


# Recopilar todas las herramientas del orquestador
orchestrator_tools = [
    customer_agent,
    menu_agent,
    order_agent,
    general_agent,
]

# Crear el prompt del orquestador
orchestrator_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", ORCHESTRATOR_PROMPT),
        ("user", "User Message: {input} \n User_ID; {user_id}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

# Crear el agente orquestador
orchestrator_agent = create_tool_calling_agent(
    llm=llm,
    tools=orchestrator_tools,
    prompt=orchestrator_prompt
)

# Crear el executor del orquestador
orchestrator_executor = AgentExecutor(
    agent=orchestrator_agent,
    tools=orchestrator_tools,
    verbose=True,
    max_iterations=4
)