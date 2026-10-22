from typing import Optional
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.auth.security import decode_access_token
from backend.app.models.user import User, UserRole
from backend.app.models.examination import Examination, ExaminationAssignment

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Dependency that resolves and validates the authenticated user from the JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception
        
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
        
    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deactivated"
        )
        
    return user


def get_current_user_flexible(
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> User:
    """
    Flexible auth dependency supporting both:
    1. 'Authorization: Bearer <token>' header
    2. '?token=<token>' query parameter (for direct file downloads and image tags)
    """
    jwt_token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        jwt_token = auth_header[7:].strip()
    elif token:
        jwt_token = token.strip()

    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(jwt_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account has been deactivated")

    return user


def require_teacher_or_admin_flexible(
    current_user: User = Depends(get_current_user_flexible),
) -> User:
    """Enforces Teacher or Admin role using flexible header/query auth."""
    if current_user.role not in [UserRole.TEACHER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher or Administrator privileges required"
        )
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency enforcing that the authenticated user is an Administrator."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required"
        )
    return current_user


def require_teacher_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency ensuring user is either a Teacher or an Administrator."""
    if current_user.role not in [UserRole.ADMIN, UserRole.TEACHER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    return current_user


def check_exam_access(
    examination_id: int,
    user: User,
    db: Session
) -> Examination:
    """Enforces strict backend cross-exam access control."""
    exam = db.query(Examination).filter(Examination.id == examination_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examination not found"
        )
        
    if user.role == UserRole.ADMIN:
        return exam
        
    # Check if teacher created it
    if exam.created_by_id == user.id:
        return exam
        
    # Check if teacher is assigned to it
    assignment = (
        db.query(ExaminationAssignment)
        .filter(
            ExaminationAssignment.examination_id == examination_id,
            ExaminationAssignment.user_id == user.id
        )
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this examination"
        )
        
    return exam
