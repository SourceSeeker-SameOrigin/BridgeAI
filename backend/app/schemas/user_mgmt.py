"""User management schemas."""

from typing import Optional

from pydantic import BaseModel, EmailStr


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str = "user"
    username: Optional[str] = None


class UpdateRoleRequest(BaseModel):
    role: str


class UserListItem(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    last_login_at: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True
