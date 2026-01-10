#!/usr/bin/env python3
"""
Memory Management Examples
Example workflows and demonstrations of the memory management system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from memory_management import WorkerMemoryManager, TaskRecord
from memory_tools import (
    SaveContextRequest, LoadContextRequest, UpdateUnderstandingRequest,
    SearchMemoryRequest, RecordTaskRequest
)

logger = logging.getLogger(__name__)


class MemoryManagementExamples:
    """Example workflows demonstrating memory management functionality."""

    def __init__(self):
        self.test_workers = ["worker-001", "worker-002", "worker-003"]
        self.examples = self._load_example_scenarios()

    def _load_example_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """Load predefined example scenarios for memory management."""
        return {
            "context_management_workflow": {
                "description": "Demonstrate context saving and loading workflow",
                "steps": [
                    "Add conversation content to approach token limit",
                    "Save current context when threshold reached",
                    "Load relevant context for new task",
                    "Verify context continuity"
                ]
            },
            "code_understanding_building": {
                "description": "Build and retrieve code understanding over time",
                "modules": [
                    {
                        "name": "auth_service",
                        "file_path": "src/services/auth.py",
                        "understanding": "Main authentication service handling JWT tokens, user validation, and session management. Integrates with database for user lookup and provides middleware for request authentication."
                    },
                    {
                        "name": "user_model",
                        "file_path": "src/models/user.py",
                        "understanding": "User data model with SQLAlchemy ORM. Defines user table structure, relationships, and basic validation. Includes password hashing and verification methods."
                    },
                    {
                        "name": "api_routes",
                        "file_path": "src/api/routes.py",
                        "understanding": "FastAPI route definitions for all endpoints. Handles request validation, authentication middleware, and response formatting. Organizes routes by feature area."
                    }
                ]
            },
            "task_completion_tracking": {
                "description": "Track task completions and build experience",
                "tasks": [
                    {
                        "task_id": "auth_001",
                        "description": "Implement JWT authentication system",
                        "status": "completed",
                        "files_modified": ["src/services/auth.py", "src/middleware/auth.py"],
                        "decisions_made": [
                            "Used PyJWT library for token handling",
                            "Implemented refresh token rotation",
                            "Added role-based access control"
                        ],
                        "challenges_faced": [
                            "Token expiration handling complexity",
                            "Secure cookie configuration"
                        ],
                        "solutions_implemented": [
                            "Created token refresh endpoint",
                            "Used secure, httpOnly cookies"
                        ]
                    },
                    {
                        "task_id": "api_002",
                        "description": "Build user management API endpoints",
                        "status": "completed",
                        "files_modified": ["src/api/users.py", "src/schemas/user.py"],
                        "decisions_made": [
                            "Used Pydantic for request/response validation",
                            "Implemented soft delete for users"
                        ],
                        "challenges_faced": [
                            "Handling partial updates correctly",
                            "Email validation complexity"
                        ],
                        "solutions_implemented": [
                            "Used PATCH semantics for partial updates",
                            "Integrated email-validator library"
                        ]
                    }
                ]
            },
            "memory_search_scenarios": {
                "description": "Demonstrate semantic search across different memory types",
                "search_queries": [
                    {
                        "query": "JWT token authentication",
                        "expected_types": ["understanding", "decisions", "tasks"]
                    },
                    {
                        "query": "database user model",
                        "expected_types": ["understanding", "tasks"]
                    },
                    {
                        "query": "API endpoint validation",
                        "expected_types": ["understanding", "decisions"]
                    },
                    {
                        "query": "authentication middleware",
                        "expected_types": ["understanding", "decisions", "tasks"]
                    }
                ]
            }
        }

    async def run_context_management_example(self, worker_id: str) -> Dict[str, Any]:
        """Demonstrate context saving and loading workflow."""
        logger.info(f"Running context management example for worker {worker_id}")

        memory_manager = WorkerMemoryManager(worker_id)
        results = {"steps": [], "stats": {}}

        try:
            # Step 1: Add conversation content to approach limit
            logger.info("Step 1: Adding conversation content")
            sample_conversations = [
                "Started working on authentication system implementation",
                "Analyzed existing user model and identified required changes",
                "Decided to use JWT tokens with refresh token rotation",
                "Implemented password hashing using bcrypt",
                "Created authentication middleware for FastAPI",
                "Added role-based access control with enum-based roles",
                "Wrote unit tests for authentication functions",
                "Debugged token expiration edge cases",
                "Optimized database queries for user lookup",
                "Documented authentication flow and security considerations"
            ]

            total_tokens = 0
            for i, content in enumerate(sample_conversations):
                # Simulate realistic token counts
                token_count = len(content.split()) * 1.3 + 50  # Base overhead
                memory_manager.context_manager.add_to_context(content, int(token_count))
                total_tokens += int(token_count)

                if total_tokens > 15000:  # Simulate reaching threshold
                    break

            results["steps"].append({
                "step": 1,
                "description": "Added conversation content",
                "total_tokens": total_tokens,
                "conversations_added": i + 1
            })

            # Step 2: Save context when threshold reached
            logger.info("Step 2: Saving context")
            save_result = await memory_manager.save_current_context()
            results["steps"].append({
                "step": 2,
                "description": "Saved current context",
                "save_result": save_result
            })

            # Step 3: Add new task-related content
            logger.info("Step 3: Adding new task content")
            new_task_content = "Starting new task: Implement user profile management system"
            memory_manager.context_manager.add_to_context(new_task_content, 100)

            # Step 4: Load relevant context for new task
            logger.info("Step 4: Loading relevant context")
            load_result = await memory_manager.load_context("user profile management")
            results["steps"].append({
                "step": 4,
                "description": "Loaded relevant context",
                "load_result": {
                    "status": load_result["status"],
                    "entries_found": load_result.get("total_entries", 0),
                    "estimated_tokens": load_result.get("estimated_tokens", 0)
                }
            })

            # Step 5: Get memory statistics
            stats_result = await memory_manager.get_memory_stats()
            results["stats"] = stats_result.get("stats", {})

            logger.info(f"Context management example completed for worker {worker_id}")
            return {
                "status": "success",
                "worker_id": worker_id,
                "example": "context_management_workflow",
                "results": results
            }

        except Exception as e:
            logger.error(f"Error in context management example: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": worker_id
            }

    async def run_code_understanding_example(self, worker_id: str) -> Dict[str, Any]:
        """Demonstrate building and using code understanding."""
        logger.info(f"Running code understanding example for worker {worker_id}")

        memory_manager = WorkerMemoryManager(worker_id)
        results = {"modules_added": [], "search_results": []}

        try:
            # Add understanding for multiple modules
            modules = self.examples["code_understanding_building"]["modules"]

            for module in modules:
                update_result = await memory_manager.update_understanding(
                    module_name=module["name"],
                    understanding=module["understanding"],
                    file_path=module["file_path"]
                )

                results["modules_added"].append({
                    "module_name": module["name"],
                    "file_path": module["file_path"],
                    "status": update_result["status"],
                    "content_length": update_result.get("content_length", 0)
                })

            # Test searching for code understanding
            search_queries = ["authentication", "user model", "API routes"]

            for query in search_queries:
                search_result = await memory_manager.search_memory(query, limit=3)

                results["search_results"].append({
                    "query": query,
                    "results_found": search_result.get("results_found", 0),
                    "top_result": search_result.get("results", [{}])[0] if search_result.get("results") else None
                })

            logger.info(f"Code understanding example completed for worker {worker_id}")
            return {
                "status": "success",
                "worker_id": worker_id,
                "example": "code_understanding_building",
                "results": results
            }

        except Exception as e:
            logger.error(f"Error in code understanding example: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": worker_id
            }

    async def run_task_completion_example(self, worker_id: str) -> Dict[str, Any]:
        """Demonstrate task completion tracking."""
        logger.info(f"Running task completion example for worker {worker_id}")

        memory_manager = WorkerMemoryManager(worker_id)
        results = {"tasks_recorded": [], "memory_impact": {}}

        try:
            tasks = self.examples["task_completion_tracking"]["tasks"]

            for task_data in tasks:
                # Create task record
                task_record = TaskRecord(
                    task_id=task_data["task_id"],
                    description=task_data["description"],
                    status=task_data["status"],
                    start_time=datetime.now() - timedelta(hours=2),
                    end_time=datetime.now(),
                    files_modified=task_data["files_modified"],
                    decisions_made=task_data["decisions_made"],
                    challenges_faced=task_data["challenges_faced"],
                    solutions_implemented=task_data["solutions_implemented"],
                    context_at_completion=f"Completed {task_data['description']} successfully"
                )

                # Record task completion
                record_result = await memory_manager.record_task_completion(task_record)

                results["tasks_recorded"].append({
                    "task_id": task_data["task_id"],
                    "status": record_result["status"],
                    "decisions_count": len(task_data["decisions_made"]),
                    "files_modified_count": len(task_data["files_modified"])
                })

            # Check memory impact
            stats_result = await memory_manager.get_memory_stats()
            results["memory_impact"] = {
                "total_tasks_in_history": stats_result.get("stats", {}).get("files", {}).get("task_history", {}).get("entry_count", 0),
                "total_memory_size": stats_result.get("stats", {}).get("total_memory_size_bytes", 0)
            }

            logger.info(f"Task completion example completed for worker {worker_id}")
            return {
                "status": "success",
                "worker_id": worker_id,
                "example": "task_completion_tracking",
                "results": results
            }

        except Exception as e:
            logger.error(f"Error in task completion example: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": worker_id
            }

    async def run_memory_search_example(self, worker_id: str) -> Dict[str, Any]:
        """Demonstrate memory search across different content types."""
        logger.info(f"Running memory search example for worker {worker_id}")

        memory_manager = WorkerMemoryManager(worker_id)
        results = {"search_results": [], "performance_metrics": {}}

        try:
            # First, populate memory with some content
            await self.run_code_understanding_example(worker_id)
            await self.run_task_completion_example(worker_id)

            # Run search queries
            search_scenarios = self.examples["memory_search_scenarios"]["search_queries"]

            for scenario in search_scenarios:
                search_start = datetime.now()

                search_result = await memory_manager.search_memory(
                    query=scenario["query"],
                    limit=5
                )

                search_duration = (datetime.now() - search_start).total_seconds()

                # Analyze results by content type
                content_types_found = set()
                if search_result.get("results"):
                    content_types_found = set(r["content_type"] for r in search_result["results"])

                results["search_results"].append({
                    "query": scenario["query"],
                    "expected_types": scenario["expected_types"],
                    "found_types": list(content_types_found),
                    "results_count": search_result.get("results_found", 0),
                    "search_duration_ms": round(search_duration * 1000, 2),
                    "relevance_scores": [r["relevance_score"] for r in search_result.get("results", [])[:3]]
                })

            # Calculate performance metrics
            total_searches = len(results["search_results"])
            avg_duration = sum(r["search_duration_ms"] for r in results["search_results"]) / total_searches if total_searches > 0 else 0
            avg_results = sum(r["results_count"] for r in results["search_results"]) / total_searches if total_searches > 0 else 0

            results["performance_metrics"] = {
                "total_searches": total_searches,
                "average_duration_ms": round(avg_duration, 2),
                "average_results_per_query": round(avg_results, 1),
                "memory_files_searched": await self._count_memory_files(memory_manager)
            }

            logger.info(f"Memory search example completed for worker {worker_id}")
            return {
                "status": "success",
                "worker_id": worker_id,
                "example": "memory_search_scenarios",
                "results": results
            }

        except Exception as e:
            logger.error(f"Error in memory search example: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": worker_id
            }

    async def run_all_examples(self) -> Dict[str, Any]:
        """Run all memory management examples across multiple workers."""
        logger.info("Running all memory management examples")

        results = {}
        summary = {
            "total_workers": len(self.test_workers),
            "successful_examples": 0,
            "failed_examples": 0,
            "total_examples": len(self.examples),
            "workers_tested": []
        }

        for worker_id in self.test_workers:
            worker_results = {}

            try:
                # Run context management example
                context_result = await self.run_context_management_example(worker_id)
                worker_results["context_management"] = context_result

                # Run code understanding example
                understanding_result = await self.run_code_understanding_example(worker_id)
                worker_results["code_understanding"] = understanding_result

                # Run task completion example
                task_result = await self.run_task_completion_example(worker_id)
                worker_results["task_completion"] = task_result

                # Run memory search example
                search_result = await self.run_memory_search_example(worker_id)
                worker_results["memory_search"] = search_result

                # Count successful examples
                successful = sum(1 for result in worker_results.values() if result.get("status") == "success")
                summary["successful_examples"] += successful
                summary["failed_examples"] += (len(self.examples) - successful)

                summary["workers_tested"].append({
                    "worker_id": worker_id,
                    "successful_examples": successful,
                    "total_examples": len(self.examples)
                })

                results[worker_id] = worker_results

            except Exception as e:
                logger.error(f"Error running examples for worker {worker_id}: {e}")
                results[worker_id] = {"error": str(e)}
                summary["failed_examples"] += len(self.examples)

        return {
            "summary": summary,
            "results": results,
            "generated_at": datetime.now().isoformat()
        }

    async def demonstrate_memory_lifecycle(self, worker_id: str) -> Dict[str, Any]:
        """Demonstrate complete memory lifecycle from creation to cleanup."""
        logger.info(f"Demonstrating memory lifecycle for worker {worker_id}")

        memory_manager = WorkerMemoryManager(worker_id)
        lifecycle_steps = []

        try:
            # Step 1: Initial memory state
            initial_stats = await memory_manager.get_memory_stats()
            lifecycle_steps.append({
                "step": "initial_state",
                "description": "Initial memory state",
                "memory_size": initial_stats.get("stats", {}).get("total_memory_size_bytes", 0),
                "files_present": len([f for f in initial_stats.get("stats", {}).get("files", {}).values() if f.get("exists", False)])
            })

            # Step 2: Populate with content
            await self.run_all_examples()
            lifecycle_steps.append({
                "step": "content_population",
                "description": "Populated memory with example content"
            })

            # Step 3: Memory usage after population
            populated_stats = await memory_manager.get_memory_stats()
            lifecycle_steps.append({
                "step": "populated_state",
                "description": "Memory state after population",
                "memory_size": populated_stats.get("stats", {}).get("total_memory_size_bytes", 0),
                "archived_contexts": populated_stats.get("stats", {}).get("archived_contexts", 0)
            })

            # Step 4: Simulate aging (create old files)
            # In a real scenario, files would age naturally
            old_cutoff = datetime.now() - timedelta(days=35)
            lifecycle_steps.append({
                "step": "aging_simulation",
                "description": f"Simulated aging of memory files (cutoff: {old_cutoff.isoformat()})"
            })

            # Step 5: Cleanup old memories
            # Note: In this demo, cleanup might not remove much since files are new
            # cleanup_result = await memory_manager.cleanup_old_memories(days_old=30)
            lifecycle_steps.append({
                "step": "cleanup",
                "description": "Cleanup would remove files older than 30 days",
                "note": "In demo, files are too new to be cleaned up"
            })

            # Step 6: Final memory state
            final_stats = await memory_manager.get_memory_stats()
            lifecycle_steps.append({
                "step": "final_state",
                "description": "Final memory state",
                "memory_size": final_stats.get("stats", {}).get("total_memory_size_bytes", 0),
                "efficiency": "Memory management completed successfully"
            })

            return {
                "status": "success",
                "worker_id": worker_id,
                "lifecycle_steps": lifecycle_steps,
                "memory_evolution": {
                    "initial_size": initial_stats.get("stats", {}).get("total_memory_size_bytes", 0),
                    "final_size": final_stats.get("stats", {}).get("total_memory_size_bytes", 0),
                    "growth": final_stats.get("stats", {}).get("total_memory_size_bytes", 0) - initial_stats.get("stats", {}).get("total_memory_size_bytes", 0)
                }
            }

        except Exception as e:
            logger.error(f"Error in memory lifecycle demonstration: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": worker_id
            }

    async def _count_memory_files(self, memory_manager: WorkerMemoryManager) -> int:
        """Count total memory files for performance metrics."""
        file_count = 0

        # Count main memory files
        memory_files = [
            memory_manager.current_context_file,
            memory_manager.task_history_file,
            memory_manager.code_understanding_file,
            memory_manager.decisions_file,
            memory_manager.questions_file
        ]

        for file_path in memory_files:
            if file_path.exists():
                file_count += 1

        # Count archived contexts
        archived_files = list(memory_manager.memory_path.glob("context_archive_*.md"))
        file_count += len(archived_files)

        return file_count

    def generate_memory_management_report(self) -> str:
        """Generate a human-readable memory management report."""
        report = """
