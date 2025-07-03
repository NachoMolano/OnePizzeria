import logging
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

from ...config import LLM_MODEL, supabase
from ...tools.customers import create_customer, find_customer, update_customer
from .prompts import CUSTOMER_AGENT_PROMPT # Mantendremos el prompt para guiar al LLM interno

logger = logging.getLogger(__name__)

def create_customer_agent_tool(llm: ChatGoogleGenerativeAI):
    """
    Crea una función que actúa como la herramienta 'customer_agent' para el orquestador.
    Esta función encapsula la lógica del agente de clientes.
    """
    # Creamos un AgentExecutor interno para que el sub-agente pueda usar sus herramientas
    # Este executor usará el CUSTOMER_AGENT_PROMPT para decidir qué herramienta llamar
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", CUSTOMER_AGENT_PROMPT),
            ("user", "User Message: {input} \n User_ID; {user_id}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    tools = [
        find_customer,
        create_customer,
        update_customer,
    ]

    customer_executor = AgentExecutor(
        agent=create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt),
        tools=tools,
        verbose=True, # Mantener verbose para depuración interna
        max_iterations=4
    )

    def customer_agent_runnable(query: str, user_id: str) -> str:
        """
        Ejecuta la lógica del agente de clientes y retorna un resumen para el orquestador.
        """
        inputs = {"input": query, "user_id": user_id}
        try:
            # Permitimos que el executor interno decida qué herramienta llamar (find_customer, create_customer, update_customer)
            result = customer_executor.invoke(inputs)

            # Aquí es donde transformamos la salida del sub-agente en un formato para el orquestador
            if "output" in result:
                # Si el sub-agente genera una respuesta directa (ej. "Sus datos han sido registrados con éxito.")
                return f"RESPUESTA_CLIENTE: {result['output']}"
            elif "tool_calls" in result and result["tool_calls"]:
                # Si el sub-agente llamó a una herramienta, podemos resumir eso
                tool_call = result["tool_calls"][0] # Asumiendo una sola llamada por simplicidad
                return f"ACCION_CLIENTE: Agente de Clientes ejecutó {tool_call.tool} con {tool_call.tool_input}"
            else:
                # En caso de que no haya output ni tool_calls (ej. si el LLM decide no hacer nada)
                return f"ACCION_CLIENTE: Agente de Clientes procesó la solicitud sin acción directa: {query}"

        except Exception as e:
            logger.error(f"Error en customer_agent_tool: {e}")
            return f"ERROR_CLIENTE: Error al procesar la solicitud del cliente: {e}"

    return customer_agent_runnable
