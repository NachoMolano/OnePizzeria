import logging
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

from ...config import LLM_MODEL, supabase
from ...tools.menu import get_menu
from .prompts import MENU_AGENT_PROMPT

logger = logging.getLogger(__name__)

def create_menu_agent_tool(llm: ChatGoogleGenerativeAI):
    """
    Crea una función que actúa como la herramienta 'menu_agent' para el orquestador.
    Esta función encapsula la lógica del agente de menú.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", MENU_AGENT_PROMPT),
            ("user", "User Message: {input} \n User_ID; {user_id}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    tools = [
        get_menu,
    ]

    menu_executor = AgentExecutor(
        agent=create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt),
        tools=tools,
        verbose=True,
        max_iterations=4
    )

    def menu_agent_runnable(query: str, user_id: str) -> str:
        """
        Ejecuta la lógica del agente de menú y retorna un resumen para el orquestador.
        """
        inputs = {"input": query, "user_id": user_id}
        try:
            result = menu_executor.invoke(inputs)
            if "output" in result:
                return f"Resultado del Agente de Menú: {result['output']}"
            elif "tool_calls" in result and result["tool_calls"]:
                tool_call = result["tool_calls"][0]
                return f"Agente de Menú ejecutó {tool_call.tool}: {tool_call.tool_input}"
            else:
                return f"Agente de Menú procesó la solicitud: {query}"
        except Exception as e:
            logger.error(f"Error en menu_agent_tool: {e}")
            return f"Error al procesar la solicitud del menú: {e}"

    return menu_agent_runnable