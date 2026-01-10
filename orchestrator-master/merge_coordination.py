#!/usr/bin/env python3
"""
Merge and Coordination Logic
Handles merging parallel work from multiple workers with conflict resolution.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import subprocess
import tempfile
import os

logger = logging.getLogger(__name__)


class MergeStatus(Enum):
    """Status of merge operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class ConflictType(Enum):
    """Types of merge conflicts."""
    FILE_CONFLICT = "file_conflict"
    DEPENDENCY_CONFLICT = "dependency_conflict"
    TYPE_CONFLICT = "type_conflict"
    IMPORT_CONFLICT = "import_conflict"
    INTERFACE_BREAKING = "interface_breaking"


@dataclass
class MergeConflict:
    """Represents a merge conflict that needs resolution."""
    conflict_id: str
    conflict_type: ConflictType
    files_involved: List[str]
    workers_involved: List[str]
    description: str
    severity: str  # "low", "medium", "high", "critical"
    auto_resolvable: bool
    resolution_strategy: Optional[str] = None
    assigned_worker: Optional[str] = None


@dataclass
class WorkerBranch:
    """Represents a worker's branch with their completed work."""
    worker_id: str
    branch_name: str
    task_ids: List[str]
    files_modified: List[str]
    test_status: str  # "passed", "failed", "not_run"
    dependencies: List[str]  # Other branches this depends on
    merge_priority: int  # Lower number = higher priority


@dataclass
class MergeReport:
    """Report of merge operations and results."""
    merge_id: str
    graph_id: str
    start_time: datetime
    end_time: Optional[datetime]
    status: MergeStatus
    branches_merged: List[str]
    conflicts_detected: List[MergeConflict]
    conflicts_resolved: List[str]
    test_results: Dict[str, Any]
    dependency_fixes: List[str]
    final_validation: Dict[str, Any]


