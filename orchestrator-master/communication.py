"""
Communication Hub Module
Handles messaging between Master and Worker instances.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Message type enumeration."""
    TASK_ASSIGNMENT = "task_assignment"
    TASK_UPDATE = "task_update"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    QUESTION = "question"
    ANSWER = "answer"
    STATUS_REQUEST = "status_request"
    STATUS_RESPONSE = "status_response"
    HEARTBEAT = "heartbeat"
    TERMINATE = "terminate"
    PAUSE = "pause"
    RESUME = "resume"
    BROADCAST = "broadcast"
    MESSAGE = "message"


@dataclass
class Message:
    """Message data structure."""
    message_id: str
    sender_id: str
    recipient_id: str
    message_type: MessageType
    payload: Dict[str, Any]
    timestamp: datetime
    expires_at: Optional[datetime] = None
    reply_to: Optional[str] = None
    priority: int = 5

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        data = asdict(self)
        data["message_type"] = self.message_type.value
        data["timestamp"] = self.timestamp.isoformat()
        data["expires_at"] = self.expires_at.isoformat() if self.expires_at else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        data = data.copy()
        data["message_type"] = MessageType(data["message_type"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["expires_at"] = datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
        return cls(**data)


class CommunicationHub:
    """Manages communication between Master and Workers."""

    def __init__(self):
        self.workers: Dict[str, Dict[str, Any]] = {}  # worker_id -> worker_info
        self.message_handlers: Dict[MessageType, Callable] = {}
        self.pending_questions: Dict[str, Message] = {}  # question_id -> question
        self.message_history: Dict[str, List[Message]] = {}  # worker_id -> messages

        # Communication directories
        self.comm_dir = Path("/tmp/multibot/communication")
        self.master_inbox = self.comm_dir / "master" / "inbox"
        self.master_outbox = self.comm_dir / "master" / "outbox"

        # Create directories
        self.comm_dir.mkdir(parents=True, exist_ok=True)
        self.master_inbox.mkdir(parents=True, exist_ok=True)
        self.master_outbox.mkdir(parents=True, exist_ok=True)

        self._cleanup_task: Optional[asyncio.Task] = None
        self._message_processor_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize the communication hub."""
        logger.info("Initializing Communication Hub")

        # Load existing state
        await self._load_communication_state()

        # Start message processing
        self._message_processor_task = asyncio.create_task(self._process_incoming_messages())

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_messages())

        logger.info("Communication Hub initialized")

    async def register_worker(self, worker_id: str, capabilities: List[str] = None) -> bool:
        """Register a worker for communication."""
        logger.info(f"Registering worker {worker_id}")

        # Create worker communication directories
        worker_inbox = self.comm_dir / "workers" / worker_id / "inbox"
        worker_outbox = self.comm_dir / "workers" / worker_id / "outbox"
        worker_inbox.mkdir(parents=True, exist_ok=True)
        worker_outbox.mkdir(parents=True, exist_ok=True)

        # Register worker
        self.workers[worker_id] = {
            "registered_at": datetime.now(),
            "last_seen": datetime.now(),
            "capabilities": capabilities or [],
            "inbox_path": worker_inbox,
            "outbox_path": worker_outbox,
            "status": "active"
        }

        # Initialize message history
        if worker_id not in self.message_history:
            self.message_history[worker_id] = []

        logger.info(f"Worker {worker_id} registered successfully")
        return True

    async def unregister_worker(self, worker_id: str) -> bool:
        """Unregister a worker from communication."""
        if worker_id not in self.workers:
            logger.warning(f"Worker {worker_id} not found for unregistration")
            return False

        logger.info(f"Unregistering worker {worker_id}")

        # Mark as inactive
        self.workers[worker_id]["status"] = "inactive"
        self.workers[worker_id]["unregistered_at"] = datetime.now()

        # Clean up pending questions from this worker
        expired_questions = []
        for question_id, question in self.pending_questions.items():
            if question.sender_id == worker_id:
                expired_questions.append(question_id)

        for question_id in expired_questions:
            del self.pending_questions[question_id]

        logger.info(f"Worker {worker_id} unregistered successfully")
        return True

    async def send_to_worker(self, worker_id: str, payload: Dict[str, Any]) -> str:
        """Send a message to a specific worker."""
        if worker_id not in self.workers:
            raise ValueError(f"Worker {worker_id} not registered")

        worker = self.workers[worker_id]
        if worker["status"] != "active":
            raise ValueError(f"Worker {worker_id} is not active")

        # Create message
        message_id = str(uuid.uuid4())
        message = Message(
            message_id=message_id,
            sender_id="master",
            recipient_id=worker_id,
            message_type=MessageType(payload.get("type", MessageType.MESSAGE.value)),
            payload=payload,
            timestamp=datetime.now(),
            priority=payload.get("priority", 5)
        )

        # Write to worker's inbox
        message_file = worker["inbox_path"] / f"{message_id}.json"
        try:
            with open(message_file, "w") as f:
                json.dump(message.to_dict(), f, indent=2)

            # Add to message history
            self.message_history[worker_id].append(message)

            logger.debug(f"Sent message {message_id} to worker {worker_id}")
            return message_id

        except Exception as e:
            logger.error(f"Failed to send message to worker {worker_id}: {str(e)}")
            raise

    async def receive_from_worker(self, worker_id: str) -> List[Dict[str, Any]]:
        """Receive messages from a specific worker."""
        if worker_id not in self.workers:
            raise ValueError(f"Worker {worker_id} not registered")

        worker = self.workers[worker_id]
        outbox_path = worker["outbox_path"]

        messages = []

        # Read all messages from worker's outbox
        for message_file in outbox_path.glob("*.json"):
            try:
                with open(message_file) as f:
                    message_data = json.load(f)

                message = Message.from_dict(message_data)
                messages.append(message.payload)

                # Update worker last seen
                worker["last_seen"] = datetime.now()

                # Handle special message types
                await self._handle_worker_message(worker_id, message)

                # Archive processed message
                archive_dir = outbox_path.parent / "archive"
                archive_dir.mkdir(exist_ok=True)
                message_file.rename(archive_dir / message_file.name)

            except Exception as e:
                logger.error(f"Failed to process message {message_file}: {str(e)}")

        logger.debug(f"Received {len(messages)} messages from worker {worker_id}")
        return messages

    async def broadcast_to_workers(self, payload: Dict[str, Any]) -> int:
        """Broadcast a message to all active workers."""
        active_workers = [
            worker_id for worker_id, worker_info in self.workers.items()
            if worker_info["status"] == "active"
        ]

        sent_count = 0
        for worker_id in active_workers:
            try:
                await self.send_to_worker(worker_id, payload)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to broadcast to worker {worker_id}: {str(e)}")

        logger.info(f"Broadcast sent to {sent_count}/{len(active_workers)} workers")
        return sent_count

    async def ask_worker_question(
        self,
        worker_id: str,
        question: str,
        context: Dict[str, Any] = None,
        timeout: int = 300
    ) -> Optional[Dict[str, Any]]:
        """Ask a question to a worker and wait for response."""
        question_id = str(uuid.uuid4())

        question_payload = {
            "type": MessageType.QUESTION.value,
            "question_id": question_id,
            "question": question,
            "context": context or {},
            "reply_required": True
        }

        # Send question
        await self.send_to_worker(worker_id, question_payload)

        # Create pending question entry
        question_msg = Message(
            message_id=question_id,
            sender_id="master",
            recipient_id=worker_id,
            message_type=MessageType.QUESTION,
            payload=question_payload,
            timestamp=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=timeout)
        )

        self.pending_questions[question_id] = question_msg

        # Wait for response
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout:
            # Check if answer received
            if question_id not in self.pending_questions:
                # Answer was processed and removed
                break

            await asyncio.sleep(1)

        # Check if we got an answer
        for message in reversed(self.message_history.get(worker_id, [])):
            if (message.message_type == MessageType.ANSWER and
                message.reply_to == question_id):
                return message.payload

        # Timeout - remove pending question
        if question_id in self.pending_questions:
            del self.pending_questions[question_id]

        logger.warning(f"Question {question_id} to worker {worker_id} timed out")
        return None

    async def answer_worker_question(self, question_id: str, answer: Dict[str, Any]) -> bool:
        """Answer a question from a worker."""
        if question_id not in self.pending_questions:
            logger.warning(f"Question {question_id} not found or already answered")
            return False

        question = self.pending_questions[question_id]
        worker_id = question.sender_id

        answer_payload = {
            "type": MessageType.ANSWER.value,
            "question_id": question_id,
            "answer": answer
        }

        # Send answer
        await self.send_to_worker(worker_id, answer_payload)

        # Remove from pending questions
        del self.pending_questions[question_id]

        logger.info(f"Answered question {question_id} from worker {worker_id}")
        return True

    async def get_pending_questions(self) -> List[Dict[str, Any]]:
        """Get all pending questions from workers."""
        questions = []

        for question_id, question in self.pending_questions.items():
            questions.append({
                "question_id": question_id,
                "worker_id": question.sender_id,
                "question": question.payload.get("question"),
                "context": question.payload.get("context", {}),
                "timestamp": question.timestamp.isoformat(),
                "expires_at": question.expires_at.isoformat() if question.expires_at else None
            })

        return questions

    async def get_worker_status(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get communication status for a worker."""
        if worker_id not in self.workers:
            return None

        worker = self.workers[worker_id]

        # Count recent messages
        recent_messages = 0
        cutoff = datetime.now() - timedelta(hours=1)

        for message in self.message_history.get(worker_id, []):
            if message.timestamp >= cutoff:
                recent_messages += 1

        return {
            "worker_id": worker_id,
            "status": worker["status"],
            "registered_at": worker["registered_at"].isoformat(),
            "last_seen": worker["last_seen"].isoformat(),
            "capabilities": worker["capabilities"],
            "recent_messages": recent_messages,
            "pending_questions": len([
                q for q in self.pending_questions.values()
                if q.sender_id == worker_id
            ])
        }

    async def get_communication_metrics(self) -> Dict[str, Any]:
        """Get communication metrics."""
        total_workers = len(self.workers)
        active_workers = len([
            w for w in self.workers.values()
            if w["status"] == "active"
        ])

        total_messages = sum(len(history) for history in self.message_history.values())
        pending_questions = len(self.pending_questions)

        # Calculate message rates
        recent_cutoff = datetime.now() - timedelta(hours=1)
        recent_messages = 0

        for history in self.message_history.values():
            for message in history:
                if message.timestamp >= recent_cutoff:
                    recent_messages += 1

        return {
            "total_workers": total_workers,
            "active_workers": active_workers,
            "total_messages": total_messages,
            "recent_messages_1h": recent_messages,
            "pending_questions": pending_questions,
            "message_rate_per_hour": recent_messages
        }

    async def _handle_worker_message(self, worker_id: str, message: Message):
        """Handle incoming message from worker."""
        message_type = message.message_type

        if message_type == MessageType.HEARTBEAT:
            # Update worker last seen
            self.workers[worker_id]["last_seen"] = datetime.now()

        elif message_type == MessageType.QUESTION:
            # Add to pending questions
            question_id = message.payload.get("question_id")
            if question_id:
                self.pending_questions[question_id] = message
                logger.info(f"Received question {question_id} from worker {worker_id}")

        elif message_type == MessageType.ANSWER:
            # Remove corresponding question from pending
            question_id = message.reply_to
            if question_id and question_id in self.pending_questions:
                del self.pending_questions[question_id]
                logger.info(f"Received answer for question {question_id}")

        elif message_type == MessageType.TASK_UPDATE:
            # Log task progress
            task_id = message.payload.get("task_id")
            status = message.payload.get("status")
            logger.info(f"Task {task_id} update from worker {worker_id}: {status}")

        # Add to message history
        if worker_id not in self.message_history:
            self.message_history[worker_id] = []
        self.message_history[worker_id].append(message)

    async def _process_incoming_messages(self):
        """Process incoming messages from workers."""
        while True:
            try:
                # Check each worker's outbox
                for worker_id in list(self.workers.keys()):
                    if self.workers[worker_id]["status"] == "active":
                        await self.receive_from_worker(worker_id)

                await asyncio.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error processing incoming messages: {str(e)}")
                await asyncio.sleep(10)

    async def _cleanup_expired_messages(self):
        """Clean up expired messages and questions."""
        while True:
            try:
                now = datetime.now()

                # Clean up expired questions
                expired_questions = []
                for question_id, question in self.pending_questions.items():
                    if question.expires_at and question.expires_at < now:
                        expired_questions.append(question_id)

                for question_id in expired_questions:
                    del self.pending_questions[question_id]
                    logger.info(f"Expired question {question_id} cleaned up")

                # Clean up old message history (keep last 1000 messages per worker)
                for worker_id, history in self.message_history.items():
                    if len(history) > 1000:
                        self.message_history[worker_id] = history[-1000:]

                await asyncio.sleep(300)  # Clean up every 5 minutes

            except Exception as e:
                logger.error(f"Error in message cleanup: {str(e)}")
                await asyncio.sleep(300)

    async def _load_communication_state(self):
        """Load communication state from disk."""
        state_file = self.comm_dir / "communication_state.json"

        if state_file.exists():
            try:
                with open(state_file) as f:
                    state = json.load(f)

                # Restore workers (but mark as inactive until they reconnect)
                for worker_id, worker_data in state.get("workers", {}).items():
                    worker_data["status"] = "inactive"
                    worker_data["registered_at"] = datetime.fromisoformat(worker_data["registered_at"])
                    worker_data["last_seen"] = datetime.fromisoformat(worker_data["last_seen"])

                    # Recreate paths
                    worker_data["inbox_path"] = self.comm_dir / "workers" / worker_id / "inbox"
                    worker_data["outbox_path"] = self.comm_dir / "workers" / worker_id / "outbox"

                    self.workers[worker_id] = worker_data

                logger.info(f"Loaded communication state for {len(self.workers)} workers")

            except Exception as e:
                logger.error(f"Failed to load communication state: {str(e)}")

    async def cleanup(self):
        """Cleanup resources."""
        if self._message_processor_task:
            self._message_processor_task.cancel()
            try:
                await self._message_processor_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Save communication state
        state_file = self.comm_dir / "communication_state.json"
        try:
            state = {
                "workers": {
                    worker_id: {
                        "registered_at": worker["registered_at"].isoformat(),
                        "last_seen": worker["last_seen"].isoformat(),
                        "capabilities": worker["capabilities"],
                        "status": worker["status"]
                    }
                    for worker_id, worker in self.workers.items()
                }
            }

            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save communication state: {str(e)}")

        logger.info("Communication Hub cleanup completed")