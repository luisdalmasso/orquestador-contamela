# app/openhands_agent/router.py
from fastapi import APIRouter

from app.openhands_agent.service import openhands_service

router = APIRouter()

@router.post("/v1/run_task")
async def run_task(payload: dict):
    """
    Endpoint to receive a task and run the OpenHands agent.
    """
    result = openhands_service.run_task(payload)
    return result