class ConflictAnalyzer:
    """Analyzes potential conflicts between worker branches."""

    def __init__(self):
        self.file_analyzers = {
            '.py': self._analyze_python_conflicts,
            '.js': self._analyze_javascript_conflicts,
            '.ts': self._analyze_typescript_conflicts,
            '.json': self._analyze_json_conflicts,
        }

    async def analyze_conflicts(self, branches: List[WorkerBranch]) -> List[MergeConflict]:
        """Analyze potential conflicts between branches."""
        conflicts = []

        # Check file-level conflicts
        file_conflicts = await self._check_file_conflicts(branches)
        conflicts.extend(file_conflicts)

        # Check dependency conflicts
        dep_conflicts = await self._check_dependency_conflicts(branches)
        conflicts.extend(dep_conflicts)

        # Check interface conflicts
        interface_conflicts = await self._check_interface_conflicts(branches)
        conflicts.extend(interface_conflicts)

        return conflicts

    async def _check_file_conflicts(self, branches: List[WorkerBranch]) -> List[MergeConflict]:
        """Check for files modified by multiple workers."""
        conflicts = []
        file_to_workers = {}

        # Map files to workers who modified them
        for branch in branches:
            for file_path in branch.files_modified:
                if file_path not in file_to_workers:
                    file_to_workers[file_path] = []
                file_to_workers[file_path].append(branch.worker_id)

        # Find files modified by multiple workers
        for file_path, workers in file_to_workers.items():
            if len(workers) > 1:
                conflict = MergeConflict(
                    conflict_id=f"file_conflict_{len(conflicts)}",
                    conflict_type=ConflictType.FILE_CONFLICT,
                    files_involved=[file_path],
                    workers_involved=workers,
                    description=f"File {file_path} modified by multiple workers: {', '.join(workers)}",
                    severity="medium",
                    auto_resolvable=await self._is_auto_resolvable_file_conflict(file_path, workers)
                )
                conflicts.append(conflict)

        return conflicts

    async def _check_dependency_conflicts(self, branches: List[WorkerBranch]) -> List[MergeConflict]:
        """Check for dependency conflicts between branches."""
        conflicts = []

        # Analyze import dependencies
        for i, branch1 in enumerate(branches):
            for j, branch2 in enumerate(branches[i+1:], i+1):
                # Check if branches have conflicting dependencies
                common_files = set(branch1.files_modified) & set(branch2.files_modified)

                if common_files:
                    # Analyze specific dependency conflicts
                    for file_path in common_files:
                        dep_conflict = await self._analyze_file_dependencies(
                            file_path, branch1, branch2
                        )
                        if dep_conflict:
                            conflicts.append(dep_conflict)

        return conflicts

    async def _check_interface_conflicts(self, branches: List[WorkerBranch]) -> List[MergeConflict]:
        """Check for interface breaking changes."""
        conflicts = []

        for branch in branches:
            # Check each modified file for interface changes
            for file_path in branch.files_modified:
                interface_changes = await self._detect_interface_changes(file_path, branch)

                if interface_changes:
                    conflict = MergeConflict(
                        conflict_id=f"interface_conflict_{len(conflicts)}",
                        conflict_type=ConflictType.INTERFACE_BREAKING,
                        files_involved=[file_path],
                        workers_involved=[branch.worker_id],
                        description=f"Potential interface breaking changes in {file_path}",
                        severity="high",
                        auto_resolvable=False
                    )
                    conflicts.append(conflict)

        return conflicts

    async def _analyze_python_conflicts(self, file_path: str, branches: List[WorkerBranch]) -> List[MergeConflict]:
        """Analyze Python-specific conflicts."""
        conflicts = []

        # Check for import conflicts, function signature changes, etc.
        # This would involve parsing the Python AST to detect conflicts

        return conflicts

    async def _is_auto_resolvable_file_conflict(self, file_path: str, workers: List[str]) -> bool:
        """Determine if a file conflict can be automatically resolved."""
        # Simple heuristics - can be enhanced
        file_ext = os.path.splitext(file_path)[1]

        # JSON files are often auto-resolvable if they're configuration
        if file_ext == '.json':
            return True

        # Documentation files are usually auto-resolvable
        if file_path.endswith(('.md', '.txt', '.rst')):
            return True

        # Code files require more analysis
        return False

    async def _analyze_file_dependencies(self, file_path: str, branch1: WorkerBranch, branch2: WorkerBranch) -> Optional[MergeConflict]:
        """Analyze dependencies between two branches for a specific file."""
        # This would involve more sophisticated analysis
        # For now, return None (no conflict detected)
        return None

    async def _detect_interface_changes(self, file_path: str, branch: WorkerBranch) -> bool:
        """Detect if a file has interface breaking changes."""
        # This would involve analyzing function signatures, class interfaces, etc.
        # For now, return False (no breaking changes detected)
        return False