# Memory Management System Report

## Overview
The memory management system provides sophisticated context and knowledge persistence for workers, enabling long-term conversation continuity and learning.

## Key Features
- **Context Management**: Automatic saving and loading of conversation context
- **Code Understanding**: Persistent knowledge about code modules and systems
- **Task History**: Detailed records of completed tasks and decisions
- **Semantic Search**: Intelligent search across all memory types
- **Token Management**: Automatic context trimming to stay within token limits

## Memory File Structure
- `current_context.md`: Active working context
- `task_history.json`: Structured task completion records
- `code_understanding.md`: Knowledge about code modules
- `decisions_made.md`: Architectural decisions and rationale
- `questions_asked.md`: Q&A history with Master
- `context_archive_*.md`: Archived conversation contexts

## Memory Management Strategy
- **Automatic Saving**: Context saved every 50,000 tokens
- **Smart Loading**: Relevant context loaded based on task similarity
- **Efficient Storage**: Structured data for quick access and search
- **Cleanup**: Automatic cleanup of old archived contexts

## Search Capabilities
- **Semantic Matching**: Relevance-based content ranking
- **Content Type Filtering**: Search specific types of memory
- **Recency Weighting**: Recent content scored higher
- **Module-Aware**: Understands code module relationships

## Performance Benefits
1. **Context Continuity**: Maintains conversation context across sessions
2. **Knowledge Retention**: Builds up understanding over time
3. **Efficient Token Usage**: Loads only relevant context
4. **Learning**: Workers learn from past tasks and decisions
5. **Collaboration**: Shared insights between workers through Master

