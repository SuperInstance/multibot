#!/usr/bin/env python3
"""
Merge Coordination MCP Tools
MCP tool integration for merge coordination functionality.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from merge_coordination import merge_coordinator, coordinate_merge_phase

logger = logging.getLogger(__name__)


@dataclass
class MergeCoordinationRequest:
    """Request for merge coordination."""
    graph_id: str
    worker_branches: List[Dict[str, Any]]
    merge_strategy: Optional[str] = "dependency_ordered"
    auto_resolve_conflicts: bool = True


@dataclass
class ConflictResolutionRequest:
    """Request for manual conflict resolution."""
    merge_id: str
    conflict_id: str
    resolution_strategy: str
    assigned_worker: Optional[str] = None


def register_merge_coordination_tools(mcp, orchestrator=None):
    """Register merge coordination tools with MCP server."""

    @mcp.tool()
    async def coordinate_merge_phase_tool(request: MergeCoordinationRequest) -> Dict[str, Any]:
        """
        Coordinate merging of parallel worker branches.

        Performs comprehensive merge coordination including:
        - Pre-merge conflict analysis
        - Automated conflict resolution where possible
        - Sequential or dependency-ordered merging
        - Post-merge validation and testing
        - Dependency issue detection and resolution

        Args:
            request: MergeCoordinationRequest with graph_id and worker branch info

        Returns:
            Detailed merge results and status
        """
        logger.info(f"Starting merge coordination for graph {request.graph_id}")

        try:
            # Set merge strategy on coordinator if provided
            if hasattr(merge_coordinator, 'default_strategy'):
                merge_coordinator.default_strategy = request.merge_strategy

            result = await coordinate_merge_phase(request.graph_id, request.worker_branches)

            # Enhanced result with additional details
            if result["status"] == "success":
                merge_report = merge_coordinator.get_merge_status(request.graph_id)
                if merge_report:
                    result.update({
                        "merge_report": {
                            "start_time": merge_report.start_time.isoformat(),
                            "end_time": merge_report.end_time.isoformat() if merge_report.end_time else None,
                            "conflicts_by_type": _group_conflicts_by_type(merge_report.conflicts_detected),
                            "test_summary": _summarize_test_results(merge_report.test_results),
                            "recommendations": _generate_merge_recommendations(merge_report)
                        }
                    })

            return result

        except Exception as e:
            logger.error(f"Error in coordinate_merge_phase_tool: {e}")
            return {
                "status": "error",
                "error": str(e),
                "graph_id": request.graph_id
            }

    @mcp.tool()
    async def get_merge_status(graph_id: str) -> Dict[str, Any]:
        """
        Get current status of merge operation for a graph.

        Args:
            graph_id: ID of the task graph

        Returns:
            Current merge status and progress information
        """
        try:
            merge_report = merge_coordinator.get_merge_status(graph_id)

            if not merge_report:
                return {
                    "status": "not_found",
                    "message": f"No merge operation found for graph {graph_id}"
                }

            return {
                "status": "success",
                "merge_id": merge_report.merge_id,
                "graph_id": merge_report.graph_id,
                "merge_status": merge_report.status.value,
                "progress": {
                    "branches_total": len(merge_report.branches_merged) +
                                    len([b for b in merge_report.conflicts_detected if b.workers_involved]),
                    "branches_merged": len(merge_report.branches_merged),
                    "conflicts_total": len(merge_report.conflicts_detected),
                    "conflicts_resolved": len(merge_report.conflicts_resolved)
                },
                "current_phase": _determine_current_phase(merge_report),
                "estimated_completion": _estimate_completion_time(merge_report),
                "issues": _get_current_issues(merge_report)
            }

        except Exception as e:
            logger.error(f"Error getting merge status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    async def list_active_merges() -> Dict[str, Any]:
        """
        List all currently active merge operations.

        Returns:
            Dictionary of active merges with their current status
        """
        try:
            active_merges = merge_coordinator.list_active_merges()

            merge_summaries = {}
            for graph_id, merge_report in active_merges.items():
                merge_summaries[graph_id] = {
                    "merge_id": merge_report.merge_id,
                    "status": merge_report.status.value,
                    "branches_merged": len(merge_report.branches_merged),
                    "conflicts_detected": len(merge_report.conflicts_detected),
                    "start_time": merge_report.start_time.isoformat(),
                    "duration_minutes": (
                        (merge_report.end_time or merge_report.start_time) - merge_report.start_time
                    ).total_seconds() / 60
                }

            return {
                "status": "success",
                "active_merges": merge_summaries,
                "total_active": len(active_merges)
            }

        except Exception as e:
            logger.error(f"Error listing active merges: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    async def resolve_merge_conflict(request: ConflictResolutionRequest) -> Dict[str, Any]:
        """
        Manually resolve or assign a merge conflict.

        Args:
            request: ConflictResolutionRequest with conflict details

        Returns:
            Result of conflict resolution attempt
        """
        try:
            merge_report = merge_coordinator.get_merge_status(request.merge_id.split('_')[-1])  # Extract graph_id

            if not merge_report:
                return {
                    "status": "error",
                    "error": f"Merge operation not found: {request.merge_id}"
                }

            # Find the specific conflict
            conflict = None
            for c in merge_report.conflicts_detected:
                if c.conflict_id == request.conflict_id:
                    conflict = c
                    break

            if not conflict:
                return {
                    "status": "error",
                    "error": f"Conflict not found: {request.conflict_id}"
                }

            # Apply resolution strategy
            if request.resolution_strategy == "auto_resolve":
                resolved = await merge_coordinator.conflict_resolver.resolve_conflict(
                    conflict, merge_coordinator.task_orchestrator
                )
                if resolved:
                    merge_report.conflicts_resolved.append(request.conflict_id)
                    return {
                        "status": "success",
                        "message": f"Conflict {request.conflict_id} automatically resolved"
                    }
                else:
                    return {
                        "status": "partial",
                        "message": f"Conflict {request.conflict_id} assigned to worker for manual resolution"
                    }

            elif request.resolution_strategy == "assign_worker":
                if request.assigned_worker:
                    conflict.assigned_worker = request.assigned_worker
                    await merge_coordinator.conflict_resolver._assign_conflict_to_worker(
                        conflict, merge_coordinator.task_orchestrator
                    )
                    return {
                        "status": "success",
                        "message": f"Conflict {request.conflict_id} assigned to worker {request.assigned_worker}"
                    }

            return {
                "status": "error",
                "error": f"Invalid resolution strategy: {request.resolution_strategy}"
            }

        except Exception as e:
            logger.error(f"Error resolving merge conflict: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    async def analyze_merge_conflicts(graph_id: str, worker_branches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze potential conflicts without performing merge.

        Args:
            graph_id: ID of the task graph
            worker_branches: List of worker branch information

        Returns:
            Detailed conflict analysis results
        """
        try:
            # Convert to WorkerBranch objects
            branches = [merge_coordinator._create_worker_branch(branch_data) for branch_data in worker_branches]

            # Analyze conflicts
            conflicts = await merge_coordinator.conflict_analyzer.analyze_conflicts(branches)

            conflict_summary = {
                "total_conflicts": len(conflicts),
                "auto_resolvable": len([c for c in conflicts if c.auto_resolvable]),
                "manual_resolution_needed": len([c for c in conflicts if not c.auto_resolvable]),
                "by_severity": _group_conflicts_by_severity(conflicts),
                "by_type": _group_conflicts_by_type(conflicts),
                "affected_files": list(set(
                    file_path for conflict in conflicts for file_path in conflict.files_involved
                )),
                "worker_conflicts": _analyze_worker_conflict_patterns(conflicts)
            }

            detailed_conflicts = [
                {
                    "conflict_id": c.conflict_id,
                    "type": c.conflict_type.value,
                    "severity": c.severity,
                    "description": c.description,
                    "files_involved": c.files_involved,
                    "workers_involved": c.workers_involved,
                    "auto_resolvable": c.auto_resolvable,
                    "resolution_strategy": c.resolution_strategy
                }
                for c in conflicts
            ]

            return {
                "status": "success",
                "graph_id": graph_id,
                "conflict_summary": conflict_summary,
                "detailed_conflicts": detailed_conflicts,
                "merge_recommendations": _generate_conflict_recommendations(conflicts, branches)
            }

        except Exception as e:
            logger.error(f"Error analyzing merge conflicts: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    async def cancel_merge_operation(graph_id: str, reason: str = "User requested") -> Dict[str, Any]:
        """
        Cancel an active merge operation.

        Args:
            graph_id: ID of the task graph
            reason: Reason for cancellation

        Returns:
            Cancellation result
        """
        try:
            merge_report = merge_coordinator.get_merge_status(graph_id)

            if not merge_report:
                return {
                    "status": "error",
                    "error": f"No active merge found for graph {graph_id}"
                }

            if merge_report.status.value in ["completed", "failed"]:
                return {
                    "status": "error",
                    "error": f"Cannot cancel merge with status: {merge_report.status.value}"
                }

            # Update merge status
            merge_report.status = merge_coordinator.MergeStatus.FAILED
            merge_report.end_time = merge_coordinator.datetime.now()

            # This would also clean up any ongoing merge processes
            logger.info(f"Cancelled merge operation for graph {graph_id}: {reason}")

            return {
                "status": "success",
                "message": f"Merge operation cancelled for graph {graph_id}",
                "reason": reason,
                "cancelled_at": merge_report.end_time.isoformat()
            }

        except Exception as e:
            logger.error(f"Error cancelling merge operation: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    return {
        "coordinate_merge_phase": coordinate_merge_phase_tool,
        "get_merge_status": get_merge_status,
        "list_active_merges": list_active_merges,
        "resolve_merge_conflict": resolve_merge_conflict,
        "analyze_merge_conflicts": analyze_merge_conflicts,
        "cancel_merge_operation": cancel_merge_operation
    }


# Helper functions for tools

def _group_conflicts_by_type(conflicts) -> Dict[str, int]:
    """Group conflicts by type."""
    conflict_types = {}
    for conflict in conflicts:
        conflict_type = conflict.conflict_type.value
        conflict_types[conflict_type] = conflict_types.get(conflict_type, 0) + 1
    return conflict_types


def _group_conflicts_by_severity(conflicts) -> Dict[str, int]:
    """Group conflicts by severity."""
    severities = {}
    for conflict in conflicts:
        severity = conflict.severity
        severities[severity] = severities.get(severity, 0) + 1
    return severities


def _summarize_test_results(test_results: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize test results across all branches."""
    if not test_results:
        return {"status": "no_tests_run"}

    total_tests = sum(result.get("total_tests", 0) for result in test_results.values())
    total_failed = sum(result.get("failed_tests", 0) for result in test_results.values())
    avg_coverage = sum(result.get("coverage", 0) for result in test_results.values()) / len(test_results)

    return {
        "total_branches": len(test_results),
        "all_passed": total_failed == 0,
        "total_tests": total_tests,
        "total_failed": total_failed,
        "average_coverage": round(avg_coverage, 1),
        "branch_results": {branch: result.get("passed", False) for branch, result in test_results.items()}
    }


def _generate_merge_recommendations(merge_report) -> List[str]:
    """Generate recommendations based on merge report."""
    recommendations = []

    if len(merge_report.conflicts_detected) > 5:
        recommendations.append("Consider breaking down tasks further to reduce conflicts")

    if merge_report.status.value == "failed":
        recommendations.append("Review task dependencies and file assignments")

    unresolved_conflicts = len(merge_report.conflicts_detected) - len(merge_report.conflicts_resolved)
    if unresolved_conflicts > 0:
        recommendations.append(f"Address {unresolved_conflicts} remaining conflicts before proceeding")

    if merge_report.dependency_fixes:
        recommendations.append("Run dependency fix tasks after merge completion")

    return recommendations


def _determine_current_phase(merge_report) -> str:
    """Determine current phase of merge operation."""
    if merge_report.status.value == "completed":
        return "completed"
    elif merge_report.status.value == "failed":
        return "failed"
    elif merge_report.conflicts_detected and not merge_report.conflicts_resolved:
        return "conflict_resolution"
    elif merge_report.branches_merged:
        return "post_merge_validation"
    else:
        return "pre_merge_analysis"


def _estimate_completion_time(merge_report) -> Optional[str]:
    """Estimate completion time for merge operation."""
    if merge_report.status.value in ["completed", "failed"]:
        return None

    # Simple estimation based on progress
    total_work = len(merge_report.conflicts_detected) + len(merge_report.branches_merged) + 2
    completed_work = len(merge_report.conflicts_resolved) + len(merge_report.branches_merged)

    if completed_work == 0:
        return "Unable to estimate"

    progress_ratio = completed_work / total_work
    elapsed_time = (merge_report.end_time or merge_report.start_time) - merge_report.start_time
    estimated_total = elapsed_time / progress_ratio

    remaining_time = estimated_total - elapsed_time
    return f"{int(remaining_time.total_seconds() / 60)} minutes"


def _get_current_issues(merge_report) -> List[str]:
    """Get current issues in merge operation."""
    issues = []

    if merge_report.status.value == "failed":
        issues.append("Merge operation has failed")

    unresolved_conflicts = len(merge_report.conflicts_detected) - len(merge_report.conflicts_resolved)
    if unresolved_conflicts > 0:
        issues.append(f"{unresolved_conflicts} unresolved conflicts")

    # Check test failures
    for branch, results in merge_report.test_results.items():
        if not results.get("passed", True):
            issues.append(f"Tests failed for branch {branch}")

    return issues


def _analyze_worker_conflict_patterns(conflicts) -> Dict[str, Any]:
    """Analyze conflict patterns between workers."""
    worker_pairs = {}
    for conflict in conflicts:
        workers = sorted(conflict.workers_involved)
        if len(workers) >= 2:
            pair = f"{workers[0]} <-> {workers[1]}"
            if pair not in worker_pairs:
                worker_pairs[pair] = 0
            worker_pairs[pair] += 1

    return {
        "most_conflicting_pairs": sorted(worker_pairs.items(), key=lambda x: x[1], reverse=True)[:3],
        "total_worker_pairs": len(worker_pairs)
    }


def _generate_conflict_recommendations(conflicts, branches) -> List[str]:
    """Generate recommendations for handling conflicts."""
    recommendations = []

    high_severity_conflicts = [c for c in conflicts if c.severity in ["high", "critical"]]
    if high_severity_conflicts:
        recommendations.append(f"Address {len(high_severity_conflicts)} high-severity conflicts first")

    auto_resolvable = [c for c in conflicts if c.auto_resolvable]
    if auto_resolvable:
        recommendations.append(f"Automatically resolve {len(auto_resolvable)} simple conflicts")

    file_conflicts = [c for c in conflicts if c.conflict_type.value == "file_conflict"]
    if len(file_conflicts) > 3:
        recommendations.append("Consider reorganizing file assignments to reduce conflicts")

    return recommendations