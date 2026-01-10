#!/usr/bin/env python3
"""
Worker Intelligence Layer
Adds intelligent decision-making, context management, error recovery,
and collaboration awareness to Worker MCP servers.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import sqlite3

logger = logging.getLogger(__name__)


class WorkerIntelligence:
    """Intelligence layer for Worker MCP servers."""

    def __init__(self, worker_id: str, memory_dir: Path, working_dir: Path, message_queue):
        self.worker_id = worker_id
        self.memory_dir = memory_dir
        self.working_dir = working_dir
        self.message_queue = message_queue

        # Intelligence state
        self.collaboration_db = memory_dir / "collaboration.db"
        self.conversation_threshold = 8000  # tokens
        self.error_attempts = {}  # Track error recovery attempts
        self.worker_areas = {}  # Track which workers work on which areas

        # Initialize collaboration database
        self._init_collaboration_db()

    def _init_collaboration_db(self):
        """Initialize SQLite database for collaboration tracking."""
        try:
            with sqlite3.connect(self.collaboration_db) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS worker_areas (
                        worker_id TEXT,
                        file_path TEXT,
                        module_name TEXT,
                        last_activity TEXT,
                        activity_type TEXT,
                        PRIMARY KEY (worker_id, file_path)
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conflict_warnings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT,
                        conflicting_workers TEXT,
                        warning_type TEXT,
                        created_at TEXT,
                        resolved INTEGER DEFAULT 0
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        context_key TEXT UNIQUE,
                        summary TEXT,
                        token_count INTEGER,
                        created_at TEXT,
                        last_updated TEXT
                    )
                """)
        except Exception as e:
            logger.error(f"Failed to initialize collaboration DB: {e}")

    def should_ask_master(
        self,
        question_type: str,
        estimated_token_cost: int,
        confidence_level: float,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Determine when to ask Master vs. figure it out independently.

        Args:
            question_type: Type of question (architecture, implementation, debugging, etc.)
            estimated_token_cost: Estimated tokens needed to solve independently
            confidence_level: Confidence in ability to solve (0.0-1.0)
            context: Additional context for decision

        Returns:
            Tuple of (should_ask, reason)
        """
        context = context or {}

        # Always ask for high-cost problems
        if estimated_token_cost > 5000:
            return True, f"High token cost ({estimated_token_cost}) - asking Master to save resources"

        # Always ask for low confidence
        if confidence_level < 0.6:
            return True, f"Low confidence ({confidence_level:.1%}) - asking Master for guidance"

        # Question type specific logic
        ask_master_types = {
            "overall_architecture": "Architecture decisions should be coordinated with Master",
            "design_patterns": "Design patterns affect other workers - asking Master",
            "inter_worker_coordination": "Cross-worker coordination requires Master involvement",
            "security_policy": "Security decisions require Master approval",
            "performance_optimization": "Performance decisions may affect other components",
            "database_schema": "Database changes affect multiple workers",
            "api_design": "API design affects other workers and clients",
            "deployment_strategy": "Deployment affects entire system"
        }

        if question_type in ask_master_types:
            return True, ask_master_types[question_type]

        # Check if question involves other workers' areas
        current_file = context.get("current_file", "")
        if current_file and self._is_other_workers_area(current_file):
            return True, f"File {current_file} is in another worker's area"

        # Check if this is about shared/common modules
        shared_indicators = ["common", "shared", "utils", "config", "constants", "base"]
        if any(indicator in current_file.lower() for indicator in shared_indicators):
            return True, f"Working on shared module - coordinating with Master"

        # Independent work types (don't ask)
        independent_types = {
            "implementation_detail": "Implementation details can be decided independently",
            "local_debugging": "Local debugging should be attempted first",
            "code_formatting": "Code formatting is worker's responsibility",
            "local_testing": "Local testing should be done independently",
            "documentation": "Documentation can be written independently",
            "refactoring": "Local refactoring can be done independently"
        }

        if question_type in independent_types:
            return False, independent_types[question_type]

        # Default: if uncertain and low cost, try independently first
        if estimated_token_cost < 1000 and confidence_level > 0.4:
            return False, "Low cost and reasonable confidence - attempting independently"

        # When in doubt, ask
        return True, "Uncertain situation - asking Master for guidance"

    async def auto_save_context_if_needed(self, current_context: str, context_key: str) -> bool:
        """
        Automatically save context to memory if conversation is getting long.

        Args:
            current_context: Current conversation/context content
            context_key: Key to save context under

        Returns:
            True if context was saved, False otherwise
        """
        try:
            # Estimate token count (rough: 1 token ≈ 4 characters)
            estimated_tokens = len(current_context) // 4

            if estimated_tokens > self.conversation_threshold:
                # Create summary
                summary = await self._summarize_context(current_context)

                # Save to database
                with sqlite3.connect(self.collaboration_db) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO conversation_summaries
                        (context_key, summary, token_count, created_at, last_updated)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        context_key,
                        summary,
                        estimated_tokens,
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    ))

                # Save full context to file
                context_file = self.memory_dir / f"context_{context_key}.json"
                context_data = {
                    "key": context_key,
                    "full_context": current_context,
                    "summary": summary,
                    "token_count": estimated_tokens,
                    "saved_at": datetime.now().isoformat(),
                    "worker_id": self.worker_id
                }

                with open(context_file, "w") as f:
                    json.dump(context_data, f, indent=2)

                logger.info(f"Auto-saved context '{context_key}' ({estimated_tokens} tokens)")
                return True

        except Exception as e:
            logger.error(f"Failed to auto-save context: {e}")

        return False

    async def _summarize_context(self, context: str) -> str:
        """Create a summary of the context to save space."""
        try:
            # Simple summarization - extract key points
            lines = context.split('\n')
            key_lines = []

            # Look for important patterns
            important_patterns = [
                r'(class|function|def)\s+\w+',  # Code definitions
                r'(TODO|FIXME|NOTE|IMPORTANT):',  # Special comments
                r'(Error|Exception|Failed):',  # Errors
                r'(Implementing|Creating|Building):',  # Actions
                r'(Decision|Conclusion|Result):',  # Decisions
            ]

            for line in lines:
                line = line.strip()
                if any(re.search(pattern, line, re.IGNORECASE) for pattern in important_patterns):
                    key_lines.append(line)

            # If no patterns found, take first and last parts
            if not key_lines:
                total_lines = len(lines)
                key_lines = lines[:5] + ['...'] + lines[-5:] if total_lines > 15 else lines

            return '\n'.join(key_lines[:50])  # Limit to 50 lines

        except Exception as e:
            logger.error(f"Failed to summarize context: {e}")
            return context[:1000] + "..." if len(context) > 1000 else context

    async def load_relevant_context(self, task_context: Dict[str, Any]) -> Dict[str, Any]:
        """Load relevant context from memory based on current task."""
        try:
            relevant_contexts = {}

            # Extract keywords from task
            task_description = task_context.get("description", "")
            current_files = task_context.get("files", [])

            # Search saved contexts for relevant ones
            with sqlite3.connect(self.collaboration_db) as conn:
                cursor = conn.execute("""
                    SELECT context_key, summary, token_count
                    FROM conversation_summaries
                    ORDER BY last_updated DESC
                    LIMIT 10
                """)

                for row in cursor.fetchall():
                    context_key, summary, token_count = row

                    # Check if context is relevant
                    if self._is_context_relevant(summary, task_description, current_files):
                        # Load full context
                        context_file = self.memory_dir / f"context_{context_key}.json"
                        if context_file.exists():
                            with open(context_file) as f:
                                context_data = json.load(f)
                                relevant_contexts[context_key] = context_data

            return relevant_contexts

        except Exception as e:
            logger.error(f"Failed to load relevant context: {e}")
            return {}

    def _is_context_relevant(
        self,
        summary: str,
        task_description: str,
        current_files: List[str]
    ) -> bool:
        """Check if a saved context is relevant to current task."""
        # Simple keyword matching
        task_words = set(re.findall(r'\w+', task_description.lower()))
        summary_words = set(re.findall(r'\w+', summary.lower()))

        # Check for file name matches
        for file_path in current_files:
            if Path(file_path).name.lower() in summary.lower():
                return True

        # Check for keyword overlap
        overlap = len(task_words.intersection(summary_words))
        relevance_threshold = max(3, len(task_words) * 0.2)

        return overlap >= relevance_threshold

    async def attempt_error_recovery(
        self,
        error: str,
        error_type: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Attempt to recover from an error independently.

        Args:
            error: Error message
            error_type: Type of error (syntax, import, logic, etc.)
            context: Error context (file, line, etc.)

        Returns:
            Tuple of (recovered, action_taken, suggested_fix)
        """
        error_key = f"{error_type}_{hash(error)}"

        # Track attempt count
        if error_key not in self.error_attempts:
            self.error_attempts[error_key] = 0

        self.error_attempts[error_key] += 1

        # Give up after 2 attempts
        if self.error_attempts[error_key] > 2:
            return False, "Max attempts reached", "Ask Master for help"

        try:
            # Error-specific recovery strategies
            if error_type == "import_error":
                return await self._recover_import_error(error, context)
            elif error_type == "syntax_error":
                return await self._recover_syntax_error(error, context)
            elif error_type == "test_failure":
                return await self._recover_test_failure(error, context)
            elif error_type == "dependency_error":
                return await self._recover_dependency_error(error, context)
            else:
                return await self._generic_error_recovery(error, context)

        except Exception as e:
            logger.error(f"Error recovery failed: {e}")
            return False, f"Recovery attempt failed: {e}", "Ask Master for help"

    async def _recover_import_error(self, error: str, context: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """Attempt to recover from import errors."""
        # Extract module name from error
        import_match = re.search(r"No module named '([^']+)'", error)
        if not import_match:
            return False, "Could not extract module name", None

        module_name = import_match.group(1)

        # Check if it's a local module that needs to be created
        if "." in module_name or module_name in ["utils", "config", "constants"]:
            return False, f"Local module '{module_name}' missing", f"Create missing module {module_name}"

        # Check if it's a standard library module with typo
        stdlib_suggestions = {
            "datetime": ["datatime", "date_time"],
            "pathlib": ["path_lib", "patlib"],
            "subprocess": ["sub_process", "subproc"],
            "json": ["JSON", "jsn"],
        }

        for correct, typos in stdlib_suggestions.items():
            if module_name in typos:
                return True, f"Fixed typo: {module_name} -> {correct}", f"import {correct}"

        return False, f"Unknown module: {module_name}", f"Install or create module {module_name}"

    async def _recover_syntax_error(self, error: str, context: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """Attempt to recover from syntax errors."""
        file_path = context.get("file")
        if not file_path:
            return False, "No file path in context", None

        # Common syntax error patterns and fixes
        if "expected ':'" in error:
            return True, "Missing colon - likely in if/for/def statement", "Add missing colon"
        elif "invalid syntax" in error and "f'" in error:
            return True, "F-string syntax error", "Check f-string formatting"
        elif "unmatched ')'" in error:
            return True, "Unmatched parentheses", "Check parentheses matching"
        elif "IndentationError" in error:
            return True, "Indentation error", "Fix indentation (use 4 spaces)"

        return False, "Unknown syntax error", "Check syntax carefully"

    async def _recover_test_failure(self, error: str, context: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """Attempt to recover from test failures."""
        if "AssertionError" in error:
            return False, "Test assertion failed", "Review test expectations vs actual output"
        elif "ModuleNotFoundError" in error:
            return await self._recover_import_error(error, context)
        elif "AttributeError" in error:
            return False, "Attribute error in test", "Check object attributes and method names"

        return False, "Test failure", "Debug test case"

    async def _recover_dependency_error(self, error: str, context: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """Attempt to recover from dependency errors."""
        if "version conflict" in error.lower():
            return False, "Version conflict", "Ask Master about dependency resolution"
        elif "not found" in error.lower():
            return False, "Dependency not found", "Check if dependency needs to be installed"

        return False, "Dependency error", "Review requirements and dependencies"

    async def _generic_error_recovery(self, error: str, context: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """Generic error recovery strategies."""
        # Simple heuristics for common issues
        if "permission denied" in error.lower():
            return False, "Permission error", "Check file permissions"
        elif "file not found" in error.lower():
            return False, "File not found", "Check file path exists"
        elif "connection" in error.lower():
            return False, "Connection error", "Check network/database connectivity"

        return False, "Unknown error", "Manual investigation needed"

    async def update_worker_area(self, file_path: str, activity_type: str):
        """Update which areas this worker is working on."""
        try:
            with sqlite3.connect(self.collaboration_db) as conn:
                # Extract module name from file path
                module_name = Path(file_path).stem

                conn.execute("""
                    INSERT OR REPLACE INTO worker_areas
                    (worker_id, file_path, module_name, last_activity, activity_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    self.worker_id,
                    file_path,
                    module_name,
                    datetime.now().isoformat(),
                    activity_type
                ))

        except Exception as e:
            logger.error(f"Failed to update worker area: {e}")

    def _is_other_workers_area(self, file_path: str) -> bool:
        """Check if file is in another worker's area."""
        try:
            with sqlite3.connect(self.collaboration_db) as conn:
                cursor = conn.execute("""
                    SELECT worker_id, last_activity
                    FROM worker_areas
                    WHERE file_path = ? AND worker_id != ?
                    ORDER BY last_activity DESC
                    LIMIT 1
                """, (file_path, self.worker_id))

                row = cursor.fetchone()
                if row:
                    worker_id, last_activity = row
                    # Consider it another worker's area if they worked on it in last 24 hours
                    last_activity_time = datetime.fromisoformat(last_activity)
                    if datetime.now() - last_activity_time < timedelta(hours=24):
                        return True

        except Exception as e:
            logger.error(f"Failed to check worker areas: {e}")

        return False

    async def check_for_conflicts(self, files_to_modify: List[str]) -> List[Dict[str, Any]]:
        """Check for potential merge conflicts before committing."""
        conflicts = []

        try:
            for file_path in files_to_modify:
                # Check if other workers recently modified this file
                with sqlite3.connect(self.collaboration_db) as conn:
                    cursor = conn.execute("""
                        SELECT worker_id, last_activity, activity_type
                        FROM worker_areas
                        WHERE file_path = ? AND worker_id != ?
                        AND last_activity > ?
                        ORDER BY last_activity DESC
                    """, (
                        file_path,
                        self.worker_id,
                        (datetime.now() - timedelta(hours=2)).isoformat()
                    ))

                    conflicting_workers = cursor.fetchall()
                    if conflicting_workers:
                        conflicts.append({
                            "file": file_path,
                            "conflicting_workers": [w[0] for w in conflicting_workers],
                            "last_activities": [w[1] for w in conflicting_workers],
                            "risk_level": "high" if len(conflicting_workers) > 1 else "medium"
                        })

                        # Log the warning
                        conn.execute("""
                            INSERT INTO conflict_warnings
                            (file_path, conflicting_workers, warning_type, created_at)
                            VALUES (?, ?, ?, ?)
                        """, (
                            file_path,
                            json.dumps([w[0] for w in conflicting_workers]),
                            "potential_merge_conflict",
                            datetime.now().isoformat()
                        ))

        except Exception as e:
            logger.error(f"Failed to check for conflicts: {e}")

        return conflicts

    async def get_collaboration_status(self) -> Dict[str, Any]:
        """Get current collaboration status and potential issues."""
        try:
            with sqlite3.connect(self.collaboration_db) as conn:
                # Get active worker areas
                cursor = conn.execute("""
                    SELECT worker_id, COUNT(*) as file_count, MAX(last_activity) as last_activity
                    FROM worker_areas
                    WHERE last_activity > ?
                    GROUP BY worker_id
                    ORDER BY last_activity DESC
                """, ((datetime.now() - timedelta(hours=24)).isoformat(),))

                active_workers = [
                    {
                        "worker_id": row[0],
                        "active_files": row[1],
                        "last_activity": row[2]
                    }
                    for row in cursor.fetchall()
                ]

                # Get recent conflicts
                cursor = conn.execute("""
                    SELECT file_path, conflicting_workers, created_at
                    FROM conflict_warnings
                    WHERE created_at > ? AND resolved = 0
                    ORDER BY created_at DESC
                    LIMIT 10
                """, ((datetime.now() - timedelta(hours=24)).isoformat(),))

                recent_conflicts = [
                    {
                        "file": row[0],
                        "workers": json.loads(row[1]),
                        "when": row[2]
                    }
                    for row in cursor.fetchall()
                ]

                return {
                    "active_workers": active_workers,
                    "recent_conflicts": recent_conflicts,
                    "my_areas": await self._get_my_active_areas()
                }

        except Exception as e:
            logger.error(f"Failed to get collaboration status: {e}")
            return {"error": str(e)}

    async def _get_my_active_areas(self) -> List[Dict[str, Any]]:
        """Get areas this worker is currently active in."""
        try:
            with sqlite3.connect(self.collaboration_db) as conn:
                cursor = conn.execute("""
                    SELECT file_path, module_name, last_activity, activity_type
                    FROM worker_areas
                    WHERE worker_id = ? AND last_activity > ?
                    ORDER BY last_activity DESC
                """, (
                    self.worker_id,
                    (datetime.now() - timedelta(hours=24)).isoformat()
                ))

                return [
                    {
                        "file": row[0],
                        "module": row[1],
                        "last_activity": row[2],
                        "activity": row[3]
                    }
                    for row in cursor.fetchall()
                ]

        except Exception as e:
            logger.error(f"Failed to get my active areas: {e}")
            return []

    async def summarize_progress_for_status(self, current_task: Dict[str, Any]) -> str:
        """Create a concise progress summary for status reports."""
        try:
            task_id = current_task.get("task_id", "unknown")
            progress = current_task.get("progress", 0)

            # Get recent activities
            recent_activities = []
            log_file = self.memory_dir / "activity.log"

            if log_file.exists():
                with open(log_file) as f:
                    lines = f.readlines()
                    # Get last 5 activities
                    recent_activities = [line.strip() for line in lines[-5:]]

            # Get changed files
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=self.working_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                changed_files = len([line for line in result.stdout.strip().split('\n') if line])
            except:
                changed_files = 0

            # Create summary
            summary_parts = [
                f"Task {task_id}: {progress}% complete",
                f"{changed_files} files modified"
            ]

            if recent_activities:
                summary_parts.append(f"Recent: {recent_activities[-1]}")

            return " | ".join(summary_parts)

        except Exception as e:
            logger.error(f"Failed to summarize progress: {e}")
            return f"Task in progress (error creating summary: {e})"