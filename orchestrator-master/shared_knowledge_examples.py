#!/usr/bin/env python3
"""
Shared Knowledge Examples
Example workflows and demonstrations of the cross-worker context sharing system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from shared_knowledge import SharedKnowledgeManager
from shared_knowledge_tools import (
    AcquireLockRequest, ReleaseLockRequest, ShareCompletionRequest,
    GetContextRequest, UpdateStandardRequest, SearchKnowledgeRequest
)

logger = logging.getLogger(__name__)


class SharedKnowledgeExamples:
    """Example workflows demonstrating shared knowledge functionality."""

    def __init__(self):
        self.knowledge_manager = SharedKnowledgeManager()
        self.test_workers = ["worker-001", "worker-002", "worker-003"]
        self.examples = self._load_example_scenarios()

    def _load_example_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """Load predefined example scenarios for shared knowledge."""
        return {
            "module_coordination": {
                "description": "Demonstrate module lock coordination between workers",
                "scenario": [
                    "Worker 1 acquires lock on user_model module",
                    "Worker 2 tries to acquire lock on same module (should conflict)",
                    "Worker 1 completes work and releases lock",
                    "Worker 2 successfully acquires lock"
                ]
            },
            "context_sharing": {
                "description": "Share task completion context between workers",
                "tasks": [
                    {
                        "worker_id": "worker-001",
                        "task_id": "user_model_001",
                        "completion_data": {
                            "modules_completed": ["user_model"],
                            "apis_created": [
                                {
                                    "name": "User Registration API",
                                    "module": "user_model",
                                    "endpoint": "/api/users/register",
                                    "method": "POST",
                                    "input_schema": {
                                        "email": "string",
                                        "password": "string",
                                        "name": "string"
                                    },
                                    "output_schema": {
                                        "user_id": "uuid",
                                        "email": "string",
                                        "created_at": "datetime"
                                    },
                                    "description": "Create new user account with email validation",
                                    "dependencies": ["email_service", "password_hasher"]
                                }
                            ],
                            "decisions_made": [
                                {
                                    "title": "Email as Primary Identifier",
                                    "decision": "Use email address as primary user identifier instead of username",
                                    "rationale": "Email is unique, verifiable, and supports password recovery",
                                    "alternatives": ["username", "phone number"],
                                    "consequences": ["Must validate email uniqueness", "Requires email verification flow"],
                                    "affects_modules": ["user_model", "auth_service"]
                                }
                            ],
                            "learnings": [
                                {
                                    "title": "Email Validation Performance",
                                    "description": "Email validation regex can be expensive for large batches",
                                    "type": "performance",
                                    "severity": "medium",
                                    "solution": "Use async validation and caching for repeated domains",
                                    "module": "user_model",
                                    "tags": ["validation", "performance", "email"]
                                }
                            ]
                        }
                    },
                    {
                        "worker_id": "worker-002",
                        "task_id": "auth_api_001",
                        "completion_data": {
                            "modules_completed": ["auth_service"],
                            "apis_created": [
                                {
                                    "name": "User Login API",
                                    "module": "auth_service",
                                    "endpoint": "/api/auth/login",
                                    "method": "POST",
                                    "input_schema": {
                                        "email": "string",
                                        "password": "string"
                                    },
                                    "output_schema": {
                                        "access_token": "string",
                                        "refresh_token": "string",
                                        "expires_in": "integer"
                                    },
                                    "description": "Authenticate user and return JWT tokens",
                                    "dependencies": ["user_model", "jwt_service"]
                                }
                            ],
                            "decisions_made": [
                                {
                                    "title": "JWT Token Strategy",
                                    "decision": "Use short-lived access tokens (15 min) with refresh tokens",
                                    "rationale": "Balance security and user experience",
                                    "alternatives": ["long-lived tokens", "session-based auth"],
                                    "consequences": ["Need refresh token endpoint", "More complex client logic"],
                                    "affects_modules": ["auth_service", "middleware"]
                                }
                            ],
                            "learnings": [
                                {
                                    "title": "Password Hash Timing",
                                    "description": "Constant-time password verification prevents timing attacks",
                                    "type": "security",
                                    "severity": "high",
                                    "solution": "Always hash provided password even for non-existent users",
                                    "module": "auth_service",
                                    "tags": ["security", "authentication", "timing-attack"]
                                }
                            ]
                        }
                    }
                ]
            },
            "conflict_prevention": {
                "description": "Demonstrate conflict detection and prevention",
                "conflicts": [
                    {
                        "worker_id": "worker-001",
                        "modules": ["user_model", "user_service"],
                        "expected_conflicts": []
                    },
                    {
                        "worker_id": "worker-002",
                        "modules": ["user_model"],  # Same as worker-001
                        "expected_conflicts": ["module_conflict"]
                    },
                    {
                        "worker_id": "worker-003",
                        "modules": ["user_profile"],
                        "dependencies": ["user_model"],  # Depends on worker-001's work
                        "expected_conflicts": ["dependency_conflict"]
                    }
                ]
            },
            "knowledge_search": {
                "description": "Search and retrieve shared knowledge",
                "search_queries": [
                    {
                        "query": "user authentication",
                        "expected_types": ["api_contract", "architectural_decision"]
                    },
                    {
                        "query": "email validation",
                        "expected_types": ["worker_learning", "api_contract"]
                    },
                    {
                        "query": "JWT tokens",
                        "expected_types": ["architectural_decision", "api_contract"]
                    },
                    {
                        "query": "performance optimization",
                        "expected_types": ["worker_learning"]
                    }
                ]
            }
        }

    async def run_module_coordination_example(self) -> Dict[str, Any]:
        """Demonstrate module lock coordination between workers."""
        logger.info("Running module coordination example")

        steps = []
        worker1, worker2 = "worker-001", "worker-002"
        module_name = "user_model"

        try:
            # Step 1: Worker 1 acquires lock
            logger.info("Step 1: Worker 1 acquiring lock on user_model")
            lock_request1 = AcquireLockRequest(
                worker_id=worker1,
                task_id="user_model_task",
                module_name=module_name,
                dependencies=[],
                expected_duration_hours=2
            )

            from shared_knowledge_tools import register_shared_knowledge_tools
            tools = register_shared_knowledge_tools(None)

            lock_result1 = await tools["acquire_module_lock"](lock_request1)
            steps.append({
                "step": 1,
                "description": f"Worker {worker1} acquiring lock on {module_name}",
                "result": lock_result1["status"],
                "conflicts": lock_result1.get("conflicts", [])
            })

            # Step 2: Worker 2 tries to acquire same lock (should conflict)
            logger.info("Step 2: Worker 2 trying to acquire same lock (should conflict)")
            lock_request2 = AcquireLockRequest(
                worker_id=worker2,
                task_id="user_auth_task",
                module_name=module_name,
                dependencies=[],
                expected_duration_hours=1
            )

            lock_result2 = await tools["acquire_module_lock"](lock_request2)
            steps.append({
                "step": 2,
                "description": f"Worker {worker2} trying to acquire lock on {module_name}",
                "result": lock_result2["status"],
                "conflicts": lock_result2.get("conflicts", [])
            })

            # Step 3: Worker 1 releases lock
            logger.info("Step 3: Worker 1 releasing lock")
            release_request1 = ReleaseLockRequest(
                worker_id=worker1,
                module_name=module_name,
                completion_status="completed"
            )

            release_result1 = await tools["release_module_lock"](release_request1)
            steps.append({
                "step": 3,
                "description": f"Worker {worker1} releasing lock on {module_name}",
                "result": release_result1["status"]
            })

            # Step 4: Worker 2 successfully acquires lock
            logger.info("Step 4: Worker 2 acquiring lock (should succeed)")
            lock_result3 = await tools["acquire_module_lock"](lock_request2)
            steps.append({
                "step": 4,
                "description": f"Worker {worker2} acquiring lock on {module_name} after release",
                "result": lock_result3["status"],
                "conflicts": lock_result3.get("conflicts", [])
            })

            # Validate expected behavior
            validation = {
                "step1_success": steps[0]["result"] == "success",
                "step2_conflict": steps[1]["result"] == "conflict",
                "step3_release": steps[2]["result"] == "success",
                "step4_success": steps[3]["result"] == "success"
            }

            all_valid = all(validation.values())

            logger.info(f"Module coordination example completed. Validation: {all_valid}")

            return {
                "status": "success",
                "example": "module_coordination",
                "steps": steps,
                "validation": validation,
                "all_steps_valid": all_valid
            }

        except Exception as e:
            logger.error(f"Error in module coordination example: {e}")
            return {
                "status": "error",
                "error": str(e),
                "steps": steps
            }

    async def run_context_sharing_example(self) -> Dict[str, Any]:
        """Demonstrate context sharing between workers."""
        logger.info("Running context sharing example")

        shared_items = []
        context_retrievals = []

        try:
            from shared_knowledge_tools import register_shared_knowledge_tools
            tools = register_shared_knowledge_tools(None)

            tasks = self.examples["context_sharing"]["tasks"]

            # Share completion context from each task
            for task_data in tasks:
                logger.info(f"Sharing completion context for task {task_data['task_id']}")

                share_request = ShareCompletionRequest(
                    worker_id=task_data["worker_id"],
                    task_id=task_data["task_id"],
                    completion_data=task_data["completion_data"]
                )

                share_result = await tools["share_task_completion"](share_request)
                shared_items.append({
                    "task_id": task_data["task_id"],
                    "worker_id": task_data["worker_id"],
                    "status": share_result["status"],
                    "shared_count": share_result.get("shared_count", 0),
                    "shared_items": share_result.get("shared_items", [])
                })

            # Now demonstrate workers getting relevant context
            context_scenarios = [
                {
                    "worker_id": "worker-003",
                    "task_description": "Implement user profile management",
                    "modules_involved": ["user_model", "user_profile"]
                },
                {
                    "worker_id": "worker-004",
                    "task_description": "Build password reset functionality",
                    "modules_involved": ["auth_service", "email_service"]
                }
            ]

            for scenario in context_scenarios:
                logger.info(f"Getting context for worker {scenario['worker_id']}")

                context_request = GetContextRequest(
                    worker_id=scenario["worker_id"],
                    task_description=scenario["task_description"],
                    modules_involved=scenario["modules_involved"]
                )

                context_result = await tools["get_relevant_context"](context_request)
                context_retrievals.append({
                    "worker_id": scenario["worker_id"],
                    "status": context_result["status"],
                    "total_items": context_result.get("total_items", 0),
                    "context_summary": context_result.get("context_summary", [])
                })

            # Calculate sharing effectiveness
            total_shared = sum(item["shared_count"] for item in shared_items)
            total_retrieved = sum(item["total_items"] for item in context_retrievals)

            logger.info(f"Context sharing example completed. Shared: {total_shared}, Retrieved: {total_retrieved}")

            return {
                "status": "success",
                "example": "context_sharing",
                "shared_completions": shared_items,
                "context_retrievals": context_retrievals,
                "effectiveness": {
                    "total_items_shared": total_shared,
                    "total_items_retrieved": total_retrieved,
                    "sharing_efficiency": total_retrieved / max(total_shared, 1)
                }
            }

        except Exception as e:
            logger.error(f"Error in context sharing example: {e}")
            return {
                "status": "error",
                "error": str(e),
                "shared_items": shared_items,
                "context_retrievals": context_retrievals
            }

    async def run_conflict_prevention_example(self) -> Dict[str, Any]:
        """Demonstrate conflict detection and prevention."""
        logger.info("Running conflict prevention example")

        conflict_checks = []

        try:
            from shared_knowledge_tools import register_shared_knowledge_tools
            tools = register_shared_knowledge_tools(None)

            # First, set up some module locks to create conflicts
            setup_locks = [
                {
                    "worker_id": "worker-001",
                    "task_id": "setup_task_1",
                    "module_name": "user_model",
                    "dependencies": []
                },
                {
                    "worker_id": "worker-002",
                    "task_id": "setup_task_2",
                    "module_name": "email_service",
                    "dependencies": ["user_model"]
                }
            ]

            # Create initial locks
            for lock_setup in setup_locks:
                lock_request = AcquireLockRequest(
                    worker_id=lock_setup["worker_id"],
                    task_id=lock_setup["task_id"],
                    module_name=lock_setup["module_name"],
                    dependencies=lock_setup["dependencies"]
                )
                await tools["acquire_module_lock"](lock_request)

            # Now test conflict detection
            conflict_scenarios = self.examples["conflict_prevention"]["conflicts"]

            for scenario in conflict_scenarios:
                logger.info(f"Checking conflicts for worker {scenario['worker_id']}")

                conflict_result = await tools["check_task_conflicts"](
                    worker_id=scenario["worker_id"],
                    modules_involved=scenario["modules"]
                )

                # Analyze conflicts found
                conflicts_found = conflict_result.get("conflicts", [])
                conflict_types = [c["type"] for c in conflicts_found]

                # Check if expected conflicts were detected
                expected = scenario.get("expected_conflicts", [])
                conflicts_match = all(exp_type in conflict_types for exp_type in expected)

                conflict_checks.append({
                    "worker_id": scenario["worker_id"],
                    "modules": scenario["modules"],
                    "status": conflict_result["status"],
                    "has_conflicts": conflict_result.get("has_conflicts", False),
                    "conflicts_found": len(conflicts_found),
                    "conflict_types": conflict_types,
                    "expected_conflicts": expected,
                    "conflicts_match_expected": conflicts_match,
                    "severity_level": conflict_result.get("severity_level", "low"),
                    "recommendations": conflict_result.get("recommendations", [])
                })

            # Calculate conflict detection accuracy
            correct_predictions = sum(1 for check in conflict_checks if check["conflicts_match_expected"])
            accuracy = correct_predictions / len(conflict_checks) if conflict_checks else 0

            logger.info(f"Conflict prevention example completed. Detection accuracy: {accuracy:.2%}")

            return {
                "status": "success",
                "example": "conflict_prevention",
                "conflict_checks": conflict_checks,
                "detection_accuracy": accuracy,
                "total_scenarios": len(conflict_checks),
                "correct_predictions": correct_predictions
            }

        except Exception as e:
            logger.error(f"Error in conflict prevention example: {e}")
            return {
                "status": "error",
                "error": str(e),
                "conflict_checks": conflict_checks
            }

    async def run_knowledge_search_example(self) -> Dict[str, Any]:
        """Demonstrate knowledge search functionality."""
        logger.info("Running knowledge search example")

        search_results = []

        try:
            # First populate knowledge base with context sharing example
            await self.run_context_sharing_example()

            from shared_knowledge_tools import register_shared_knowledge_tools
            tools = register_shared_knowledge_tools(None)

            # Test various search queries
            search_queries = self.examples["knowledge_search"]["search_queries"]

            for query_data in search_queries:
                logger.info(f"Searching for: '{query_data['query']}'")

                search_request = SearchKnowledgeRequest(
                    query=query_data["query"],
                    content_types=None,  # Search all types
                    limit=5
                )

                search_result = await tools["search_shared_knowledge"](search_request)

                # Analyze results
                results_found = search_result.get("results", [])
                content_types_found = set(r["type"] for r in results_found)
                expected_types = set(query_data["expected_types"])

                # Check if we found expected content types
                found_expected = len(content_types_found & expected_types) > 0
                avg_relevance = sum(r["relevance_score"] for r in results_found) / len(results_found) if results_found else 0

                search_results.append({
                    "query": query_data["query"],
                    "status": search_result["status"],
                    "results_count": len(results_found),
                    "content_types_found": list(content_types_found),
                    "expected_types": query_data["expected_types"],
                    "found_expected_types": found_expected,
                    "average_relevance": round(avg_relevance, 3),
                    "top_result": results_found[0] if results_found else None
                })

            # Calculate search effectiveness
            successful_searches = sum(1 for result in search_results if result["found_expected_types"])
            search_effectiveness = successful_searches / len(search_results) if search_results else 0

            logger.info(f"Knowledge search example completed. Effectiveness: {search_effectiveness:.2%}")

            return {
                "status": "success",
                "example": "knowledge_search",
                "search_results": search_results,
                "search_effectiveness": search_effectiveness,
                "total_queries": len(search_results),
                "successful_queries": successful_searches
            }

        except Exception as e:
            logger.error(f"Error in knowledge search example: {e}")
            return {
                "status": "error",
                "error": str(e),
                "search_results": search_results
            }

    async def run_all_examples(self) -> Dict[str, Any]:
        """Run all shared knowledge examples."""
        logger.info("Running all shared knowledge examples")

        results = {}
        summary = {
            "total_examples": len(self.examples),
            "successful_examples": 0,
            "failed_examples": 0,
            "example_results": {}
        }

        # Run each example
        examples = [
            ("module_coordination", self.run_module_coordination_example),
            ("context_sharing", self.run_context_sharing_example),
            ("conflict_prevention", self.run_conflict_prevention_example),
            ("knowledge_search", self.run_knowledge_search_example)
        ]

        for example_name, example_func in examples:
            try:
                logger.info(f"Running example: {example_name}")
                result = await example_func()
                results[example_name] = result

                if result["status"] == "success":
                    summary["successful_examples"] += 1
                    summary["example_results"][example_name] = "success"
                else:
                    summary["failed_examples"] += 1
                    summary["example_results"][example_name] = "failed"

            except Exception as e:
                logger.error(f"Error running example {example_name}: {e}")
                results[example_name] = {"status": "error", "error": str(e)}
                summary["failed_examples"] += 1
                summary["example_results"][example_name] = "error"

        return {
            "summary": summary,
            "results": results,
            "generated_at": datetime.now().isoformat()
        }

    async def demonstrate_complete_workflow(self) -> Dict[str, Any]:
        """Demonstrate complete cross-worker coordination workflow."""
        logger.info("Demonstrating complete cross-worker coordination workflow")

        workflow_steps = []

        try:
            from shared_knowledge_tools import register_shared_knowledge_tools
            tools = register_shared_knowledge_tools(None)

            # Workflow: Multiple workers building authentication system
            workflow = [
                {
                    "step": 1,
                    "description": "Worker 1 starts user model, checks for conflicts",
                    "worker_id": "worker-001",
                    "action": "check_conflicts",
                    "modules": ["user_model"]
                },
                {
                    "step": 2,
                    "description": "Worker 1 acquires lock on user model",
                    "worker_id": "worker-001",
                    "action": "acquire_lock",
                    "module": "user_model",
                    "task_id": "user_model_impl"
                },
                {
                    "step": 3,
                    "description": "Worker 2 checks conflicts for auth service (depends on user model)",
                    "worker_id": "worker-002",
                    "action": "check_conflicts",
                    "modules": ["auth_service", "user_model"]
                },
                {
                    "step": 4,
                    "description": "Worker 1 completes user model and shares context",
                    "worker_id": "worker-001",
                    "action": "share_completion",
                    "task_id": "user_model_impl"
                },
                {
                    "step": 5,
                    "description": "Worker 2 gets relevant context before starting auth service",
                    "worker_id": "worker-002",
                    "action": "get_context",
                    "task_description": "Implement authentication service with JWT",
                    "modules": ["auth_service", "user_model"]
                },
                {
                    "step": 6,
                    "description": "Worker 2 acquires lock on auth service",
                    "worker_id": "worker-002",
                    "action": "acquire_lock",
                    "module": "auth_service",
                    "task_id": "auth_service_impl"
                },
                {
                    "step": 7,
                    "description": "Worker 3 searches for authentication patterns",
                    "worker_id": "worker-003",
                    "action": "search_knowledge",
                    "query": "authentication JWT patterns"
                }
            ]

            # Execute workflow steps
            for step_data in workflow:
                step_result = {"step": step_data["step"], "description": step_data["description"]}

                try:
                    if step_data["action"] == "check_conflicts":
                        result = await tools["check_task_conflicts"](
                            worker_id=step_data["worker_id"],
                            modules_involved=step_data["modules"]
                        )
                        step_result.update({
                            "action": "check_conflicts",
                            "has_conflicts": result.get("has_conflicts", False),
                            "conflicts_count": len(result.get("conflicts", [])),
                            "severity": result.get("severity_level", "low")
                        })

                    elif step_data["action"] == "acquire_lock":
                        lock_request = AcquireLockRequest(
                            worker_id=step_data["worker_id"],
                            task_id=step_data["task_id"],
                            module_name=step_data["module"]
                        )
                        result = await tools["acquire_module_lock"](lock_request)
                        step_result.update({
                            "action": "acquire_lock",
                            "lock_status": result["status"],
                            "module": step_data["module"]
                        })

                    elif step_data["action"] == "share_completion":
                        # Simulate completion data
                        completion_data = {
                            "modules_completed": ["user_model"],
                            "apis_created": [
                                {
                                    "name": "User Model API",
                                    "module": "user_model",
                                    "description": "User registration and management"
                                }
                            ],
                            "decisions_made": [
                                {
                                    "title": "User ID Strategy",
                                    "decision": "Use UUID for user IDs",
                                    "rationale": "Scalable and secure"
                                }
                            ]
                        }

                        share_request = ShareCompletionRequest(
                            worker_id=step_data["worker_id"],
                            task_id=step_data["task_id"],
                            completion_data=completion_data
                        )
                        result = await tools["share_task_completion"](share_request)
                        step_result.update({
                            "action": "share_completion",
                            "shared_items": result.get("shared_count", 0)
                        })

                    elif step_data["action"] == "get_context":
                        context_request = GetContextRequest(
                            worker_id=step_data["worker_id"],
                            task_description=step_data["task_description"],
                            modules_involved=step_data["modules"]
                        )
                        result = await tools["get_relevant_context"](context_request)
                        step_result.update({
                            "action": "get_context",
                            "context_items": result.get("total_items", 0)
                        })

                    elif step_data["action"] == "search_knowledge":
                        search_request = SearchKnowledgeRequest(
                            query=step_data["query"],
                            limit=3
                        )
                        result = await tools["search_shared_knowledge"](search_request)
                        step_result.update({
                            "action": "search_knowledge",
                            "results_found": result.get("total_found", 0)
                        })

                    step_result["status"] = "success"

                except Exception as e:
                    step_result.update({
                        "status": "error",
                        "error": str(e)
                    })

                workflow_steps.append(step_result)
                logger.info(f"Completed workflow step {step_data['step']}: {step_data['action']}")

            # Analyze workflow effectiveness
            successful_steps = sum(1 for step in workflow_steps if step["status"] == "success")
            workflow_success_rate = successful_steps / len(workflow_steps)

            logger.info(f"Complete workflow demonstration finished. Success rate: {workflow_success_rate:.2%}")

            return {
                "status": "success",
                "workflow_steps": workflow_steps,
                "workflow_effectiveness": {
                    "total_steps": len(workflow_steps),
                    "successful_steps": successful_steps,
                    "success_rate": workflow_success_rate
                }
            }

        except Exception as e:
            logger.error(f"Error in complete workflow demonstration: {e}")
            return {
                "status": "error",
                "error": str(e),
                "workflow_steps": workflow_steps
            }

    def generate_shared_knowledge_report(self) -> str:
        """Generate a human-readable shared knowledge system report."""
        report = """
