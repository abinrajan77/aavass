from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    ResetPasswordRequest,
    TowerMembership,
    UserOut,
)
from app.services import auth as auth_service
from app.services.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    user = await auth_service.authenticate_user(db, email=payload.email, password=payload.password)
    permissions, towers = await auth_service.get_user_permissions_and_towers(db, user)

    access_token = create_access_token(user_id=user.id)
    refresh_token = await auth_service.issue_refresh_token(
        db,
        user=user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return LoginResponse(
        user=UserOut.model_validate(user),
        permissions=permissions,
        towers=[TowerMembership(**t) for t in towers],
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    raw_refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not raw_refresh_token:
        raise AppError(401, "REFRESH_TOKEN_INVALID", "No refresh token presented.")

    user, new_refresh_token = await auth_service.rotate_refresh_token(
        db,
        raw_token=raw_refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    access_token = create_access_token(user_id=user.id)
    permissions, towers = await auth_service.get_user_permissions_and_towers(db, user)
    set_auth_cookies(response, access_token=access_token, refresh_token=new_refresh_token)
    return LoginResponse(
        user=UserOut.model_validate(user),
        permissions=permissions,
        towers=[TowerMembership(**t) for t in towers],
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> None:
    raw_refresh_token = request.cookies.get(REFRESH_COOKIE)
    if raw_refresh_token:
        await auth_service.revoke_refresh_token(db, raw_token=raw_refresh_token)
        await db.commit()
    clear_auth_cookies(response)


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    permissions, towers = await auth_service.get_user_permissions_and_towers(db, current_user)
    return MeResponse(
        user=UserOut.model_validate(current_user),
        permissions=permissions,
        towers=[TowerMembership(**t) for t in towers],
    )


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Always 202 regardless of whether the email exists — no user-enumeration.
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is not None and user.is_active:
        await auth_service.create_password_reset_token(db, user=user)
        await db.commit()
        # TODO(module-5/notifications): relay the reset link via the manual-notification
        # model described in overview.md / PRD §8 — no email/SMS sending exists yet in v1.0.
    return {"detail": "If that email exists, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await auth_service.reset_password(
        db, raw_token=payload.token, new_password=payload.new_password
    )
    await db.commit()
    return {"detail": "Password has been reset. Please log in again."}
