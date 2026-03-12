"""
app/routes/sprints.py
---------------------
Sprint API routes.
Validates project_id FK exists before creating a sprint.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.middleware.rbac import require_role
from app.middleware.auth import get_current_user
from app.models.sprints import Sprint
from app.models.projects import Project

router = APIRouter(prefix="/sprints", tags=["Sprints"])


class SprintCreate(BaseModel):
    project_id: str    # UUID as string
    name: str
    goal: Optional[str] = None


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_sprint(
    data: SprintCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("super_admin", "project_manager")),
):
    """
    Create a sprint.
    FK check: project_id must exist — returns 404 if it doesn't.
    """
    project = db.query(Project).filter(Project.id == uuid.UUID(data.project_id)).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {data.project_id} not found")

    sprint = Sprint(
        id=uuid.uuid4(),
        project_id=uuid.UUID(data.project_id),
        name=data.name,
        goal=data.goal,
    )
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    return {"message": "Sprint created", "sprint_id": str(sprint.id)}


@router.patch("/{sprint_id}/activate")
def activate_sprint(
    sprint_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("super_admin", "project_manager")),
):
    """Activate a sprint — changes status to active."""
    sprint = db.query(Sprint).filter(Sprint.id == uuid.UUID(sprint_id)).first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")

    sprint.status = "active"
    db.commit()
    return {"message": "Sprint activated", "sprint_id": sprint_id}


@router.get("/")
def list_sprints(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    sprints = db.query(Sprint).all()
    return [{"id": str(s.id), "name": s.name, "project_id": str(s.project_id)} for s in sprints]
