"""
Enhanced Orchestrator Tools
Additional MCP tools that utilize the new communication system.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastmcp import FastMCP
from pydantic import BaseModel

from message_queue import MessageType, MessagePriority, TaskStatus

logger = logging.getLogger(__name__)

# These tools will be added to the main orchestrator MCP server


class QuestionRequest(BaseModel):
    """Request model for asking questions."""
    worker_id: str
    question: str
    context: Optional[Dict[str, Any]] = {}
    priority: int = 5
    timeout_seconds: Optional[int] = 300


class BroadcastRequest(BaseModel):
    """Request model for broadcasting messages."""
    worker_ids: List[str]
    message_type: str
    content: Dict[str, Any]
    priority: int = 3


class MessageResponse(BaseModel):
    """Response model for message operations."""
    status: str
    message_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = {}


def register_enhanced_tools(mcp: FastMCP, orchestrator):
    """Register enhanced communication tools with the MCP server."""

    @mcp.tool()
    async def ask_worker_question(request: QuestionRequest) -> Dict[str, Any]:
        """Ask a question to a specific worker and wait for response.

        This tool allows the Master to ask questions to workers to save tokens
        by getting clarification instead of making assumptions.
        """
        try:
            logger.info(f"Asking question to worker {request.worker_id}: {request.question[:100]}...")

            # Send question and wait for response
            response = await orchestrator.master_communication.send_question_and_wait(
                worker_id=request.worker_id,
                question=request.question,
                context=request.context,
                timeout_seconds=request.timeout_seconds or 300
            )

            if response:
                return {
                    "status": "success",
                    "answer": response.get("answer", ""),
                    "additional_context": response.get("additional_context", {}),
                    "response_time": response.get("response_time", 0)
                }
            else:
                return {
                    "status": "timeout",
                    "message": f"Worker {request.worker_id} did not respond within {request.timeout_seconds} seconds"
                }

        except Exception as e:
            handle_error(e, f"ask_worker_question:{request.worker_id}")
            return {
                "status": "error",
                "message": f"Failed to ask question: {str(e)}"
            }

    @mcp.tool()
    async def get_pending_questions() -> Dict[str, Any]:
        """Get all pending questions from workers.

        Returns questions that workers have asked and are waiting for answers.
        """
        try:
            questions = await orchestrator.master_communication.get_pending_questions()

            formatted_questions = []
            for question in questions:
                formatted_questions.append({
                    "message_id": question.message_id,
                    "worker_id": question.worker_id,
                    "question": question.question,
                    "context": question.context,
                    "priority": question.priority.value,
                    "created_at": question.created_at.isoformat(),
                    "expires_at": question.expires_at.isoformat() if question.expires_at else None
                })

            return {
                "status": "success",
                "questions": formatted_questions,
                "count": len(formatted_questions)
            }

        except Exception as e:
            handle_error(e, "get_pending_questions")
            return {
                "status": "error",
                "message": f"Failed to get pending questions: {str(e)}",
                "questions": [],
                "count": 0
            }

    @mcp.tool()
    async def answer_worker_question(message_id: str, answer: str, additional_context: Optional[str] = None) -> Dict[str, Any]:
        """Answer a pending question from a worker.

        Args:
            message_id: ID of the question message to answer
            answer: The answer to provide to the worker
            additional_context: Optional additional context or guidance
        """
        try:
            context_dict = {}
            if additional_context:
                try:
                    context_dict = json.loads(additional_context)
                except json.JSONDecodeError:
                    context_dict = {"additional_info": additional_context}

            success = await orchestrator.master_communication.answer_question(
                message_id=message_id,
                answer=answer,
                additional_context=context_dict
            )

            if success:
                return {
                    "status": "success",
                    "message": f"Question {message_id} answered successfully"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to answer question {message_id}"
                }

        except Exception as e:
            handle_error(e, f"answer_worker_question:{message_id}")
            return {
                "status": "error",
                "message": f"Failed to answer question: {str(e)}"
            }

    @mcp.tool()
    async def send_guidance_to_worker(worker_id: str, guidance_type: str, guidance: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Send guidance or correction to a specific worker.

        Args:
            worker_id: Target worker ID
            guidance_type: Type of guidance (correction, suggestion, direction, etc.)
            guidance: The guidance message
            context: Optional context information
        """
        try:
            context_dict = {}
            if context:
                try:
                    context_dict = json.loads(context)
                except json.JSONDecodeError:
                    context_dict = {"context": context}

            message_id = await orchestrator.master_communication.send_guidance(
                worker_id=worker_id,
                guidance_type=guidance_type,
                guidance=guidance,
                context=context_dict,
                priority=MessagePriority.HIGH
            )

            return {
                "status": "success",
                "message_id": message_id,
                "message": f"Guidance sent to worker {worker_id}"
            }

        except Exception as e:
            handle_error(e, f"send_guidance_to_worker:{worker_id}")
            return {
                "status": "error",
                "message": f"Failed to send guidance: {str(e)}"
            }

    @mcp.tool()
    async def share_context_between_workers(source_worker_id: str, target_worker_ids: List[str], context_type: str, context_data: str) -> Dict[str, Any]:
        """Share context or information from one worker with others.

        Args:
            source_worker_id: Worker ID who generated the context
            target_worker_ids: List of worker IDs to share with
            context_type: Type of context being shared
            context_data: The context data (JSON string)
        """
        try:
            # Parse context data
            try:
                context_dict = json.loads(context_data)
            except json.JSONDecodeError:
                context_dict = {"data": context_data}

            message_ids = []
            for target_worker_id in target_worker_ids:
                message_id = await orchestrator.master_communication.share_context(
                    worker_id=target_worker_id,
                    context_type=context_type,
                    context_data=context_dict,
                    source_worker=source_worker_id
                )
                message_ids.append(message_id)

            return {
                "status": "success",
                "message_ids": message_ids,
                "shared_with": len(target_worker_ids),
                "message": f"Context shared from {source_worker_id} to {len(target_worker_ids)} workers"
            }

        except Exception as e:
            handle_error(e, f"share_context_between_workers:{source_worker_id}")
            return {
                "status": "error",
                "message": f"Failed to share context: {str(e)}"
            }

    @mcp.tool()
    async def broadcast_to_workers(request: BroadcastRequest) -> Dict[str, Any]:
        """Broadcast a message to multiple workers.

        Args:
            worker_ids: List of worker IDs to broadcast to
            message_type: Type of message to broadcast
            content: Message content
            priority: Message priority (1-9)
        """
        try:
            message_type_enum = MessageType(request.message_type)

            message_ids = await orchestrator.master_communication.broadcast_to_workers(
                worker_ids=request.worker_ids,
                message_type=message_type_enum,
                content=request.content,
                priority=MessagePriority(request.priority)
            )

            return {
                "status": "success",
                "message_ids": message_ids,
                "sent_to": len(message_ids),
                "total_workers": len(request.worker_ids),
                "message": f"Broadcast sent to {len(message_ids)}/{len(request.worker_ids)} workers"
            }

        except Exception as e:
            handle_error(e, "broadcast_to_workers")
            return {
                "status": "error",
                "message": f"Failed to broadcast: {str(e)}"
            }

    @mcp.tool()
    async def get_worker_communication_status() -> Dict[str, Any]:
        """Get communication status summary for all workers."""
        try:
            status_summary = await orchestrator.master_communication.get_worker_status_summary()

            return {
                "status": "success",
                **status_summary
            }

        except Exception as e:
            handle_error(e, "get_worker_communication_status")
            return {
                "status": "error",
                "message": f"Failed to get communication status: {str(e)}"
            }

    @mcp.tool()
    async def get_message_queue_stats() -> Dict[str, Any]:
        """Get message queue statistics and metrics."""
        try:
            # Get message queue stats
            queue_stats = await orchestrator.message_queue.get_message_stats()

            # Get priority handler metrics
            priority_metrics = orchestrator.priority_handler.get_metrics()

            return {
                "status": "success",
                "queue_stats": queue_stats,
                "priority_metrics": priority_metrics,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            handle_error(e, "get_message_queue_stats")
            return {
                "status": "error",
                "message": f"Failed to get queue stats: {str(e)}"
            }

    @mcp.tool()
    async def urgent_worker_message(worker_id: str, message_type: str, content: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        """Send an urgent message to a worker with custom timeout.

        Args:
            worker_id: Target worker ID
            message_type: Type of urgent message
            content: Message content
            timeout_seconds: Custom timeout for this message
        """
        try:
            # Parse content if JSON
            try:
                content_dict = json.loads(content)
            except json.JSONDecodeError:
                content_dict = {"message": content}

            message_id = await orchestrator.priority_handler.urgent_message(
                from_id="master",
                to_id=worker_id,
                message_type=MessageType(message_type),
                content=content_dict,
                timeout_seconds=timeout_seconds
            )

            return {
                "status": "success",
                "message_id": message_id,
                "timeout_seconds": timeout_seconds,
                "message": f"Urgent message sent to worker {worker_id}"
            }

        except Exception as e:
            handle_error(e, f"urgent_worker_message:{worker_id}")
            return {
                "status": "error",
                "message": f"Failed to send urgent message: {str(e)}"
            }

    @mcp.tool()
    async def escalate_worker_issue(worker_id: str, issue_type: str, description: str, severity: str = "medium") -> Dict[str, Any]:
        """Escalate an issue with a worker to higher priority handling.

        Args:
            worker_id: Worker with the issue
            issue_type: Type of issue (unresponsive, error, performance, etc.)
            description: Description of the issue
            severity: Issue severity (low, medium, high, critical)
        """
        try:
            # Determine priority based on severity
            priority_map = {
                "low": MessagePriority.NORMAL,
                "medium": MessagePriority.HIGH,
                "high": MessagePriority.URGENT,
                "critical": MessagePriority.CRITICAL
            }

            priority = priority_map.get(severity, MessagePriority.HIGH)

            # Create escalation message
            escalation_content = {
                "escalation_type": "worker_issue",
                "worker_id": worker_id,
                "issue_type": issue_type,
                "description": description,
                "severity": severity,
                "escalated_at": datetime.now().isoformat(),
                "escalated_by": "master"
            }

            message_id = await orchestrator.message_queue.send_message(
                from_id="master",
                to_id="escalation_handler",  # Could be human operator or automated system
                message_type=MessageType.ERROR,
                content=escalation_content,
                priority=priority
            )

            return {
                "status": "success",
                "message_id": message_id,
                "escalation_level": severity,
                "message": f"Issue with worker {worker_id} escalated as {severity} priority"
            }

        except Exception as e:
            handle_error(e, f"escalate_worker_issue:{worker_id}")
            return {
                "status": "error",
                "message": f"Failed to escalate issue: {str(e)}"
            }

    logger.info("Enhanced orchestrator communication tools registered")