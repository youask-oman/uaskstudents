"""
Admin Dependencies: RBAC middleware for admin-only access.

Usage:
    from app.admin_billing.deps import get_admin_user, get_superadmin_user
    
    @router.get("/admin/resource")
    async def get_resource(admin: User = Depends(get_admin_user)):
        ...
    
    @router.post("/admin/dangerous-action")
    async def dangerous_action(admin: User = Depends(get_superadmin_user)):
        ...
"""

from fastapi import Depends, HTTPException, status, Header
from sqlmodel import Session, select
from jose import JWTError, jwt

from app.database import get_session
from app.models import User
from app.auth import SECRET_KEY, ALGORITHM


# Self-contained auth dependency to avoid circular imports
def get_current_user(
    authorization: str = Header(None),
    session: Session = Depends(get_session)
) -> User:
    """Extract user from JWT token in Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency that ensures the current user is an admin.
    
    Raises:
        HTTPException 403: If user is not an admin
    """
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def get_superadmin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency that ensures the current user is a superadmin.
    
    Required for dangerous actions like:
    - Kill switch activation
    - Force releasing holds
    - Modifying feature flags
    
    Raises:
        HTTPException 403: If user is not a superadmin
    """
    # Check for superadmin role OR admin with superadmin flag
    is_superadmin = (
        current_user.role == "superadmin" or
        (current_user.role == "admin" and getattr(current_user, "is_superadmin", False))
    )
    
    if not is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required for this action"
        )
    return current_user