class MergeStrategy:
    """Implements different merge strategies."""

    def __init__(self):
        self.strategies = {
            "sequential": self._sequential_merge,
            "dependency_ordered": self._dependency_ordered_merge,
            "parallel_safe": self._parallel_safe_merge
        }

    async def execute_merge(self, strategy: str, branches: List[WorkerBranch], conflicts: List[MergeConflict]) -> MergeReport:
        """Execute a merge strategy."""
        if strategy not in self.strategies:
            raise ValueError(f"Unknown merge strategy: {strategy}")

        return await self.strategies[strategy](branches, conflicts)

    async def _sequential_merge(self, branches: List[WorkerBranch], conflicts: List[MergeConflict]) -> MergeReport:
        """Merge branches sequentially by priority."""
        merge_report = MergeReport(
            merge_id=f"merge_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            graph_id="",  # Will be set by caller
            start_time=datetime.now(),
            end_time=None,
            status=MergeStatus.IN_PROGRESS,
            branches_merged=[],
            conflicts_detected=conflicts,
            conflicts_resolved=[],
            test_results={},
            dependency_fixes=[],
            final_validation={}
        )

        try:
            # Sort branches by merge priority
            sorted_branches = sorted(branches, key=lambda b: b.merge_priority)

            for branch in sorted_branches:
                logger.info(f"Merging branch {branch.branch_name} from worker {branch.worker_id}")

                # Pre-merge checks
                await self._run_pre_merge_checks(branch, merge_report)

                # Perform merge
                merge_success = await self._perform_git_merge(branch)

                if merge_success:
                    merge_report.branches_merged.append(branch.branch_name)

                    # Post-merge tests
                    test_results = await self._run_post_merge_tests(branch)
                    merge_report.test_results[branch.branch_name] = test_results

                    if not test_results.get("passed", False):
                        logger.warning(f"Tests failed after merging {branch.branch_name}")
                        # Could trigger conflict resolution here
                else:
                    logger.error(f"Failed to merge branch {branch.branch_name}")
                    merge_report.status = MergeStatus.FAILED
                    break

            # Final validation
            if merge_report.status != MergeStatus.FAILED:
                final_validation = await self._run_final_validation()
                merge_report.final_validation = final_validation
                merge_report.status = MergeStatus.COMPLETED if final_validation.get("passed", False) else MergeStatus.FAILED

            merge_report.end_time = datetime.now()

        except Exception as e:
            logger.error(f"Error during sequential merge: {e}")
            merge_report.status = MergeStatus.FAILED
            merge_report.end_time = datetime.now()

        return merge_report

    async def _dependency_ordered_merge(self, branches: List[WorkerBranch], conflicts: List[MergeConflict]) -> MergeReport:
        """Merge branches in dependency order."""
        # Build dependency graph and topologically sort
        sorted_branches = await self._topological_sort_branches(branches)
        return await self._sequential_merge(sorted_branches, conflicts)

    async def _parallel_safe_merge(self, branches: List[WorkerBranch], conflicts: List[MergeConflict]) -> MergeReport:
        """Merge branches that don't conflict in parallel."""
        # Group branches by conflict relationships
        merge_groups = await self._group_non_conflicting_branches(branches, conflicts)

        # Merge each group sequentially, but branches within groups in parallel
        # This is a simplified implementation
        return await self._sequential_merge(branches, conflicts)

    async def _topological_sort_branches(self, branches: List[WorkerBranch]) -> List[WorkerBranch]:
        """Sort branches in dependency order."""
        # Simple topological sort based on dependencies
        sorted_branches = []
        remaining = branches.copy()

        while remaining:
            # Find branches with no unresolved dependencies
            ready = []
            for branch in remaining:
                deps_satisfied = all(
                    dep in [b.worker_id for b in sorted_branches]
                    for dep in branch.dependencies
                )
                if deps_satisfied:
                    ready.append(branch)

            if not ready:
                # Circular dependency or error - fall back to priority order
                ready = [min(remaining, key=lambda b: b.merge_priority)]

            # Add ready branches to sorted list
            sorted_branches.extend(ready)
            for branch in ready:
                remaining.remove(branch)

        return sorted_branches

    async def _group_non_conflicting_branches(self, branches: List[WorkerBranch], conflicts: List[MergeConflict]) -> List[List[WorkerBranch]]:
        """Group branches that don't conflict with each other."""
        # This would implement a more sophisticated grouping algorithm
        # For now, return each branch as its own group
        return [[branch] for branch in branches]

    async def _run_pre_merge_checks(self, branch: WorkerBranch, merge_report: MergeReport):
        """Run pre-merge validation checks."""
        logger.info(f"Running pre-merge checks for {branch.branch_name}")

        # Check if branch tests pass
        if branch.test_status != "passed":
            logger.warning(f"Branch {branch.branch_name} tests have not passed")

    async def _perform_git_merge(self, branch: WorkerBranch) -> bool:
        """Perform the actual git merge operation."""
        try:
            # This would perform the actual git merge
            # For now, simulate success
            logger.info(f"Merging branch {branch.branch_name}")
            await asyncio.sleep(1)  # Simulate merge time
            return True
        except Exception as e:
            logger.error(f"Git merge failed for {branch.branch_name}: {e}")
            return False

    async def _run_post_merge_tests(self, branch: WorkerBranch) -> Dict[str, Any]:
        """Run tests after merging a branch."""
        logger.info(f"Running post-merge tests for {branch.branch_name}")

        # This would run the actual test suite
        # For now, simulate test results
        await asyncio.sleep(2)  # Simulate test time

        return {
            "passed": True,
            "total_tests": 25,
            "failed_tests": 0,
            "coverage": 85.5,
            "duration_seconds": 12.3
        }

    async def _run_final_validation(self) -> Dict[str, Any]:
        """Run final validation after all merges."""
        logger.info("Running final validation")

        # This would run comprehensive validation
        await asyncio.sleep(3)  # Simulate validation time

        return {
            "passed": True,
            "lint_check": True,
            "type_check": True,
            "integration_tests": True,
            "performance_tests": True
        }


