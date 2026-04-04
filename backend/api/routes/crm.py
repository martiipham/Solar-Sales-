from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()

@router.delete("/config")
async def delete_crm_config(
    db: Session = Depends(get_db)
):
    # Add logic to disconnect CRM from wizard here
    pass
