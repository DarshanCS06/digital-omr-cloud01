from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.user import UserCreate, UserUpdate, UserResponse
from backend.app.auth.security import hash_password
from backend.app.auth.dependencies import require_admin
from backend.app.services.audit import log_audit_action

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Lists all users (Administrator only)."""
    return db.query(User).order_by(User.id.asc()).all()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Creates a new teacher or admin account (Administrator only)."""
    existing = db.query(User).filter(User.email == user_in.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    if len(user_in.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    new_user = User(
        email=user_in.email.lower().strip(),
        full_name=user_in.full_name.strip(),
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        is_active=user_in.is_active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit_action(
        db=db,
        action="USER_CREATED",
        resource_type="USER",
        user_id=admin.id,
        resource_id=str(new_user.id),
        details={"created_email": new_user.email, "role": new_user.role.value}
    )
    return new_user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Updates user details, role, or activation status (Administrator only)."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.email:
        target_user.email = user_in.email.lower().strip()
    if user_in.full_name:
        target_user.full_name = user_in.full_name.strip()
    if user_in.role:
        target_user.role = user_in.role
    if user_in.is_active is not None:
        target_user.is_active = user_in.is_active
    if user_in.password:
        target_user.hashed_password = hash_password(user_in.password)

    db.commit()
    db.refresh(target_user)

    log_audit_action(
        db=db,
        action="USER_UPDATED",
        resource_type="USER",
        user_id=admin.id,
        resource_id=str(target_user.id),
        details={"updated_id": target_user.id, "is_active": target_user.is_active}
    )
    return target_user


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Safely deactivates user account (Administrator only)."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own administrator account")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.is_active = False
    db.commit()

    log_audit_action(
        db=db,
        action="USER_DEACTIVATED",
        resource_type="USER",
        user_id=admin.id,
        resource_id=str(target_user.id),
    )
    return {"message": f"User {target_user.email} deactivated successfully"}
