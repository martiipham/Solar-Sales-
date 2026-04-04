from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class LogEntry(BaseModel):
    level: str
    message: str
    timestamp: Optional[str] = None

@router.post("/logs")
async def log_message(log: LogEntry):
    """Log an error message to the system logs"""
    # In a production system, this would write to a file or database
    # For demo purposes, we'll just print to console
    print(f"[{log.level}] {log.message}")
    return {"status": "logged"}
