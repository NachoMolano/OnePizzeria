import logging
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

from ...config import LLM_MODEL, supabase
from .prompts import GENERAL_AGENT_PROMPT

logger = logging.getLogger(__name__)

def create_general_agent_tool(llm: ChatGoogleGenerativeAI):
    """
    Crea una función que actúa como la herramienta 'general_agent' para el orquestador.
    Esta función encapsula la lógica del agente general.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", GENERAL_AGENT_PROMPT),
            ("user", "User Message: {input} \n User_ID; {user_id}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    tools = [] # El agente general no tiene herramientas específicas

    general_executor = AgentExecutor(
        agent=create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt),
        tools=tools,
        verbose=True,
        max_iterations=4
    )

    def general_agent_runnable(query: str, user_id: str) -> str:
        """
        Ejecuta la lógica del agente general y retorna un resumen para el orquestador.
        """
        inputs = {"input": query, "user_id": user_id}
        try:
            result = general_executor.invoke(inputs)
            if "output" in result:
                return f"Respuesta General: {result['output']}"
            elif "tool_calls" in result and result["tool_calls"]:
                tool_call = result["tool_calls"][0]
                return f"Agente General ejecutó {tool_call.tool}: {tool_call.tool_input}"
            else:
                return f"Agente General procesó la solicitud: {query}"
        except Exception as e:
            logger.error(f"Error en general_agent_tool: {e}")
            return f"Error al procesar la solicitud general: {e}"

    return general_agent_runnable