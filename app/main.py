import logging
from fastapi import FastAPI
from pydantic import BaseModel
import json
from typing import Dict, Any

# Import the new smart memory system
from .core.smart_graph import smart_process_message
from .config import GOOGLE_API_KEY

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class Msg(BaseModel):
    user_id: str
    text: str

app = FastAPI()

def parse_response_for_n8n(response: str) -> Dict[str, Any]:
    """
    Parse Juan's response to determine if it contains image commands.
    Returns structured data for n8n to process.
    """
    try:
        # Try to parse as JSON first (from send_full_menu tool)
        parsed = json.loads(response)
        if isinstance(parsed, dict) and parsed.get("type") == "image":
            return {
                "message_type": "image",
                "text": parsed.get("text", ""),
                "image_path": parsed.get("image_path", ""),
                "has_image": True
            }
    except json.JSONDecodeError:
        # Not JSON, treat as regular text
        pass
    
    # Check for special image markers in text
    if "[SEND_IMAGE:" in response:
        # Extract image path and clean text
        import re
        image_match = re.search(r'\[SEND_IMAGE:([^\]]+)\]', response)
        if image_match:
            image_path = image_match.group(1)
            clean_text = re.sub(r'\[SEND_IMAGE:[^\]]+\]', '', response).strip()
            return {
                "message_type": "image",
                "text": clean_text,
                "image_path": image_path,
                "has_image": True
            }
    
    # Regular text response
    return {
        "message_type": "text",
        "text": response,
        "image_path": "",
        "has_image": False
    }

@app.post("/v1/agent")
async def route(msg: Msg):
    try:
        # Process message through Juan's smart system
        response = await smart_process_message(msg.user_id, msg.text)
        
        # Parse response for n8n
        parsed_response = parse_response_for_n8n(response)
        
        return {
            "response": parsed_response["text"],
            "message_type": parsed_response["message_type"],
            "has_image": parsed_response["has_image"],
            "image_path": parsed_response["image_path"]
        }
    except Exception as e:
        return {
            "response": "Perdón, tuve un problema técnico. En que más te puedo ayudar?",
            "message_type": "text",
            "has_image": False,
            "image_path": ""
        }

@app.get("/v1/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "memory_system": "smart_memory_enabled"}

@app.get("/v1/memory/stats/{user_id}")
async def get_memory_stats(user_id: str):
    """
    Get memory statistics for a specific user.
    Useful for debugging and monitoring.
    """
    try:
        from .core.smart_memory import smart_memory
        stats = await smart_memory.get_conversation_stats(user_id)
        return {"user_id": user_id, "stats": stats}
    except Exception as e:
        logger.error(f"Error getting memory stats for {user_id}: {e}")
        return {"error": "Could not retrieve memory stats"}

@app.post("/v1/memory/cleanup")
async def cleanup_old_conversations():
    """
    Manually trigger cleanup of old conversations.
    In production, this should be called via a cron job.
    """
    try:
        from .core.smart_memory import smart_memory
        cleaned_count = await smart_memory.cleanup_old_conversations()
        return {"message": f"Cleaned up {cleaned_count} old conversations"}
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return {"error": "Cleanup failed"}
