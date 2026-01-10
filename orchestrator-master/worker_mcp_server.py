#!/usr/bin/env python3
"""
Worker MCP Server
Provides MCP tools for Claude Code worker instances to communicate with Master,
manage memory, handle tasks, and maintain repository awareness.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import sqlite3
import uuid

from fastmcp import FastMCP
from worker_intelligence import WorkerIntelligence

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Orchestrator Worker")

# Global state
WORKER_ID = os.environ.get("WORKER_ID", "unknown")
WORKER_MODEL = os.environ.get("WORKER_MODEL", "sonnet")
MEMORY_DIR = Path(os.environ.get("WORKER_MEMORY_DIR", "/tmp/worker_memory"))
WORKING_DIR = Path(os.environ.get("WORKER_WORKING_DIR", "/tmp/worker"))
MESSAGE_QUEUE_DB = os.environ.get("MESSAGE_QUEUE_DB", "/tmp/multibot/message_queue.db")

# Ensure directories exist
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
WORKING_DIR.mkdir(parents=True, exist_ok=True)

# Worker state
worker_state = {
    "worker_id": WORKER_ID,
    "model": WORKER_MODEL,
    "status": "initializing",
    "current_task": None,
    "last_heartbeat": None,
    "start_time": datetime.now().isoformat(),
    "activity_log": []
}


class WorkerMessageQueue:
    """Simplified message queue interface for workers."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path, timeout=30.0)

    async def send_message(
        self,
        from_id: str,
        to_id: str,
        message_type: str,
        content: Dict[str, Any],
        priority: int = 3
    ) -> str:
        """Send message to queue."""
        message_id = str(uuid.uuid4())
        now = datetime.now()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (
                    id, from_id, to_id, message_type, content, priority,
                    created_at, status, retry_count, max_retries, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message_id, from_id, to_id, message_type,
                json.dumps(content), priority, now.isoformat(),
                "pending", 0, 3, now.isoformat()
            ))
            conn.commit()
            return message_id
        finally:
            conn.close()

    async def receive_messages(self, recipient_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Receive messages for recipient."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages
                WHERE to_id = ? AND status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """, (recipient_id, limit))

            messages = []
            message_ids = []

            for row in cursor.fetchall():
                message = {
                    "id": row[0],
                    "from_id": row[1],
                    "to_id": row[2],
                    "message_type": row[3],
                    "content": json.loads(row[4]),
                    "priority": row[5],
                    "created_at": row[6],
                    "status": row[8]
                }
                messages.append(message)
                message_ids.append(row[0])

            # Mark as delivered
            if message_ids:
                placeholders = ",".join("?" * len(message_ids))
                cursor.execute(f"""
                    UPDATE messages
                    SET status = 'delivered', updated_at = ?
                    WHERE id IN ({placeholders})
                """, [datetime.now().isoformat()] + message_ids)
                conn.commit()

            return messages
        finally:
            conn.close()

    async def acknowledge_message(self, message_id: str):
        """Acknowledge message receipt."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE messages
                SET status = 'acknowledged', updated_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), message_id))
            conn.commit()
        finally:
            conn.close()


# Initialize message queue and intelligence layer
message_queue = WorkerMessageQueue(MESSAGE_QUEUE_DB)
intelligence = WorkerIntelligence(WORKER_ID, MEMORY_DIR, WORKING_DIR, message_queue)


def log_activity(activity: str, level: str = "info"):
    """Log worker activity."""
    timestamp = datetime.now().isoformat()
    entry = {
        "timestamp": timestamp,
        "activity": activity,
        "level": level
    }

    worker_state["activity_log"].append(entry)

    # Keep only last 100 activities
    if len(worker_state["activity_log"]) > 100:
        worker_state["activity_log"] = worker_state["activity_log"][-100:]

    # Log to file
    log_file = MEMORY_DIR / "activity.log"
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {activity}\n")

    logger.info(f"[{WORKER_ID}] {activity}")


