from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from solaradmin.models import Report
from solaradmin.schemas import ReportCreate, ReportUpdate

async def create(db: AsyncSession, report_data: ReportCreate):
    report = Report(**report_data.dict())
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report

async def update(db: AsyncSession, report_id: int, report_data: ReportUpdate):
    report = await db.execute(select(Report).where(Report.id == report_id))
    report = report.scalar_one_or_none()
    if report:
        for key, value in report_data.dict(exclude_unset=True).items():
            setattr(report, key, value)
        await db.commit()
        await db.refresh(report)
        return report
    return None

async def delete(db: AsyncSession, report_id: int):
    report = await db.execute(select(Report).where(Report.id == report_id))
    report = report.scalar_one_or_none()
    if report:
        db.delete(report)
        await db.commit()
        return report
    return None
