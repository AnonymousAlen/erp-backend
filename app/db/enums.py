from enum import Enum


class UserRole(str, Enum):
    super_admin = "super_admin"
    project_manager = "project_manager"
    employee = "employee"


class ProjectStatus(str, Enum):
    planning = "planning"
    active = "active"
    completed = "completed"


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"