# === COMMUNICATION TOOLS ===

@mcp.tool()
async def send_to_master(message_type: str, content: str, priority: int = 3) -> str:
    """Send message to the Master orchestrator.

    Args:
        message_type: Type of message (question, status_update, task_complete, error, resource_request)
        content: Message content (string or JSON)
        priority: Message priority (1=low, 3=normal, 5=high, 7=urgent, 9=critical)

    Returns:
        Message ID for tracking
    """
    try:
        # Parse content if it's JSON
        try:
            content_dict = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            content_dict = {"message": content}

        # Add worker context
        content_dict.update({
            "worker_id": WORKER_ID,
            "worker_model": WORKER_MODEL,
            "timestamp": datetime.now().isoformat()
        })

        message_id = await message_queue.send_message(
            from_id=WORKER_ID,
            to_id="master",
            message_type=message_type,
            content=content_dict,
            priority=priority
        )

        log_activity(f"Sent {message_type} message to master: {message_id}")
        return f"Message sent successfully. ID: {message_id}"

    except Exception as e:
        error_msg = f"Failed to send message to master: {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


@mcp.tool()
async def check_for_messages() -> str:
    """Check for new messages from Master.

    Returns:
        JSON string with messages or empty list
    """
    try:
        messages = await message_queue.receive_messages(WORKER_ID, limit=50)

        if not messages:
            return json.dumps({"messages": [], "count": 0})

        # Process messages
        processed_messages = []
        for message in messages:
            processed_messages.append({
                "id": message["id"],
                "type": message["message_type"],
                "content": message["content"],
                "priority": message["priority"],
                "created_at": message["created_at"]
            })

            # Auto-acknowledge certain message types
            if message["message_type"] in ["heartbeat", "context_share"]:
                await message_queue.acknowledge_message(message["id"])

        log_activity(f"Received {len(messages)} messages from master")

        return json.dumps({
            "messages": processed_messages,
            "count": len(processed_messages)
        })

    except Exception as e:
        error_msg = f"Failed to check messages: {str(e)}"
        log_activity(error_msg, "error")
        return json.dumps({"error": error_msg, "messages": [], "count": 0})


@mcp.tool()
async def acknowledge_message(message_id: str) -> str:
    """Acknowledge receipt of a message from Master.

    Args:
        message_id: ID of the message to acknowledge

    Returns:
        Confirmation message
    """
    try:
        await message_queue.acknowledge_message(message_id)
        log_activity(f"Acknowledged message: {message_id}")
        return f"Message {message_id} acknowledged successfully"

    except Exception as e:
        error_msg = f"Failed to acknowledge message {message_id}: {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


# === MEMORY MANAGEMENT ===

@mcp.tool()
async def save_context(key: str, content: str) -> str:
    """Save context information to worker's memory.

    Args:
        key: Context key/identifier
        content: Content to save (can be JSON string)

    Returns:
        Confirmation message
    """
    try:
        context_file = MEMORY_DIR / f"{key}.json"

        # Try to parse as JSON, otherwise save as string
        try:
            content_data = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            content_data = {"content": content, "type": "text"}

        # Add metadata
        context_data = {
            "key": key,
            "data": content_data,
            "saved_at": datetime.now().isoformat(),
            "worker_id": WORKER_ID
        }

        with open(context_file, "w") as f:
            json.dump(context_data, f, indent=2)

        log_activity(f"Saved context: {key}")
        return f"Context '{key}' saved successfully"

    except Exception as e:
        error_msg = f"Failed to save context '{key}': {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


@mcp.tool()
async def load_context(key: str) -> str:
    """Load context information from worker's memory.

    Args:
        key: Context key to retrieve

    Returns:
        JSON string with context data or error message
    """
    try:
        context_file = MEMORY_DIR / f"{key}.json"

        if not context_file.exists():
            return json.dumps({"error": f"Context '{key}' not found"})

        with open(context_file) as f:
            context_data = json.load(f)

        log_activity(f"Loaded context: {key}")
        return json.dumps(context_data)

    except Exception as e:
        error_msg = f"Failed to load context '{key}': {str(e)}"
        log_activity(error_msg, "error")
        return json.dumps({"error": error_msg})


