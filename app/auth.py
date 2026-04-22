from __future__ import annotations

from fastapi import Header, HTTPException

from .config import AppSettings
from .models import AuthenticatedUser, UserRole


def build_auth_dependency(settings: AppSettings):
    def authenticate_user(
        x_api_key: str | None = Header(default=None),
        x_user_id: str | None = Header(default=None),
        x_user_name: str | None = Header(default=None),
        x_user_role: str | None = Header(default=None),
    ) -> AuthenticatedUser:
        if x_api_key != settings.app_secret_key:
            raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header.")

        role_value = (x_user_role or UserRole.operator.value).strip().lower()
        try:
            role = UserRole(role_value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Unsupported role '{role_value}'.") from exc

        user_id = (x_user_id or "local-operator").strip()
        display_name = (x_user_name or user_id).strip()
        return AuthenticatedUser(
            user_id=user_id,
            display_name=display_name,
            role=role,
            api_key_name="primary",
        )

    return authenticate_user
