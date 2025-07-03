import logging
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

from ...config import LLM_MODEL, supabase
from ...tools.orders import get_active_order, upsert_cart
from ...tools.menu import get_menu
from .prompts import ORDER_AGENT_PROMPT

logger = logging.getLogger(__name__)

def create_order_agent_tool(llm: ChatGoogleGenerativeAI):
    """
    Crea una función que actúa como la herramienta 'order_agent' para el orquestador.
    Esta función encapsula la lógica del agente de pedidos.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ORDER_AGENT_PROMPT),
            ("user", "User Message: {input} \n User_ID; {user_id}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    tools = [
        get_active_order,
        upsert_cart,
        get_menu,
    ]

    order_executor = AgentExecutor(
        agent=create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt),
        tools=tools,
        verbose=True,
        max_iterations=4
    )

    def order_agent_runnable(query: str, user_id: str) -> str:
        """
        Ejecuta la lógica del agente de pedidos y retorna un resumen para el orquestador.
        """
        inputs = {"input": query, "user_id": user_id}
        try:
            result = order_executor.invoke(inputs)
            if "output" in result:
                return f"Resultado del Agente de Pedidos: {result['output']}"
            elif "tool_calls" in result and result["tool_calls"]:
                tool_call = result["tool_calls"][0]
                return f"Agente de Pedidos ejecutó {tool_call.tool}: {tool_call.tool_input}"
            else:
                return f"Agente de Pedidos procesó la solicitud: {query}"
        except Exception as e:
            logger.error(f"Error en order_agent_tool: {e}")
            return f"Error al procesar la solicitud del pedido: {e}"

    return order_agent_runnable