#!/usr/bin/env python3
"""
Shared Knowledge MCP Tools
MCP tool integration for cross-worker context sharing and knowledge management.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from shared_knowledge import shared_knowledge_manager, CodingStandard

logger = logging.getLogger(__name__)


@dataclass
class AcquireLockRequest:
    """Request to acquire module lock."""
    worker_id: str
    task_id: str
    module_name: str
    dependencies: List[str] = None
    expected_duration_hours: int = 2
    description: str = ""


@dataclass
class ReleaseLockRequest:
    """Request to release module lock."""
    worker_id: str
    module_name: str
    completion_status: str = "completed"


@dataclass
class ShareCompletionRequest:
    """Request to share task completion context."""
    worker_id: str
    task_id: str
    completion_data: Dict[str, Any]


@dataclass
class GetContextRequest:
    """Request to get relevant shared context."""
    worker_id: str
    task_description: str
    modules_involved: List[str] = None


@dataclass
class UpdateStandardRequest:
    """Request to update coding standards."""
    category: str
    rule: str
    description: str
    examples: List[str] = None
    enforced_by: List[str] = None
    exceptions: List[str] = None
    updated_by: str = ""


@dataclass
class SearchKnowledgeRequest:
    """Request to search shared knowledge."""
    query: str
    content_types: List[str] = None
    limit: int = 10


def register_shared_knowledge_tools(mcp, orchestrator=None):
    """Register shared knowledge tools with MCP server."""

    @mcp.tool()
    async def acquire_module_lock(request: AcquireLockRequest) -> Dict[str, Any]:
        """
        Acquire a lock on a module to prevent conflicts.

        Before starting work on a module, workers should acquire a lock to
        coordinate with other workers and prevent conflicts. The system will
        check for existing locks and dependencies.

        Args:
            request: AcquireLockRequest with worker, task, and module details

        Returns:
            Lock acquisition result with conflict information if any
        """
        try:
            logger.info(f"Worker {request.worker_id} requesting lock on module {request.module_name}")

            result = await shared_knowledge_manager.acquire_module_lock(
                worker_id=request.worker_id,
                task_id=request.task_id,
                module_name=request.module_name,
                dependencies=request.dependencies or [],
                expected_duration_hours=request.expected_duration_hours
            )

            if result["status"] == "success":
                logger.info(f"Lock acquired on {request.module_name} by worker {request.worker_id}")
            elif result["status"] == "conflict":
                logger.warning(f"Lock conflict for {request.module_name}: {len(result.get('conflicts', []))} conflicts")

            return result

        except Exception as e:
            logger.error(f"Error acquiring module lock: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": request.worker_id,
                "module_name": request.module_name
            }

    @mcp.tool()
    async def release_module_lock(request: ReleaseLockRequest) -> Dict[str, Any]:
        """
        Release a module lock after completing work.

        When a worker finishes working on a module, they should release the lock
        so other workers can access it. The completion status helps track
        the module's state.

        Args:
            request: ReleaseLockRequest with worker and module details

        Returns:
            Lock release confirmation
        """
        try:
            logger.info(f"Worker {request.worker_id} releasing lock on module {request.module_name}")

            result = await shared_knowledge_manager.release_module_lock(
                worker_id=request.worker_id,
                module_name=request.module_name,
                completion_status=request.completion_status
            )

            if result["status"] == "success":
                logger.info(f"Lock released on {request.module_name} by worker {request.worker_id}")

            return result

        except Exception as e:
            logger.error(f"Error releasing module lock: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": request.worker_id,
                "module_name": request.module_name
            }

    @mcp.tool()
    async def share_task_completion(request: ShareCompletionRequest) -> Dict[str, Any]:
        """
        Share task completion context with all workers.

        When a worker completes a task, they should share what was built,
        APIs created, decisions made, and learnings discovered. This information
        becomes available to all other workers.

        Args:
            request: ShareCompletionRequest with task completion details

        Returns:
            Summary of shared information
        """
        try:
            logger.info(f"Worker {request.worker_id} sharing completion for task {request.task_id}")

            result = await shared_knowledge_manager.share_task_completion(
                worker_id=request.worker_id,
                task_id=request.task_id,
                completion_data=request.completion_data
            )

            if result["status"] == "success":
                logger.info(f"Shared {result['shared_count']} items from task {request.task_id}")

            return result

        except Exception as e:
            logger.error(f"Error sharing task completion: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": request.worker_id,
                "task_id": request.task_id
            }

    @mcp.tool()
    async def get_relevant_context(request: GetContextRequest) -> Dict[str, Any]:
        """
        Get relevant shared context before starting a task.

        Workers should call this before starting work to get relevant API
        contracts, architectural decisions, learnings, and conflict warnings
        related to their task.

        Args:
            request: GetContextRequest with worker and task details

        Returns:
            Relevant context from shared knowledge base
        """
        try:
            logger.info(f"Worker {request.worker_id} requesting context for task involving modules: {request.modules_involved}")

            result = await shared_knowledge_manager.get_relevant_context(
                worker_id=request.worker_id,
                task_description=request.task_description,
                modules_involved=request.modules_involved
            )

            if result["status"] == "success":
                total_items = result["total_items"]
                logger.info(f"Retrieved {total_items} relevant context items for worker {request.worker_id}")

                # Log specific context types found
                context = result["context"]
                context_summary = []
                if context["api_contracts"]:
                    context_summary.append(f"{len(context['api_contracts'])} API contracts")
                if context["architectural_decisions"]:
                    context_summary.append(f"{len(context['architectural_decisions'])} decisions")
                if context["worker_learnings"]:
                    context_summary.append(f"{len(context['worker_learnings'])} learnings")
                if context["conflict_warnings"]:
                    context_summary.append(f"{len(context['conflict_warnings'])} conflict warnings")

                result["context_summary"] = context_summary

            return result

        except Exception as e:
            logger.error(f"Error getting relevant context: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": request.worker_id
            }

    @mcp.tool()
    async def update_coding_standards(request: UpdateStandardRequest) -> Dict[str, Any]:
        """
        Update or add coding standards for the project.

        Workers can contribute new coding standards or update existing ones
        based on decisions made during development. These standards become
        available to all workers.

        Args:
            request: UpdateStandardRequest with standard details

        Returns:
            Confirmation of standard update
        """
        try:
            logger.info(f"Updating coding standard: {request.category} - {request.rule}")

            standard = CodingStandard(
                category=request.category,
                rule=request.rule,
                description=request.description,
                examples=request.examples or [],
                enforced_by=request.enforced_by or [],
                exceptions=request.exceptions or [],
                last_updated=datetime.now(),
                updated_by=request.updated_by
            )

            result = await shared_knowledge_manager.update_coding_standards(
                standard=standard,
                worker_id=request.updated_by
            )

            if result["status"] == "success":
                logger.info(f"Updated coding standard: {request.category}")

            return result

        except Exception as e:
            logger.error(f"Error updating coding standards: {e}")
            return {
                "status": "error",
                "error": str(e),
                "category": request.category
            }

    @mcp.tool()
    async def search_shared_knowledge(request: SearchKnowledgeRequest) -> Dict[str, Any]:
        """
        Search across all shared knowledge.

        Search through API contracts, architectural decisions, worker learnings,
        and coding standards to find relevant information. Supports filtering
        by content type and relevance ranking.

        Args:
            request: SearchKnowledgeRequest with search criteria

        Returns:
            Ranked search results with relevance scores
        """
        try:
            logger.info(f"Searching shared knowledge for: '{request.query}'")

            result = await shared_knowledge_manager.search_shared_knowledge(
                query=request.query,
                content_types=request.content_types,
                limit=request.limit
            )

            if result["status"] == "success":
                logger.info(f"Found {result['total_found']} results for search: '{request.query}'")

                # Add result summary
                if result["results"]:
                    content_types_found = set(r["type"] for r in result["results"])
                    result["content_types_found"] = list(content_types_found)

                    avg_relevance = sum(r["relevance_score"] for r in result["results"]) / len(result["results"])
                    result["average_relevance"] = round(avg_relevance, 3)

            return result

        except Exception as e:
            logger.error(f"Error searching shared knowledge: {e}")
            return {
                "status": "error",
                "error": str(e),
                "query": request.query
            }

    @mcp.tool()
    async def get_module_status(module_name: str) -> Dict[str, Any]:
        """
        Get current status of a specific module.

        Check if a module is currently locked, who owns it, and any relevant
        context about work being done on it.

        Args:
            module_name: Name of the module to check

        Returns:
            Module status and ownership information
        """
        try:
            logger.info(f"Checking status of module: {module_name}")

            # Check module locks
            locks = await shared_knowledge_manager._load_module_locks()
            current_lock = None
            for lock in locks:
                if lock["module_name"] == module_name and lock["status"] in ["locked", "in_progress"]:
                    current_lock = lock
                    break

            # Check module ownership
            if shared_knowledge_manager.module_ownership_file.exists():
                with open(shared_knowledge_manager.module_ownership_file, 'r') as f:
                    ownership_data = json.load(f)

                ownership = None
                for owner_record in ownership_data:
                    if owner_record.get("module") == module_name:
                        ownership = owner_record
                        break
            else:
                ownership = None

            # Get related API contracts
            api_contracts = await shared_knowledge_manager._load_api_contracts()
            related_apis = [api for api in api_contracts if api.get("module") == module_name]

            status_info = {
                "module_name": module_name,
                "is_locked": current_lock is not None,
                "current_lock": current_lock,
                "ownership": ownership,
                "related_apis": len(related_apis),
                "api_contracts": related_apis,
                "checked_at": datetime.now().isoformat()
            }

            logger.info(f"Module {module_name} status: locked={status_info['is_locked']}, APIs={len(related_apis)}")

            return {
                "status": "success",
                "module_status": status_info
            }

        except Exception as e:
            logger.error(f"Error getting module status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "module_name": module_name
            }

    @mcp.tool()
    async def list_active_locks() -> Dict[str, Any]:
        """
        List all currently active module locks.

        Get an overview of all modules currently being worked on and by whom.
        Useful for coordination and avoiding conflicts.

        Returns:
            List of active module locks
        """
        try:
            logger.info("Listing all active module locks")

            locks = await shared_knowledge_manager._load_module_locks()
            active_locks = [
                lock for lock in locks
                if lock["status"] in ["locked", "in_progress"]
            ]

            # Group by worker
            locks_by_worker = {}
            for lock in active_locks:
                worker_id = lock["worker_id"]
                if worker_id not in locks_by_worker:
                    locks_by_worker[worker_id] = []
                locks_by_worker[worker_id].append(lock)

            # Calculate stats
            total_active = len(active_locks)
            workers_active = len(locks_by_worker)
            modules_locked = [lock["module_name"] for lock in active_locks]

            logger.info(f"Found {total_active} active locks across {workers_active} workers")

            return {
                "status": "success",
                "active_locks": active_locks,
                "locks_by_worker": locks_by_worker,
                "stats": {
                    "total_active_locks": total_active,
                    "workers_with_locks": workers_active,
                    "modules_locked": modules_locked
                }
            }

        except Exception as e:
            logger.error(f"Error listing active locks: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    async def get_knowledge_stats() -> Dict[str, Any]:
        """
        Get statistics about the shared knowledge base.

        Returns overview of knowledge base size, worker activity, and content
        distribution. Useful for monitoring and maintenance.

        Returns:
            Detailed knowledge base statistics
        """
        try:
            logger.info("Getting shared knowledge statistics")

            result = await shared_knowledge_manager.get_knowledge_stats()

            if result["status"] == "success":
                stats = result["stats"]
                logger.info(f"Knowledge base stats: {stats['totals']['api_contracts']} APIs, "
                          f"{stats['totals']['worker_learnings']} learnings, "
                          f"{stats['totals']['active_locks']} active locks")

            return result

        except Exception as e:
            logger.error(f"Error getting knowledge stats: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    async def check_task_conflicts(worker_id: str, modules_involved: List[str]) -> Dict[str, Any]:
        """
        Check for potential conflicts before starting a task.

        Proactively check if working on specified modules would conflict with
        other workers' ongoing tasks. Helps prevent conflicts before they occur.

        Args:
            worker_id: ID of the worker planning to start work
            modules_involved: List of modules the task will involve

        Returns:
            Conflict analysis and recommendations
        """
        try:
            logger.info(f"Checking task conflicts for worker {worker_id} on modules: {modules_involved}")

            # Check module locks
            locks = await shared_knowledge_manager._load_module_locks()
            conflicts = []

            for module in modules_involved:
                for lock in locks:
                    if (lock["module_name"] == module and
                        lock["worker_id"] != worker_id and
                        lock["status"] in ["locked", "in_progress"]):
                        conflicts.append({
                            "type": "module_conflict",
                            "module": module,
                            "conflicting_worker": lock["worker_id"],
                            "locked_since": lock["locked_at"],
                            "expected_completion": lock.get("expected_completion"),
                            "severity": "high"
                        })

                    # Check dependencies
                    if module in lock.get("dependencies", []):
                        conflicts.append({
                            "type": "dependency_conflict",
                            "module": module,
                            "depends_on": lock["module_name"],
                            "blocked_by": lock["worker_id"],
                            "severity": "medium"
                        })

            # Generate recommendations
            recommendations = []
            if conflicts:
                high_severity = [c for c in conflicts if c["severity"] == "high"]
                if high_severity:
                    recommendations.append("Wait for high-severity conflicts to resolve before starting")

                medium_severity = [c for c in conflicts if c["severity"] == "medium"]
                if medium_severity:
                    recommendations.append("Coordinate with other workers on dependency conflicts")

                recommendations.append("Consider breaking task into smaller, non-conflicting parts")
            else:
                recommendations.append("No conflicts detected - safe to proceed")

            has_conflicts = len(conflicts) > 0
            severity_level = "high" if any(c["severity"] == "high" for c in conflicts) else (
                "medium" if any(c["severity"] == "medium" for c in conflicts) else "low"
            )

            logger.info(f"Conflict check for worker {worker_id}: {len(conflicts)} conflicts found (severity: {severity_level})")

            return {
                "status": "success",
                "worker_id": worker_id,
                "modules_checked": modules_involved,
                "has_conflicts": has_conflicts,
                "conflicts": conflicts,
                "severity_level": severity_level,
                "recommendations": recommendations,
                "checked_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error checking task conflicts: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": worker_id
            }

    return {
        "acquire_module_lock": acquire_module_lock,
        "release_module_lock": release_module_lock,
        "share_task_completion": share_task_completion,
        "get_relevant_context": get_relevant_context,
        "update_coding_standards": update_coding_standards,
        "search_shared_knowledge": search_shared_knowledge,
        "get_module_status": get_module_status,
        "list_active_locks": list_active_locks,
        "get_knowledge_stats": get_knowledge_stats,
        "check_task_conflicts": check_task_conflicts
    }