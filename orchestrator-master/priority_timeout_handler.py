"""
Priority Queue and Timeout Handler
Advanced message handling with priority processing, timeout management,
and retry logic for the communication system.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import heapq

from message_queue import (
    MessageQueueManager, Message, MessageType, MessagePriority, MessageStatus
)

logger = logging.getLogger(__name__)


class TimeoutAction(Enum):
    """Actions to take when a message times out."""
    RETRY = "retry"
    ESCALATE = "escalate"
    FAIL = "fail"
    CALLBACK = "callback"


@dataclass
class TimeoutRule:
    """Defines timeout behavior for different message types."""
    message_type: MessageType
    timeout_seconds: int
    action: TimeoutAction
    max_retries: int = 3
    escalation_target: Optional[str] = None
    callback: Optional[Callable] = None


@dataclass
class PriorityMessage:
    """Message wrapper for priority queue processing."""
    priority: int
    created_at: float
    message: Message

    def __lt__(self, other):
        """Compare for priority queue (higher priority first, then older first)."""
        if self.priority != other.priority:
            return self.priority > other.priority  # Higher priority first
        return self.created_at < other.created_at  # Older first for same priority


class PriorityTimeoutHandler:
    """Handles message priority processing and timeout management."""

    def __init__(self, message_queue: MessageQueueManager):
        self.message_queue = message_queue
        self.priority_queue: List[PriorityMessage] = []
        self.pending_timeouts: Dict[str, asyncio.Task] = {}
        self.timeout_rules: Dict[MessageType, TimeoutRule] = {}
        self.retry_counts: Dict[str, int] = {}

        # Processing state
        self._processing_task: Optional[asyncio.Task] = None
        self._timeout_check_task: Optional[asyncio.Task] = None
        self._running = False

        # Callbacks
        self.message_processors: Dict[MessageType, List[Callable]] = {}
        self.timeout_callbacks: List[Callable] = []

        # Metrics
        self.metrics = {
            "messages_processed": 0,
            "messages_timed_out": 0,
            "messages_retried": 0,
            "messages_escalated": 0,
            "priority_queue_size": 0
        }

    async def initialize(self):
        """Initialize the priority timeout handler."""
        logger.info("Initializing Priority Timeout Handler")

        # Set up default timeout rules
        self._setup_default_timeout_rules()

        # Start processing
        self._running = True
        self._processing_task = asyncio.create_task(self._process_priority_queue())
        self._timeout_check_task = asyncio.create_task(self._check_timeouts())

        logger.info("Priority Timeout Handler initialized")

    def _setup_default_timeout_rules(self):
        """Set up default timeout rules for different message types."""
        self.timeout_rules = {
            # Questions need prompt response
            MessageType.QUESTION: TimeoutRule(
                message_type=MessageType.QUESTION,
                timeout_seconds=300,  # 5 minutes
                action=TimeoutAction.ESCALATE,
                max_retries=1,
                escalation_target="human_operator"
            ),

            # Task assignments should be acknowledged quickly
            MessageType.TASK_ASSIGN: TimeoutRule(
                message_type=MessageType.TASK_ASSIGN,
                timeout_seconds=60,  # 1 minute
                action=TimeoutAction.RETRY,
                max_retries=3
            ),

            # Status updates are less critical
            MessageType.STATUS_UPDATE: TimeoutRule(
                message_type=MessageType.STATUS_UPDATE,
                timeout_seconds=30,  # 30 seconds
                action=TimeoutAction.FAIL,
                max_retries=0
            ),

            # Guidance is important
            MessageType.GUIDANCE: TimeoutRule(
                message_type=MessageType.GUIDANCE,
                timeout_seconds=120,  # 2 minutes
                action=TimeoutAction.RETRY,
                max_retries=2
            ),

            # Control messages are critical
            MessageType.PAUSE: TimeoutRule(
                message_type=MessageType.PAUSE,
                timeout_seconds=30,
                action=TimeoutAction.ESCALATE,
                max_retries=1
            ),

            MessageType.RESUME: TimeoutRule(
                message_type=MessageType.RESUME,
                timeout_seconds=30,
                action=TimeoutAction.ESCALATE,
                max_retries=1
            ),

            MessageType.TERMINATE: TimeoutRule(
                message_type=MessageType.TERMINATE,
                timeout_seconds=60,
                action=TimeoutAction.ESCALATE,
                max_retries=0
            ),

            # Errors need attention
            MessageType.ERROR: TimeoutRule(
                message_type=MessageType.ERROR,
                timeout_seconds=180,  # 3 minutes
                action=TimeoutAction.ESCALATE,
                max_retries=1
            ),

            # Resource requests need response
            MessageType.RESOURCE_REQUEST: TimeoutRule(
                message_type=MessageType.RESOURCE_REQUEST,
                timeout_seconds=240,  # 4 minutes
                action=TimeoutAction.RETRY,
                max_retries=2
            )
        }

    async def enqueue_message(self, message: Message, custom_priority: Optional[int] = None):
        """Add message to priority queue with timeout tracking."""
        priority = custom_priority or message.priority.value

        priority_message = PriorityMessage(
            priority=priority,
            created_at=message.created_at.timestamp(),
            message=message
        )

        heapq.heappush(self.priority_queue, priority_message)
        self.metrics["priority_queue_size"] = len(self.priority_queue)

        # Set up timeout tracking
        await self._setup_timeout_tracking(message)

        logger.debug(f"Enqueued message {message.id} with priority {priority}")

    async def _setup_timeout_tracking(self, message: Message):
        """Set up timeout tracking for a message."""
        timeout_rule = self.timeout_rules.get(message.message_type)

        if timeout_rule:
            timeout_task = asyncio.create_task(
                self._handle_message_timeout(message, timeout_rule)
            )
            self.pending_timeouts[message.id] = timeout_task

    async def _handle_message_timeout(self, message: Message, timeout_rule: TimeoutRule):
        """Handle message timeout according to rules."""
        try:
            await asyncio.sleep(timeout_rule.timeout_seconds)

            # Check if message was processed
            if message.id not in self.pending_timeouts:
                return  # Already processed

            logger.warning(f"Message {message.id} timed out after {timeout_rule.timeout_seconds}s")
            self.metrics["messages_timed_out"] += 1

            # Execute timeout action
            await self._execute_timeout_action(message, timeout_rule)

        except asyncio.CancelledError:
            # Timeout was cancelled (message processed)
            pass
        except Exception as e:
            logger.error(f"Error handling timeout for message {message.id}: {str(e)}")

    async def _execute_timeout_action(self, message: Message, timeout_rule: TimeoutRule):
        """Execute the appropriate timeout action."""
        if timeout_rule.action == TimeoutAction.RETRY:
            await self._retry_message(message, timeout_rule)

        elif timeout_rule.action == TimeoutAction.ESCALATE:
            await self._escalate_message(message, timeout_rule)

        elif timeout_rule.action == TimeoutAction.FAIL:
            await self._fail_message(message)

        elif timeout_rule.action == TimeoutAction.CALLBACK:
            await self._callback_message(message, timeout_rule)

        # Notify timeout callbacks
        for callback in self.timeout_callbacks:
            try:
                await callback(message, timeout_rule)
            except Exception as e:
                logger.error(f"Timeout callback error: {str(e)}")

    async def _retry_message(self, message: Message, timeout_rule: TimeoutRule):
        """Retry a timed-out message."""
        retry_count = self.retry_counts.get(message.id, 0) + 1
        self.retry_counts[message.id] = retry_count

        if retry_count <= timeout_rule.max_retries:
            logger.info(f"Retrying message {message.id} (attempt {retry_count}/{timeout_rule.max_retries})")

            # Increase priority for retry
            new_priority = min(message.priority.value + 1, MessagePriority.URGENT.value)

            # Re-enqueue with higher priority
            await self.enqueue_message(message, custom_priority=new_priority)
            self.metrics["messages_retried"] += 1

        else:
            logger.error(f"Message {message.id} exceeded max retries ({timeout_rule.max_retries})")
            await self._escalate_message(message, timeout_rule)

    async def _escalate_message(self, message: Message, timeout_rule: TimeoutRule):
        """Escalate a timed-out message."""
        logger.warning(f"Escalating message {message.id} to {timeout_rule.escalation_target or 'default'}")

        escalation_target = timeout_rule.escalation_target or "master"

        # Create escalation message
        escalation_content = {
            "escalated_message_id": message.id,
            "original_type": message.message_type.value,
            "timeout_seconds": timeout_rule.timeout_seconds,
            "retry_count": self.retry_counts.get(message.id, 0),
            "escalation_reason": "timeout",
            "original_content": message.content
        }

        await self.message_queue.send_message(
            from_id="timeout_handler",
            to_id=escalation_target,
            message_type=MessageType.ERROR,
            content=escalation_content,
            priority=MessagePriority.URGENT
        )

        self.metrics["messages_escalated"] += 1

    async def _fail_message(self, message: Message):
        """Mark a message as failed due to timeout."""
        logger.warning(f"Marking message {message.id} as failed due to timeout")

        # Update message status in database
        # This would require extending the message queue interface
        # For now, just log the failure

    async def _callback_message(self, message: Message, timeout_rule: TimeoutRule):
        """Execute custom callback for timed-out message."""
        if timeout_rule.callback:
            try:
                await timeout_rule.callback(message)
            except Exception as e:
                logger.error(f"Timeout callback error for message {message.id}: {str(e)}")

    async def _process_priority_queue(self):
        """Process messages from priority queue."""
        while self._running:
            try:
                if self.priority_queue:
                    priority_message = heapq.heappop(self.priority_queue)
                    self.metrics["priority_queue_size"] = len(self.priority_queue)

                    await self._process_message(priority_message.message)

                else:
                    await asyncio.sleep(0.1)  # Short sleep when queue is empty

            except Exception as e:
                logger.error(f"Error processing priority queue: {str(e)}")
                await asyncio.sleep(1)

    async def _process_message(self, message: Message):
        """Process a single message."""
        try:
            logger.debug(f"Processing message {message.id} of type {message.message_type.value}")

            # Call registered processors
            processors = self.message_processors.get(message.message_type, [])
            for processor in processors:
                try:
                    await processor(message)
                except Exception as e:
                    logger.error(f"Message processor error: {str(e)}")

            # Cancel timeout tracking
            if message.id in self.pending_timeouts:
                self.pending_timeouts[message.id].cancel()
                del self.pending_timeouts[message.id]

            self.metrics["messages_processed"] += 1

        except Exception as e:
            logger.error(f"Error processing message {message.id}: {str(e)}")

    async def _check_timeouts(self):
        """Periodic cleanup of expired timeout tasks."""
        while self._running:
            try:
                # Clean up completed timeout tasks
                completed_tasks = []
                for message_id, task in self.pending_timeouts.items():
                    if task.done():
                        completed_tasks.append(message_id)

                for message_id in completed_tasks:
                    del self.pending_timeouts[message_id]

                # Check for messages that should have expired
                current_time = datetime.now()
                for message_id, task in list(self.pending_timeouts.items()):
                    # Additional timeout logic could go here
                    pass

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error in timeout check: {str(e)}")
                await asyncio.sleep(30)

    def register_message_processor(self, message_type: MessageType, processor: Callable):
        """Register a processor for specific message type."""
        if message_type not in self.message_processors:
            self.message_processors[message_type] = []
        self.message_processors[message_type].append(processor)

    def register_timeout_callback(self, callback: Callable):
        """Register a callback for timeout events."""
        self.timeout_callbacks.append(callback)

    def set_timeout_rule(self, message_type: MessageType, timeout_rule: TimeoutRule):
        """Set or update timeout rule for message type."""
        self.timeout_rules[message_type] = timeout_rule
        logger.info(f"Updated timeout rule for {message_type.value}: {timeout_rule.timeout_seconds}s")

    def get_metrics(self) -> Dict[str, Any]:
        """Get processing metrics."""
        return {
            **self.metrics,
            "pending_timeouts": len(self.pending_timeouts),
            "retry_counts": dict(self.retry_counts)
        }

    async def urgent_message(
        self,
        from_id: str,
        to_id: str,
        message_type: MessageType,
        content: Dict[str, Any],
        timeout_seconds: Optional[int] = None
    ) -> str:
        """Send an urgent message with custom timeout."""
        # Send message with critical priority
        message_id = await self.message_queue.send_message(
            from_id=from_id,
            to_id=to_id,
            message_type=message_type,
            content=content,
            priority=MessagePriority.CRITICAL
        )

        # Set custom timeout if provided
        if timeout_seconds:
            custom_rule = TimeoutRule(
                message_type=message_type,
                timeout_seconds=timeout_seconds,
                action=TimeoutAction.ESCALATE,
                max_retries=1
            )

            # Create and track timeout
            timeout_task = asyncio.create_task(
                self._handle_message_timeout_custom(message_id, custom_rule)
            )
            self.pending_timeouts[message_id] = timeout_task

        logger.info(f"Sent urgent message {message_id}")
        return message_id

    async def _handle_message_timeout_custom(self, message_id: str, timeout_rule: TimeoutRule):
        """Handle timeout for custom timeout rule."""
        try:
            await asyncio.sleep(timeout_rule.timeout_seconds)

            if message_id in self.pending_timeouts:
                logger.warning(f"Urgent message {message_id} timed out")
                # Execute timeout action
                # Would need message object here for full implementation
                # For now, just log and escalate

        except asyncio.CancelledError:
            pass

    async def batch_process_messages(self, messages: List[Message], batch_size: int = 10):
        """Process multiple messages in batches for efficiency."""
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]

            # Add all messages to queue
            for message in batch:
                await self.enqueue_message(message)

            # Allow processing to catch up
            await asyncio.sleep(0.1)

        logger.info(f"Batch processed {len(messages)} messages in batches of {batch_size}")

    async def priority_override(self, message_id: str, new_priority: MessagePriority):
        """Override priority of a pending message."""
        # Find message in priority queue
        for i, priority_message in enumerate(self.priority_queue):
            if priority_message.message.id == message_id:
                # Remove old entry
                self.priority_queue.pop(i)

                # Re-add with new priority
                priority_message.priority = new_priority.value
                heapq.heappush(self.priority_queue, priority_message)

                # Re-heapify to maintain order
                heapq.heapify(self.priority_queue)

                logger.info(f"Updated priority for message {message_id} to {new_priority.value}")
                return True

        logger.warning(f"Message {message_id} not found for priority override")
        return False

    async def cleanup(self):
        """Cleanup priority timeout handler resources."""
        logger.info("Cleaning up Priority Timeout Handler")

        self._running = False

        # Cancel processing tasks
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        if self._timeout_check_task:
            self._timeout_check_task.cancel()
            try:
                await self._timeout_check_task
            except asyncio.CancelledError:
                pass

        # Cancel all pending timeouts
        for task in self.pending_timeouts.values():
            task.cancel()

        self.pending_timeouts.clear()
        self.priority_queue.clear()

        logger.info("Priority Timeout Handler cleanup completed")