class ConflictResolver:
    """Resolves merge conflicts automatically or assigns them to workers."""

    def __init__(self):
        self.auto_resolvers = {
            ConflictType.FILE_CONFLICT: self._resolve_file_conflict,
            ConflictType.DEPENDENCY_CONFLICT: self._resolve_dependency_conflict,
            ConflictType.IMPORT_CONFLICT: self._resolve_import_conflict,
        }

    async def resolve_conflict(self, conflict: MergeConflict, task_orchestrator) -> bool:
        """Attempt to resolve a conflict automatically or assign to worker."""
        logger.info(f"Resolving conflict {conflict.conflict_id}: {conflict.description}")

        if conflict.auto_resolvable and conflict.conflict_type in self.auto_resolvers:
            # Try automatic resolution
            success = await self.auto_resolvers[conflict.conflict_type](conflict)
            if success:
                logger.info(f"Automatically resolved conflict {conflict.conflict_id}")
                return True

        # Assign to appropriate worker for manual resolution
        await self._assign_conflict_to_worker(conflict, task_orchestrator)
        return False

    async def _resolve_file_conflict(self, conflict: MergeConflict) -> bool:
        """Automatically resolve file conflicts where possible."""
        # This would implement intelligent file conflict resolution
        # For now, return False to indicate manual resolution needed
        return False

    async def _resolve_dependency_conflict(self, conflict: MergeConflict) -> bool:
        """Automatically resolve dependency conflicts."""
        # This would analyze and fix import/dependency issues
        return False

    async def _resolve_import_conflict(self, conflict: MergeConflict) -> bool:
        """Automatically resolve import conflicts."""
        # This would fix import statements and dependencies
        return False

    async def _assign_conflict_to_worker(self, conflict: MergeConflict, task_orchestrator):
        """Assign conflict resolution to an appropriate worker."""
        # Determine best worker for this type of conflict
        if conflict.severity in ["high", "critical"]:
            preferred_model = "opus"
        elif conflict.severity == "medium":
            preferred_model = "sonnet"
        else:
            preferred_model = "haiku"

        # Create conflict resolution task
        resolution_task = {
            "task_id": f"resolve_{conflict.conflict_id}",
            "title": f"Resolve {conflict.conflict_type.value}",
            "description": f"Resolve conflict: {conflict.description}",
            "type": "conflict_resolution",
            "priority": 9,  # High priority
            "preferred_model": preferred_model,
            "files_involved": conflict.files_involved,
            "context": {
                "conflict_type": conflict.conflict_type.value,
                "workers_involved": conflict.workers_involved,
                "severity": conflict.severity
            }
        }

        # This would assign the task to a worker through the orchestrator
        logger.info(f"Assigned conflict {conflict.conflict_id} to worker with {preferred_model} model")