# Shared Knowledge Management System Report

## Overview
The shared knowledge management system enables seamless cross-worker coordination and context sharing, preventing conflicts and building cumulative team knowledge.

## Key Features
- **Module Locking**: Prevent conflicts through exclusive module access
- **Context Sharing**: Automatic sharing of task completion context
- **Knowledge Base**: Centralized storage of APIs, decisions, and learnings
- **Conflict Detection**: Proactive identification of potential conflicts
- **Semantic Search**: Intelligent search across all shared knowledge

## Shared Knowledge Structure
```
/workspace/shared_knowledge/
├── architecture_decisions.md  # Team architectural decisions
├── api_contracts.json         # API specifications and contracts
├── coding_standards.md        # Project coding standards
├── module_ownership.json      # Module ownership tracking
├── module_locks.json          # Active module locks
├── worker_learnings.json      # Accumulated team learnings
└── knowledge_index.json       # Fast lookup index
```

## Cross-Worker Coordination Protocol
1. **Pre-Task Checks**: Workers check for conflicts before starting
2. **Module Locking**: Acquire locks on modules being modified
3. **Context Loading**: Load relevant shared context for task
4. **Work Execution**: Perform task with awareness of shared knowledge
5. **Context Sharing**: Share completion results with team
6. **Lock Release**: Release module locks when done

