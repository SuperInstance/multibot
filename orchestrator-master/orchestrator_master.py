#!/usr/bin/env python3
"""
Master Orchestrator MCP Server
Main server that coordinates multiple Claude Code worker instances.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP
from pydantic import BaseModel

from worker_manager import WorkerManager
from worker_lifecycle import WorkerLifecycleManager
from task_queue import TaskQueue
from communication import CommunicationHub
from repo_manager import RepositoryManager
from monitoring_gui import MonitoringDashboard
from config import initialize_globals, handle_error, check_safety, config
from message_queue import MessageQueueManager
from master_communication import MasterCommunicationHandler
from priority_timeout_handler import PriorityTimeoutHandler
from enhanced_orchestrator_tools import register_enhanced_tools


# Request/Response Models
class SpawnWorkerRequest(BaseModel):
    worker_id: str
    model: str = "sonnet"
    task_name: str
    base_branch: str = "main"


class AssignTaskRequest(BaseModel):
    worker_id: str
    task_description: str
    context: List[str] = []
    priority: int = 5


class SendMessageRequest(BaseModel):
    worker_id: str
    message: str


class MergeRequest(BaseModel):
    worker_id: str
    target_branch: str = "main"


class WorkerStatusResponse(BaseModel):
    worker_id: str
    status: str
    current_task: Optional[str]
    branch: str
    last_heartbeat: Optional[str]


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    worker_id: Optional[str]
    created_at: str
    completed_at: Optional[str]


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OrchestratorMaster:
    """Main orchestrator class managing all system components."""

    def __init__(self):
        # Legacy components
        self.worker_manager = WorkerManager()
        self.task_queue = TaskQueue()
        self.communication = CommunicationHub()
        self.repo_manager = RepositoryManager()
        self.monitoring = MonitoringDashboard()

        # Enhanced components
        self.worker_lifecycle = WorkerLifecycleManager()
        self.message_queue = MessageQueueManager()
        self.master_communication = MasterCommunicationHandler(self.message_queue)
        self.priority_handler = PriorityTimeoutHandler(self.message_queue)

    async def initialize(self):
        """Initialize all components."""
        # Initialize legacy components
        await self.worker_manager.initialize()
        await self.task_queue.initialize()
        await self.communication.initialize()
        await self.repo_manager.initialize()

        # Initialize enhanced components
        await self.worker_lifecycle.initialize()
        await self.message_queue.initialize()
        await self.master_communication.initialize()
        await self.priority_handler.initialize()

        logger.info("Master Orchestrator initialized successfully")


# Initialize FastMCP server
mcp = FastMCP("Orchestrator Master")
orchestrator = OrchestratorMaster()


@mcp.tool()
async def spawn_worker(request: SpawnWorkerRequest) -> Dict[str, Any]:
    """Spawn a new worker instance with enhanced lifecycle management."""
    try:
        logger.info(f"Spawning worker {request.worker_id} for task '{request.task_name}' with model {request.model}")

        # Check safety constraints
        active_count = len(orchestrator.worker_lifecycle.active_workers)
        if not check_safety("worker_limits", active_workers=active_count):
            raise Exception("Worker limit reached or resource constraints exceeded")

        # Spawn the worker with enhanced lifecycle
        result = await orchestrator.worker_lifecycle.spawn_worker(
            worker_id=request.worker_id,
            model=request.model,
            task_name=request.task_name,
            base_branch=request.base_branch
        )

        # Register worker in communication hub
        await orchestrator.communication.register_worker(request.worker_id)

        # Update monitoring with enhanced info
        orchestrator.monitoring.add_worker_terminal(
            request.worker_id,
            f"Worker-{request.worker_id}-{request.task_name}"
        )

        logger.info(f"Worker {request.worker_id} spawned successfully")
        return {
            "status": "success",
            "worker_id": request.worker_id,
            "message": f"Worker {request.worker_id} spawned successfully",
            "details": result
        }

    except Exception as e:
        handle_error(e, f"spawn_worker:{request.worker_id}")
        return {
            "status": "error",
            "worker_id": request.worker_id,
            "message": f"Failed to spawn worker: {str(e)}"
        }


@mcp.tool()
async def terminate_worker(
    worker_id: str,
    save_state: bool = True,
    commit_changes: bool = True,
    preserve_worktree: bool = False
) -> Dict[str, Any]:
    """Terminate a worker instance with enhanced lifecycle management."""
    try:
        logger.info(f"Terminating worker {worker_id}")

        # Get any pending tasks from worker
        pending_tasks = await orchestrator.task_queue.get_worker_tasks(worker_id)

        # Enhanced termination with lifecycle management
        result = await orchestrator.worker_lifecycle.terminate_worker(
            worker_id=worker_id,
            save_state=save_state,
            commit_changes=commit_changes,
            preserve_worktree=preserve_worktree
        )

        # Unregister from communication
        await orchestrator.communication.unregister_worker(worker_id)

        # Remove from monitoring
        orchestrator.monitoring.remove_worker_terminal(worker_id)

        # Reassign pending tasks
        if pending_tasks:
            reassigned = await orchestrator.task_queue.reassign_orphaned_tasks(pending_tasks)
            result["reassigned_tasks"] = len(reassigned)

        logger.info(f"Worker {worker_id} terminated successfully")
        return {
            "status": "success",
            **result
        }

    except Exception as e:
        handle_error(e, f"terminate_worker:{worker_id}")
        return {
            "status": "error",
            "worker_id": worker_id,
            "message": f"Failed to terminate worker: {str(e)}"
        }


@mcp.tool()
async def pause_worker(worker_id: str) -> Dict[str, Any]:
    """Pause a worker instance."""
    try:
        result = await orchestrator.worker_lifecycle.pause_worker(worker_id)
        if result:
            logger.info(f"Worker {worker_id} paused")
            return {
                "status": "success",
                "worker_id": worker_id,
                "message": f"Worker {worker_id} paused successfully"
            }
        else:
            return {
                "status": "error",
                "worker_id": worker_id,
                "message": f"Failed to pause worker {worker_id}"
            }
    except Exception as e:
        handle_error(e, f"pause_worker:{worker_id}")
        return {
            "status": "error",
            "worker_id": worker_id,
            "message": f"Failed to pause worker: {str(e)}"
        }


@mcp.tool()
async def resume_worker(worker_id: str) -> Dict[str, Any]:
    """Resume a paused worker instance."""
    try:
        result = await orchestrator.worker_lifecycle.resume_worker(worker_id)
        if result:
            logger.info(f"Worker {worker_id} resumed")
            return {
                "status": "success",
                "worker_id": worker_id,
                "message": f"Worker {worker_id} resumed successfully"
            }
        else:
            return {
                "status": "error",
                "worker_id": worker_id,
                "message": f"Failed to resume worker {worker_id}"
            }
    except Exception as e:
        handle_error(e, f"resume_worker:{worker_id}")
        return {
            "status": "error",
            "worker_id": worker_id,
            "message": f"Failed to resume worker: {str(e)}"
        }


@mcp.tool()
async def list_workers() -> Dict[str, Any]:
    """Get status of all workers with enhanced information."""
    try:
        workers = await orchestrator.worker_lifecycle.list_workers()
        return {
            "status": "success",
            "workers": workers,
            "total_count": len(workers)
        }
    except Exception as e:
        handle_error(e, "list_workers")
        return {
            "status": "error",
            "message": f"Failed to list workers: {str(e)}"
        }


@mcp.tool()
async def get_worker_status(worker_id: str) -> Dict[str, Any]:
    """Get detailed status of a specific worker."""
    try:
        status = await orchestrator.worker_lifecycle.get_worker_status(worker_id)
        return {
            "status": "success",
            "worker_status": status
        }
    except Exception as e:
        handle_error(e, f"get_worker_status:{worker_id}")
        return {
            "status": "error",
            "worker_id": worker_id,
            "message": f"Failed to get worker status: {str(e)}"
        }


@mcp.tool()
async def assign_task(request: AssignTaskRequest) -> Dict[str, Any]:
    """Assign a task to a specific worker."""
    try:
        task_id = await orchestrator.task_queue.assign_task(
            worker_id=request.worker_id,
            task_description=request.task_description,
            context=request.context,
            priority=request.priority
        )

        # Update worker's current task
        await orchestrator.worker_lifecycle.update_worker_task(
            request.worker_id,
            task_id,
            request.task_description
        )

        # Send task assignment via enhanced communication system
        success = await orchestrator.master_communication.send_task_assignment(
            worker_id=request.worker_id,
            task_id=task_id,
            description=request.task_description,
            context={"context_list": request.context, "additional_info": {}},
            priority=request.priority,
            timeout_seconds=3600  # 1 hour default timeout
        )

        if not success:
            logger.error(f"Failed to send task assignment to worker {request.worker_id}")
            return {
                "status": "error",
                "message": "Failed to send task assignment"
            }

        logger.info(f"Task {task_id} assigned to worker {request.worker_id}")
        return {
            "status": "success",
            "task_id": task_id,
            "worker_id": request.worker_id,
            "message": "Task assigned successfully"
        }

    except Exception as e:
        logger.error(f"Failed to assign task to {request.worker_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to assign task: {str(e)}"
        }


@mcp.tool()
async def reassign_task(task_id: str, from_worker: str, to_worker: str) -> Dict[str, Any]:
    """Reassign a task from one worker to another."""
    try:
        result = await orchestrator.task_queue.reassign_task(task_id, from_worker, to_worker)

        # Notify both workers
        await orchestrator.communication.send_to_worker(
            from_worker,
            {
                "type": "TASK_CANCELLED",
                "task_id": task_id
            }
        )

        task_details = await orchestrator.task_queue.get_task_details(task_id)
        await orchestrator.communication.send_to_worker(
            to_worker,
            {
                "type": "TASK_ASSIGNMENT",
                "task_id": task_id,
                **task_details
            }
        )

        logger.info(f"Task {task_id} reassigned from {from_worker} to {to_worker}")
        return {
            "status": "success",
            "task_id": task_id,
            "from_worker": from_worker,
            "to_worker": to_worker,
            "message": "Task reassigned successfully"
        }

    except Exception as e:
        logger.error(f"Failed to reassign task {task_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to reassign task: {str(e)}"
        }


@mcp.tool()
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """Get status of a specific task."""
    try:
        status = await orchestrator.task_queue.get_task_status(task_id)
        return TaskStatusResponse(**status)
    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {str(e)}")
        raise


@mcp.tool()
async def send_to_worker(request: SendMessageRequest) -> Dict[str, Any]:
    """Send a message to a specific worker."""
    try:
        await orchestrator.communication.send_to_worker(
            request.worker_id,
            {
                "type": "MESSAGE",
                "content": request.message,
                "timestamp": asyncio.get_event_loop().time()
            }
        )

        return {
            "status": "success",
            "worker_id": request.worker_id,
            "message": "Message sent successfully"
        }

    except Exception as e:
        logger.error(f"Failed to send message to {request.worker_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to send message: {str(e)}"
        }


@mcp.tool()
async def receive_from_worker(worker_id: str) -> Dict[str, Any]:
    """Receive messages/questions from a specific worker."""
    try:
        messages = await orchestrator.communication.receive_from_worker(worker_id)
        return {
            "status": "success",
            "worker_id": worker_id,
            "messages": messages,
            "count": len(messages)
        }

    except Exception as e:
        logger.error(f"Failed to receive from {worker_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to receive messages: {str(e)}"
        }


@mcp.tool()
async def broadcast_to_workers(message: str) -> Dict[str, Any]:
    """Broadcast a message to all active workers."""
    try:
        worker_count = await orchestrator.communication.broadcast_to_workers({
            "type": "BROADCAST",
            "content": message,
            "timestamp": asyncio.get_event_loop().time()
        })

        return {
            "status": "success",
            "message": "Broadcast sent successfully",
            "worker_count": worker_count
        }

    except Exception as e:
        logger.error(f"Failed to broadcast message: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to broadcast: {str(e)}"
        }


@mcp.tool()
async def create_worktree(worker_id: str, branch_name: str) -> Dict[str, Any]:
    """Create a Git worktree for a worker."""
    try:
        result = await orchestrator.repo_manager.create_worktree(worker_id, branch_name)
        return {
            "status": "success",
            "worker_id": worker_id,
            "branch": branch_name,
            "worktree_path": result["path"]
        }

    except Exception as e:
        logger.error(f"Failed to create worktree for {worker_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to create worktree: {str(e)}"
        }


@mcp.tool()
async def delete_worktree(worker_id: str) -> Dict[str, Any]:
    """Delete a worker's Git worktree."""
    try:
        await orchestrator.repo_manager.delete_worktree(worker_id)
        return {
            "status": "success",
            "worker_id": worker_id,
            "message": "Worktree deleted successfully"
        }

    except Exception as e:
        logger.error(f"Failed to delete worktree for {worker_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to delete worktree: {str(e)}"
        }


