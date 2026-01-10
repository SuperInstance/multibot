"""
Message Queue System
SQLite-based bidirectional communication system between Master and Workers.
"""

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
import threading

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Message types for Master-Worker communication."""
    # Master → Worker
    TASK_ASSIGN = "task_assign"
    TASK_UPDATE = "task_update"
    CONTEXT_SHARE = "context_share"
    GUIDANCE = "guidance"
    PAUSE = "pause"
    RESUME = "resume"
    TERMINATE = "terminate"

    # Worker → Master
    QUESTION = "question"
    STATUS_UPDATE = "status_update"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"
    RESOURCE_REQUEST = "resource_request"

    # Bidirectional
    HEARTBEAT = "heartbeat"
    ACK = "acknowledgment"


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 3
    HIGH = 5
    URGENT = 7
    CRITICAL = 9


class MessageStatus(Enum):
    """Message status enumeration."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    EXPIRED = "expired"


class TaskStatus(Enum):
    """Task assignment status."""
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Message:
    """Message data structure."""
    id: str
    from_id: str
    to_id: str
    message_type: MessageType
    content: Dict[str, Any]
    priority: MessagePriority
    created_at: datetime
    expires_at: Optional[datetime] = None
    status: MessageStatus = MessageStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    response_to: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "message_type": self.message_type.value,
            "content": self.content,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "response_to": self.response_to,
            "metadata": self.metadata or {}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        return cls(
            id=data["id"],
            from_id=data["from_id"],
            to_id=data["to_id"],
            message_type=MessageType(data["message_type"]),
            content=data["content"],
            priority=MessagePriority(data["priority"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            status=MessageStatus(data["status"]),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            response_to=data.get("response_to"),
            metadata=data.get("metadata", {})
        )


@dataclass
class TaskAssignment:
    """Task assignment data structure."""
    task_id: str
    worker_id: str
    description: str
    context: Dict[str, Any]
    priority: int
    created_at: datetime
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.ASSIGNED
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timeout_at: Optional[datetime] = None
    dependencies: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "description": self.description,
            "context": self.context,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "result": self.result,
            "error_message": self.error_message,
            "timeout_at": self.timeout_at.isoformat() if self.timeout_at else None,
            "dependencies": self.dependencies or []
        }


class MessageQueueManager:
    """SQLite-based message queue manager."""

    def __init__(self, db_path: str = "/tmp/multibot/message_queue.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

        # Message polling
        self._polling_task: Optional[asyncio.Task] = None
        self._message_handlers: Dict[str, List[callable]] = {}
        self._running = False

    async def initialize(self):
        """Initialize the message queue database."""
        logger.info("Initializing Message Queue Manager")

        # Create database connection
        self._connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=30.0
        )
        self._connection.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrency
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute("PRAGMA cache_size=10000")
        self._connection.execute("PRAGMA temp_store=memory")

        # Create tables
        await self._create_tables()

        # Start message polling
        self._running = True
        self._polling_task = asyncio.create_task(self._poll_messages())

        logger.info("Message Queue Manager initialized")

    async def _create_tables(self):
        """Create database tables."""
        with self._lock:
            cursor = self._connection.cursor()

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    from_id TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 3,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    response_to TEXT,
                    metadata TEXT,
                    updated_at TEXT
                )
            """)

            # Task assignments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_assignments (
                    task_id TEXT PRIMARY KEY,
                    worker_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    context TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 5,
                    created_at TEXT NOT NULL,
                    assigned_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    status TEXT NOT NULL DEFAULT 'assigned',
                    result TEXT,
                    error_message TEXT,
                    timeout_at TEXT,
                    dependencies TEXT
                )
            """)

            # Create indices for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_to_status ON messages(to_id, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_priority ON messages(priority DESC, created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_expires ON messages(expires_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_worker_status ON task_assignments(worker_id, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON task_assignments(status)")

            self._connection.commit()
            logger.debug("Database tables created/verified")

    async def send_message(
        self,
        from_id: str,
        to_id: str,
        message_type: MessageType,
        content: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        expires_in_seconds: Optional[int] = None,
        response_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Send a message."""
        message_id = str(uuid.uuid4())
        now = datetime.now()

        expires_at = None
        if expires_in_seconds:
            expires_at = now + timedelta(seconds=expires_in_seconds)

        message = Message(
            id=message_id,
            from_id=from_id,
            to_id=to_id,
            message_type=message_type,
            content=content,
            priority=priority,
            created_at=now,
            expires_at=expires_at,
            response_to=response_to,
            metadata=metadata
        )

        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("""
                INSERT INTO messages (
                    id, from_id, to_id, message_type, content, priority,
                    created_at, expires_at, status, retry_count, max_retries,
                    response_to, metadata, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.id,
                message.from_id,
                message.to_id,
                message.message_type.value,
                json.dumps(message.content),
                message.priority.value,
                message.created_at.isoformat(),
                message.expires_at.isoformat() if message.expires_at else None,
                message.status.value,
                message.retry_count,
                message.max_retries,
                message.response_to,
                json.dumps(message.metadata or {}),
                now.isoformat()
            ))
            self._connection.commit()

        logger.debug(f"Sent message {message_id} from {from_id} to {to_id}: {message_type.value}")
        return message_id

    async def receive_messages(
        self,
        recipient_id: str,
        message_types: Optional[List[MessageType]] = None,
        limit: int = 100
    ) -> List[Message]:
        """Receive messages for a recipient."""
        with self._lock:
            cursor = self._connection.cursor()

            # Build query
            query = """
                SELECT * FROM messages
                WHERE to_id = ? AND status = 'pending'
            """
            params = [recipient_id]

            if message_types:
                placeholders = ",".join("?" * len(message_types))
                query += f" AND message_type IN ({placeholders})"
                params.extend([mt.value for mt in message_types])

            query += " ORDER BY priority DESC, created_at ASC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            messages = []
            for row in rows:
                message_data = {
                    "id": row["id"],
                    "from_id": row["from_id"],
                    "to_id": row["to_id"],
                    "message_type": row["message_type"],
                    "content": json.loads(row["content"]),
                    "priority": row["priority"],
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                    "status": row["status"],
                    "retry_count": row["retry_count"],
                    "max_retries": row["max_retries"],
                    "response_to": row["response_to"],
                    "metadata": json.loads(row["metadata"] or "{}")
                }

                messages.append(Message.from_dict(message_data))

            # Mark messages as delivered
            if messages:
                message_ids = [msg.id for msg in messages]
                placeholders = ",".join("?" * len(message_ids))
                cursor.execute(f"""
                    UPDATE messages
                    SET status = 'delivered', updated_at = ?
                    WHERE id IN ({placeholders})
                """, [datetime.now().isoformat()] + message_ids)
                self._connection.commit()

        logger.debug(f"Retrieved {len(messages)} messages for {recipient_id}")
        return messages

    async def acknowledge_message(self, message_id: str, response_content: Optional[Dict[str, Any]] = None):
        """Acknowledge a received message."""
        with self._lock:
            cursor = self._connection.cursor()

            # Update message status
            cursor.execute("""
                UPDATE messages
                SET status = 'acknowledged', updated_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), message_id))

            # Send acknowledgment response if requested
            if response_content:
                cursor.execute("SELECT from_id, to_id FROM messages WHERE id = ?", (message_id,))
                row = cursor.fetchone()

                if row:
                    await self.send_message(
                        from_id=row["to_id"],
                        to_id=row["from_id"],
                        message_type=MessageType.ACK,
                        content=response_content,
                        response_to=message_id
                    )

            self._connection.commit()

    async def assign_task(
        self,
        task_id: str,
        worker_id: str,
        description: str,
        context: Dict[str, Any],
        priority: int = 5,
        timeout_seconds: Optional[int] = None,
        dependencies: Optional[List[str]] = None
    ) -> bool:
        """Assign a task to a worker."""
        now = datetime.now()

        timeout_at = None
        if timeout_seconds:
            timeout_at = now + timedelta(seconds=timeout_seconds)

        task = TaskAssignment(
            task_id=task_id,
            worker_id=worker_id,
            description=description,
            context=context,
            priority=priority,
            created_at=now,
            assigned_at=now,
            timeout_at=timeout_at,
            dependencies=dependencies
        )

        with self._lock:
            cursor = self._connection.cursor()

            try:
                cursor.execute("""
                    INSERT INTO task_assignments (
                        task_id, worker_id, description, context, priority,
                        created_at, assigned_at, status, timeout_at, dependencies
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.task_id,
                    task.worker_id,
                    task.description,
                    json.dumps(task.context),
                    task.priority,
                    task.created_at.isoformat(),
                    task.assigned_at.isoformat(),
                    task.status.value,
                    task.timeout_at.isoformat() if task.timeout_at else None,
                    json.dumps(task.dependencies or [])
                ))

                self._connection.commit()

                # Send task assignment message
                await self.send_message(
                    from_id="master",
                    to_id=worker_id,
                    message_type=MessageType.TASK_ASSIGN,
                    content={
                        "task_id": task_id,
                        "description": description,
                        "context": context,
                        "priority": priority,
                        "dependencies": dependencies or []
                    },
                    priority=MessagePriority.HIGH
                )

                logger.info(f"Assigned task {task_id} to worker {worker_id}")
                return True

            except sqlite3.IntegrityError:
                logger.error(f"Task {task_id} already exists")
                return False

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update task status."""
        with self._lock:
            cursor = self._connection.cursor()

            # Get current task
            cursor.execute("SELECT * FROM task_assignments WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()

            if not row:
                logger.error(f"Task {task_id} not found")
                return False

            now = datetime.now()

            # Prepare update values
            values = [status.value, now.isoformat()]
            query = "UPDATE task_assignments SET status = ?, updated_at = ?"

            if status == TaskStatus.IN_PROGRESS and not row["started_at"]:
                query += ", started_at = ?"
                values.append(now.isoformat())

            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                query += ", completed_at = ?"
                values.append(now.isoformat())

            if result:
                query += ", result = ?"
                values.append(json.dumps(result))

            if error_message:
                query += ", error_message = ?"
                values.append(error_message)

            query += " WHERE task_id = ?"
            values.append(task_id)

            cursor.execute(query, values)
            self._connection.commit()

            logger.info(f"Updated task {task_id} status to {status.value}")
            return True

    async def get_pending_questions(self, limit: int = 50) -> List[Message]:
        """Get pending questions from workers."""
        return await self.receive_messages(
            recipient_id="master",
            message_types=[MessageType.QUESTION],
            limit=limit
        )

    async def get_worker_tasks(self, worker_id: str) -> List[TaskAssignment]:
        """Get tasks for a specific worker."""
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("""
                SELECT * FROM task_assignments
                WHERE worker_id = ?
                ORDER BY priority DESC, created_at ASC
            """, (worker_id,))

            tasks = []
            for row in cursor.fetchall():
                task_data = {
                    "task_id": row["task_id"],
                    "worker_id": row["worker_id"],
                    "description": row["description"],
                    "context": json.loads(row["context"]),
                    "priority": row["priority"],
                    "created_at": row["created_at"],
                    "assigned_at": row["assigned_at"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "status": row["status"],
                    "result": json.loads(row["result"]) if row["result"] else None,
                    "error_message": row["error_message"],
                    "timeout_at": row["timeout_at"],
                    "dependencies": json.loads(row["dependencies"] or "[]")
                }

                tasks.append(TaskAssignment(**{
                    k: (datetime.fromisoformat(v) if k.endswith('_at') and v else v)
                    for k, v in task_data.items()
                }))

            return tasks

    async def cleanup_expired_messages(self):
        """Clean up expired messages."""
        now = datetime.now()

        with self._lock:
            cursor = self._connection.cursor()

            # Mark expired messages
            cursor.execute("""
                UPDATE messages
                SET status = 'expired', updated_at = ?
                WHERE expires_at IS NOT NULL
                AND expires_at < ?
                AND status IN ('pending', 'sent', 'delivered')
            """, (now.isoformat(), now.isoformat()))

            # Clean up old acknowledged/expired messages (older than 7 days)
            cutoff = now - timedelta(days=7)
            cursor.execute("""
                DELETE FROM messages
                WHERE status IN ('acknowledged', 'expired', 'failed')
                AND created_at < ?
            """, (cutoff.isoformat(),))

            self._connection.commit()

    async def get_message_stats(self) -> Dict[str, Any]:
        """Get message queue statistics."""
        with self._lock:
            cursor = self._connection.cursor()

            # Message stats
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM messages
                GROUP BY status
            """)
            message_stats = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Task stats
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM task_assignments
                GROUP BY status
            """)
            task_stats = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Recent activity
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM messages
                WHERE created_at > ?
            """, ((datetime.now() - timedelta(hours=1)).isoformat(),))
            recent_messages = cursor.fetchone()["count"]

            return {
                "message_stats": message_stats,
                "task_stats": task_stats,
                "recent_messages_1h": recent_messages,
                "database_size": self.db_path.stat().st_size if self.db_path.exists() else 0
            }

    def register_message_handler(self, recipient_id: str, handler: callable):
        """Register a message handler for a recipient."""
        if recipient_id not in self._message_handlers:
            self._message_handlers[recipient_id] = []
        self._message_handlers[recipient_id].append(handler)

    async def _poll_messages(self):
        """Poll for new messages and call handlers."""
        while self._running:
            try:
                # Process handlers
                for recipient_id, handlers in self._message_handlers.items():
                    messages = await self.receive_messages(recipient_id, limit=50)

                    for message in messages:
                        for handler in handlers:
                            try:
                                await handler(message)
                            except Exception as e:
                                logger.error(f"Message handler error: {str(e)}")

                # Cleanup expired messages
                await self.cleanup_expired_messages()

                await asyncio.sleep(5)  # Poll every 5 seconds

            except Exception as e:
                logger.error(f"Error in message polling: {str(e)}")
                await asyncio.sleep(10)

    async def cleanup(self):
        """Cleanup message queue resources."""
        logger.info("Cleaning up Message Queue Manager")

        self._running = False

        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

        if self._connection:
            self._connection.close()

        logger.info("Message Queue Manager cleanup completed")