#!/usr/bin/env python3
"""
Memory Management System
Sophisticated memory management for worker context and knowledge persistence.
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """Individual memory entry with metadata."""
    id: str
    timestamp: datetime
    content: str
    content_type: str  # "context", "understanding", "decision", "question", "task"
    tags: List[str]
    relevance_score: float = 0.0
    module_name: Optional[str] = None
    task_id: Optional[str] = None


@dataclass
class ContextSummary:
    """Summary of conversation context."""
    summary: str
    key_points: List[str]
    decisions_made: List[str]
    questions_raised: List[str]
    code_areas_touched: List[str]
    token_count: int
    created_at: datetime


@dataclass
class CodeUnderstanding:
    """Understanding of specific code modules."""
    module_name: str
    file_path: str
    purpose: str
    key_functions: List[str]
    dependencies: List[str]
    complexity_level: str
    notes: str
    last_updated: datetime


@dataclass
class TaskRecord:
    """Record of completed task."""
    task_id: str
    description: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    files_modified: List[str]
    decisions_made: List[str]
    challenges_faced: List[str]
    solutions_implemented: List[str]
    context_at_completion: str


class MemorySearcher:
    """Semantic search across memory files."""

    def __init__(self):
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can'
        }

    def calculate_relevance_score(self, query: str, content: str, metadata: Dict[str, Any]) -> float:
        """Calculate relevance score for search query."""
        score = 0.0

        # Tokenize query and content
        query_tokens = self._tokenize(query.lower())
        content_tokens = self._tokenize(content.lower())

        # Exact phrase matching (high weight)
        if query.lower() in content.lower():
            score += 10.0

        # Token overlap scoring
        query_set = set(query_tokens)
        content_set = set(content_tokens)

        if query_set:
            overlap_ratio = len(query_set & content_set) / len(query_set)
            score += overlap_ratio * 5.0

        # Recent content gets higher score
        if 'timestamp' in metadata:
            timestamp = metadata['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

            days_old = (datetime.now() - timestamp).days
            recency_score = max(0, 2.0 - (days_old / 30))  # Decay over 30 days
            score += recency_score

        # Module/file relevance
        if 'module_name' in metadata and metadata['module_name']:
            for token in query_tokens:
                if token in metadata['module_name'].lower():
                    score += 1.0

        # Tag relevance
        if 'tags' in metadata:
            for tag in metadata['tags']:
                for token in query_tokens:
                    if token in tag.lower():
                        score += 1.0

        return score

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for search."""
        # Simple tokenization - can be enhanced with NLP libraries
        tokens = re.findall(r'\w+', text.lower())
        return [token for token in tokens if token not in self.stop_words and len(token) > 2]

    async def search_memories(self, query: str, memories: List[MemoryEntry], limit: int = 10) -> List[MemoryEntry]:
        """Search memories and return ranked results."""
        scored_memories = []

        for memory in memories:
            metadata = {
                'timestamp': memory.timestamp,
                'module_name': memory.module_name,
                'tags': memory.tags
            }

            score = self.calculate_relevance_score(query, memory.content, metadata)
            memory.relevance_score = score
            scored_memories.append(memory)

        # Sort by relevance score and return top results
        scored_memories.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_memories[:limit]


