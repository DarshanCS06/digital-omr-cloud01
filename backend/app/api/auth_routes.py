from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.config import settings
from backend.app.models.user import User, UserRole
from backend.app.schemas.auth import (
    Token,
    LoginRequest,
    PasswordResetRequest,
    PasswordChangeRequest,
    UserSummary,
)
from backend.app.auth.security import hash_password, verify_password, create_access_token
from backend.app.auth.dependencies import get_current_user
from backend.app.services.audit import log_audit_action

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
def login(login_req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticates users via email and password using Argon2id."""
    user = db.query(User).filter(User.email == login_req.email.lower().strip()).first()
    if not user or not verify_password(login_req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact the administrator.",
        )

    # Issue JWT
    token_str = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )

    # Audit log login
    client_ip = request.client.host if request.client else None
    log_audit_action(
        db=db,
        action="USER_LOGIN",
        resource_type="USER",
        user_id=user.id,
        resource_id=str(user.id),
        ip_address=client_ip
    )

    return Token(
        access_token=token_str,
        token_type="bearer",
        user=UserSummary(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            is_active=user.is_active,
        ),
    )


@router.get("/me", response_model=UserSummary)
def get_profile(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile."""
    return UserSummary(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
    )


@router.post("/change-password")
def change_password(
    req: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allows an authenticated user to change their password securely."""
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    current_user.hashed_password = hash_password(req.new_password)
    db.commit()

    log_audit_action(
        db=db,
        action="PASSWORD_CHANGE",
        resource_type="USER",
        user_id=current_user.id,
        resource_id=str(current_user.id),
    )
    return {"message": "Password changed successfully"}


@router.post("/reset-password")
def request_password_reset(req: PasswordResetRequest, db: Session = Depends(get_db)):
    """Production password reset request endpoint (prevents email enumeration)."""
    user = db.query(User).filter(User.email == req.email.lower().strip()).first()
    # In production, dispatch email reset token; always return identical response to prevent user enumeration
    if user:
        log_audit_action(
            db=db,
            action="PASSWORD_RESET_REQUESTED",
            resource_type="USER",
            user_id=user.id,
            resource_id=str(user.id),
        )
    return {
        "message": "If the email is registered in our system, password reset instructions have been sent."
    }