@mcp.tool()
async def list_contexts() -> str:
    """List all saved contexts in worker's memory.

    Returns:
        JSON string with list of available contexts
    """
    try:
        contexts = []

        for context_file in MEMORY_DIR.glob("*.json"):
            if context_file.name != "activity.log":
                try:
                    with open(context_file) as f:
                        data = json.load(f)

                    contexts.append({
                        "key": context_file.stem,
                        "saved_at": data.get("saved_at", "unknown"),
                        "size": context_file.stat().st_size
                    })
                except Exception:
                    pass  # Skip corrupted files

        contexts.sort(key=lambda x: x["saved_at"], reverse=True)

        log_activity(f"Listed {len(contexts)} contexts")
        return json.dumps({"contexts": contexts, "count": len(contexts)})

    except Exception as e:
        error_msg = f"Failed to list contexts: {str(e)}"
        log_activity(error_msg, "error")
        return json.dumps({"error": error_msg, "contexts": []})


@mcp.tool()
async def clear_old_contexts(days: int = 7) -> str:
    """Clear old context files from memory.

    Args:
        days: Remove contexts older than this many days

    Returns:
        Summary of cleanup operation
    """
    try:
        cutoff = datetime.now() - timedelta(days=days)
        removed_count = 0

        for context_file in MEMORY_DIR.glob("*.json"):
            if context_file.name == "activity.log":
                continue

            try:
                with open(context_file) as f:
                    data = json.load(f)

                saved_at = datetime.fromisoformat(data.get("saved_at", ""))
                if saved_at < cutoff:
                    context_file.unlink()
                    removed_count += 1

            except Exception:
                pass  # Skip corrupted files

        log_activity(f"Cleared {removed_count} old contexts (older than {days} days)")
        return f"Removed {removed_count} contexts older than {days} days"

    except Exception as e:
        error_msg = f"Failed to clear old contexts: {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


# === TASK MANAGEMENT ===

@mcp.tool()
async def get_current_task() -> str:
    """Get details of the currently assigned task.

    Returns:
        JSON string with current task details
    """
    try:
        if worker_state["current_task"]:
            return json.dumps(worker_state["current_task"])
        else:
            # Check for new task assignments
            messages = await message_queue.receive_messages(WORKER_ID, limit=10)

            for message in messages:
                if message["message_type"] == "task_assign":
                    task_data = message["content"]
                    worker_state["current_task"] = {
                        "task_id": task_data.get("task_id"),
                        "description": task_data.get("description"),
                        "context": task_data.get("context", {}),
                        "priority": task_data.get("priority", 5),
                        "assigned_at": message["created_at"],
                        "status": "assigned"
                    }

                    await message_queue.acknowledge_message(message["id"])
                    log_activity(f"Assigned new task: {task_data.get('task_id')}")

                    return json.dumps(worker_state["current_task"])

            return json.dumps({"message": "No current task assigned"})

    except Exception as e:
        error_msg = f"Failed to get current task: {str(e)}"
        log_activity(error_msg, "error")
        return json.dumps({"error": error_msg})


@mcp.tool()
async def update_task_progress(task_id: str, progress: int, notes: str = "") -> str:
    """Update progress on current task.

    Args:
        task_id: ID of the task being updated
        progress: Progress percentage (0-100)
        notes: Optional progress notes

    Returns:
        Confirmation message
    """
    try:
        # Send progress update to master
        await send_to_master("status_update", json.dumps({
            "task_id": task_id,
            "task_status": "in_progress",
            "progress": progress,
            "notes": notes,
            "status": "working"
        }), priority=3)

        # Update local state
        if worker_state["current_task"] and worker_state["current_task"]["task_id"] == task_id:
            worker_state["current_task"]["progress"] = progress
            worker_state["current_task"]["status"] = "in_progress"
            worker_state["current_task"]["last_update"] = datetime.now().isoformat()

        log_activity(f"Updated task {task_id} progress: {progress}% - {notes}")
        return f"Task {task_id} progress updated to {progress}%"

    except Exception as e:
        error_msg = f"Failed to update task progress: {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