## Conflict Prevention Mechanisms
- **Direct Conflicts**: Same module locked by multiple workers
- **Dependency Conflicts**: Working on module that depends on locked module
- **Interface Conflicts**: Breaking changes to shared APIs
- **Coordination Warnings**: Notifications about related ongoing work

## Knowledge Sharing Types
- **API Contracts**: Interface specifications between modules
- **Architectural Decisions**: Design choices and rationale
- **Worker Learnings**: Gotchas, optimizations, and patterns
- **Coding Standards**: Team conventions and best practices
- **Module Ownership**: Current responsibility assignment

## Example Coordination Workflow
1. Worker 1 starts user model implementation
2. Worker 1 acquires lock on `user_model` module
3. Worker 2 wants to build auth service (depends on user model)
4. Worker 2 gets conflict warning about dependency
5. Worker 1 completes user model, shares API contract
6. Worker 2 loads user model context automatically
7. Worker 2 can now implement auth service with full context

## Performance Benefits
1. **Conflict Avoidance**: Prevents merge conflicts and rework
2. **Knowledge Reuse**: Workers learn from each other's solutions
3. **Coordination Efficiency**: Automatic context sharing reduces communication overhead
4. **Quality Consistency**: Shared standards ensure consistent code quality
5. **Onboarding Speed**: New workers access accumulated team knowledge

