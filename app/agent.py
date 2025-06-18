from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from .config import GROQ_API_KEY, LLM_MODEL

# Configure the Groq client
llm = ChatGroq(
    model=LLM_MODEL,
    api_key=GROQ_API_KEY,
    temperature=0.6
)


# Add your tools here
tools = []

# Create the prompt template using the hub approach or manual creation
# This is the most reliable way to ensure compatibility
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a helpful assistant that can answer questions about a restaurant's menu, customers, and orders. 
You can look up menu items, add or update customer information, and create new orders.
Always be polite and helpful when assisting customers.""",
        ),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

# Verify the prompt has the required variables
print("Prompt input variables:", prompt.input_variables)

agent = create_tool_calling_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=4
)