@mcp.tool()
async def mark_task_complete(task_id: str, result: str) -> str:
    """Mark current task as completed.

    Args:
        task_id: ID of the completed task
        result: Task completion result/summary

    Returns:
        Confirmation message
    """
    try:
        # Parse result if it's JSON
        try:
            result_data = json.loads(result) if isinstance(result, str) else result
        except json.JSONDecodeError:
            result_data = {"summary": result}

        # Send completion to master
        await send_to_master("task_complete", json.dumps({
            "task_id": task_id,
            "result": result_data,
            "completed_at": datetime.now().isoformat()
        }), priority=5)

        # Update local state
        if worker_state["current_task"] and worker_state["current_task"]["task_id"] == task_id:
            worker_state["current_task"]["status"] = "completed"
            worker_state["current_task"]["completed_at"] = datetime.now().isoformat()
            worker_state["current_task"]["result"] = result_data

        log_activity(f"Completed task: {task_id}")
        return f"Task {task_id} marked as completed"

    except Exception as e:
        error_msg = f"Failed to mark task complete: {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


@mcp.tool()
async def report_task_error(task_id: str, error: str) -> str:
    """Report an error with the current task.

    Args:
        task_id: ID of the task with error
        error: Error description

    Returns:
        Confirmation message
    """
    try:
        # Send error to master
        await send_to_master("error", json.dumps({
            "task_id": task_id,
            "error_type": "task_error",
            "error_message": error,
            "timestamp": datetime.now().isoformat()
        }), priority=7)

        # Update local state
        if worker_state["current_task"] and worker_state["current_task"]["task_id"] == task_id:
            worker_state["current_task"]["status"] = "error"
            worker_state["current_task"]["error"] = error

        log_activity(f"Reported task error for {task_id}: {error}", "error")
        return f"Error reported for task {task_id}"

    except Exception as e:
        error_msg = f"Failed to report task error: {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


# === STATUS REPORTING ===

