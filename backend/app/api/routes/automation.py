from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.application.services.daily_import import DailyImportScheduler
from app.database.database import get_session
from app.infrastructure.persistence.automation_repository import SqlAlchemyAutomationRepository
from app.schemas.automation import ImportAutomationRead, ImportAutomationUpdate

router = APIRouter(prefix="/automation", tags=["automation"], dependencies=[Depends(require_admin)])


def get_repository(session: Session = Depends(get_session)) -> SqlAlchemyAutomationRepository:
    return SqlAlchemyAutomationRepository(session)


@router.get("", response_model=ImportAutomationRead)
def read_automation(
    repository: SqlAlchemyAutomationRepository = Depends(get_repository),
) -> ImportAutomationRead:
    return ImportAutomationRead.of(repository.get())


@router.put("", response_model=ImportAutomationRead)
def update_automation(
    payload: ImportAutomationUpdate,
    request: Request,
    repository: SqlAlchemyAutomationRepository = Depends(get_repository),
) -> ImportAutomationRead:
    """Save the schedule and move the routine to it, without a restart.

    Saving to the database is not enough on its own: the scheduler already holds a
    job at the old hour, and it would keep firing there until the application was
    restarted — which on a booth machine means nobody would ever notice.
    """
    automation = repository.save_schedule(enabled=payload.enabled, run_at=payload.run_at)
    if payload.check_enabled is not None or payload.check_interval_minutes is not None:
        automation = repository.save_check(
            enabled=(
                automation.check_enabled if payload.check_enabled is None else payload.check_enabled
            ),
            interval_minutes=payload.check_interval_minutes or automation.check_interval_minutes,
        )
    scheduler: DailyImportScheduler | None = getattr(request.app.state, "daily_import", None)
    if scheduler is not None:
        scheduler.apply(automation)
    return ImportAutomationRead.of(automation)


@router.post("/check", response_model=ImportAutomationRead)
async def run_check(request: Request) -> ImportAutomationRead:
    """Run the facial check now, instead of waiting for the next interval.

    Serves the operator who just enrolled somebody and wants them on the screen
    before they walk to the gate.
    """
    scheduler: DailyImportScheduler | None = getattr(request.app.state, "daily_import", None)
    if scheduler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Monitoramento das faciais não configurado.",
        )
    return ImportAutomationRead.of(await scheduler.check())
