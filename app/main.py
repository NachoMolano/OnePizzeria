import logging
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
import google.generativeai as genai

from .config import LLM_MODEL, GOOGLE_API_KEY, supabase
from .memory import PersistedBufferMemory
from .orchestrator.agent import orchestrator_executor # Importar el executor del orquestador

logger = logging.getLogger(__name__)

# Configure logging (if not already configured globally)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[  
        logging.StreamHandler()  # Outputs logs to the console
    ]
)

# Configure the Gemini API key globally
genai.configure(api_key=GOOGLE_API_KEY)

class Msg(BaseModel):
    user_id: str
    text: str
    channel: str = "telegram" 


app = FastAPI()

@app.post("/v1/agent")
async def route(msg: Msg):
    logger.info("Received request for user_id: %s", msg.user_id)
    inputs = {
        "input": msg.text,
        "user_id": msg.user_id,
        "channel": msg.channel
    }
    logger.debug("Agent inputs: %s", inputs)
    # Usar el executor del orquestador
    result = await orchestrator_executor.ainvoke(inputs)
    return {"response": result["output"]}