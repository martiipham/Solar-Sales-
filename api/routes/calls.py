from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from crud import call_crud  # Import the CRUD module
from models import Call  # Import the Call model
from schemas import CallCreate, CallUpdate

router = APIRouter()

@router.post("/", response_model=Call)
def create_call(call: CallCreate, db: Session = Depends(get_db)):
    db_call = call_crud.create(db=db, call=call)
    return db_call

@router.get("/", response_model=list[Call])
def read_calls(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    calls = call_crud.read_all(db=db, skip=skip, limit=limit)
    return calls

@router.get("/{call_id}", response_model=Call)
def read_call(call_id: int, db: Session = Depends(get_db)):
    db_call = call_crud.read_by_id(db=db, call_id=call_id)
    if not db_call:
        raise HTTPException(status_code=404, detail="Call not found")
    return db_call

@router.put("/{call_id}", response_model=Call)
def update_call(call_id: int, call_update: CallUpdate, db: Session = Depends(get_db)):
    db_call = call_crud.read_by_id(db=db, call_id=call_id)
    if not db_call:
        raise HTTPException(status_code=404, detail="Call not found")
    updated_call = call_crud.update(db=db, db_call=db_call, update_data=call_update)
    return updated_call

@router.delete("/{call_id}", status_code=204)
def delete_call(call_id: int, db: Session = Depends(get_db)):
    db_call = call_crud.read_by_id(db=db, call_id=call_id)
    if not db_call:
        raise HTTPException(status_code=404, detail="Call not found")
    call_crud.delete(db=db, db_call=db_call)
    return
