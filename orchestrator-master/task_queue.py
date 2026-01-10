"""
Task Queue Module
Manages task assignment, scheduling, and tracking for worker instances.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
import heapq

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 3
    HIGH = 5
    URGENT = 7
    CRITICAL = 9


@dataclass
class Task:
    """Task data structure."""
    task_id: str
    description: str
    context: List[str]
    priority: int
    created_at: datetime
    assigned_worker: Optional[str] = None
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = None
    estimated_duration: Optional[int] = None  # seconds
    actual_duration: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["assigned_at"] = self.assigned_at.isoformat() if self.assigned_at else None
        data["started_at"] = self.started_at.isoformat() if self.started_at else None
        data["completed_at"] = self.completed_at.isoformat() if self.completed_at else None
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create task from dictionary."""
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["assigned_at"] = datetime.fromisoformat(data["assigned_at"]) if data.get("assigned_at") else None
        data["started_at"] = datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
        data["completed_at"] = datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
        data["status"] = TaskStatus(data["status"])
        return cls(**data)


class TaskQueue:
    """Manages task queue with priority scheduling and dependency resolution."""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.priority_queue: List[tuple] = []  # (priority, created_time, task_id)
        self.worker_assignments: Dict[str, List[str]] = {}  # worker_id -> [task_ids]
        self.state_dir = Path("/tmp/multibot/tasks")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize the task queue."""
        logger.info("Initializing Task Queue")
        await self._load_state()
        await self._rebuild_priority_queue()
        logger.info(f"Task Queue initialized with {len(self.tasks)} tasks")

    async def assign_task(
        self,
        worker_id: str,
        task_description: str,
        context: List[str] = None,
        priority: int = TaskPriority.NORMAL.value,
        dependencies: List[str] = None,
        estimated_duration: Optional[int] = None
    ) -> str:
        """Assign a new task to a worker."""
        async with self._lock:
            task_id = str(uuid.uuid4())

            task = Task(
                task_id=task_id,
                description=task_description,
                context=context or [],
                priority=priority,
                created_at=datetime.now(),
                dependencies=dependencies or [],
                estimated_duration=estimated_duration
            )

            # Check dependencies
            if not await self._check_dependencies(task.dependencies):
                raise ValueError(f"Unresolved dependencies: {task.dependencies}")

            # Assign to worker
            task.assigned_worker = worker_id
            task.assigned_at = datetime.now()
            task.status = TaskStatus.ASSIGNED

            # Store task
            self.tasks[task_id] = task

            # Update worker assignments
            if worker_id not in self.worker_assignments:
                self.worker_assignments[worker_id] = []
            self.worker_assignments[worker_id].append(task_id)

            # Add to priority queue
            heapq.heappush(
                self.priority_queue,
                (-priority, task.created_at.timestamp(), task_id)
            )

            # Save state
            await self._save_task_state(task_id)

            logger.info(f"Task {task_id} assigned to worker {worker_id}")
            return task_id

    async def create_task(
        self,
        task_description: str,
        context: List[str] = None,
        priority: int = TaskPriority.NORMAL.value,
        dependencies: List[str] = None,
        estimated_duration: Optional[int] = None
    ) -> str:
        """Create a task without assigning to a worker."""
        async with self._lock:
            task_id = str(uuid.uuid4())

            task = Task(
                task_id=task_id,
                description=task_description,
                context=context or [],
                priority=priority,
                created_at=datetime.now(),
                dependencies=dependencies or [],
                estimated_duration=estimated_duration
            )

            # Check dependencies
            if not await self._check_dependencies(task.dependencies):
                raise ValueError(f"Unresolved dependencies: {task.dependencies}")

            # Store task
            self.tasks[task_id] = task

            # Add to priority queue
            heapq.heappush(
                self.priority_queue,
                (-priority, task.created_at.timestamp(), task_id)
            )

            # Save state
            await self._save_task_state(task_id)

            logger.info(f"Task {task_id} created and queued")
            return task_id

    async def assign_next_task(self, worker_id: str) -> Optional[str]:
        """Assign the next available task to a worker."""
        async with self._lock:
            # Find highest priority available task
            available_tasks = []

            for priority, created_time, task_id in self.priority_queue:
                if task_id in self.tasks:
                    task = self.tasks[task_id]
                    if (task.status == TaskStatus.PENDING and
                        await self._check_dependencies(task.dependencies)):
                        available_tasks.append((priority, created_time, task_id))

            if not available_tasks:
                return None

            # Get highest priority task
            _, _, task_id = min(available_tasks)
            task = self.tasks[task_id]

            # Assign to worker
            task.assigned_worker = worker_id
            task.assigned_at = datetime.now()
            task.status = TaskStatus.ASSIGNED

            # Update worker assignments
            if worker_id not in self.worker_assignments:
                self.worker_assignments[worker_id] = []
            self.worker_assignments[worker_id].append(task_id)

            # Save state
            await self._save_task_state(task_id)

            logger.info(f"Task {task_id} auto-assigned to worker {worker_id}")
            return task_id

    async def reassign_task(self, task_id: str, from_worker: str, to_worker: str) -> bool:
        """Reassign a task from one worker to another."""
        async with self._lock:
            if task_id not in self.tasks:
                raise ValueError(f"Task {task_id} not found")

            task = self.tasks[task_id]

            if task.assigned_worker != from_worker:
                raise ValueError(f"Task {task_id} is not assigned to worker {from_worker}")

            if task.status == TaskStatus.COMPLETED:
                raise ValueError(f"Cannot reassign completed task {task_id}")

            # Update assignment
            task.assigned_worker = to_worker
            task.assigned_at = datetime.now()
            task.status = TaskStatus.ASSIGNED
            task.started_at = None  # Reset start time

            # Update worker assignments
            if from_worker in self.worker_assignments:
                if task_id in self.worker_assignments[from_worker]:
                    self.worker_assignments[from_worker].remove(task_id)

            if to_worker not in self.worker_assignments:
                self.worker_assignments[to_worker] = []
            self.worker_assignments[to_worker].append(task_id)

            # Save state
            await self._save_task_state(task_id)

            logger.info(f"Task {task_id} reassigned from {from_worker} to {to_worker}")
            return True

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update task status and result."""
        async with self._lock:
            if task_id not in self.tasks:
                raise ValueError(f"Task {task_id} not found")

            task = self.tasks[task_id]
            old_status = task.status
            task.status = status

            # Update timestamps
            if status == TaskStatus.IN_PROGRESS and not task.started_at:
                task.started_at = datetime.now()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                task.completed_at = datetime.now()
                if task.started_at:
                    task.actual_duration = int((task.completed_at - task.started_at).total_seconds())

            # Update result/error
            if result:
                task.result = result
            if error_message:
                task.error_message = error_message

            # Handle failures
            if status == TaskStatus.FAILED:
                task.retry_count += 1
                if task.retry_count < task.max_retries:
                    # Reset for retry
                    task.status = TaskStatus.PENDING
                    task.assigned_worker = None
                    task.assigned_at = None
                    task.started_at = None
                    task.completed_at = None
                    logger.info(f"Task {task_id} queued for retry ({task.retry_count}/{task.max_retries})")

            # Save state
            await self._save_task_state(task_id)

            logger.info(f"Task {task_id} status updated: {old_status.value} -> {status.value}")
            return True

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status and details."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task = self.tasks[task_id]
        return task.to_dict()

    async def get_task_details(self, task_id: str) -> Dict[str, Any]:
        """Get detailed task information for assignment."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task = self.tasks[task_id]
        return {
            "task_id": task_id,
            "description": task.description,
            "context": task.context,
            "priority": task.priority,
            "dependencies": task.dependencies,
            "estimated_duration": task.estimated_duration
        }

    async def get_worker_tasks(self, worker_id: str) -> List[str]:
        """Get all tasks assigned to a worker."""
        return self.worker_assignments.get(worker_id, [])

    async def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get all pending tasks."""
        pending_tasks = []
        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING:
                pending_tasks.append(task.to_dict())

        # Sort by priority and creation time
        pending_tasks.sort(key=lambda x: (-x["priority"], x["created_at"]))
        return pending_tasks

    async def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get all active (assigned or in progress) tasks."""
        active_tasks = []
        for task in self.tasks.values():
            if task.status in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]:
                active_tasks.append(task.to_dict())

        return active_tasks

    async def get_completed_tasks(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get completed tasks."""
        completed_tasks = []
        for task in self.tasks.values():
            if task.status == TaskStatus.COMPLETED:
                if since and task.completed_at and task.completed_at < since:
                    continue
                completed_tasks.append(task.to_dict())

        # Sort by completion time (newest first)
        completed_tasks.sort(key=lambda x: x["completed_at"] or "", reverse=True)

        if limit:
            completed_tasks = completed_tasks[:limit]

        return completed_tasks

    async def reassign_orphaned_tasks(self, task_ids: List[str]) -> List[str]:
        """Reassign tasks that were orphaned due to worker termination."""
        reassigned = []

        async with self._lock:
            for task_id in task_ids:
                if task_id in self.tasks:
                    task = self.tasks[task_id]
                    if task.status in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]:
                        # Reset task for reassignment
                        task.status = TaskStatus.PENDING
                        task.assigned_worker = None
                        task.assigned_at = None
                        task.started_at = None

                        # Add back to priority queue
                        heapq.heappush(
                            self.priority_queue,
                            (-task.priority, task.created_at.timestamp(), task_id)
                        )

                        await self._save_task_state(task_id)
                        reassigned.append(task_id)

        logger.info(f"Reassigned {len(reassigned)} orphaned tasks")
        return reassigned

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        async with self._lock:
            if task_id not in self.tasks:
                raise ValueError(f"Task {task_id} not found")

            task = self.tasks[task_id]

            if task.status == TaskStatus.COMPLETED:
                raise ValueError(f"Cannot cancel completed task {task_id}")

            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()

            # Remove from worker assignments
            if task.assigned_worker and task.assigned_worker in self.worker_assignments:
                if task_id in self.worker_assignments[task.assigned_worker]:
                    self.worker_assignments[task.assigned_worker].remove(task_id)

            await self._save_task_state(task_id)

            logger.info(f"Task {task_id} cancelled")
            return True

    async def get_task_metrics(self) -> Dict[str, Any]:
        """Get task queue metrics."""
        total_tasks = len(self.tasks)
        status_counts = {}

        for status in TaskStatus:
            status_counts[status.value] = sum(
                1 for task in self.tasks.values() if task.status == status
            )

        # Calculate average duration for completed tasks
        completed_tasks = [
            task for task in self.tasks.values()
            if task.status == TaskStatus.COMPLETED and task.actual_duration
        ]

        avg_duration = None
        if completed_tasks:
            avg_duration = sum(task.actual_duration for task in completed_tasks) / len(completed_tasks)

        return {
            "total_tasks": total_tasks,
            "status_distribution": status_counts,
            "average_duration": avg_duration,
            "active_workers": len(self.worker_assignments),
            "queue_size": len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING])
        }

    async def _check_dependencies(self, dependencies: List[str]) -> bool:
        """Check if all dependencies are satisfied."""
        if not dependencies:
            return True

        for dep_id in dependencies:
            if dep_id not in self.tasks:
                return False
            if self.tasks[dep_id].status != TaskStatus.COMPLETED:
                return False

        return True

    async def _rebuild_priority_queue(self):
        """Rebuild priority queue from existing tasks."""
        self.priority_queue = []

        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING:
                heapq.heappush(
                    self.priority_queue,
                    (-task.priority, task.created_at.timestamp(), task.task_id)
                )

        logger.info(f"Priority queue rebuilt with {len(self.priority_queue)} pending tasks")

    async def _save_task_state(self, task_id: str):
        """Save task state to disk."""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]
        state_file = self.state_dir / f"{task_id}.json"

        try:
            with open(state_file, "w") as f:
                json.dump(task.to_dict(), f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save task state {task_id}: {str(e)}")

    async def _load_state(self):
        """Load task state from disk."""
        if not self.state_dir.exists():
            return

        for state_file in self.state_dir.glob("*.json"):
            try:
                with open(state_file) as f:
                    task_data = json.load(f)

                task = Task.from_dict(task_data)
                self.tasks[task.task_id] = task

                # Rebuild worker assignments
                if task.assigned_worker:
                    if task.assigned_worker not in self.worker_assignments:
                        self.worker_assignments[task.assigned_worker] = []
                    self.worker_assignments[task.assigned_worker].append(task.task_id)

                logger.debug(f"Loaded task {task.task_id} with status {task.status.value}")

            except Exception as e:
                logger.error(f"Failed to load task from {state_file}: {str(e)}")