from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from solaradmin.dependencies import get_db_session
from solaradmin.schemas import Report, ReportCreate, ReportUpdate
from solaradmin.crud import reports

router = APIRouter()

@router.get("/reports/", response_model=list[Report])
async def get_reports(
    db: AsyncSession = Depends(get_db_session)
):
   stmt = select(Report)
    results = await db.execute(stmt)
    return results.scalars().all()

@router.post("/reports/", response_model=Report)
async def create_report(
    report_data: ReportCreate,
    db: AsyncSession = Depends(get_db_session)
):
    report = reports.create(db=db, report_data=report_data)
    return report

@router.patch("/reports/{report_id}", response_model=Report)
async def update_report(
    report_id: int,
    report_data: ReportUpdate,
    db: AsyncSession = Depends(get_db_session)
):
    report = reports.update(db=db, report_id=report_id, report_data=report_data)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.delete("/reports/{report_id}", response_model=Report)
async def delete_report(
    report_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    report = reports.delete(db=db, report_id=report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
