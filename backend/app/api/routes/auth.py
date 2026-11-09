from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.models.action_item import ActionItem
from app.models.decision import Decision
from app.models.meeting import Meeting
from app.models.meeting_summary import MeetingSummary
from app.models.recording import Recording
from app.models.transcript import Transcript
from app.models.user import User

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    is_guest: bool = False

    model_config = {
        "from_attributes": True,
    }


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    existing_user = db.scalar(
        select(User).where(User.email == request.email)
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=request.email,
        full_name=request.full_name,
    )

    user.password_hash = hash_password(request.password)

    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_guest=False,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.email == request.email)
    )

    if not user or not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    access_token = create_access_token(
        user_id=user.id,
    )

    is_guest = user.email.startswith("guest_") and user.email.endswith("@guest.local")

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_guest=is_guest,
        ),
    )


@router.post("/guest", response_model=LoginResponse)
def guest_login(
    db: Session = Depends(get_db),
):
    """
    Create an ephemeral guest session.
    Guest data is marked temporary and vanishes when user logs out or session is closed.
    """
    guest_uuid = uuid4().hex[:8]
    guest_email = f"guest_{guest_uuid}@guest.local"

    user = User(
        email=guest_email,
        full_name=f"Guest Explorer #{guest_uuid[:4].upper()}",
        password_hash=hash_password(uuid4().hex),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(
        user_id=user.id,
        expires_minutes=60 * 24,
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_guest=True,
        ),
    )


@router.delete("/guest/cleanup", status_code=status.HTTP_204_NO_CONTENT)
def cleanup_guest_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Completely delete guest user and all temporary meetings, transcripts,
    summaries, action items, and decisions when a guest session ends.
    """
    if not (current_user.email.startswith("guest_") and current_user.email.endswith("@guest.local")):
        # Only guest users can be wiped by this endpoint
        return None

    # Delete all meetings belonging to guest (cascade deletes transcripts, summaries, actions, decisions)
    db.execute(delete(Meeting).where(Meeting.owner_id == current_user.id))
    db.execute(delete(User).where(User.id == current_user.id))
    db.commit()
    return None


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    is_guest = current_user.email.startswith("guest_") and current_user.email.endswith("@guest.local")
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_guest=is_guest,
    )