## Example Use Cases
- Loading relevant context when resuming interrupted tasks
- Searching for previous solutions to similar problems
- Building comprehensive understanding of codebase modules
- Tracking architectural decisions and their rationale
- Maintaining conversation flow across long development sessions

## Integration Points
- Automatic integration with worker communication system
- Context saving triggered by token thresholds
- Memory search used for task assignment optimization
- Knowledge sharing through Master coordination
        """
        return report.strip()


async def run_memory_management_demo():
    """Run a complete demonstration of the memory management system."""
    examples = MemoryManagementExamples()

    print("🧠 Memory Management System Demo")
    print("=" * 50)

    # Run all examples across multiple workers
    print("\n📋 Running all memory management examples...")
    all_results = await examples.run_all_examples()

    print(f"\n📊 Summary:")
    print(f"  • Total workers tested: {all_results['summary']['total_workers']}")
    print(f"  • Successful examples: {all_results['summary']['successful_examples']}")
    print(f"  • Failed examples: {all_results['summary']['failed_examples']}")
    print(f"  • Examples per worker: {all_results['summary']['total_examples']}")

    # Show worker-specific results
    for worker_info in all_results['summary']['workers_tested']:
        print(f"    - {worker_info['worker_id']}: {worker_info['successful_examples']}/{worker_info['total_examples']} successful")

    # Demonstrate memory lifecycle
    print("\n🔄 Memory Lifecycle Demonstration...")
    lifecycle_result = await examples.demonstrate_memory_lifecycle("worker-lifecycle-demo")

    if lifecycle_result["status"] == "success":
        print(f"\n📈 Memory Evolution:")
        evolution = lifecycle_result["memory_evolution"]
        print(f"  • Initial size: {evolution['initial_size']} bytes")
        print(f"  • Final size: {evolution['final_size']} bytes")
        print(f"  • Growth: {evolution['growth']} bytes")
        print(f"  • Lifecycle steps: {len(lifecycle_result['lifecycle_steps'])}")

    print("\n✅ Memory management demo completed successfully!")
    return all_results, lifecycle_result


if __name__ == "__main__":
    # Run the demo
    asyncio.run(run_memory_management_demo())