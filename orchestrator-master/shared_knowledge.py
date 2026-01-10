#!/usr/bin/env python3
"""
Shared Knowledge Management System
Cross-worker context sharing and coordination through centralized knowledge base.
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import fcntl
from enum import Enum
import yaml

logger = logging.getLogger(__name__)


class ModuleStatus(Enum):
    """Status of module ownership."""
    AVAILABLE = "available"
    LOCKED = "locked"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEW = "review"


class ConflictSeverity(Enum):
    """Severity of potential conflicts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ModuleLock:
    """Represents a lock on a module or component."""
    module_name: str
    worker_id: str
    task_id: str
    locked_at: datetime
    expected_completion: Optional[datetime]
    status: ModuleStatus
    dependencies: List[str]
    description: str


@dataclass
class APIContract:
    """Represents an API contract between modules."""
    name: str
    module: str
    endpoint: Optional[str]
    method: Optional[str]
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    description: str
    version: str
    created_by: str
    created_at: datetime
    dependencies: List[str]


@dataclass
class ArchitecturalDecision:
    """Records an architectural decision."""
    id: str
    title: str
    decision: str
    rationale: str
    alternatives_considered: List[str]
    consequences: List[str]
    status: str  # "proposed", "accepted", "superseded"
    decided_by: str
    decided_at: datetime
    affects_modules: List[str]
    related_tasks: List[str]


@dataclass
class CodingStandard:
    """Coding standard or guideline."""
    category: str
    rule: str
    description: str
    examples: List[str]
    enforced_by: List[str]  # Tools that enforce this
    exceptions: List[str]
    last_updated: datetime
    updated_by: str


@dataclass
class WorkerLearning:
    """Learning or gotcha discovered by a worker."""
    id: str
    worker_id: str
    task_id: str
    module: str
    title: str
    description: str
    type: str  # "gotcha", "optimization", "pattern", "warning"
    severity: str
    solution: str
    tags: List[str]
    discovered_at: datetime


