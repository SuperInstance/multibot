#!/usr/bin/env python3
"""
Integration Tests for Multi-Agent Orchestrator
Tests component interactions and communication flows.
"""

import pytest
import asyncio
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from task_decomposition import TaskDecomposer, TaskOrchestrator
from merge_coordination import MergeCoordinator
from communication import CommunicationHub
from worker_manager import WorkerManager
from shared_knowledge import SharedKnowledgeManager
from memory_management import WorkerMemoryManager


@pytest.mark.integration
class TestMasterWorkerCommunication:
    """Test communication between Master and Workers."""

    @pytest.mark.asyncio
    async def test_worker_registration(self, communication_hub, worker_manager):
        """Test worker registration with master."""
        worker_id = "test-worker-001"

        # Simulate worker registration
        registration_message = {
            "from": worker_id,
            "to": "master",
            "type": "worker_registration",
            "content": {
                "worker_id": worker_id,
                "model": "sonnet-4",
                "capabilities": ["coding", "analysis"],
                "status": "ready"
            }
        }

        await communication_hub.message_queue.send_message(registration_message)

        # Process registration
        messages = await communication_hub.message_queue.get_messages("master")
        assert len(messages) == 1
        assert messages[0]["content"]["worker_id"] == worker_id

        # Verify worker is registered
        # Note: In real implementation, this would update worker manager state
        assert messages[0]["type"] == "worker_registration"

    @pytest.mark.asyncio
    async def test_task_assignment_flow(self, communication_hub, sample_task):
        """Test task assignment from master to worker."""
        worker_id = "test-worker-001"

        # Master assigns task to worker
        assignment_message = {
            "from": "master",
            "to": worker_id,
            "type": "task_assignment",
            "content": {
                "task_id": sample_task["task_id"],
                "description": sample_task["description"],
                "context": sample_task["context"],
                "deadline": "2024-01-15T12:00:00Z"
            }
        }

        await communication_hub.message_queue.send_message(assignment_message)

        # Worker receives task
        worker_messages = await communication_hub.message_queue.get_messages(worker_id)
        assert len(worker_messages) == 1
        assert worker_messages[0]["content"]["task_id"] == sample_task["task_id"]

        # Worker acknowledges task
        acknowledgment = {
            "from": worker_id,
            "to": "master",
            "type": "task_acknowledgment",
            "content": {
                "task_id": sample_task["task_id"],
                "status": "accepted",
                "estimated_completion": "2024-01-15T11:30:00Z"
            }
        }

        await communication_hub.message_queue.send_message(acknowledgment)

        # Master receives acknowledgment
        master_messages = await communication_hub.message_queue.get_messages("master")
        assert len(master_messages) == 1
        assert master_messages[0]["content"]["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_heartbeat_mechanism(self, communication_hub):
        """Test heartbeat mechanism between master and workers."""
        worker_id = "test-worker-001"

        # Worker sends heartbeat
        heartbeat = {
            "from": worker_id,
            "to": "master",
            "type": "heartbeat",
            "content": {
                "worker_id": worker_id,
                "status": "active",
                "current_task": "auth_001",
                "memory_usage": 75,
                "timestamp": datetime.now().isoformat()
            }
        }

        await communication_hub.message_queue.send_message(heartbeat)

        # Master processes heartbeat
        messages = await communication_hub.message_queue.get_messages("master")
        assert len(messages) == 1
        assert messages[0]["content"]["status"] == "active"

        # Master responds with heartbeat acknowledgment
        ack = {
            "from": "master",
            "to": worker_id,
            "type": "heartbeat_ack",
            "content": {
                "worker_id": worker_id,
                "status": "acknowledged",
                "instructions": "continue"
            }
        }

        await communication_hub.message_queue.send_message(ack)

        # Worker receives acknowledgment
        worker_messages = await communication_hub.message_queue.get_messages(worker_id)
        assert len(worker_messages) == 1
        assert worker_messages[0]["content"]["status"] == "acknowledged"


@pytest.mark.integration
class TestWorkerQuestionFlow:
    """Test worker question/answer flow with master."""

    @pytest.mark.asyncio
    async def test_worker_asks_question(self, communication_hub):
        """Test worker asking question to master."""
        worker_id = "test-worker-001"

        # Worker asks question
        question = {
            "from": worker_id,
            "to": "master",
            "type": "question",
            "content": {
                "task_id": "auth_001",
                "question": "Should I use bcrypt or argon2 for password hashing?",
                "context": {
                    "current_progress": "Implementing user registration",
                    "files_being_modified": ["src/auth.py"],
                    "urgency": "medium"
                },
                "question_id": "q_001"
            }
        }

        await communication_hub.message_queue.send_message(question)

        # Master receives question
        master_messages = await communication_hub.message_queue.get_messages("master")
        assert len(master_messages) == 1
        assert master_messages[0]["content"]["question_id"] == "q_001"
        assert "bcrypt or argon2" in master_messages[0]["content"]["question"]

        # Master provides answer
        answer = {
            "from": "master",
            "to": worker_id,
            "type": "answer",
            "content": {
                "question_id": "q_001",
                "answer": "Use argon2 for better security. Install argon2-cffi package.",
                "reasoning": "Argon2 is more resistant to GPU-based attacks",
                "additional_context": {
                    "implementation_note": "Use Argon2id variant",
                    "reference": "https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html"
                }
            }
        }

        await communication_hub.message_queue.send_message(answer)

        # Worker receives answer
        worker_messages = await communication_hub.message_queue.get_messages(worker_id)
        assert len(worker_messages) == 1
        assert worker_messages[0]["content"]["question_id"] == "q_001"
        assert "argon2" in worker_messages[0]["content"]["answer"]

    @pytest.mark.asyncio
    async def test_clarification_flow(self, communication_hub):
        """Test clarification request flow."""
        worker_id = "test-worker-002"

        # Worker requests clarification
        clarification_request = {
            "from": worker_id,
            "to": "master",
            "type": "clarification_request",
            "content": {
                "task_id": "auth_002",
                "original_instruction": "Implement JWT token validation",
                "confusion_point": "Token expiration handling",
                "specific_question": "Should expired tokens be automatically refreshed or require re-authentication?",
                "current_implementation": "Basic token validation without expiration",
                "clarification_id": "c_001"
            }
        }

        await communication_hub.message_queue.send_message(clarification_request)

        # Master provides clarification
        clarification = {
            "from": "master",
            "to": worker_id,
            "type": "clarification",
            "content": {
                "clarification_id": "c_001",
                "clarified_instruction": "Implement both automatic refresh and re-authentication",
                "details": {
                    "refresh_threshold": "5 minutes before expiration",
                    "refresh_endpoint": "/auth/refresh",
                    "fallback": "Redirect to login if refresh fails"
                },
                "updated_requirements": [
                    "Add refresh token mechanism",
                    "Implement token expiration checks",
                    "Handle refresh failures gracefully"
                ]
            }
        }

        await communication_hub.message_queue.send_message(clarification)

        # Verify clarification received
        messages = await communication_hub.message_queue.get_messages(worker_id)
        assert len(messages) == 1
        assert messages[0]["content"]["clarification_id"] == "c_001"


@pytest.mark.integration
class TestTaskDecompositionIntegration:
    """Test task decomposition integration with other components."""

    @pytest.mark.asyncio
    async def test_decomposition_to_assignment(self, sample_task, communication_hub):
        """Test full flow from task decomposition to worker assignment."""
        decomposer = TaskDecomposer()
        orchestrator = TaskOrchestrator(communication_hub)

        # Decompose task
        task_graph = await decomposer.decompose_task(
            sample_task["description"],
            sample_task["context"]
        )

        assert task_graph is not None
        assert len(task_graph.tasks) > 0

        # Simulate task assignment to workers
        available_workers = ["worker-001", "worker-002", "worker-003"]

        assignments = []
        for i, (task_id, task) in enumerate(task_graph.tasks.items()):
            worker_id = available_workers[i % len(available_workers)]

            assignment = {
                "task_id": task_id,
                "worker_id": worker_id,
                "task_details": {
                    "title": task.title,
                    "description": task.description,
                    "complexity": task.complexity.value,
                    "estimated_tokens": task.estimated_tokens,
                    "files_involved": task.files_involved
                }
            }
            assignments.append(assignment)

            # Send assignment message
            message = {
                "from": "master",
                "to": worker_id,
                "type": "task_assignment",
                "content": assignment
            }
            await communication_hub.message_queue.send_message(message)

        # Verify all assignments were sent
        for worker_id in available_workers:
            messages = await communication_hub.message_queue.get_messages(worker_id)
            # Each worker should have at least one task (depending on distribution)
            worker_assignments = [msg for msg in messages if msg["type"] == "task_assignment"]
            # Note: Actual number depends on task distribution

        assert len(assignments) == len(task_graph.tasks)

    @pytest.mark.asyncio
    async def test_dependency_aware_scheduling(self):
        """Test scheduling tasks with dependencies."""
        decomposer = TaskDecomposer()

        # Use authentication system pattern which has dependencies
        task_description = "Implement complete authentication system"
        context = {"type": "authentication_system"}

        task_graph = await decomposer.decompose_task(task_description, context)

        # Verify phases are ordered by dependencies
        assert len(task_graph.phases) > 1

        # Check that dependent tasks are in later phases
        phase_0_tasks = set(task_graph.phases[0])

        for phase_num in range(1, len(task_graph.phases)):
            phase_tasks = task_graph.phases[phase_num]

            for task_id in phase_tasks:
                task = task_graph.tasks[task_id]

                # All dependencies should be in earlier phases
                for dep_id in task.dependencies:
                    dep_phase = None
                    for p_num, p_tasks in enumerate(task_graph.phases):
                        if dep_id in p_tasks:
                            dep_phase = p_num
                            break

                    assert dep_phase is not None, f"Dependency {dep_id} not found in any phase"
                    assert dep_phase < phase_num, f"Dependency {dep_id} in later phase than dependent task {task_id}"


@pytest.mark.integration
class TestMergeCoordinationIntegration:
    """Test merge coordination integration."""

    @pytest.mark.asyncio
    async def test_merge_coordination_with_shared_knowledge(self, sample_worker_branches, shared_knowledge_manager):
        """Test merge coordination with shared knowledge integration."""
        coordinator = MergeCoordinator()

        # First, simulate workers sharing completion context
        completion_contexts = [
            {
                "worker_id": "worker-001",
                "task_id": "auth_001",
                "modules_completed": ["user_model"],
                "apis_created": [{
                    "name": "User Model API",
                    "module": "user_model",
                    "description": "User registration and authentication"
                }]
            },
            {
                "worker_id": "worker-002",
                "task_id": "auth_002",
                "modules_completed": ["jwt_service"],
                "apis_created": [{
                    "name": "JWT Service API",
                    "module": "jwt_service",
                    "description": "Token generation and validation"
                }]
            }
        ]

        # Share completion contexts
        for context in completion_contexts:
            await shared_knowledge_manager.share_task_completion(
                context["worker_id"],
                context["task_id"],
                context
            )

        # Now coordinate merge
        merge_result = await coordinator.coordinate_merge_phase(
            "test_graph_integration",
            sample_worker_branches
        )

        assert merge_result.graph_id == "test_graph_integration"
        # In a real scenario, merge coordination would use shared knowledge
        # to resolve conflicts and validate integrations

    @pytest.mark.asyncio
    async def test_conflict_resolution_flow(self, shared_knowledge_manager):
        """Test conflict resolution with knowledge sharing."""
        coordinator = MergeCoordinator()

        # Create conflicting worker branches
        conflicting_branches = [
            {
                "worker_id": "worker-001",
                "branch_name": "feature/user-auth",
                "task_ids": ["auth_001"],
                "files_modified": ["src/models/user.py", "src/auth/config.py"],
                "test_status": "passed",
                "dependencies": [],
                "merge_priority": 1
            },
            {
                "worker_id": "worker-002",
                "branch_name": "feature/admin-auth",
                "task_ids": ["auth_002"],
                "files_modified": ["src/models/admin.py", "src/auth/config.py"],  # Conflict on config.py
                "test_status": "passed",
                "dependencies": [],
                "merge_priority": 2
            }
        ]

        # Start merge coordination
        merge_result = await coordinator.coordinate_merge_phase(
            "conflict_test_graph",
            conflicting_branches
        )

        # Should detect conflicts
        assert len(merge_result.conflicts_detected) > 0

        # Verify conflict involves the expected file
        file_conflicts = [c for c in merge_result.conflicts_detected
                         if c.conflict_type.value == "file_conflict"]
        assert len(file_conflicts) > 0
        assert any("config.py" in c.files_involved for c in file_conflicts)


@pytest.mark.integration
class TestMemoryAndKnowledgeIntegration:
    """Test integration between memory management and shared knowledge."""

    @pytest.mark.asyncio
    async def test_context_sharing_integration(self, worker_memory_manager, shared_knowledge_manager):
        """Test integration between worker memory and shared knowledge."""
        worker_id = "integration-worker-001"

        # Worker saves understanding to memory
        understanding = """
        User authentication module handles login/logout functionality.
        Key components: UserModel, PasswordHasher, SessionManager.
        Dependencies: database connection, redis for sessions.
        Security considerations: rate limiting, password strength validation.
        """

        memory_result = await worker_memory_manager.update_understanding(
            module_name="user_auth",
            understanding=understanding,
            file_path="src/auth/user_auth.py"
        )

        assert memory_result["status"] == "success"

        # Worker completes task and shares with team
        completion_data = {
            "modules_completed": ["user_auth"],
            "decisions_made": [{
                "title": "Session Storage Strategy",
                "decision": "Use Redis for session storage with 24h expiration",
                "rationale": "Better performance and automatic cleanup",
                "affects_modules": ["user_auth", "session_manager"]
            }],
            "learnings": [{
                "title": "Rate Limiting Implementation",
                "description": "Implemented sliding window rate limiting for login attempts",
                "type": "security",
                "severity": "high",
                "module": "user_auth"
            }]
        }

        knowledge_result = await shared_knowledge_manager.share_task_completion(
            worker_id=worker_id,
            task_id="auth_integration_001",
            completion_data=completion_data
        )

        assert knowledge_result["status"] == "success"
        assert knowledge_result["shared_count"] > 0

        # Another worker can now access this shared context
        context_result = await shared_knowledge_manager.get_relevant_context(
            worker_id="integration-worker-002",
            task_description="Implement admin authentication",
            modules_involved=["user_auth", "admin_auth"]
        )

        assert context_result["status"] == "success"
        assert context_result["total_items"] > 0

        # Should find the shared decisions and learnings
        decisions = context_result["context"]["architectural_decisions"]
        learnings = context_result["context"]["worker_learnings"]

        # Verify shared content is accessible
        assert len(decisions) > 0 or len(learnings) > 0

    @pytest.mark.asyncio
    async def test_memory_search_with_shared_knowledge(self, worker_memory_manager, shared_knowledge_manager):
        """Test memory search integration with shared knowledge."""
        # Add understanding to worker memory
        await worker_memory_manager.update_understanding(
            "jwt_service",
            "JWT token service for authentication and authorization",
            "src/services/jwt.py"
        )

        # Share knowledge
        await shared_knowledge_manager.share_task_completion(
            "worker-001",
            "jwt_task",
            {
                "apis_created": [{
                    "name": "JWT Token API",
                    "description": "Generate and validate JWT tokens",
                    "module": "jwt_service"
                }]
            }
        )

        # Search worker memory
        memory_results = await worker_memory_manager.search_memory("JWT token")
        assert memory_results["status"] == "success"
        assert memory_results["results_found"] > 0

        # Search shared knowledge
        knowledge_results = await shared_knowledge_manager.search_shared_knowledge("JWT token")
        assert knowledge_results["status"] == "success"
        assert knowledge_results["total_found"] > 0

        # Both searches should find relevant JWT-related content
        assert memory_results["results_found"] > 0
        assert knowledge_results["total_found"] > 0


@pytest.mark.integration
class TestWorkerLifecycleIntegration:
    """Test full worker lifecycle integration."""

    @pytest.mark.asyncio
    async def test_worker_spawn_to_termination(self, worker_manager, communication_hub, test_workspace_dir):
        """Test complete worker lifecycle from spawn to termination."""
        worker_id = "lifecycle-test-worker"

        # Note: This test simulates the worker lifecycle without actually spawning processes
        # In a real integration test, you might spawn actual worker processes

        # 1. Spawn worker (simulated)
        spawn_result = {
            "worker_id": worker_id,
            "model": "sonnet-4",
            "status": "spawned",
            "workspace_path": str(test_workspace_dir / "workers" / worker_id),
            "branch_name": f"worker-{worker_id}"
        }

        # Simulate worker registration
        registration = {
            "from": worker_id,
            "to": "master",
            "type": "worker_registration",
            "content": {
                "worker_id": worker_id,
                "status": "ready",
                "capabilities": ["coding", "analysis"]
            }
        }
        await communication_hub.message_queue.send_message(registration)

        # 2. Assign task
        task_assignment = {
            "from": "master",
            "to": worker_id,
            "type": "task_assignment",
            "content": {
                "task_id": "lifecycle_task_001",
                "description": "Implement user registration endpoint",
                "deadline": (datetime.now() + timedelta(hours=2)).isoformat()
            }
        }
        await communication_hub.message_queue.send_message(task_assignment)

        # 3. Worker processes task (simulated completion)
        task_completion = {
            "from": worker_id,
            "to": "master",
            "type": "task_completion",
            "content": {
                "task_id": "lifecycle_task_001",
                "status": "completed",
                "files_modified": ["src/api/users.py"],
                "result": "User registration endpoint implemented successfully"
            }
        }
        await communication_hub.message_queue.send_message(task_completion)

        # 4. Worker termination (simulated)
        termination = {
            "from": worker_id,
            "to": "master",
            "type": "worker_termination",
            "content": {
                "worker_id": worker_id,
                "reason": "task_completed",
                "final_status": "clean_shutdown"
            }
        }
        await communication_hub.message_queue.send_message(termination)

        # Verify message flow
        master_messages = await communication_hub.message_queue.get_messages("master")
        master_message_types = [msg["type"] for msg in master_messages]

        assert "worker_registration" in master_message_types
        assert "task_completion" in master_message_types
        assert "worker_termination" in master_message_types

        worker_messages = await communication_hub.message_queue.get_messages(worker_id)
        worker_message_types = [msg["type"] for msg in worker_messages]

        assert "task_assignment" in worker_message_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])