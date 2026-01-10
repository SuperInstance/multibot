"""
Master Communication Handler
Handles all communication for the Master orchestrator including message processing,
question handling, and worker coordination.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

from message_queue import (
    MessageQueueManager, Message, TaskAssignment,
    MessageType, MessagePriority, TaskStatus
)

logger = logging.getLogger(__name__)


@dataclass
class PendingQuestion:
    """Represents a pending question from a worker."""
    message_id: str
    worker_id: str
    question: str
    context: Dict[str, Any]
    priority: MessagePriority
    created_at: datetime
    expires_at: Optional[datetime] = None


class MasterCommunicationHandler:
    """Handles Master-side communication with workers."""

    def __init__(self, message_queue: MessageQueueManager):
        self.message_queue = message_queue
        self.pending_questions: Dict[str, PendingQuestion] = {}
        self.question_handlers: List[Callable] = []
        self.status_callbacks: Dict[str, List[Callable]] = {}
        self.auto_response_enabled = True

        # Message type handlers
        self.message_handlers = {
            MessageType.QUESTION: self._handle_question,
            MessageType.STATUS_UPDATE: self._handle_status_update,
            MessageType.TASK_COMPLETE: self._handle_task_complete,
            MessageType.ERROR: self._handle_error,
            MessageType.RESOURCE_REQUEST: self._handle_resource_request,
            MessageType.HEARTBEAT: self._handle_heartbeat
        }

    async def initialize(self):
        """Initialize the communication handler."""
        logger.info("Initializing Master Communication Handler")

        # Register as message handler for master
        self.message_queue.register_message_handler("master", self._process_message)

        logger.info("Master Communication Handler initialized")

    async def send_task_assignment(
        self,
        worker_id: str,
        task_id: str,
        description: str,
        context: Dict[str, Any],
        priority: int = 5,
        timeout_seconds: Optional[int] = 3600,
        dependencies: Optional[List[str]] = None
    ) -> bool:
        """Send task assignment to worker."""
        try:
            # Create task in database
            success = await self.message_queue.assign_task(
                task_id=task_id,
                worker_id=worker_id,
                description=description,
                context=context,
                priority=priority,
                timeout_seconds=timeout_seconds,
                dependencies=dependencies
            )

            if success:
                logger.info(f"Assigned task {task_id} to worker {worker_id}")
                return True
            else:
                logger.error(f"Failed to assign task {task_id} to worker {worker_id}")
                return False

        except Exception as e:
            logger.error(f"Error assigning task {task_id}: {str(e)}")
            return False

    async def send_task_update(
        self,
        worker_id: str,
        task_id: str,
        updates: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> str:
        """Send task update to worker."""
        message_id = await self.message_queue.send_message(
            from_id="master",
            to_id=worker_id,
            message_type=MessageType.TASK_UPDATE,
            content={
                "task_id": task_id,
                "updates": updates,
                "timestamp": datetime.now().isoformat()
            },
            priority=priority
        )

        logger.info(f"Sent task update for {task_id} to worker {worker_id}")
        return message_id

    async def share_context(
        self,
        worker_id: str,
        context_type: str,
        context_data: Dict[str, Any],
        source_worker: Optional[str] = None
    ) -> str:
        """Share context information with a worker."""
        message_id = await self.message_queue.send_message(
            from_id="master",
            to_id=worker_id,
            message_type=MessageType.CONTEXT_SHARE,
            content={
                "context_type": context_type,
                "context_data": context_data,
                "source_worker": source_worker,
                "timestamp": datetime.now().isoformat()
            },
            priority=MessagePriority.NORMAL
        )

        logger.info(f"Shared context '{context_type}' with worker {worker_id}")
        return message_id

    async def send_guidance(
        self,
        worker_id: str,
        guidance_type: str,
        guidance: str,
        context: Optional[Dict[str, Any]] = None,
        priority: MessagePriority = MessagePriority.HIGH
    ) -> str:
        """Send guidance/correction to worker."""
        message_id = await self.message_queue.send_message(
            from_id="master",
            to_id=worker_id,
            message_type=MessageType.GUIDANCE,
            content={
                "guidance_type": guidance_type,
                "guidance": guidance,
                "context": context or {},
                "timestamp": datetime.now().isoformat()
            },
            priority=priority
        )

        logger.info(f"Sent guidance to worker {worker_id}: {guidance_type}")
        return message_id

    async def pause_worker(self, worker_id: str) -> str:
        """Send pause signal to worker."""
        message_id = await self.message_queue.send_message(
            from_id="master",
            to_id=worker_id,
            message_type=MessageType.PAUSE,
            content={
                "timestamp": datetime.now().isoformat(),
                "reason": "pause_requested"
            },
            priority=MessagePriority.HIGH
        )

        logger.info(f"Sent pause signal to worker {worker_id}")
        return message_id

    async def resume_worker(self, worker_id: str) -> str:
        """Send resume signal to worker."""
        message_id = await self.message_queue.send_message(
            from_id="master",
            to_id=worker_id,
            message_type=MessageType.RESUME,
            content={
                "timestamp": datetime.now().isoformat(),
                "reason": "resume_requested"
            },
            priority=MessagePriority.HIGH
        )

        logger.info(f"Sent resume signal to worker {worker_id}")
        return message_id

    async def terminate_worker(self, worker_id: str, reason: str = "shutdown") -> str:
        """Send termination signal to worker."""
        message_id = await self.message_queue.send_message(
            from_id="master",
            to_id=worker_id,
            message_type=MessageType.TERMINATE,
            content={
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "graceful": True
            },
            priority=MessagePriority.CRITICAL
        )

        logger.info(f"Sent termination signal to worker {worker_id}: {reason}")
        return message_id

    async def send_question_and_wait(
        self,
        worker_id: str,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 300
    ) -> Optional[Dict[str, Any]]:
        """Send a question to worker and wait for response."""
        try:
            # Send question
            message_id = await self.message_queue.send_message(
                from_id="master",
                to_id=worker_id,
                message_type=MessageType.QUESTION,
                content={
                    "question": question,
                    "context": context or {},
                    "requires_response": True
                },
                priority=MessagePriority.HIGH,
                expires_in_seconds=timeout_seconds
            )

            # Wait for response
            start_time = datetime.now()
            while (datetime.now() - start_time).total_seconds() < timeout_seconds:
                # Check for response
                messages = await self.message_queue.receive_messages(
                    recipient_id="master",
                    message_types=[MessageType.ACK],
                    limit=50
                )

                for message in messages:
                    if message.response_to == message_id and message.from_id == worker_id:
                        response_time = (datetime.now() - start_time).total_seconds()
                        return {
                            "answer": message.content.get("answer", ""),
                            "additional_context": message.content.get("additional_context", {}),
                            "response_time": response_time
                        }

                await asyncio.sleep(1)

            logger.warning(f"Question to worker {worker_id} timed out after {timeout_seconds}s")
            return None

        except Exception as e:
            logger.error(f"Error sending question to worker {worker_id}: {str(e)}")
            return None

    async def answer_question(
        self,
        message_id: str,
        answer: str,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Answer a worker's question."""
        try:
            if message_id not in self.pending_questions:
                logger.warning(f"Question {message_id} not found in pending questions")
                return False

            question = self.pending_questions[message_id]

            # Send answer back to worker
            await self.message_queue.send_message(
                from_id="master",
                to_id=question.worker_id,
                message_type=MessageType.ACK,
                content={
                    "answer": answer,
                    "additional_context": additional_context or {},
                    "answered_at": datetime.now().isoformat()
                },
                response_to=message_id,
                priority=MessagePriority.HIGH
            )

            # Acknowledge the original question
            await self.message_queue.acknowledge_message(message_id)

            # Remove from pending
            del self.pending_questions[message_id]

            logger.info(f"Answered question {message_id} from worker {question.worker_id}")
            return True

        except Exception as e:
            logger.error(f"Error answering question {message_id}: {str(e)}")
            return False

    async def get_pending_questions(self) -> List[PendingQuestion]:
        """Get all pending questions sorted by priority and age."""
        questions = list(self.pending_questions.values())

        # Sort by priority (desc) then by age (oldest first)
        questions.sort(key=lambda q: (-q.priority.value, q.created_at))

        return questions

    async def get_worker_status_summary(self) -> Dict[str, Any]:
        """Get summary of all worker statuses."""
        try:
            # Get recent status updates
            messages = await self.message_queue.receive_messages(
                recipient_id="master",
                message_types=[MessageType.STATUS_UPDATE],
                limit=200
            )

            worker_statuses = {}
            for message in messages:
                worker_id = message.from_id
                if worker_id not in worker_statuses:
                    worker_statuses[worker_id] = {
                        "worker_id": worker_id,
                        "last_update": message.created_at,
                        "status": message.content.get("status", "unknown"),
                        "current_task": message.content.get("current_task"),
                        "progress": message.content.get("progress", 0),
                        "resource_usage": message.content.get("resource_usage", {})
                    }
                elif message.created_at > worker_statuses[worker_id]["last_update"]:
                    worker_statuses[worker_id].update({
                        "last_update": message.created_at,
                        "status": message.content.get("status", "unknown"),
                        "current_task": message.content.get("current_task"),
                        "progress": message.content.get("progress", 0),
                        "resource_usage": message.content.get("resource_usage", {})
                    })

            return {
                "worker_count": len(worker_statuses),
                "workers": list(worker_statuses.values()),
                "last_updated": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting worker status summary: {str(e)}")
            return {"worker_count": 0, "workers": [], "error": str(e)}

    async def broadcast_to_workers(
        self,
        worker_ids: List[str],
        message_type: MessageType,
        content: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> List[str]:
        """Broadcast message to multiple workers."""
        message_ids = []

        for worker_id in worker_ids:
            try:
                message_id = await self.message_queue.send_message(
                    from_id="master",
                    to_id=worker_id,
                    message_type=message_type,
                    content=content,
                    priority=priority
                )
                message_ids.append(message_id)
            except Exception as e:
                logger.error(f"Failed to broadcast to worker {worker_id}: {str(e)}")

        logger.info(f"Broadcast {message_type.value} to {len(message_ids)}/{len(worker_ids)} workers")
        return message_ids

    def register_question_handler(self, handler: Callable[[PendingQuestion], None]):
        """Register a handler for new questions."""
        self.question_handlers.append(handler)

    def register_status_callback(self, worker_id: str, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback for worker status updates."""
        if worker_id not in self.status_callbacks:
            self.status_callbacks[worker_id] = []
        self.status_callbacks[worker_id].append(callback)

    async def _process_message(self, message: Message):
        """Process incoming message from worker."""
        try:
            handler = self.message_handlers.get(message.message_type)
            if handler:
                await handler(message)
            else:
                logger.warning(f"No handler for message type: {message.message_type.value}")

            # Acknowledge message
            await self.message_queue.acknowledge_message(message.id)

        except Exception as e:
            logger.error(f"Error processing message {message.id}: {str(e)}")

    async def _handle_question(self, message: Message):
        """Handle question from worker."""
        question_content = message.content
        worker_id = message.from_id

        question = PendingQuestion(
            message_id=message.id,
            worker_id=worker_id,
            question=question_content.get("question", ""),
            context=question_content.get("context", {}),
            priority=message.priority,
            created_at=message.created_at,
            expires_at=message.expires_at
        )

        self.pending_questions[message.id] = question

        logger.info(f"Received question from worker {worker_id}: {question.question[:100]}...")

        # Notify question handlers
        for handler in self.question_handlers:
            try:
                await handler(question)
            except Exception as e:
                logger.error(f"Question handler error: {str(e)}")

        # Auto-respond to simple questions if enabled
        if self.auto_response_enabled:
            await self._try_auto_response(question)

    async def _handle_status_update(self, message: Message):
        """Handle status update from worker."""
        worker_id = message.from_id
        status_content = message.content

        logger.debug(f"Status update from worker {worker_id}: {status_content.get('status', 'unknown')}")

        # Update task status if provided
        if "task_id" in status_content and "task_status" in status_content:
            await self.message_queue.update_task_status(
                task_id=status_content["task_id"],
                status=TaskStatus(status_content["task_status"]),
                result=status_content.get("result")
            )

        # Call status callbacks
        if worker_id in self.status_callbacks:
            for callback in self.status_callbacks[worker_id]:
                try:
                    await callback(status_content)
                except Exception as e:
                    logger.error(f"Status callback error: {str(e)}")

    async def _handle_task_complete(self, message: Message):
        """Handle task completion from worker."""
        worker_id = message.from_id
        task_content = message.content

        task_id = task_content.get("task_id")
        result = task_content.get("result", {})

        if task_id:
            await self.message_queue.update_task_status(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result=result
            )

            logger.info(f"Task {task_id} completed by worker {worker_id}")
        else:
            logger.warning(f"Task completion message missing task_id from worker {worker_id}")

    async def _handle_error(self, message: Message):
        """Handle error report from worker."""
        worker_id = message.from_id
        error_content = message.content

        error_type = error_content.get("error_type", "unknown")
        error_message = error_content.get("error_message", "")
        task_id = error_content.get("task_id")

        logger.error(f"Error from worker {worker_id}: {error_type} - {error_message}")

        # Update task status if task-related error
        if task_id:
            await self.message_queue.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error_message=error_message
            )

    async def _handle_resource_request(self, message: Message):
        """Handle resource request from worker."""
        worker_id = message.from_id
        request_content = message.content

        resource_type = request_content.get("resource_type", "unknown")
        details = request_content.get("details", {})

        logger.info(f"Resource request from worker {worker_id}: {resource_type}")

        # Handle common resource requests
        if resource_type == "file_access":
            await self._handle_file_access_request(worker_id, details, message.id)
        elif resource_type == "context_data":
            await self._handle_context_data_request(worker_id, details, message.id)
        else:
            # Send generic acknowledgment
            await self.message_queue.send_message(
                from_id="master",
                to_id=worker_id,
                message_type=MessageType.ACK,
                content={
                    "status": "acknowledged",
                    "message": f"Resource request '{resource_type}' received"
                },
                response_to=message.id
            )

    async def _handle_heartbeat(self, message: Message):
        """Handle heartbeat from worker."""
        worker_id = message.from_id
        heartbeat_content = message.content

        logger.debug(f"Heartbeat from worker {worker_id}")

        # Could update worker last-seen timestamp here
        # For now, just acknowledge
        await self.message_queue.acknowledge_message(message.id)

    async def _try_auto_response(self, question: PendingQuestion):
        """Try to automatically respond to simple questions."""
        question_text = question.question.lower()

        # Simple auto-responses for common questions
        auto_responses = {
            "what time is it": f"Current time: {datetime.now().strftime('%H:%M:%S')}",
            "what date is it": f"Current date: {datetime.now().strftime('%Y-%m-%d')}",
            "should i continue": "Yes, please continue with your current task.",
            "is this correct": "Please use your best judgment based on the context provided.",
        }

        for keyword, response in auto_responses.items():
            if keyword in question_text:
                await self.answer_question(
                    question.message_id,
                    response,
                    {"auto_response": True}
                )
                logger.info(f"Auto-responded to question from worker {question.worker_id}")
                return

    async def _handle_file_access_request(self, worker_id: str, details: Dict[str, Any], message_id: str):
        """Handle file access request."""
        file_path = details.get("file_path", "")
        access_type = details.get("access_type", "read")

        # For now, approve all read requests, deny writes outside worktree
        if access_type == "read":
            response = {
                "status": "approved",
                "message": f"Read access approved for {file_path}"
            }
        else:
            response = {
                "status": "denied",
                "message": "Write access only allowed within worker worktree"
            }

        await self.message_queue.send_message(
            from_id="master",
            to_id=worker_id,
            message_type=MessageType.ACK,
            content=response,
            response_to=message_id
        )

    async def _handle_context_data_request(self, worker_id: str, details: Dict[str, Any], message_id: str):
        """Handle context data request."""
        context_type = details.get("context_type", "")

        # Provide basic context data
        context_data = {
            "project_name": "multibot-orchestration",
            "current_workers": len(self.status_callbacks),
            "timestamp": datetime.now().isoformat()
        }

        await self.message_queue.send_message(
            from_id="master",
            to_id=worker_id,
            message_type=MessageType.CONTEXT_SHARE,
            content={
                "context_type": context_type,
                "context_data": context_data
            },
            response_to=message_id
        )

    async def cleanup(self):
        """Cleanup communication handler resources."""
        logger.info("Cleaning up Master Communication Handler")
        # Cleanup is handled by the message queue manager
        logger.info("Master Communication Handler cleanup completed")