@mcp.tool()
async def report_status() -> str:
    """Send current worker status to Master.

    Returns:
        Confirmation message
    """
    try:
        # Gather system info
        import psutil

        # Get intelligent progress summary
        progress_summary = await intelligence.summarize_progress_for_status(
            worker_state.get("current_task", {})
        )

        status_data = {
            "worker_id": WORKER_ID,
            "status": worker_state["status"],
            "current_task": worker_state["current_task"],
            "progress_summary": progress_summary,
            "uptime": (datetime.now() - datetime.fromisoformat(worker_state["start_time"])).total_seconds(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage(str(WORKING_DIR)).percent,
            "activity_count": len(worker_state["activity_log"])
        }

        await send_to_master("status_update", json.dumps(status_data), priority=3)

        worker_state["last_heartbeat"] = datetime.now().isoformat()
        log_activity("Sent status update to master")

        return "Status reported to master successfully"

    except Exception as e:
        error_msg = f"Failed to report status: {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


@mcp.tool()
def log_worker_activity(activity: str) -> str:
    """Log what the worker is currently doing.

    Args:
        activity: Description of current activity

    Returns:
        Confirmation message
    """
    log_activity(activity)
    return f"Activity logged: {activity}"


# === REPOSITORY AWARENESS ===

@mcp.tool()
async def get_my_branch() -> str:
    """Get the current Git branch name for this worker.

    Returns:
        Current branch name or error message
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=WORKING_DIR,
            capture_output=True,
            text=True,
            check=True
        )

        branch_name = result.stdout.strip()
        log_activity(f"Current branch: {branch_name}")

        return branch_name

    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to get branch name: {e.stderr}"
        log_activity(error_msg, "error")
        return error_msg
    except Exception as e:
        error_msg = f"Error getting branch: {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


@mcp.tool()
async def get_changed_files() -> str:
    """Get list of files modified in current working directory.

    Returns:
        JSON string with list of changed files
    """
    try:
        # Get git status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=WORKING_DIR,
            capture_output=True,
            text=True,
            check=True
        )

        changed_files = []
        for line in result.stdout.strip().split('\n'):
            if line:
                status_code = line[:2]
                filename = line[3:]
                changed_files.append({
                    "file": filename,
                    "status": status_code.strip(),
                    "type": "modified" if "M" in status_code else "added" if "A" in status_code else "deleted" if "D" in status_code else "unknown"
                })

        log_activity(f"Found {len(changed_files)} changed files")

        return json.dumps({
            "changed_files": changed_files,
            "count": len(changed_files)
        })

    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to get changed files: {e.stderr}"
        log_activity(error_msg, "error")
        return json.dumps({"error": error_msg, "changed_files": []})
    except Exception as e:
        error_msg = f"Error getting changed files: {str(e)}"
        log_activity(error_msg, "error")
        return json.dumps({"error": error_msg, "changed_files": []})


@mcp.tool()
async def commit_progress(message: str) -> str:
    """Commit current work with a progress message.

    Args:
        message: Commit message describing the progress

    Returns:
        Commit hash or error message
    """
    try:
        # Add all changes
        subprocess.run(
            ["git", "add", "."],
            cwd=WORKING_DIR,
            check=True
        )

        # Create commit
        commit_message = f"[{WORKER_ID}] {message}\n\nAuto-commit by worker {WORKER_ID}"

        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=WORKING_DIR,
            capture_output=True,
            text=True,
            check=True
        )

        # Get commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=WORKING_DIR,
            capture_output=True,
            text=True,
            check=True
        )

        commit_hash = hash_result.stdout.strip()

        log_activity(f"Committed progress: {commit_hash[:8]} - {message}")

        return f"Committed successfully: {commit_hash[:8]}"

    except subprocess.CalledProcessError as e:
        if "nothing to commit" in e.stderr:
            log_activity("No changes to commit")
            return "No changes to commit"
        else:
            error_msg = f"Failed to commit: {e.stderr}"
            log_activity(error_msg, "error")
            return error_msg
    except Exception as e:
        error_msg = f"Error committing: {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


# === INTELLIGENCE LAYER TOOLS ===

@mcp.tool()
async def should_ask_master_decision(
    question_type: str,
    estimated_token_cost: int,
    confidence_level: float,
    context: Optional[str] = None
) -> str:
    """
    Intelligent decision on whether to ask Master or solve independently.

    Args:
        question_type: Type of question (architecture, implementation, debugging, etc.)
        estimated_token_cost: Estimated tokens needed to solve independently
        confidence_level: Confidence in ability to solve (0.0-1.0)
        context: Optional JSON context string

    Returns:
        JSON with decision and reasoning
    """
    try:
        context_dict = {}
        if context:
            try:
                context_dict = json.loads(context)
            except json.JSONDecodeError:
                context_dict = {"context": context}

        should_ask, reason = intelligence.should_ask_master(
            question_type=question_type,
            estimated_token_cost=estimated_token_cost,
            confidence_level=confidence_level,
            context=context_dict
        )

        decision = {
            "should_ask_master": should_ask,
            "reason": reason,
            "question_type": question_type,
            "token_cost": estimated_token_cost,
            "confidence": confidence_level,
            "timestamp": datetime.now().isoformat()
        }

        log_activity(f"Decision: {'Ask Master' if should_ask else 'Solve independently'} - {reason}")

        return json.dumps(decision)

    except Exception as e:
        error_msg = f"Failed to make decision: {str(e)}"
        log_activity(error_msg, "error")
        return json.dumps({"error": error_msg, "should_ask_master": True, "reason": "Error in decision logic"})


@mcp.tool()
async def auto_save_context_check(context_content: str, context_key: str) -> str:
    """
    Check if context should be auto-saved and save if needed.

    Args:
        context_content: Current conversation/context content
        context_key: Key to save context under

    Returns:
        Status of auto-save operation
    """
    try:
        was_saved = await intelligence.auto_save_context_if_needed(context_content, context_key)

        if was_saved:
            log_activity(f"Auto-saved context: {context_key}")
            return f"Context '{context_key}' auto-saved due to length"
        else:
            return f"Context '{context_key}' within limits, not saved"

    except Exception as e:
        error_msg = f"Failed to check/save context: {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


@mcp.tool()
async def load_relevant_context_for_task(task_context: str) -> str:
    """
    Load relevant context from memory based on current task.

    Args:
        task_context: JSON string with task description and context

    Returns:
        JSON with relevant contexts found
    """
    try:
        # Parse task context
        try:
            task_dict = json.loads(task_context)
        except json.JSONDecodeError:
            task_dict = {"description": task_context}

        relevant_contexts = await intelligence.load_relevant_context(task_dict)

        log_activity(f"Loaded {len(relevant_contexts)} relevant contexts")

        return json.dumps({
            "relevant_contexts": relevant_contexts,
            "count": len(relevant_contexts)
        })

    except Exception as e:
        error_msg = f"Failed to load relevant context: {str(e)}"
        log_activity(error_msg, "error")
        return json.dumps({"error": error_msg, "relevant_contexts": {}})


@mcp.tool()
async def attempt_error_recovery(error_message: str, error_type: str, error_context: str) -> str:
    """
    Attempt to recover from an error independently before asking Master.

    Args:
        error_message: The error message
        error_type: Type of error (syntax, import, logic, test, etc.)
        error_context: JSON context about the error (file, line, etc.)

    Returns:
        JSON with recovery attempt result
    """
    try:
        # Parse error context
        try:
            context_dict = json.loads(error_context)
        except json.JSONDecodeError:
            context_dict = {"context": error_context}

        recovered, action_taken, suggested_fix = await intelligence.attempt_error_recovery(
            error=error_message,
            error_type=error_type,
            context=context_dict
        )

        result = {
            "recovered": recovered,
            "action_taken": action_taken,
            "suggested_fix": suggested_fix,
            "error_type": error_type,
            "timestamp": datetime.now().isoformat()
        }

        if recovered:
            log_activity(f"Error recovery successful: {action_taken}")
        else:
            log_activity(f"Error recovery failed: {action_taken}")

        return json.dumps(result)

    except Exception as e:
        error_msg = f"Failed error recovery attempt: {str(e)}"
        log_activity(error_msg, "error")
        return json.dumps({
            "recovered": False,
            "action_taken": f"Recovery failed: {error_msg}",
            "suggested_fix": "Ask Master for help",
            "error": error_msg
        })


@mcp.tool()
async def check_collaboration_conflicts(files_to_modify: str) -> str:
    """
    Check for potential merge conflicts with other workers before committing.

    Args:
        files_to_modify: JSON array of file paths to check

    Returns:
        JSON with conflict analysis
    """
    try:
        # Parse file list
        try:
            file_list = json.loads(files_to_modify)
        except json.JSONDecodeError:
            file_list = [files_to_modify]

        conflicts = await intelligence.check_for_conflicts(file_list)

        if conflicts:
            log_activity(f"Found {len(conflicts)} potential conflicts")
            # Alert Master if high-risk conflicts
            high_risk_conflicts = [c for c in conflicts if c.get("risk_level") == "high"]
            if high_risk_conflicts:
                await send_to_master("resource_request", json.dumps({
                    "resource_type": "conflict_resolution",
                    "conflicts": high_risk_conflicts,
                    "files": file_list,
                    "urgency": "high"
                }), priority=7)
        else:
            log_activity("No collaboration conflicts detected")

        return json.dumps({
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "safe_to_commit": len(conflicts) == 0
        })

    except Exception as e:
        error_msg = f"Failed to check conflicts: {str(e)}"
        log_activity(error_msg, "error")
        return json.dumps({"error": error_msg, "conflicts": [], "safe_to_commit": False})


@mcp.tool()
async def update_my_work_area(file_path: str, activity_type: str) -> str:
    """
    Update which files/areas this worker is actively working on.

    Args:
        file_path: File being worked on
        activity_type: Type of activity (editing, testing, debugging, etc.)

    Returns:
        Confirmation message
    """
    try:
        await intelligence.update_worker_area(file_path, activity_type)
        log_activity(f"Updated work area: {file_path} ({activity_type})")
        return f"Work area updated: {file_path} - {activity_type}"

    except Exception as e:
        error_msg = f"Failed to update work area: {str(e)}"
        log_activity(error_msg, "error")
        return error_msg


@mcp.tool()
async def get_collaboration_status() -> str:
    """
    Get current collaboration status and potential conflicts.

    Returns:
        JSON with collaboration information
    """
    try:
        status = await intelligence.get_collaboration_status()
        log_activity("Retrieved collaboration status")
        return json.dumps(status)

    except Exception as e:
        error_msg = f"Failed to get collaboration status: {str(e)}"
        log_activity(error_msg, "error")
        return json.dumps({"error": error_msg})


@mcp.tool()
async def smart_progress_summary() -> str:
    """
    Generate intelligent progress summary for status reports.

    Returns:
        Concise progress summary
    """
    try:
        current_task = worker_state.get("current_task", {})
        if not current_task:
            return "No active task"

        summary = await intelligence.summarize_progress_for_status(current_task)
        log_activity(f"Generated progress summary")
        return summary

    except Exception as e:
        error_msg = f"Failed to generate progress summary: {str(e)}"
        log_activity(error_msg, "error")
        return f"Progress summary error: {error_msg}"


# === STARTUP AND HEARTBEAT ===

async def register_with_master():
    """Register this worker with the Master on startup."""
    try:
        registration_data = {
            "worker_id": WORKER_ID,
            "model": WORKER_MODEL,
            "working_dir": str(WORKING_DIR),
            "memory_dir": str(MEMORY_DIR),
            "capabilities": [
                "communication", "memory_management", "task_execution",
                "repository_awareness", "status_reporting", "intelligent_decisions",
                "error_recovery", "collaboration_awareness", "context_management"
            ],
            "startup_time": worker_state["start_time"]
        }

        await send_to_master("status_update", json.dumps(registration_data), priority=5)
        worker_state["status"] = "active"

        log_activity("Registered with master successfully")

    except Exception as e:
        log_activity(f"Failed to register with master: {str(e)}", "error")


async def send_heartbeat():
    """Send periodic heartbeat to Master."""
    while True:
        try:
            await asyncio.sleep(30)  # Send every 30 seconds

            heartbeat_data = {
                "worker_id": WORKER_ID,
                "status": worker_state["status"],
                "timestamp": datetime.now().isoformat(),
                "current_task": worker_state["current_task"]["task_id"] if worker_state["current_task"] else None
            }

            await message_queue.send_message(
                from_id=WORKER_ID,
                to_id="master",
                message_type="heartbeat",
                content=heartbeat_data,
                priority=1
            )

            worker_state["last_heartbeat"] = datetime.now().isoformat()

        except Exception as e:
            log_activity(f"Heartbeat failed: {str(e)}", "error")


async def startup_initialization():
    """Initialize worker on startup."""
    log_activity(f"Worker {WORKER_ID} starting up with model {WORKER_MODEL}")

    # Register with master
    await register_with_master()

    # Start heartbeat
    asyncio.create_task(send_heartbeat())

    log_activity("Worker initialization completed")


# Add startup hook
@mcp.on_startup
async def on_startup():
    """Called when MCP server starts."""
    await startup_initialization()


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()