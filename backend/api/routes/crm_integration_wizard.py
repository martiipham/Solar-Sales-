from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()

@router.post("/crm-integration-wizard/start", response_model=dict)
async def start_crm_integration():
    raise HTTPException(status_code=405, detail="NotImplementedError")

@router.post("/crm-integration-wizard/step1", response_model=dict)
async def step1(payload: dict):
    raise HTTPException(status_code=405, detail="NotImplementedError")

@router.post("/crm-integration-wizard/step2", response_model=dict)
async def step2(payload: dict):
    raise HTTPException(status_code=405, detail="NotImplementedError")

@router.post("/crm-integration-wizard/complete", response_model=dict)
async def complete(payload: dict):
    raise HTTPException(status_code=405, detail="NotImplementedError")
