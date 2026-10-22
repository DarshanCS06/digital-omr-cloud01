from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.auth.dependencies import require_teacher_or_admin_flexible, check_exam_access
from backend.app.reports.exporter import ReportExporter

router = APIRouter(prefix="/reports", tags=["Reports & Exports"])


@router.get("/csv/{exam_id}")
def export_csv(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin_flexible),
):
    """Exports examination results as a formula-sanitized CSV file.
    Accepts authentication via Bearer header OR ?token= query parameter.
    """
    exam = check_exam_access(exam_id, current_user, db)
    csv_data = ReportExporter.generate_csv_results(exam, db)
    filename = f"Results_{exam.code}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/excel/{exam_id}")
def export_excel(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin_flexible),
):
    """Exports examination results as a styled Excel workbook.
    Accepts authentication via Bearer header OR ?token= query parameter.
    """
    exam = check_exam_access(exam_id, current_user, db)
    excel_bytes = ReportExporter.generate_excel_results(exam, db)
    filename = f"Results_{exam.code}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pdf/{exam_id}")
def export_pdf(
    exam_id: int,
    batch_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin_flexible),
):
    """Exports examination or batch results as a printable PDF report.
    Accepts authentication via Bearer header OR ?token= query parameter.
    """
    exam = check_exam_access(exam_id, current_user, db)
    pdf_bytes = ReportExporter.generate_pdf_results(exam, db, batch_id=batch_id)
    filename = f"Results_{exam.code}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