## Integration Points
- Automatic integration with task orchestration system
- Context loading triggered by task assignment
- Knowledge sharing on task completion
- Conflict checking during planning phase
        """
        return report.strip()


async def run_shared_knowledge_demo():
    """Run a complete demonstration of the shared knowledge system."""
    examples = SharedKnowledgeExamples()

    print("🌐 Shared Knowledge Management System Demo")
    print("=" * 50)

    # Run all examples
    print("\n📋 Running all shared knowledge examples...")
    all_results = await examples.run_all_examples()

    print(f"\n📊 Summary:")
    print(f"  • Total examples: {all_results['summary']['total_examples']}")
    print(f"  • Successful examples: {all_results['summary']['successful_examples']}")
    print(f"  • Failed examples: {all_results['summary']['failed_examples']}")

    # Show individual example results
    for example_name, status in all_results['summary']['example_results'].items():
        print(f"    - {example_name}: {status}")

    # Demonstrate complete workflow
    print("\n🔄 Complete Workflow Demonstration...")
    workflow_result = await examples.demonstrate_complete_workflow()

    if workflow_result["status"] == "success":
        effectiveness = workflow_result["workflow_effectiveness"]
        print(f"\n📈 Workflow Results:")
        print(f"  • Total steps: {effectiveness['total_steps']}")
        print(f"  • Successful steps: {effectiveness['successful_steps']}")
        print(f"  • Success rate: {effectiveness['success_rate']:.2%}")

        # Show step summary
        for step in workflow_result["workflow_steps"]:
            status_icon = "✓" if step["status"] == "success" else "✗"
            print(f"    {status_icon} Step {step['step']}: {step['action']}")

    print("\n✅ Shared knowledge demo completed successfully!")
    return all_results, workflow_result


if __name__ == "__main__":
    # Run the demo
    asyncio.run(run_shared_knowledge_demo())