@mcp.tool()
async def merge_worker_branch(request: MergeRequest) -> Dict[str, Any]:
    """Merge a worker's branch into target branch."""
    try:
        result = await orchestrator.repo_manager.merge_worker_branch(
            request.worker_id,
            request.target_branch
        )

        return {
            "status": "success",
            "worker_id": request.worker_id,
            "target_branch": request.target_branch,
            "merge_commit": result.get("commit_hash"),
            "conflicts": result.get("conflicts", [])
        }

    except Exception as e:
        logger.error(f"Failed to merge branch for {request.worker_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to merge branch: {str(e)}"
        }


@mcp.tool()
async def resolve_conflicts(worker_branches: List[str]) -> Dict[str, Any]:
    """Resolve conflicts between multiple worker branches."""
    try:
        result = await orchestrator.repo_manager.resolve_conflicts(worker_branches)
        return {
            "status": "success",
            "resolved_conflicts": result["resolved"],
            "remaining_conflicts": result["remaining"],
            "resolution_strategy": result["strategy"]
        }

    except Exception as e:
        logger.error(f"Failed to resolve conflicts: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to resolve conflicts: {str(e)}"
        }


@mcp.tool()
async def open_monitoring_dashboard() -> Dict[str, Any]:
    """Open the monitoring GUI dashboard."""
    try:
        orchestrator.monitoring.open_dashboard()
        return {
            "status": "success",
            "message": "Monitoring dashboard opened successfully"
        }

    except Exception as e:
        logger.error(f"Failed to open monitoring dashboard: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to open dashboard: {str(e)}"
        }