class SharedKnowledgeManager:
    """Main manager for cross-worker knowledge sharing."""

    def __init__(self, workspace_path: str = "/workspace"):
        self.workspace_path = Path(workspace_path)
        self.shared_path = self.workspace_path / "shared_knowledge"

        # Knowledge base file paths
        self.architecture_file = self.shared_path / "architecture_decisions.md"
        self.api_contracts_file = self.shared_path / "api_contracts.json"
        self.coding_standards_file = self.shared_path / "coding_standards.md"
        self.module_ownership_file = self.shared_path / "module_ownership.json"
        self.module_locks_file = self.shared_path / "module_locks.json"
        self.worker_learnings_file = self.shared_path / "worker_learnings.json"
        self.knowledge_index_file = self.shared_path / "knowledge_index.json"

        # Ensure shared knowledge directory exists
        self.shared_path.mkdir(parents=True, exist_ok=True)

        # Initialize knowledge base files
        self._initialize_knowledge_files()

    def _initialize_knowledge_files(self):
        """Initialize knowledge base files if they don't exist."""
        # Architecture decisions
        if not self.architecture_file.exists():
            self.architecture_file.write_text("# Architectural Decisions\n\n")

        # API contracts
        if not self.api_contracts_file.exists():
            self.api_contracts_file.write_text("[]")

        # Coding standards
        if not self.coding_standards_file.exists():
            initial_standards = """# Coding Standards

## Python Standards
- Follow PEP 8 for code style
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use docstrings for all public functions

## API Standards
- RESTful endpoint naming conventions
- Consistent error response format
- Version all APIs (v1, v2, etc.)
- Include request/response examples in documentation

## Database Standards
- Use descriptive table and column names
- Include created_at and updated_at timestamps
- Use foreign key constraints
- Index frequently queried columns

"""
            self.coding_standards_file.write_text(initial_standards)

        # Module ownership
        if not self.module_ownership_file.exists():
            self.module_ownership_file.write_text("[]")

        # Module locks
        if not self.module_locks_file.exists():
            self.module_locks_file.write_text("[]")

        # Worker learnings
        if not self.worker_learnings_file.exists():
            self.worker_learnings_file.write_text("[]")

        # Knowledge index
        if not self.knowledge_index_file.exists():
            initial_index = {
                "last_updated": datetime.now().isoformat(),
                "modules": {},
                "apis": {},
                "decisions": {},
                "workers": {}
            }
            self.knowledge_index_file.write_text(json.dumps(initial_index, indent=2))

    async def acquire_module_lock(self, worker_id: str, task_id: str, module_name: str,
                                 dependencies: List[str] = None, expected_duration_hours: int = 2) -> Dict[str, Any]:
        """Acquire a lock on a module for a worker."""
        try:
            # Check for conflicts
            conflict_check = await self._check_lock_conflicts(module_name, dependencies or [])

            if conflict_check["has_conflicts"]:
                return {
                    "status": "conflict",
                    "conflicts": conflict_check["conflicts"],
                    "message": f"Cannot acquire lock on {module_name} due to conflicts"
                }

            # Create module lock
            module_lock = ModuleLock(
                module_name=module_name,
                worker_id=worker_id,
                task_id=task_id,
                locked_at=datetime.now(),
                expected_completion=datetime.now() + timedelta(hours=expected_duration_hours),
                status=ModuleStatus.LOCKED,
                dependencies=dependencies or [],
                description=f"Worker {worker_id} working on {module_name}"
            )

            # Save lock
            locks = await self._load_module_locks()

            # Remove any existing locks for this module
            locks = [lock for lock in locks if lock["module_name"] != module_name]

            # Add new lock
            lock_data = asdict(module_lock)
            lock_data["locked_at"] = module_lock.locked_at.isoformat()
            lock_data["expected_completion"] = module_lock.expected_completion.isoformat() if module_lock.expected_completion else None
            lock_data["status"] = module_lock.status.value

            locks.append(lock_data)

            await self._save_module_locks(locks)

            # Update knowledge index
            await self._update_knowledge_index("module_lock", module_name, worker_id)

            logger.info(f"Acquired lock on module {module_name} for worker {worker_id}")

            return {
                "status": "success",
                "module_name": module_name,
                "worker_id": worker_id,
                "locked_at": module_lock.locked_at.isoformat(),
                "expected_completion": module_lock.expected_completion.isoformat() if module_lock.expected_completion else None
            }

        except Exception as e:
            logger.error(f"Error acquiring module lock: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def release_module_lock(self, worker_id: str, module_name: str,
                                 completion_status: str = "completed") -> Dict[str, Any]:
        """Release a module lock."""
        try:
            locks = await self._load_module_locks()

            # Find and remove the lock
            updated_locks = []
            lock_found = False

            for lock_data in locks:
                if lock_data["module_name"] == module_name and lock_data["worker_id"] == worker_id:
                    lock_found = True
                    # Update status instead of removing for audit trail
                    lock_data["status"] = completion_status
                    lock_data["completed_at"] = datetime.now().isoformat()

                updated_locks.append(lock_data)

            if not lock_found:
                return {
                    "status": "error",
                    "message": f"No lock found for module {module_name} by worker {worker_id}"
                }

            await self._save_module_locks(updated_locks)

            # Update knowledge index
            await self._update_knowledge_index("module_unlock", module_name, worker_id)

            logger.info(f"Released lock on module {module_name} by worker {worker_id}")

            return {
                "status": "success",
                "module_name": module_name,
                "worker_id": worker_id,
                "completion_status": completion_status
            }

        except Exception as e:
            logger.error(f"Error releasing module lock: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def share_task_completion(self, worker_id: str, task_id: str, completion_data: Dict[str, Any]) -> Dict[str, Any]:
        """Share task completion context with all workers."""
        try:
            shared_items = []

            # Extract and save API contracts
            if "apis_created" in completion_data:
                for api_data in completion_data["apis_created"]:
                    api_contract = APIContract(
                        name=api_data["name"],
                        module=api_data.get("module", "unknown"),
                        endpoint=api_data.get("endpoint"),
                        method=api_data.get("method"),
                        input_schema=api_data.get("input_schema", {}),
                        output_schema=api_data.get("output_schema", {}),
                        description=api_data.get("description", ""),
                        version=api_data.get("version", "1.0"),
                        created_by=worker_id,
                        created_at=datetime.now(),
                        dependencies=api_data.get("dependencies", [])
                    )

                    await self._save_api_contract(api_contract)
                    shared_items.append(f"API: {api_contract.name}")

            # Extract and save architectural decisions
            if "decisions_made" in completion_data:
                for decision_data in completion_data["decisions_made"]:
                    decision = ArchitecturalDecision(
                        id=f"ad_{task_id}_{len(shared_items)}",
                        title=decision_data.get("title", "Decision"),
                        decision=decision_data.get("decision", ""),
                        rationale=decision_data.get("rationale", ""),
                        alternatives_considered=decision_data.get("alternatives", []),
                        consequences=decision_data.get("consequences", []),
                        status="accepted",
                        decided_by=worker_id,
                        decided_at=datetime.now(),
                        affects_modules=decision_data.get("affects_modules", []),
                        related_tasks=[task_id]
                    )

                    await self._save_architectural_decision(decision)
                    shared_items.append(f"Decision: {decision.title}")

            # Extract and save learnings/gotchas
            if "learnings" in completion_data:
                for learning_data in completion_data["learnings"]:
                    learning = WorkerLearning(
                        id=f"learning_{task_id}_{len(shared_items)}",
                        worker_id=worker_id,
                        task_id=task_id,
                        module=learning_data.get("module", "general"),
                        title=learning_data.get("title", "Learning"),
                        description=learning_data.get("description", ""),
                        type=learning_data.get("type", "gotcha"),
                        severity=learning_data.get("severity", "medium"),
                        solution=learning_data.get("solution", ""),
                        tags=learning_data.get("tags", []),
                        discovered_at=datetime.now()
                    )

                    await self._save_worker_learning(learning)
                    shared_items.append(f"Learning: {learning.title}")

            # Update module ownership
            if "modules_completed" in completion_data:
                await self._update_module_ownership(worker_id, completion_data["modules_completed"])

            # Release any module locks
            if "modules_completed" in completion_data:
                for module in completion_data["modules_completed"]:
                    await self.release_module_lock(worker_id, module)

            # Update knowledge index
            await self._update_knowledge_index("task_completion", task_id, worker_id)

            logger.info(f"Shared task completion for {task_id} by worker {worker_id}: {len(shared_items)} items")

            return {
                "status": "success",
                "task_id": task_id,
                "worker_id": worker_id,
                "shared_items": shared_items,
                "shared_count": len(shared_items)
            }

        except Exception as e:
            logger.error(f"Error sharing task completion: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_relevant_context(self, worker_id: str, task_description: str,
                                  modules_involved: List[str] = None) -> Dict[str, Any]:
        """Get relevant shared context for a worker starting a task."""
        try:
            context = {
                "api_contracts": [],
                "architectural_decisions": [],
                "module_locks": [],
                "worker_learnings": [],
                "coding_standards": "",
                "conflict_warnings": []
            }

            # Get relevant API contracts
            api_contracts = await self._load_api_contracts()
            if modules_involved:
                relevant_apis = [
                    api for api in api_contracts
                    if api.get("module") in modules_involved or
                       any(dep in modules_involved for dep in api.get("dependencies", []))
                ]
                context["api_contracts"] = relevant_apis

            # Get relevant architectural decisions
            decisions = await self._load_architectural_decisions()
            if modules_involved:
                relevant_decisions = [
                    decision for decision in decisions
                    if any(module in decision.get("affects_modules", []) for module in modules_involved)
                ]
                context["architectural_decisions"] = relevant_decisions

            # Get current module locks
            locks = await self._load_module_locks()
            active_locks = [
                lock for lock in locks
                if lock["status"] in ["locked", "in_progress"] and lock["worker_id"] != worker_id
            ]
            context["module_locks"] = active_locks

            # Get relevant learnings
            learnings = await self._load_worker_learnings()
            if modules_involved:
                relevant_learnings = [
                    learning for learning in learnings
                    if learning.get("module") in modules_involved or
                       any(tag in task_description.lower() for tag in learning.get("tags", []))
                ]
                context["worker_learnings"] = relevant_learnings

            # Get coding standards
            if self.coding_standards_file.exists():
                context["coding_standards"] = self.coding_standards_file.read_text()

            # Check for potential conflicts
            if modules_involved:
                conflict_warnings = await self._check_potential_conflicts(modules_involved, worker_id)
                context["conflict_warnings"] = conflict_warnings

            # Calculate relevance scores
            total_items = (len(context["api_contracts"]) + len(context["architectural_decisions"]) +
                          len(context["worker_learnings"]) + len(context["conflict_warnings"]))

            logger.info(f"Retrieved relevant context for worker {worker_id}: {total_items} items")

            return {
                "status": "success",
                "worker_id": worker_id,
                "context": context,
                "total_items": total_items,
                "modules_checked": modules_involved or [],
                "retrieved_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting relevant context: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def update_coding_standards(self, standard: CodingStandard, worker_id: str) -> Dict[str, Any]:
        """Update coding standards."""
        try:
            # Read existing standards
            existing_content = self.coding_standards_file.read_text() if self.coding_standards_file.exists() else ""

            # Format new standard
            new_standard_md = f"""
## {standard.category}: {standard.rule}

**Description:** {standard.description}

**Examples:**
```
{chr(10).join(standard.examples)}
```

**Enforced by:** {', '.join(standard.enforced_by)}
**Exceptions:** {', '.join(standard.exceptions)}
**Last updated:** {standard.last_updated.strftime('%Y-%m-%d')} by {standard.updated_by}

---

"""

            # Append to file
            updated_content = existing_content + new_standard_md
            self.coding_standards_file.write_text(updated_content)

            # Update knowledge index
            await self._update_knowledge_index("coding_standard", standard.category, worker_id)

            logger.info(f"Updated coding standard: {standard.category} - {standard.rule}")

            return {
                "status": "success",
                "category": standard.category,
                "rule": standard.rule,
                "updated_by": worker_id
            }

        except Exception as e:
            logger.error(f"Error updating coding standards: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def search_shared_knowledge(self, query: str, content_types: List[str] = None,
                                    limit: int = 10) -> Dict[str, Any]:
        """Search across all shared knowledge."""
        try:
            results = []

            # Search API contracts
            if not content_types or "api_contracts" in content_types:
                api_contracts = await self._load_api_contracts()
                for api in api_contracts:
                    score = self._calculate_search_score(query, api.get("description", "") + " " + api.get("name", ""))
                    if score > 0:
                        results.append({
                            "type": "api_contract",
                            "content": api,
                            "relevance_score": score,
                            "title": api.get("name", "Unknown API")
                        })

            # Search architectural decisions
            if not content_types or "decisions" in content_types:
                decisions = await self._load_architectural_decisions()
                for decision in decisions:
                    score = self._calculate_search_score(query,
                        decision.get("title", "") + " " + decision.get("decision", "") + " " + decision.get("rationale", ""))
                    if score > 0:
                        results.append({
                            "type": "architectural_decision",
                            "content": decision,
                            "relevance_score": score,
                            "title": decision.get("title", "Unknown Decision")
                        })

            # Search worker learnings
            if not content_types or "learnings" in content_types:
                learnings = await self._load_worker_learnings()
                for learning in learnings:
                    score = self._calculate_search_score(query,
                        learning.get("title", "") + " " + learning.get("description", "") + " " + learning.get("solution", ""))
                    if score > 0:
                        results.append({
                            "type": "worker_learning",
                            "content": learning,
                            "relevance_score": score,
                            "title": learning.get("title", "Unknown Learning")
                        })

            # Search coding standards
            if not content_types or "standards" in content_types:
                if self.coding_standards_file.exists():
                    standards_content = self.coding_standards_file.read_text()
                    score = self._calculate_search_score(query, standards_content)
                    if score > 0:
                        results.append({
                            "type": "coding_standards",
                            "content": {"content": standards_content},
                            "relevance_score": score,
                            "title": "Coding Standards"
                        })

            # Sort by relevance
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            results = results[:limit]

            logger.info(f"Searched shared knowledge for '{query}': {len(results)} results")

            return {
                "status": "success",
                "query": query,
                "results": results,
                "total_found": len(results)
            }

        except Exception as e:
            logger.error(f"Error searching shared knowledge: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get statistics about the shared knowledge base."""
        try:
            stats = {
                "knowledge_files": {},
                "totals": {
                    "api_contracts": 0,
                    "architectural_decisions": 0,
                    "worker_learnings": 0,
                    "active_locks": 0,
                    "completed_modules": 0
                },
                "worker_activity": {},
                "module_status": {}
            }

            # Check each knowledge file
            knowledge_files = [
                ("architecture_decisions", self.architecture_file),
                ("api_contracts", self.api_contracts_file),
                ("coding_standards", self.coding_standards_file),
                ("module_ownership", self.module_ownership_file),
                ("module_locks", self.module_locks_file),
                ("worker_learnings", self.worker_learnings_file)
            ]

            total_size = 0
            for name, file_path in knowledge_files:
                if file_path.exists():
                    size = file_path.stat().st_size
                    total_size += size

                    stats["knowledge_files"][name] = {
                        "exists": True,
                        "size_bytes": size,
                        "last_modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    }
                else:
                    stats["knowledge_files"][name] = {"exists": False}

            # Count specific items
            api_contracts = await self._load_api_contracts()
            stats["totals"]["api_contracts"] = len(api_contracts)

            learnings = await self._load_worker_learnings()
            stats["totals"]["worker_learnings"] = len(learnings)

            locks = await self._load_module_locks()
            active_locks = [lock for lock in locks if lock["status"] in ["locked", "in_progress"]]
            stats["totals"]["active_locks"] = len(active_locks)

            # Analyze worker activity
            worker_activity = {}
            for learning in learnings:
                worker_id = learning.get("worker_id", "unknown")
                if worker_id not in worker_activity:
                    worker_activity[worker_id] = 0
                worker_activity[worker_id] += 1

            stats["worker_activity"] = worker_activity
            stats["total_knowledge_size_bytes"] = total_size

            return {
                "status": "success",
                "stats": stats
            }

        except Exception as e:
            logger.error(f"Error getting knowledge stats: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    # Helper methods

    async def _load_module_locks(self) -> List[Dict[str, Any]]:
        """Load module locks from file."""
        if self.module_locks_file.exists():
            with open(self.module_locks_file, 'r') as f:
                return json.load(f)
        return []

    async def _save_module_locks(self, locks: List[Dict[str, Any]]):
        """Save module locks to file."""
        with open(self.module_locks_file, 'w') as f:
            json.dump(locks, f, indent=2)

    async def _load_api_contracts(self) -> List[Dict[str, Any]]:
        """Load API contracts from file."""
        if self.api_contracts_file.exists():
            with open(self.api_contracts_file, 'r') as f:
                return json.load(f)
        return []

    async def _save_api_contract(self, contract: APIContract):
        """Save API contract to file."""
        contracts = await self._load_api_contracts()

        # Convert to dict
        contract_data = asdict(contract)
        contract_data["created_at"] = contract.created_at.isoformat()

        # Remove existing contract with same name
        contracts = [c for c in contracts if c.get("name") != contract.name]
        contracts.append(contract_data)

        with open(self.api_contracts_file, 'w') as f:
            json.dump(contracts, f, indent=2)

    async def _load_architectural_decisions(self) -> List[Dict[str, Any]]:
        """Load architectural decisions."""
        # For now, parse from markdown file
        # In production, might use structured format
        decisions = []
        if self.architecture_file.exists():
            content = self.architecture_file.read_text()
            # Simple parsing - could be enhanced
            sections = content.split("## ")
            for section in sections[1:]:  # Skip header
                lines = section.split('\n')
                if lines:
                    decisions.append({
                        "title": lines[0].strip(),
                        "content": '\n'.join(lines[1:]).strip()
                    })
        return decisions

    async def _save_architectural_decision(self, decision: ArchitecturalDecision):
        """Save architectural decision."""
        # Read existing content
        existing_content = self.architecture_file.read_text() if self.architecture_file.exists() else "# Architectural Decisions\n\n"

        # Format decision as markdown
        decision_md = f"""
## {decision.title}

**Decision:** {decision.decision}

**Rationale:** {decision.rationale}

**Alternatives Considered:**
{chr(10).join(f"- {alt}" for alt in decision.alternatives_considered)}

**Consequences:**
{chr(10).join(f"- {cons}" for cons in decision.consequences)}

**Status:** {decision.status}
**Decided by:** {decision.decided_by}
**Date:** {decision.decided_at.strftime('%Y-%m-%d')}
**Affects modules:** {', '.join(decision.affects_modules)}
**Related tasks:** {', '.join(decision.related_tasks)}

---

"""

        # Append to file
        updated_content = existing_content + decision_md
        self.architecture_file.write_text(updated_content)

    async def _load_worker_learnings(self) -> List[Dict[str, Any]]:
        """Load worker learnings from file."""
        if self.worker_learnings_file.exists():
            with open(self.worker_learnings_file, 'r') as f:
                return json.load(f)
        return []

    async def _save_worker_learning(self, learning: WorkerLearning):
        """Save worker learning to file."""
        learnings = await self._load_worker_learnings()

        # Convert to dict
        learning_data = asdict(learning)
        learning_data["discovered_at"] = learning.discovered_at.isoformat()

        learnings.append(learning_data)

        # Keep only last 1000 learnings
        learnings = learnings[-1000:]

        with open(self.worker_learnings_file, 'w') as f:
            json.dump(learnings, f, indent=2)

    async def _update_module_ownership(self, worker_id: str, modules: List[str]):
        """Update module ownership records."""
        if self.module_ownership_file.exists():
            with open(self.module_ownership_file, 'r') as f:
                ownership = json.load(f)
        else:
            ownership = []

        # Update ownership for each module
        for module in modules:
            # Remove existing ownership
            ownership = [o for o in ownership if o.get("module") != module]

            # Add new ownership
            ownership.append({
                "module": module,
                "owner": worker_id,
                "completed_at": datetime.now().isoformat(),
                "status": "completed"
            })

        with open(self.module_ownership_file, 'w') as f:
            json.dump(ownership, f, indent=2)

    async def _check_lock_conflicts(self, module_name: str, dependencies: List[str]) -> Dict[str, Any]:
        """Check for module lock conflicts."""
        locks = await self._load_module_locks()
        conflicts = []

        # Check direct module conflict
        for lock in locks:
            if (lock["module_name"] == module_name and
                lock["status"] in ["locked", "in_progress"]):
                conflicts.append({
                    "type": "direct_conflict",
                    "module": module_name,
                    "locked_by": lock["worker_id"],
                    "locked_at": lock["locked_at"],
                    "severity": "critical"
                })

        # Check dependency conflicts
        for dep in dependencies:
            for lock in locks:
                if (lock["module_name"] == dep and
                    lock["status"] in ["locked", "in_progress"]):
                    conflicts.append({
                        "type": "dependency_conflict",
                        "module": dep,
                        "locked_by": lock["worker_id"],
                        "locked_at": lock["locked_at"],
                        "severity": "high"
                    })

        return {
            "has_conflicts": len(conflicts) > 0,
            "conflicts": conflicts
        }

    async def _check_potential_conflicts(self, modules: List[str], worker_id: str) -> List[Dict[str, Any]]:
        """Check for potential conflicts when starting work on modules."""
        warnings = []
        locks = await self._load_module_locks()

        for module in modules:
            # Check if someone else is working on this module
            for lock in locks:
                if (lock["module_name"] == module and
                    lock["worker_id"] != worker_id and
                    lock["status"] in ["locked", "in_progress"]):
                    warnings.append({
                        "type": "concurrent_work",
                        "module": module,
                        "other_worker": lock["worker_id"],
                        "message": f"Worker {lock['worker_id']} is also working on {module}",
                        "severity": "medium"
                    })

                # Check if this module depends on something being worked on
                if module in lock.get("dependencies", []):
                    warnings.append({
                        "type": "dependency_in_progress",
                        "module": module,
                        "depends_on": lock["module_name"],
                        "blocked_by": lock["worker_id"],
                        "message": f"Module {module} depends on {lock['module_name']} which is being worked on by {lock['worker_id']}",
                        "severity": "high"
                    })

        return warnings

    async def _update_knowledge_index(self, operation: str, item_id: str, worker_id: str):
        """Update the knowledge index for fast lookups."""
        try:
            if self.knowledge_index_file.exists():
                with open(self.knowledge_index_file, 'r') as f:
                    index = json.load(f)
            else:
                index = {
                    "last_updated": datetime.now().isoformat(),
                    "modules": {},
                    "apis": {},
                    "decisions": {},
                    "workers": {}
                }

            # Update index based on operation
            index["last_updated"] = datetime.now().isoformat()

            if worker_id not in index["workers"]:
                index["workers"][worker_id] = {"operations": 0, "last_activity": ""}

            index["workers"][worker_id]["operations"] += 1
            index["workers"][worker_id]["last_activity"] = datetime.now().isoformat()

            # Save updated index
            with open(self.knowledge_index_file, 'w') as f:
                json.dump(index, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to update knowledge index: {e}")

    def _calculate_search_score(self, query: str, content: str) -> float:
        """Calculate search relevance score."""
        if not content:
            return 0.0

        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words:
            return 0.0

        # Calculate word overlap
        overlap = len(query_words & content_words)
        score = overlap / len(query_words)

        # Boost for exact phrase matches
        if query.lower() in content.lower():
            score += 0.5

        return score


# Global shared knowledge manager
shared_knowledge_manager = SharedKnowledgeManager()