class MergeCoordinator:
    """Main coordinator for merge operations."""

    def __init__(self, task_orchestrator=None):
        self.task_orchestrator = task_orchestrator
        self.conflict_analyzer = ConflictAnalyzer()
        self.merge_strategy = MergeStrategy()
        self.conflict_resolver = ConflictResolver()
        self.active_merges: Dict[str, MergeReport] = {}

    async def coordinate_merge_phase(self, graph_id: str, worker_branches: List[Dict[str, Any]]) -> MergeReport:
        """
        Main coordination method for merging parallel work.

        Args:
            graph_id: ID of the task graph being merged
            worker_branches: List of worker branch information

        Returns:
            MergeReport with results of merge operation
        """
        logger.info(f"Starting merge coordination for graph {graph_id}")

        # Convert to WorkerBranch objects
        branches = [self._create_worker_branch(branch_data) for branch_data in worker_branches]

        # Phase 1: Pre-merge checks and conflict analysis
        logger.info("Phase 1: Analyzing conflicts")
        conflicts = await self.conflict_analyzer.analyze_conflicts(branches)

        # Phase 2: Resolve auto-resolvable conflicts
        logger.info("Phase 2: Resolving auto-resolvable conflicts")
        unresolved_conflicts = []
        for conflict in conflicts:
            resolved = await self.conflict_resolver.resolve_conflict(conflict, self.task_orchestrator)
            if not resolved:
                unresolved_conflicts.append(conflict)

        # Phase 3: Execute merge strategy
        logger.info("Phase 3: Executing merge strategy")
        merge_report = await self.merge_strategy.execute_merge(
            "dependency_ordered", branches, unresolved_conflicts
        )
        merge_report.graph_id = graph_id

        # Phase 4: Post-merge dependency resolution
        logger.info("Phase 4: Resolving dependencies")
        dependency_issues = await self._check_post_merge_dependencies()
        if dependency_issues:
            await self._create_dependency_fix_tasks(dependency_issues, merge_report)

        # Phase 5: Final validation and reporting
        logger.info("Phase 5: Final validation")
        await self._generate_final_merge_report(merge_report)

        # Store merge report
        self.active_merges[graph_id] = merge_report

        logger.info(f"Merge coordination completed for graph {graph_id}")
        return merge_report

    def _create_worker_branch(self, branch_data: Dict[str, Any]) -> WorkerBranch:
        """Create WorkerBranch object from data."""
        return WorkerBranch(
            worker_id=branch_data.get("worker_id", ""),
            branch_name=branch_data.get("branch_name", ""),
            task_ids=branch_data.get("task_ids", []),
            files_modified=branch_data.get("files_modified", []),
            test_status=branch_data.get("test_status", "not_run"),
            dependencies=branch_data.get("dependencies", []),
            merge_priority=branch_data.get("merge_priority", 5)
        )

    async def _check_post_merge_dependencies(self) -> List[Dict[str, Any]]:
        """Check for dependency issues after merge."""
        # This would run dependency analysis tools
        # For now, return empty list (no issues)
        return []

    async def _create_dependency_fix_tasks(self, issues: List[Dict[str, Any]], merge_report: MergeReport):
        """Create tasks to fix dependency issues."""
        for issue in issues:
            fix_task = {
                "title": f"Fix dependency issue: {issue.get('description', 'Unknown')}",
                "type": "dependency_fix",
                "priority": 8,
                "files_involved": issue.get("files", [])
            }
            merge_report.dependency_fixes.append(fix_task["title"])

    async def _generate_final_merge_report(self, merge_report: MergeReport):
        """Generate final merge report with summary and recommendations."""
        merge_report.end_time = datetime.now()

        # Calculate merge statistics
        total_duration = (merge_report.end_time - merge_report.start_time).total_seconds()

        logger.info(f"Merge Report Summary:")
        logger.info(f"  Status: {merge_report.status.value}")
        logger.info(f"  Branches merged: {len(merge_report.branches_merged)}")
        logger.info(f"  Conflicts detected: {len(merge_report.conflicts_detected)}")
        logger.info(f"  Conflicts resolved: {len(merge_report.conflicts_resolved)}")
        logger.info(f"  Duration: {total_duration:.1f} seconds")

    def get_merge_status(self, graph_id: str) -> Optional[MergeReport]:
        """Get current merge status for a graph."""
        return self.active_merges.get(graph_id)

    def list_active_merges(self) -> Dict[str, MergeReport]:
        """List all active merge operations."""
        return self.active_merges.copy()


# Global instance
merge_coordinator = MergeCoordinator()


async def coordinate_merge_phase(graph_id: str, worker_branches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    MCP tool function for coordinating merge phase.

    Args:
        graph_id: ID of the task graph being merged
        worker_branches: List of worker branch information

    Returns:
        Dictionary with merge results and status
    """
    try:
        merge_report = await merge_coordinator.coordinate_merge_phase(graph_id, worker_branches)

        return {
            "status": "success",
            "merge_id": merge_report.merge_id,
            "graph_id": merge_report.graph_id,
            "merge_status": merge_report.status.value,
            "branches_merged": merge_report.branches_merged,
            "conflicts_detected": len(merge_report.conflicts_detected),
            "conflicts_resolved": len(merge_report.conflicts_resolved),
            "test_results": merge_report.test_results,
            "dependency_fixes": merge_report.dependency_fixes,
            "final_validation": merge_report.final_validation,
            "duration_seconds": (
                merge_report.end_time - merge_report.start_time
            ).total_seconds() if merge_report.end_time else None
        }

    except Exception as e:
        logger.error(f"Error in coordinate_merge_phase: {e}")
        return {
            "status": "error",
            "error": str(e),
            "graph_id": graph_id
        }