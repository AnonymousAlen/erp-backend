"""
app/routes/tasks.py
--------------------
Task API routes with ownership enforcement and comments.
- Employee can only edit tasks assigned to them
- Only admin/manager can delete tasks
- Comments stored in task_comments table
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.middleware.rbac import require_role
from app.middleware.auth import get_current_user
from app.models.tasks import Task
from app.models.task_comments import TaskComment
from app.models.projects import Project
from app.models.sprints import Sprint

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ── Request schemas ────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    project_id: str
    sprint_id: Optional[str] = None
    parent_task_id: Optional[str] = None   # for nested (sub) tasks
    title: str
    description: Optional[str] = None
    assignee_id: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assignee_id: Optional[str] = None


class CommentCreate(BaseModel):
    content: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a task — validates project, sprint, and parent task exist."""
    # FK: project must exist
    project = db.query(Project).filter(Project.id == uuid.UUID(data.project_id)).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {data.project_id} not found")

    # FK: sprint must exist if provided
    if data.sprint_id:
        sprint = db.query(Sprint).filter(Sprint.id == uuid.UUID(data.sprint_id)).first()
        if not sprint:
            raise HTTPException(status_code=404, detail=f"Sprint {data.sprint_id} not found")

    # FK: parent task must exist if provided (recursive/nested tasks)
    if data.parent_task_id:
        parent = db.query(Task).filter(Task.id == uuid.UUID(data.parent_task_id)).first()
        if not parent:
            raise HTTPException(status_code=404, detail=f"Parent task {data.parent_task_id} not found")

    task = Task(
        id=uuid.uuid4(),
        project_id=uuid.UUID(data.project_id),
        sprint_id=uuid.UUID(data.sprint_id) if data.sprint_id else None,
        parent_task_id=uuid.UUID(data.parent_task_id) if data.parent_task_id else None,
        title=data.title,
        description=data.description,
        assignee_id=uuid.UUID(data.assignee_id) if data.assignee_id else None,
        reporter_id=uuid.UUID(current_user["user_id"]),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"message": "Task created", "task_id": str(task.id)}


@router.patch("/{task_id}")
def update_task(
    task_id: str,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Update a task.
    RBAC ownership: employee can only update tasks where assignee_id = their own user_id.
    """
    task = db.query(Task).filter(Task.id == uuid.UUID(task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Employees can only edit their own tasks
    if current_user["role"] == "employee":
        if str(task.assignee_id) != current_user["user_id"]:
            raise HTTPException(
                status_code=403,
                detail="You can only update tasks assigned to you",
            )

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    db.commit()
    return {"message": "Task updated", "task_id": task_id}


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("super_admin", "project_manager")),
):
    """Delete a task. RBAC: employee gets 403."""
    task = db.query(Task).filter(Task.id == uuid.UUID(task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return {"message": "Task deleted", "task_id": task_id}


@router.post("/{task_id}/comments", status_code=status.HTTP_201_CREATED)
def add_comment(
    task_id: str,
    data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add a comment to a task. Creates a row in task_comments table."""
    task = db.query(Task).filter(Task.id == uuid.UUID(task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    comment = TaskComment(
        id=uuid.uuid4(),
        task_id=uuid.UUID(task_id),
        author_id=uuid.UUID(current_user["user_id"]),
        content=data.content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"message": "Comment added", "comment_id": str(comment.id)}


@router.get("/{task_id}/comments")
def get_comments(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all comments for a task."""
    task = db.query(Task).filter(Task.id == uuid.UUID(task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    comments = db.query(TaskComment).filter(TaskComment.task_id == uuid.UUID(task_id)).all()
    return [{"id": str(c.id), "content": c.content, "author_id": str(c.author_id)} for c in comments]
