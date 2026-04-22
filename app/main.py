from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .auth import build_auth_dependency
from .command_service import CommandService
from .config import AppSettings
from .execution_engine import ExecutionEngine
from .models import (
    ApprovalActionRequest,
    AuthenticatedUser,
    CommandListResponse,
    CommandRequest,
    CommandResponse,
    MetricsResponse,
)
from .rate_limit import RateLimiter
from .storage import CommandRepository


def create_app(settings: AppSettings | None = None) -> FastAPI:
    active_settings = settings or AppSettings.from_env()
    repository = CommandRepository(active_settings.command_db_path)
    rate_limiter = RateLimiter(
        max_requests=active_settings.request_rate_limit,
        window_seconds=active_settings.rate_limit_window_seconds,
    )
    execution_engine = ExecutionEngine(repository, active_settings)
    command_service = CommandService(repository, execution_engine, active_settings)
    get_current_user = build_auth_dependency(active_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository.initialize()
        yield

    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        description="Guardrailed natural-language command center with persistence, approvals, and mock execution.",
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.repository = repository
    app.state.command_service = command_service
    app.state.rate_limiter = rate_limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_repository(request: Request) -> CommandRepository:
        return request.app.state.repository

    def get_command_service(request: Request) -> CommandService:
        return request.app.state.command_service

    def enforce_rate_limit(request: Request, user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        client_host = request.client.host if request.client else "unknown"
        rate_key = f"{user.user_id}:{client_host}"
        request.app.state.rate_limiter.enforce(rate_key)
        return user

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/parse-command", response_model=CommandResponse)
    async def parse_command(
        request_body: CommandRequest,
        background_tasks: BackgroundTasks,
        user: AuthenticatedUser = Depends(enforce_rate_limit),
        service: CommandService = Depends(get_command_service),
    ) -> CommandResponse:
        return service.submit_command(request_body, user, background_tasks)

    @app.get("/api/v1/commands", response_model=CommandListResponse)
    async def list_commands(
        limit: int = 25,
        _: AuthenticatedUser = Depends(get_current_user),
        repository: CommandRepository = Depends(get_repository),
    ) -> CommandListResponse:
        return CommandListResponse(commands=repository.list_commands(limit=limit))

    @app.get("/api/v1/commands/{command_id}", response_model=CommandResponse)
    async def get_command(
        command_id: str,
        _: AuthenticatedUser = Depends(get_current_user),
        repository: CommandRepository = Depends(get_repository),
    ) -> CommandResponse:
        try:
            return CommandResponse(success=True, data=repository.get_command(command_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/metrics", response_model=MetricsResponse)
    async def get_metrics(
        _: AuthenticatedUser = Depends(get_current_user),
        repository: CommandRepository = Depends(get_repository),
    ) -> MetricsResponse:
        return MetricsResponse(**repository.get_metrics())

    @app.post("/api/v1/commands/{command_id}/approve", response_model=CommandResponse)
    async def approve_command(
        command_id: str,
        request_body: ApprovalActionRequest,
        background_tasks: BackgroundTasks,
        user: AuthenticatedUser = Depends(get_current_user),
        service: CommandService = Depends(get_command_service),
    ) -> CommandResponse:
        try:
            return CommandResponse(
                success=True,
                data=service.approve_command(command_id, user, background_tasks, request_body.note),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/commands/{command_id}/reject", response_model=CommandResponse)
    async def reject_command(
        command_id: str,
        request_body: ApprovalActionRequest,
        user: AuthenticatedUser = Depends(get_current_user),
        service: CommandService = Depends(get_command_service),
    ) -> CommandResponse:
        try:
            return CommandResponse(
                success=True,
                data=service.reject_command(command_id, user, request_body.note),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()