@mcp.tool()
async def log_activity(worker_id: str, activity: str) -> Dict[str, Any]:
    """Log activity for a specific worker."""
    try:
        await orchestrator.monitoring.log_activity(worker_id, activity)
        return {
            "status": "success",
            "worker_id": worker_id,
            "message": "Activity logged successfully"
        }

    except Exception as e:
        logger.error(f"Failed to log activity for {worker_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to log activity: {str(e)}"
        }


@mcp.tool()
async def get_activity_log(worker_id: str, since_timestamp: Optional[float] = None) -> Dict[str, Any]:
    """Get activity log for a worker since specified timestamp."""
    try:
        activities = await orchestrator.monitoring.get_activity_log(worker_id, since_timestamp)
        return {
            "status": "success",
            "worker_id": worker_id,
            "activities": activities,
            "count": len(activities)
        }

    except Exception as e:
        logger.error(f"Failed to get activity log for {worker_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to get activity log: {str(e)}"
        }


async def main():
    """Main entry point for the MCP server."""
    try:
        # Initialize global configuration
        initialize_globals()

        # Initialize orchestrator
        await orchestrator.initialize()

        # Register enhanced communication tools
        register_enhanced_tools(mcp, orchestrator)

        # Register task orchestration tools
        from task_orchestration_tools import register_task_orchestration_tools
        orchestration_tools = register_task_orchestration_tools(mcp, orchestrator)

        # Register merge coordination tools
        from merge_coordination_tools import register_merge_coordination_tools
        merge_tools = register_merge_coordination_tools(mcp, orchestrator)

        # Register memory management tools
        from memory_tools import register_memory_tools
        memory_tools = register_memory_tools(mcp, orchestrator)

        # Register shared knowledge tools
        from shared_knowledge_tools import register_shared_knowledge_tools
        knowledge_tools = register_shared_knowledge_tools(mcp, orchestrator)

        # Register configuration management tools
        from config_tools import register_config_tools
        config_tools = register_config_tools(mcp, orchestrator)
        logger.info("Task orchestration, merge coordination, memory, shared knowledge, and configuration tools registered")

        # Start MCP server
        logger.info(f"Starting MCP server on {config.server_host}:{config.server_port}")
        await mcp.run(host=config.server_host, port=config.server_port)

    except Exception as e:
        handle_error(e, "main", critical=True, reraise=True)


if __name__ == "__main__":
    asyncio.run(main())