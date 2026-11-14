from pydantic import BaseModel, EmailStr, constr
from typing import Optional, List
from datetime import datetime
from app.models import InvitationStatus, Role

class Tasks(BaseModel):
    title: str
    content: Optional[str] = ""
    description: Optional[str] = None
    completed: Optional[bool] = False
    is_completed: Optional[bool] = False
    priority: Optional[str] = "medium"
    due_date: Optional[datetime] = None

class TasksCreate(Tasks):
    pass

class SubtaskCreate(BaseModel):
    title: str
    content: Optional[str] = ""
    completed: Optional[bool] = False
    due_date: Optional[datetime] = None

class SubtaskResponse(BaseModel):
    id: int
    task_id: int
    title: str
    content: Optional[str] = ""
    completed: bool = False
    is_completed: bool = False
    due_date: Optional[datetime] = None
    class Config:
        from_attributes = True

class TasksPost(BaseModel):
    id: int
    title: str
    content: Optional[str] = ""
    description: Optional[str] = ""
    completed: bool = False
    is_completed: bool = False
    priority: Optional[str] = "medium"
    due_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    subtasks: List[SubtaskResponse] = []
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: constr(min_length=8, max_length=72)

class UserPost(BaseModel):
    id: int
    email: EmailStr
    name: Optional[str] = None
    username: Optional[str] = None
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None
    
class Group(BaseModel):
    name: str
    description: str

class GroupPost(Group):
    id: int
    class Config:
        from_attributes = True
             
class UpdateGroup(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    
class GroupInvitationBase(BaseModel):
    email: EmailStr

class GroupInvitationCreate(GroupInvitationBase):
    expires_at: datetime

class GroupInvitationResponse(GroupInvitationBase):
    id: int
    invited_by: int
    token: str
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime
    class Config:
        from_attributes = True

class GroupMemberResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: Role
    joined_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message: str

class GroupTasksCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_to: int

class GroupTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    assigned_to: Optional[int] = None

class GroupTaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool = False
    group_id: int
    assigned_to: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True
