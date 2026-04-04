from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Report, ReportSchema

router = APIRouter()

@router.get("/reports/", response_model=list[ReportSchema])
def get_reports(db: Session = Depends(get_db)):
    reports = db.query(Report).all()
    if not reports:
        raise HTTPException(status_code=404, detail="Reports not found")
    return reports

@router.post("/reports/", response_model=ReportSchema)
def create_report(report: ReportSchema, db: Session = Depends(get_db)):
    new_report = Report(**report.dict())
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report
