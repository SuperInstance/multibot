#!/usr/bin/env python3
"""
Task Orchestration MCP Tools
MCP tools for task decomposition, assignment, and orchestration.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastmcp import FastMCP
from pydantic import BaseModel

from task_decomposition import (
    TaskDecomposer,
    TaskOrchestrator,
    TaskGraph,
    SubTask,
    TaskComplexity,
    TaskType,
    TaskStatus
)

logger = logging.getLogger(__name__)


class TaskDecompositionRequest(BaseModel):
    """Request model for task decomposition."""
    task_description: str
    context: Optional[Dict[str, Any]] = {}
    priority: int = 5
    deadline: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = {}


class TaskAssignmentRequest(BaseModel):
    """Request model for manual task assignment."""
    task_id: str
    worker_id: str
    priority: int = 5


class TaskGraphStatus(BaseModel):
    """Status information for a task graph."""
    graph_id: str
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    pending_tasks: int
    failed_tasks: int
    progress_percentage: float
    estimated_completion: Optional[str]


def register_task_orchestration_tools(mcp: FastMCP, orchestrator):
    """Register task orchestration tools with the MCP server."""

    # Initialize task decomposition components
    task_decomposer = TaskDecomposer()
    task_orchestrator = TaskOrchestrator(
        orchestrator.message_queue,
        orchestrator.worker_lifecycle
    )

    # Store active task graphs for status tracking
    active_graphs: Dict[str, TaskGraph] = {}

    @mcp.tool()
    async def decompose_and_assign(request: TaskDecompositionRequest) -> Dict[str, Any]:
        """
        Decompose a complex task into subtasks and assign to workers.

        This is the main orchestration tool that breaks down complex tasks,
        creates dependency graphs, and coordinates execution across workers.

        Args:
            task_description: Description of the complex task to decompose
            context: Additional context for task decomposition
            priority: Task priority (1-9)
            deadline: Optional deadline for task completion
            constraints: Optional constraints (worker preferences, etc.)

        Returns:
            Task graph information and execution status
        """
        try:
            logger.info(f"Decomposing and assigning task: {request.task_description}")

            # Generate unique graph ID
            graph_id = f"graph_{uuid.uuid4().hex[:8]}"

            # Decompose the task
            task_graph = await task_decomposer.decompose_task(
                request.task_description,
                request.context
            )

            # Store the graph
            active_graphs[graph_id] = task_graph

            # Start task execution
            execution_id = await task_orchestrator.execute_task_graph(graph_id, task_graph)

            # Prepare response
            response = {
                "status": "success",
                "graph_id": graph_id,
                "execution_id": execution_id,
                "decomposition_summary": {
                    "total_tasks": len(task_graph.tasks),
                    "phases": len(task_graph.phases),
                    "estimated_tokens": task_graph.total_estimated_tokens,
                    "estimated_duration_minutes": task_graph.total_estimated_duration,
                    "parallelization_factor": task_graph.parallelization_factor,
                    "critical_path_length": len(task_graph.critical_path)
                },
                "task_breakdown": [
                    {
                        "task_id": task.task_id,
                        "title": task.title,
                        "type": task.task_type.value,
                        "complexity": task.complexity.value,
                        "preferred_model": task.preferred_model,
                        "phase": task.phase,
                        "estimated_tokens": task.estimated_tokens,
                        "estimated_duration": task.estimated_duration,
                        "dependencies": task.dependencies
                    }
                    for task in task_graph.tasks.values()
                ],
                "execution_phases": [
                    {
                        "phase": i,
                        "tasks": phase_tasks,
                        "parallel_execution": True
                    }
                    for i, phase_tasks in enumerate(task_graph.phases)
                ]
            }

            logger.info(f"Task decomposed into {len(task_graph.tasks)} subtasks across {len(task_graph.phases)} phases")

            return response

        except Exception as e:
            logger.error(f"Error in decompose_and_assign: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error_message": str(e),
                "error_type": type(e).__name__
            }

    @mcp.tool()
    async def get_task_graph_status(graph_id: str) -> Dict[str, Any]:
        """
        Get the current status of a task graph execution.

        Args:
            graph_id: ID of the task graph to check

        Returns:
            Current status and progress information
        """
        try:
            if graph_id not in active_graphs:
                return {
                    "status": "error",
                    "error_message": f"Task graph {graph_id} not found"
                }

            task_graph = active_graphs[graph_id]
            completed_tasks = task_orchestrator.completed_tasks.get(graph_id, set())

            # Calculate status metrics
            total_tasks = len(task_graph.tasks)
            completed_count = len(completed_tasks)
            in_progress_count = len([tid for tid in task_orchestrator.task_assignments
                                   if tid in task_graph.tasks])
            pending_count = total_tasks - completed_count - in_progress_count

            progress_percentage = (completed_count / total_tasks * 100) if total_tasks > 0 else 0

            # Estimate completion time
            estimated_completion = None
            if completed_count > 0 and in_progress_count > 0:
                # Simple linear projection
                elapsed_time = datetime.now()  # Would need actual start time
                estimated_total_time = task_graph.total_estimated_duration
                remaining_time = estimated_total_time * (1 - progress_percentage / 100)
                estimated_completion = (datetime.now()).isoformat()

            return {
                "status": "success",
                "graph_id": graph_id,
                "total_tasks": total_tasks,
                "completed_tasks": completed_count,
                "in_progress_tasks": in_progress_count,
                "pending_tasks": pending_count,
                "failed_tasks": 0,  # Would track failures
                "progress_percentage": round(progress_percentage, 2),
                "estimated_completion": estimated_completion,
                "task_details": [
                    {
                        "task_id": task_id,
                        "title": task.title,
                        "status": "completed" if task_id in completed_tasks
                                else "in_progress" if task_id in task_orchestrator.task_assignments
                                else "pending",
                        "assigned_worker": task_orchestrator.task_assignments.get(task_id),
                        "phase": task.phase,
                        "complexity": task.complexity.value
                    }
                    for task_id, task in task_graph.tasks.items()
                ],
                "phase_progress": [
                    {
                        "phase": i,
                        "total_tasks": len(phase_tasks),
                        "completed_tasks": len([tid for tid in phase_tasks if tid in completed_tasks]),
                        "task_ids": phase_tasks
                    }
                    for i, phase_tasks in enumerate(task_graph.phases)
                ]
            }

        except Exception as e:
            logger.error(f"Error getting task graph status: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e)
            }

    @mcp.tool()
    async def list_active_task_graphs() -> Dict[str, Any]:
        """
        List all currently active task graphs.

        Returns:
            List of active task graphs with summary information
        """
        try:
            graphs_info = []

            for graph_id, task_graph in active_graphs.items():
                completed_tasks = task_orchestrator.completed_tasks.get(graph_id, set())
                total_tasks = len(task_graph.tasks)
                completed_count = len(completed_tasks)

                graphs_info.append({
                    "graph_id": graph_id,
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_count,
                    "progress_percentage": round((completed_count / total_tasks * 100) if total_tasks > 0 else 0, 2),
                    "phases": len(task_graph.phases),
                    "estimated_total_duration": task_graph.total_estimated_duration,
                    "estimated_total_tokens": task_graph.total_estimated_tokens,
                    "critical_path_tasks": len(task_graph.critical_path)
                })

            return {
                "status": "success",
                "active_graphs": graphs_info,
                "total_active_graphs": len(graphs_info)
            }

        except Exception as e:
            logger.error(f"Error listing active task graphs: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e),
                "active_graphs": []
            }

    @mcp.tool()
    async def manually_assign_task(request: TaskAssignmentRequest) -> Dict[str, Any]:
        """
        Manually assign a specific task to a specific worker.

        This overrides the automatic assignment logic for special cases.

        Args:
            task_id: ID of the task to assign
            worker_id: ID of the worker to assign to
            priority: Priority level for the assignment

        Returns:
            Assignment confirmation
        """
        try:
            # Find the task in active graphs
            task_found = False
            task_graph = None

            for graph_id, graph in active_graphs.items():
                if request.task_id in graph.tasks:
                    task_graph = graph
                    task_found = True
                    break

            if not task_found:
                return {
                    "status": "error",
                    "error_message": f"Task {request.task_id} not found in any active graph"
                }

            # Check if worker is available
            available_workers = await task_orchestrator._get_available_workers()
            if request.worker_id not in available_workers:
                return {
                    "status": "warning",
                    "message": f"Worker {request.worker_id} may not be available",
                    "proceeding": True
                }

            # Assign the task
            await task_orchestrator._assign_task_to_worker(
                request.task_id,
                request.worker_id,
                task_graph
            )

            task_orchestrator.task_assignments[request.task_id] = request.worker_id

            return {
                "status": "success",
                "message": f"Task {request.task_id} manually assigned to worker {request.worker_id}",
                "task_id": request.task_id,
                "worker_id": request.worker_id,
                "assignment_time": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in manual task assignment: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e)
            }

    @mcp.tool()
    async def get_task_dependencies(task_id: str) -> Dict[str, Any]:
        """
        Get dependency information for a specific task.

        Args:
            task_id: ID of the task to analyze

        Returns:
            Dependency graph information for the task
        """
        try:
            # Find the task in active graphs
            for graph_id, task_graph in active_graphs.items():
                if task_id in task_graph.tasks:
                    task = task_graph.tasks[task_id]

                    # Find dependent tasks (tasks that depend on this one)
                    dependent_tasks = []
                    for other_id, other_task in task_graph.tasks.items():
                        if task_id in other_task.dependencies:
                            dependent_tasks.append({
                                "task_id": other_id,
                                "title": other_task.title,
                                "type": other_task.task_type.value
                            })

                    return {
                        "status": "success",
                        "task_id": task_id,
                        "title": task.title,
                        "dependencies": [
                            {
                                "task_id": dep_id,
                                "title": task_graph.tasks[dep_id].title,
                                "type": task_graph.tasks[dep_id].task_type.value
                            }
                            for dep_id in task.dependencies
                            if dep_id in task_graph.tasks
                        ],
                        "dependent_tasks": dependent_tasks,
                        "phase": task.phase,
                        "critical_path": task_id in task_graph.critical_path
                    }

            return {
                "status": "error",
                "error_message": f"Task {task_id} not found"
            }

        except Exception as e:
            logger.error(f"Error getting task dependencies: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e)
            }

    @mcp.tool()
    async def cancel_task_graph(graph_id: str, reason: str = "Cancelled by user") -> Dict[str, Any]:
        """
        Cancel an active task graph execution.

        Args:
            graph_id: ID of the task graph to cancel
            reason: Reason for cancellation

        Returns:
            Cancellation confirmation
        """
        try:
            if graph_id not in active_graphs:
                return {
                    "status": "error",
                    "error_message": f"Task graph {graph_id} not found"
                }

            task_graph = active_graphs[graph_id]

            # Cancel all in-progress tasks
            cancelled_tasks = []
            for task_id, worker_id in task_orchestrator.task_assignments.items():
                if task_id in task_graph.tasks:
                    # Send cancellation message to worker
                    await orchestrator.message_queue.send_message(
                        from_id="master",
                        to_id=worker_id,
                        message_type="task_cancel",
                        content={
                            "task_id": task_id,
                            "reason": reason
                        },
                        priority=8
                    )
                    cancelled_tasks.append(task_id)

            # Clean up
            if graph_id in task_orchestrator.active_task_graphs:
                del task_orchestrator.active_task_graphs[graph_id]
            if graph_id in task_orchestrator.completed_tasks:
                del task_orchestrator.completed_tasks[graph_id]

            # Remove from active graphs
            del active_graphs[graph_id]

            return {
                "status": "success",
                "message": f"Task graph {graph_id} cancelled",
                "cancelled_tasks": cancelled_tasks,
                "reason": reason,
                "cancellation_time": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error cancelling task graph: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e)
            }

    @mcp.tool()
    async def analyze_task_complexity(task_description: str) -> Dict[str, Any]:
        """
        Analyze task complexity without creating a full decomposition.

        Useful for estimation and planning before committing to task execution.

        Args:
            task_description: Description of the task to analyze

        Returns:
            Complexity analysis and estimates
        """
        try:
            # Use the task decomposer's analysis methods
            analysis = await task_decomposer._analyze_task_description(task_description, {})

            # Generate a minimal decomposition for estimation
            task_graph = await task_decomposer.decompose_task(task_description, {})

            complexity_distribution = {}
            for task in task_graph.tasks.values():
                complexity = task.complexity.value
                if complexity not in complexity_distribution:
                    complexity_distribution[complexity] = 0
                complexity_distribution[complexity] += 1

            model_distribution = {}
            for task in task_graph.tasks.values():
                model = task.preferred_model
                if model not in model_distribution:
                    model_distribution[model] = 0
                model_distribution[model] += 1

            return {
                "status": "success",
                "task_description": task_description,
                "analysis": {
                    "task_type": analysis.get("task_type", "unknown"),
                    "overall_complexity": analysis.get("complexity_level", "unknown"),
                    "identified_technologies": analysis.get("technologies", []),
                    "keywords": analysis.get("keywords", [])
                },
                "estimates": {
                    "total_subtasks": len(task_graph.tasks),
                    "total_estimated_tokens": task_graph.total_estimated_tokens,
                    "total_estimated_duration_minutes": task_graph.total_estimated_duration,
                    "phases_required": len(task_graph.phases),
                    "parallelization_factor": task_graph.parallelization_factor
                },
                "complexity_distribution": complexity_distribution,
                "model_distribution": model_distribution,
                "resource_requirements": {
                    "opus_workers": model_distribution.get("opus", 0),
                    "sonnet_workers": model_distribution.get("sonnet", 0),
                    "haiku_workers": model_distribution.get("haiku", 0)
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing task complexity: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e)
            }

    @mcp.tool()
    async def get_task_execution_recommendations(
        task_description: str,
        available_workers: Optional[List[str]] = None,
        time_constraints: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get recommendations for optimal task execution strategy.

        Args:
            task_description: Description of the task
            available_workers: List of available worker IDs (optional)
            time_constraints: Time constraint in minutes (optional)

        Returns:
            Execution strategy recommendations
        """
        try:
            # Analyze the task
            complexity_analysis = await analyze_task_complexity(task_description)

            if complexity_analysis["status"] != "success":
                return complexity_analysis

            estimates = complexity_analysis["estimates"]
            model_requirements = complexity_analysis["resource_requirements"]

            # Get current worker availability if not provided
            if available_workers is None:
                available_workers = await task_orchestrator._get_available_workers()

            # Analyze worker capabilities
            worker_models = {}
            if orchestrator.worker_lifecycle:
                worker_states = await orchestrator.worker_lifecycle.get_all_worker_states()
                for worker_id in available_workers:
                    if worker_id in worker_states:
                        worker_models[worker_id] = worker_states[worker_id].get("model", "sonnet")

            # Count available models
            available_models = {"opus": 0, "sonnet": 0, "haiku": 0}
            for model in worker_models.values():
                if model in available_models:
                    available_models[model] += 1

            # Generate recommendations
            recommendations = []
            warnings = []

            # Check if we have required models
            for model, required in model_requirements.items():
                available = available_models.get(model, 0)
                if required > available:
                    warnings.append(f"Need {required} {model} workers, but only {available} available")
                    recommendations.append(f"Consider spawning {required - available} additional {model} workers")

            # Time constraint analysis
            if time_constraints and estimates["total_estimated_duration_minutes"] > time_constraints:
                recommendations.append(f"Task estimated at {estimates['total_estimated_duration_minutes']} minutes, "
                                     f"exceeds constraint of {time_constraints} minutes")
                recommendations.append("Consider breaking task into smaller chunks or adding more workers")

            # Optimal execution strategy
            strategy = "parallel" if estimates["parallelization_factor"] > 1.5 else "sequential"

            return {
                "status": "success",
                "task_description": task_description,
                "execution_strategy": strategy,
                "estimated_duration": estimates["total_estimated_duration_minutes"],
                "worker_requirements": model_requirements,
                "available_workers": len(available_workers),
                "available_by_model": available_models,
                "recommendations": recommendations,
                "warnings": warnings,
                "feasibility": "feasible" if not warnings else "challenging",
                "optimal_worker_count": sum(model_requirements.values())
            }

        except Exception as e:
            logger.error(f"Error generating execution recommendations: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e)
            }

    # Hook into task completion events
    original_mark_complete = task_orchestrator.mark_task_completed

    async def enhanced_mark_complete(task_id: str):
        """Enhanced task completion handler."""
        await original_mark_complete(task_id)

        # Update any web dashboard or monitoring systems
        logger.info(f"Task {task_id} completed and next phase triggered")

    task_orchestrator.mark_task_completed = enhanced_mark_complete

    logger.info("Task orchestration tools registered successfully")

    return {
        "decompose_and_assign": decompose_and_assign,
        "get_task_graph_status": get_task_graph_status,
        "list_active_task_graphs": list_active_task_graphs,
        "manually_assign_task": manually_assign_task,
        "get_task_dependencies": get_task_dependencies,
        "cancel_task_graph": cancel_task_graph,
        "analyze_task_complexity": analyze_task_complexity,
        "get_task_execution_recommendations": get_task_execution_recommendations
    }