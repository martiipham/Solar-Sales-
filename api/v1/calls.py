from fastapi import APIRouter, Depends
from models.call_data import CallData
from agents.call_handler import CallHandlerAgent

router = APIRouter()

@router.post("/calls/")
async def handle_call(call_data: CallData):
    agent = CallHandlerAgent(call_data)
    await agent.process_call()
    return {"message": "Call processed"}
