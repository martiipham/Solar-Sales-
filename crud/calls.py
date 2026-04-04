from sqlalchemy import delete, insert
from models.call_data import CallData

async def create_call(db, call_data):
    query = insert(CallData).values(**call_data.dict())
    await db.execute(query)
    await db.commit()

async def delete_call(db, call_id):
    query = delete(CallData).where(CallData.id == call_id)
    await db.execute(query)
    await db.commit()