class ContextManager:
    """Manages conversation context and token limits."""

    def __init__(self, max_active_tokens: int = 20000, save_threshold: int = 50000):
        self.max_active_tokens = max_active_tokens
        self.save_threshold = save_threshold
        self.current_token_count = 0
        self.conversation_history = []

    def add_to_context(self, content: str, token_count: int):
        """Add content to current context."""
        self.conversation_history.append({
            'content': content,
            'token_count': token_count,
            'timestamp': datetime.now()
        })
        self.current_token_count += token_count

    def should_save_context(self) -> bool:
        """Check if context should be saved."""
        return self.current_token_count >= self.save_threshold

    def create_context_summary(self) -> ContextSummary:
        """Create summary of current conversation context."""
        all_content = '\n'.join([item['content'] for item in self.conversation_history])

        # Extract key information
        key_points = self._extract_key_points(all_content)
        decisions_made = self._extract_decisions(all_content)
        questions_raised = self._extract_questions(all_content)
        code_areas_touched = self._extract_code_areas(all_content)

        # Generate summary
        summary = self._generate_summary(all_content, key_points)

        return ContextSummary(
            summary=summary,
            key_points=key_points,
            decisions_made=decisions_made,
            questions_raised=questions_raised,
            code_areas_touched=code_areas_touched,
            token_count=self.current_token_count,
            created_at=datetime.now()
        )

    def trim_context(self) -> List[Dict[str, Any]]:
        """Trim context to keep only recent tokens."""
        trimmed_history = []
        current_tokens = 0

        # Keep most recent entries within token limit
        for item in reversed(self.conversation_history):
            if current_tokens + item['token_count'] <= self.max_active_tokens:
                trimmed_history.insert(0, item)
                current_tokens += item['token_count']
            else:
                break

        removed_history = self.conversation_history[:-len(trimmed_history)] if trimmed_history else self.conversation_history
        self.conversation_history = trimmed_history
        self.current_token_count = current_tokens

        return removed_history

    def _extract_key_points(self, content: str) -> List[str]:
        """Extract key points from conversation."""
        # Simple extraction - can be enhanced with NLP
        key_patterns = [
            r'(?:Key point|Important|Note that|Remember|Conclusion): (.+)',
            r'(?:Decision|Decided|Chose): (.+)',
            r'(?:Problem|Issue|Bug): (.+)',
            r'(?:Solution|Fix|Resolved): (.+)'
        ]

        key_points = []
        for pattern in key_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            key_points.extend(matches)

        return key_points[:10]  # Limit to top 10

    def _extract_decisions(self, content: str) -> List[str]:
        """Extract architectural decisions."""
        decision_patterns = [
            r'(?:Decided to|Decision:|We will|Let\'s use|I\'ll implement): (.+)',
            r'(?:Architecture|Design|Pattern): (.+)',
        ]

        decisions = []
        for pattern in decision_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            decisions.extend(matches)

        return decisions[:5]

    def _extract_questions(self, content: str) -> List[str]:
        """Extract questions asked."""
        questions = re.findall(r'[.!]?\s*([A-Z][^.!?]*\?)', content)
        return questions[:5]

    def _extract_code_areas(self, content: str) -> List[str]:
        """Extract code areas/modules mentioned."""
        code_patterns = [
            r'(?:file|module|class|function|method):\s*([a-zA-Z_][a-zA-Z0-9_./]*)',
            r'`([a-zA-Z_][a-zA-Z0-9_./]*\.py)`',
            r'src/([a-zA-Z0-9_/]+)',
            r'([a-zA-Z_][a-zA-Z0-9_]*\.py)',
        ]

        areas = set()
        for pattern in code_patterns:
            matches = re.findall(pattern, content)
            areas.update(matches)

        return list(areas)[:10]

    def _generate_summary(self, content: str, key_points: List[str]) -> str:
        """Generate concise summary of conversation."""
        # Extract first and last parts of conversation
        lines = content.split('\n')
        total_lines = len(lines)

        # Take first 10% and last 10% of conversation
        start_lines = lines[:max(1, total_lines // 10)]
        end_lines = lines[-max(1, total_lines // 10):]

        summary_parts = []

        if start_lines:
            summary_parts.append("Started with: " + ' '.join(start_lines)[:200])

        if key_points:
            summary_parts.append("Key points: " + '; '.join(key_points[:3]))

        if end_lines:
            summary_parts.append("Ended with: " + ' '.join(end_lines)[:200])

        return '\n\n'.join(summary_parts)


class WorkerMemoryManager:
    """Main memory management system for workers."""

    def __init__(self, worker_id: str, workspace_path: str = "/workspace"):
        self.worker_id = worker_id
        self.workspace_path = Path(workspace_path)
        self.memory_path = self.workspace_path / "workers" / worker_id / "memory"
        self.context_manager = ContextManager()
        self.searcher = MemorySearcher()

        # Memory file paths
        self.current_context_file = self.memory_path / "current_context.md"
        self.task_history_file = self.memory_path / "task_history.json"
        self.code_understanding_file = self.memory_path / "code_understanding.md"
        self.decisions_file = self.memory_path / "decisions_made.md"
        self.questions_file = self.memory_path / "questions_asked.md"

        # Ensure memory directory exists
        self.memory_path.mkdir(parents=True, exist_ok=True)

        # Initialize memory files if they don't exist
        self._initialize_memory_files()

    def _initialize_memory_files(self):
        """Initialize memory files if they don't exist."""
        if not self.current_context_file.exists():
            self.current_context_file.write_text("# Current Context\n\nNo active context.\n")

        if not self.task_history_file.exists():
            self.task_history_file.write_text("[]")

        if not self.code_understanding_file.exists():
            self.code_understanding_file.write_text("# Code Understanding\n\n")

        if not self.decisions_file.exists():
            self.decisions_file.write_text("# Architectural Decisions\n\n")

        if not self.questions_file.exists():
            self.questions_file.write_text("# Questions Asked\n\n")

    async def save_current_context(self) -> Dict[str, Any]:
        """Save current conversation context and clear active memory."""
        try:
            # Create context summary
            summary = self.context_manager.create_context_summary()

            # Format as markdown
            context_md = self._format_context_summary(summary)

            # Save to file with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_file = self.memory_path / f"context_archive_{timestamp}.md"
            archive_file.write_text(context_md)

            # Update current context file
            self.current_context_file.write_text(f"# Current Context\n\nLast saved: {datetime.now().isoformat()}\n\n{summary.summary}")

            # Trim conversation history
            removed_history = self.context_manager.trim_context()

            logger.info(f"Saved context for worker {self.worker_id}: {summary.token_count} tokens archived")

            return {
                "status": "success",
                "tokens_saved": summary.token_count,
                "tokens_remaining": self.context_manager.current_token_count,
                "archive_file": str(archive_file),
                "key_points": len(summary.key_points),
                "decisions_made": len(summary.decisions_made)
            }

        except Exception as e:
            logger.error(f"Error saving context for worker {self.worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def load_context(self, task_description: str = "", max_entries: int = 5) -> Dict[str, Any]:
        """Load relevant context based on current task."""
        try:
            relevant_context = []

            # Load current context
            if self.current_context_file.exists():
                current_context = self.current_context_file.read_text()
                relevant_context.append({
                    "type": "current_context",
                    "content": current_context,
                    "relevance": 10.0  # Always highly relevant
                })

            # Search archived contexts if task description provided
            if task_description:
                archived_contexts = await self._search_archived_contexts(task_description, max_entries)
                relevant_context.extend(archived_contexts)

            # Load relevant code understanding
            code_understanding = await self._load_relevant_code_understanding(task_description)
            if code_understanding:
                relevant_context.extend(code_understanding)

            # Load recent decisions
            recent_decisions = await self._load_recent_decisions(max_entries)
            if recent_decisions:
                relevant_context.extend(recent_decisions)

            # Sort by relevance
            relevant_context.sort(key=lambda x: x.get("relevance", 0), reverse=True)

            # Prepare response
            total_tokens = sum(len(item["content"].split()) * 1.3 for item in relevant_context)  # Rough token estimate

            return {
                "status": "success",
                "context_entries": relevant_context[:max_entries],
                "total_entries": len(relevant_context),
                "estimated_tokens": int(total_tokens),
                "loaded_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error loading context for worker {self.worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def update_understanding(self, module_name: str, understanding: str, file_path: str = "") -> Dict[str, Any]:
        """Update understanding of specific code modules."""
        try:
            # Read existing understanding
            existing_content = self.code_understanding_file.read_text() if self.code_understanding_file.exists() else "# Code Understanding\n\n"

            # Create understanding entry
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_entry = f"""
## {module_name}

**File:** {file_path}
**Updated:** {timestamp}

{understanding}

---

"""

            # Check if module already exists in file
            if f"## {module_name}" in existing_content:
                # Replace existing entry
                pattern = rf"## {re.escape(module_name)}.*?(?=\n## |\n---\n|\Z)"
                updated_content = re.sub(pattern, new_entry.strip(), existing_content, flags=re.DOTALL)
            else:
                # Add new entry
                updated_content = existing_content + new_entry

            # Save updated understanding
            self.code_understanding_file.write_text(updated_content)

            # Also save as structured data for searching
            understanding_record = CodeUnderstanding(
                module_name=module_name,
                file_path=file_path,
                purpose=understanding[:200],  # First 200 chars as purpose
                key_functions=[],  # Could be extracted from understanding
                dependencies=[],
                complexity_level="unknown",
                notes=understanding,
                last_updated=datetime.now()
            )

            logger.info(f"Updated understanding for module {module_name} in worker {self.worker_id}")

            return {
                "status": "success",
                "module_name": module_name,
                "file_path": file_path,
                "updated_at": timestamp,
                "content_length": len(understanding)
            }

        except Exception as e:
            logger.error(f"Error updating understanding for worker {self.worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def search_memory(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Semantic search across all memory files."""
        try:
            all_memories = []

            # Search current context
            if self.current_context_file.exists():
                content = self.current_context_file.read_text()
                memory = MemoryEntry(
                    id="current_context",
                    timestamp=datetime.now(),
                    content=content,
                    content_type="context",
                    tags=["current", "active"],
                    module_name=None,
                    task_id=None
                )
                all_memories.append(memory)

            # Search archived contexts
            for archive_file in self.memory_path.glob("context_archive_*.md"):
                content = archive_file.read_text()
                timestamp_str = archive_file.stem.split("_", 2)[-1]
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                except ValueError:
                    timestamp = datetime.fromtimestamp(archive_file.stat().st_mtime)

                memory = MemoryEntry(
                    id=archive_file.stem,
                    timestamp=timestamp,
                    content=content,
                    content_type="archived_context",
                    tags=["archived", "context"],
                    module_name=None,
                    task_id=None
                )
                all_memories.append(memory)

            # Search code understanding
            if self.code_understanding_file.exists():
                content = self.code_understanding_file.read_text()
                # Split by module sections
                sections = re.split(r'\n## ', content)
                for section in sections[1:]:  # Skip header
                    lines = section.split('\n')
                    module_name = lines[0] if lines else "unknown"

                    memory = MemoryEntry(
                        id=f"understanding_{module_name}",
                        timestamp=datetime.now(),
                        content=section,
                        content_type="understanding",
                        tags=["code", "understanding", module_name.lower()],
                        module_name=module_name,
                        task_id=None
                    )
                    all_memories.append(memory)

            # Search decisions
            if self.decisions_file.exists():
                content = self.decisions_file.read_text()
                memory = MemoryEntry(
                    id="decisions",
                    timestamp=datetime.now(),
                    content=content,
                    content_type="decisions",
                    tags=["decisions", "architecture"],
                    module_name=None,
                    task_id=None
                )
                all_memories.append(memory)

            # Search questions
            if self.questions_file.exists():
                content = self.questions_file.read_text()
                memory = MemoryEntry(
                    id="questions",
                    timestamp=datetime.now(),
                    content=content,
                    content_type="questions",
                    tags=["questions", "qa"],
                    module_name=None,
                    task_id=None
                )
                all_memories.append(memory)

            # Perform search
            results = await self.searcher.search_memories(query, all_memories, limit)

            # Format results
            formatted_results = []
            for memory in results:
                formatted_results.append({
                    "id": memory.id,
                    "content_type": memory.content_type,
                    "relevance_score": memory.relevance_score,
                    "timestamp": memory.timestamp.isoformat(),
                    "content_preview": memory.content[:300] + "..." if len(memory.content) > 300 else memory.content,
                    "module_name": memory.module_name,
                    "tags": memory.tags
                })

            return {
                "status": "success",
                "query": query,
                "total_memories_searched": len(all_memories),
                "results_found": len(results),
                "results": formatted_results
            }

        except Exception as e:
            logger.error(f"Error searching memory for worker {self.worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def record_task_completion(self, task_record: TaskRecord) -> Dict[str, Any]:
        """Record a completed task in memory."""
        try:
            # Load existing task history
            if self.task_history_file.exists():
                with open(self.task_history_file, 'r') as f:
                    task_history = json.load(f)
            else:
                task_history = []

            # Add new task record
            task_data = asdict(task_record)
            # Convert datetime objects to strings
            task_data['start_time'] = task_record.start_time.isoformat()
            task_data['end_time'] = task_record.end_time.isoformat() if task_record.end_time else None

            task_history.append(task_data)

            # Keep only last 100 tasks
            task_history = task_history[-100:]

            # Save updated history
            with open(self.task_history_file, 'w') as f:
                json.dump(task_history, f, indent=2)

            # Also update decisions file if decisions were made
            if task_record.decisions_made:
                await self._append_decisions(task_record.decisions_made, task_record.task_id)

            logger.info(f"Recorded task completion for {task_record.task_id} in worker {self.worker_id}")

            return {
                "status": "success",
                "task_id": task_record.task_id,
                "recorded_at": datetime.now().isoformat(),
                "total_tasks_in_history": len(task_history)
            }

        except Exception as e:
            logger.error(f"Error recording task completion for worker {self.worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about worker memory usage."""
        try:
            stats = {
                "worker_id": self.worker_id,
                "memory_path": str(self.memory_path),
                "current_tokens": self.context_manager.current_token_count,
                "max_tokens": self.context_manager.max_active_tokens,
                "files": {}
            }

            # Check each memory file
            memory_files = [
                ("current_context", self.current_context_file),
                ("task_history", self.task_history_file),
                ("code_understanding", self.code_understanding_file),
                ("decisions", self.decisions_file),
                ("questions", self.questions_file)
            ]

            total_size = 0
            for name, file_path in memory_files:
                if file_path.exists():
                    size = file_path.stat().st_size
                    total_size += size

                    # Count lines/entries
                    content = file_path.read_text()
                    if name == "task_history":
                        try:
                            data = json.loads(content)
                            entry_count = len(data)
                        except:
                            entry_count = 0
                    else:
                        entry_count = len(content.split('\n'))

                    stats["files"][name] = {
                        "exists": True,
                        "size_bytes": size,
                        "entry_count": entry_count,
                        "last_modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    }
                else:
                    stats["files"][name] = {"exists": False}

            # Count archived contexts
            archived_files = list(self.memory_path.glob("context_archive_*.md"))
            stats["archived_contexts"] = len(archived_files)
            stats["total_memory_size_bytes"] = total_size

            return {
                "status": "success",
                "stats": stats
            }

        except Exception as e:
            logger.error(f"Error getting memory stats for worker {self.worker_id}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    # Helper methods

    def _format_context_summary(self, summary: ContextSummary) -> str:
        """Format context summary as markdown."""
        md_content = f"""# Context Summary

**Created:** {summary.created_at.isoformat()}
**Token Count:** {summary.token_count}

## Summary

{summary.summary}

## Key Points

"""
        for i, point in enumerate(summary.key_points, 1):
            md_content += f"{i}. {point}\n"

        if summary.decisions_made:
            md_content += "\n## Decisions Made\n\n"
            for i, decision in enumerate(summary.decisions_made, 1):
                md_content += f"{i}. {decision}\n"

        if summary.questions_raised:
            md_content += "\n## Questions Raised\n\n"
            for i, question in enumerate(summary.questions_raised, 1):
                md_content += f"{i}. {question}\n"

        if summary.code_areas_touched:
            md_content += "\n## Code Areas Touched\n\n"
            for area in summary.code_areas_touched:
                md_content += f"- {area}\n"

        return md_content

    async def _search_archived_contexts(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search through archived context files."""
        results = []

        for archive_file in self.memory_path.glob("context_archive_*.md"):
            content = archive_file.read_text()
            score = self.searcher.calculate_relevance_score(query, content, {
                'timestamp': datetime.fromtimestamp(archive_file.stat().st_mtime)
            })

            if score > 0:
                results.append({
                    "type": "archived_context",
                    "content": content,
                    "relevance": score,
                    "source": archive_file.name
                })

        return sorted(results, key=lambda x: x["relevance"], reverse=True)[:limit]

    async def _load_relevant_code_understanding(self, task_description: str) -> List[Dict[str, Any]]:
        """Load code understanding relevant to task."""
        if not self.code_understanding_file.exists():
            return []

        content = self.code_understanding_file.read_text()
        if not task_description:
            return [{
                "type": "code_understanding",
                "content": content,
                "relevance": 5.0
            }]

        # Search for relevant modules
        score = self.searcher.calculate_relevance_score(task_description, content, {})
        if score > 1.0:
            return [{
                "type": "code_understanding",
                "content": content,
                "relevance": score
            }]

        return []

    async def _load_recent_decisions(self, limit: int) -> List[Dict[str, Any]]:
        """Load recent architectural decisions."""
        if not self.decisions_file.exists():
            return []

        content = self.decisions_file.read_text()
        # Get last few decisions (simple approach)
        lines = content.split('\n')
        recent_lines = lines[-50:] if len(lines) > 50 else lines
        recent_content = '\n'.join(recent_lines)

        return [{
            "type": "recent_decisions",
            "content": recent_content,
            "relevance": 7.0
        }]

    async def _append_decisions(self, decisions: List[str], task_id: str):
        """Append new decisions to decisions file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_content = f"\n## Task: {task_id} ({timestamp})\n\n"

        for i, decision in enumerate(decisions, 1):
            new_content += f"{i}. {decision}\n"

        new_content += "\n---\n"

        # Append to file
        with open(self.decisions_file, 'a') as f:
            f.write(new_content)


# Global memory managers for workers
worker_memory_managers: Dict[str, WorkerMemoryManager] = {}


def get_memory_manager(worker_id: str) -> WorkerMemoryManager:
    """Get or create memory manager for worker."""
    if worker_id not in worker_memory_managers:
        worker_memory_managers[worker_id] = WorkerMemoryManager(worker_id)
    return worker_memory_managers[worker_id]