"""
app/routes/finance.py
---------------------
Finance entry routes — strictest RBAC in the system.
POST: super_admin ONLY
GET:  super_admin + project_manager (employee fully blocked with 403)
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.middleware.rbac import require_role
from app.models.finance_entries import FinanceEntry

router = APIRouter(prefix="/finance", tags=["Finance"])


class FinanceCreate(BaseModel):
    type: str                   # e.g. subscription, one-time, expense
    amount: float
    client_name: str
    currency: str = "INR"
    category: Optional[str] = None


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_finance_entry(
    data: FinanceCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("super_admin")),   # ONLY super_admin
):
    """
    Create a finance entry.
    RBAC: super_admin ONLY — project_manager and employee both get 403.
    """
    entry = FinanceEntry(
        id=uuid.uuid4(),
        type=data.type,
        amount=data.amount,
        client_name=data.client_name,
        currency=data.currency,
        category=data.category,
        created_by=uuid.UUID(current_user["user_id"]),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {
        "message": "Finance entry created",
        "entry": {"id": str(entry.id), "client_name": entry.client_name, "amount": entry.amount},
    }


@router.get("/")
def get_finance_entries(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("super_admin", "project_manager")),
):
    """
    Get all finance entries.
    RBAC: employee gets 403 — completely blocked.
    """
    entries = db.query(FinanceEntry).all()
    return [
        {"id": str(e.id), "type": str(e.type), "amount": e.amount, "client_name": e.client_name}
        for e in entries
    ]
