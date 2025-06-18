from fastapi import FastAPI
from pydantic import BaseModel
from .agent import executor

class Msg(BaseModel):
    user_id: str
    text: str
    channel: str = "telegram" 


app = FastAPI()


@app.post("/v1/agent")
async def route(msg: Msg):
    result = executor.invoke({"input": msg.text})
    return {"response": result["output"]}