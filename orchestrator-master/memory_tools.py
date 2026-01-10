#!/usr/bin/env python3
"""
Memory Management MCP Tools
MCP tool integration for worker memory management functionality.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from memory_management import get_memory_manager, TaskRecord

logger = logging.getLogger(__name__)


@dataclass
class SaveContextRequest:
    """Request to save current context."""
    worker_id: str
    force_save: bool = False
    include_metadata: bool = True


@dataclass
class LoadContextRequest:
    """Request to load relevant context."""
    worker_id: str
    task_description: str = ""
    max_entries: int = 5
    include_archived: bool = True


@dataclass
class UpdateUnderstandingRequest:
    """Request to update code understanding."""
    worker_id: str
    module_name: str
    understanding: str
    file_path: str = ""
    tags: List[str] = None


@dataclass
class SearchMemoryRequest:
    """Request to search memory."""
    worker_id: str
    query: str
    limit: int = 10
    content_types: List[str] = None  # Filter by content types


@dataclass
class RecordTaskRequest:
    """Request to record task completion."""
    worker_id: str
    task_id: str
    description: str
    status: str
    start_time: str  # ISO format
    end_time: str = None  # ISO format
    files_modified: List[str] = None
    decisions_made: List[str] = None
    challenges_faced: List[str] = None
    solutions_implemented: List[str] = None
    context_at_completion: str = ""


def register_memory_tools(mcp, orchestrator=None):
    """Register memory management tools with MCP server."""

    @mcp.tool()
    async def save_current_context(request: SaveContextRequest) -> Dict[str, Any]:
        """
        Save current conversation context to memory and clear active conversation.

        Summarizes the current conversation, saves it to memory files, and trims
        the active context to free up tokens. This should be called when the
        conversation approaches token limits or at natural break points.

        Args:
            request: SaveContextRequest with worker_id and save options

        Returns:
            Status and statistics about the save operation
        """
        try:
            memory_manager = get_memory_manager(request.worker_id)

            # Check if save is needed (unless forced)
            if not request.force_save and not memory_manager.context_manager.should_save_context():
                return {
                    "status": "skipped",
                    "reason": "Context save not needed yet",
                    "current_tokens": memory_manager.context_manager.current_token_count,
                    "save_threshold": memory_manager.context_manager.save_threshold
                }

            # Save context
            result = await memory_manager.save_current_context()

            if result["status"] == "success":
                logger.info(f"Context saved for worker {request.worker_id}: {result['tokens_saved']} tokens")

            return result

        except Exception as e:
            logger.error(f"Error saving context for worker {request.worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": request.worker_id
            }

    @mcp.tool()
    async def load_context(request: LoadContextRequest) -> Dict[str, Any]:
        """
        Load relevant context based on current task.

        Searches through saved contexts, code understanding, and decisions to find
        information relevant to the current task. Uses semantic search to rank
        relevance and returns the most useful context entries.

        Args:
            request: LoadContextRequest with worker_id and task details

        Returns:
            Relevant context entries ranked by relevance
        """
        try:
            memory_manager = get_memory_manager(request.worker_id)

            result = await memory_manager.load_context(
                task_description=request.task_description,
                max_entries=request.max_entries
            )

            if result["status"] == "success":
                logger.info(f"Loaded {result['total_entries']} context entries for worker {request.worker_id}")

            return result

        except Exception as e:
            logger.error(f"Error loading context for worker {request.worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": request.worker_id
            }

    @mcp.tool()
    async def update_understanding(request: UpdateUnderstandingRequest) -> Dict[str, Any]:
        """
        Save understanding of specific code modules.

        Records detailed understanding of code modules, files, or systems for
        future reference. This builds up the worker's knowledge base about
        different parts of the codebase.

        Args:
            request: UpdateUnderstandingRequest with module details and understanding

        Returns:
            Confirmation of updated understanding
        """
        try:
            memory_manager = get_memory_manager(request.worker_id)

            result = await memory_manager.update_understanding(
                module_name=request.module_name,
                understanding=request.understanding,
                file_path=request.file_path
            )

            if result["status"] == "success":
                logger.info(f"Updated understanding for {request.module_name} in worker {request.worker_id}")

            return result

        except Exception as e:
            logger.error(f"Error updating understanding for worker {request.worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": request.worker_id
            }

    @mcp.tool()
    async def search_memory(request: SearchMemoryRequest) -> Dict[str, Any]:
        """
        Semantic search across all memory files.

        Searches through all saved contexts, code understanding, decisions, and
        questions to find information relevant to the search query. Uses semantic
        matching to rank results by relevance.

        Args:
            request: SearchMemoryRequest with query and search options

        Returns:
            Ranked search results with relevance scores
        """
        try:
            memory_manager = get_memory_manager(request.worker_id)

            result = await memory_manager.search_memory(
                query=request.query,
                limit=request.limit
            )

            # Filter by content types if specified
            if request.content_types and result["status"] == "success":
                filtered_results = [
                    r for r in result["results"]
                    if r["content_type"] in request.content_types
                ]
                result["results"] = filtered_results
                result["results_found"] = len(filtered_results)

            if result["status"] == "success":
                logger.info(f"Memory search for worker {request.worker_id}: {result['results_found']} results for '{request.query}'")

            return result

        except Exception as e:
            logger.error(f"Error searching memory for worker {request.worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": request.worker_id
            }

    @mcp.tool()
    async def record_task_completion(request: RecordTaskRequest) -> Dict[str, Any]:
        """
        Record completion of a task in worker memory.

        Saves detailed information about a completed task including what was done,
        decisions made, challenges faced, and solutions implemented. This builds
        up the worker's experience and knowledge base.

        Args:
            request: RecordTaskRequest with task details and outcomes

        Returns:
            Confirmation of recorded task
        """
        try:
            memory_manager = get_memory_manager(request.worker_id)

            # Convert string timestamps to datetime objects
            start_time = datetime.fromisoformat(request.start_time.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(request.end_time.replace('Z', '+00:00')) if request.end_time else None

            # Create task record
            task_record = TaskRecord(
                task_id=request.task_id,
                description=request.description,
                status=request.status,
                start_time=start_time,
                end_time=end_time,
                files_modified=request.files_modified or [],
                decisions_made=request.decisions_made or [],
                challenges_faced=request.challenges_faced or [],
                solutions_implemented=request.solutions_implemented or [],
                context_at_completion=request.context_at_completion
            )

            result = await memory_manager.record_task_completion(task_record)

            if result["status"] == "success":
                logger.info(f"Recorded task completion {request.task_id} for worker {request.worker_id}")

            return result

        except Exception as e:
            logger.error(f"Error recording task completion for worker {request.worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": request.worker_id
            }

    @mcp.tool()
    async def get_memory_stats(worker_id: str) -> Dict[str, Any]:
        """
        Get statistics about worker memory usage.

        Returns detailed statistics about the worker's memory files, token usage,
        and storage consumption. Useful for monitoring and maintenance.

        Args:
            worker_id: ID of the worker

        Returns:
            Detailed memory usage statistics
        """
        try:
            memory_manager = get_memory_manager(worker_id)
            result = await memory_manager.get_memory_stats()

            if result["status"] == "success":
                logger.info(f"Retrieved memory stats for worker {worker_id}")

            return result

        except Exception as e:
            logger.error(f"Error getting memory stats for worker {worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": worker_id
            }

    @mcp.tool()
    async def add_conversation_content(worker_id: str, content: str, token_count: int) -> Dict[str, Any]:
        """
        Add content to worker's active conversation context.

        Tracks conversation content and token usage. Automatically triggers
        context saving when approaching token limits.

        Args:
            worker_id: ID of the worker
            content: Conversation content to add
            token_count: Estimated token count for the content

        Returns:
            Status and token usage information
        """
        try:
            memory_manager = get_memory_manager(worker_id)

            # Add to context
            memory_manager.context_manager.add_to_context(content, token_count)

            # Check if save is needed
            should_save = memory_manager.context_manager.should_save_context()

            return {
                "status": "success",
                "worker_id": worker_id,
                "content_added": True,
                "current_tokens": memory_manager.context_manager.current_token_count,
                "max_tokens": memory_manager.context_manager.max_active_tokens,
                "save_recommended": should_save,
                "save_threshold": memory_manager.context_manager.save_threshold
            }

        except Exception as e:
            logger.error(f"Error adding conversation content for worker {worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": worker_id
            }

    @mcp.tool()
    async def get_context_summary(worker_id: str) -> Dict[str, Any]:
        """
        Get summary of current conversation context.

        Returns a summary of the current active conversation without saving it.
        Useful for checking what would be saved or getting current context overview.

        Args:
            worker_id: ID of the worker

        Returns:
            Summary of current context
        """
        try:
            memory_manager = get_memory_manager(worker_id)

            # Create summary without saving
            summary = memory_manager.context_manager.create_context_summary()

            return {
                "status": "success",
                "worker_id": worker_id,
                "summary": {
                    "token_count": summary.token_count,
                    "key_points": summary.key_points,
                    "decisions_made": summary.decisions_made,
                    "questions_raised": summary.questions_raised,
                    "code_areas_touched": summary.code_areas_touched,
                    "created_at": summary.created_at.isoformat()
                },
                "should_save": memory_manager.context_manager.should_save_context()
            }

        except Exception as e:
            logger.error(f"Error getting context summary for worker {worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": worker_id
            }

    @mcp.tool()
    async def cleanup_old_memories(worker_id: str, days_old: int = 30) -> Dict[str, Any]:
        """
        Clean up old memory files to free storage space.

        Removes archived context files older than specified days and compacts
        memory usage. Keeps essential information while freeing space.

        Args:
            worker_id: ID of the worker
            days_old: Remove files older than this many days

        Returns:
            Cleanup statistics
        """
        try:
            memory_manager = get_memory_manager(worker_id)

            # Find old archive files
            cutoff_date = datetime.now() - timedelta(days=days_old)
            removed_files = []
            total_size_freed = 0

            for archive_file in memory_manager.memory_path.glob("context_archive_*.md"):
                file_time = datetime.fromtimestamp(archive_file.stat().st_mtime)
                if file_time < cutoff_date:
                    file_size = archive_file.stat().st_size
                    archive_file.unlink()
                    removed_files.append(archive_file.name)
                    total_size_freed += file_size

            logger.info(f"Cleaned up {len(removed_files)} old memory files for worker {worker_id}")

            return {
                "status": "success",
                "worker_id": worker_id,
                "files_removed": len(removed_files),
                "size_freed_bytes": total_size_freed,
                "cutoff_date": cutoff_date.isoformat(),
                "removed_files": removed_files
            }

        except Exception as e:
            logger.error(f"Error cleaning up memories for worker {worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": worker_id
            }

    return {
        "save_current_context": save_current_context,
        "load_context": load_context,
        "update_understanding": update_understanding,
        "search_memory": search_memory,
        "record_task_completion": record_task_completion,
        "get_memory_stats": get_memory_stats,
        "add_conversation_content": add_conversation_content,
        "get_context_summary": get_context_summary,
        "cleanup_old_memories": cleanup_old_memories
    }