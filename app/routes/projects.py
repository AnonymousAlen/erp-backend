"""
app/routes/projects.py
-----------------------
Project API routes with RBAC enforcement.
Uses team's existing SQLAlchemy models from app/models/projects.py
and session from app/db/session.py
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.middleware.rbac import require_role
from app.middleware.auth import get_current_user
from app.models.projects import Project
from app.models.project_members import ProjectMember

router = APIRouter(prefix="/projects", tags=["Projects"])


# ── Request schemas ────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    manager_id: str   # UUID as string


class AddMemberRequest(BaseModel):
    user_id: str      # UUID as string


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("super_admin", "project_manager")),
):
    """
    Create a new project.
    RBAC: Only super_admin and project_manager allowed. Employee gets 403.
    """
    project = Project(
        id=uuid.uuid4(),
        name=data.name,
        description=data.description,
        manager_id=uuid.UUID(data.manager_id),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"message": "Project created", "project_id": str(project.id)}


@router.get("/")
def list_projects(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all projects. All logged-in users can view."""
    projects = db.query(Project).all()
    return [{"id": str(p.id), "name": p.name, "status": str(p.status)} for p in projects]


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(
    project_id: str,
    data: AddMemberRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("super_admin", "project_manager")),
):
    """Add a user to a project. RBAC: admin/manager only."""
    project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    member = ProjectMember(
        id=uuid.uuid4(),
        project_id=uuid.UUID(project_id),
        user_id=uuid.UUID(data.user_id),
    )
    db.add(member)
    db.commit()
    return {"message": "Member added", "project_id": project_id, "user_id": data.user_id}
