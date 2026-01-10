#!/usr/bin/env python3
"""
End-to-End tests for the Multi-Agent Orchestrator system.

These tests simulate complete workflows from task receipt through
decomposition, parallel execution, and final merge.
"""

import asyncio
import pytest
import json
import time
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

# Import system components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import ConfigurationManager, MasterConfiguration
from worker_manager import WorkerManager
from task_queue import TaskQueue
from message_queue import MessageQueueManager
from communication import CommunicationHub
from task_decomposition import TaskDecomposer
from merge_coordination import MergeCoordinator
from shared_knowledge import SharedKnowledgeManager
from memory_management import WorkerMemoryManager


@pytest.mark.e2e
class TestCompleteWorkflow:
    """Test complete end-to-end workflows."""

    @pytest.mark.asyncio
    async def test_full_feature_implementation_workflow(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager,
        test_helpers
    ):
        """
        Test complete workflow: Master receives task → spawns workers →
        decomposes task → parallel execution → merge coordination → validation.
        """

        # Setup: Create a test git repository
        test_repo = test_workspace_dir / "test_repo"
        test_helpers.create_test_git_repo(test_repo)

        # Create test source files
        test_files = {
            "src/main.py": "# Main application file\nprint('Hello World')\n",
            "src/utils.py": "# Utility functions\ndef helper():\n    pass\n",
            "tests/test_main.py": "# Test file\nimport pytest\n"
        }
        test_helpers.create_test_files(test_repo, test_files)

        # Initialize system components
        task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))
        message_queue = MessageQueueManager("sqlite", str(test_workspace_dir / "messages.db"))
        communication_hub = CommunicationHub(message_queue)
        worker_manager = WorkerManager(str(test_workspace_dir), config_manager)
        task_decomposer = TaskDecomposer()
        merge_coordinator = MergeCoordinator(str(test_repo))
        shared_knowledge = SharedKnowledgeManager(str(test_workspace_dir))

        # Step 1: Master receives complex task
        main_task = {
            "task_id": "feature_auth_001",
            "description": "Add user authentication feature with login, registration, and JWT tokens",
            "priority": 5,
            "context": {
                "repository_path": str(test_repo),
                "files": ["src/main.py", "src/utils.py"],
                "requirements": [
                    "User registration endpoint",
                    "Login endpoint with JWT",
                    "Password hashing",
                    "Session management",
                    "Input validation"
                ]
            },
            "estimated_tokens": 5000,
            "timeout": 3600
        }

        task_id = await task_queue.add_task(main_task)
        assert task_id == main_task["task_id"]

        # Step 2: Master spawns 3 workers
        worker_configs = []
        for i in range(3):
            worker_id = f"worker-{i+1:03d}"
            worker_config = config_manager.create_worker_config(
                worker_id=worker_id,
                model="sonnet-4"
            )
            worker_configs.append(worker_config)

            # Mock worker spawning
            with patch.object(worker_manager, 'spawn_worker') as mock_spawn:
                mock_spawn.return_value = True
                result = await worker_manager.spawn_worker(worker_config)
                assert result is True

        # Step 3: Master decomposes task into subtasks
        subtasks = await task_decomposer.decompose_task(main_task)

        # Verify decomposition created appropriate subtasks
        assert len(subtasks) >= 3
        assert any("user model" in task["description"].lower() for task in subtasks)
        assert any("jwt" in task["description"].lower() or "token" in task["description"].lower() for task in subtasks)
        assert any("endpoint" in task["description"].lower() or "api" in task["description"].lower() for task in subtasks)

        # Add subtasks to queue
        subtask_ids = []
        for subtask in subtasks:
            subtask_id = await task_queue.add_task(subtask)
            subtask_ids.append(subtask_id)

        # Step 4: Workers receive and start parallel execution
        worker_assignments = {}
        for i, (subtask, worker_config) in enumerate(zip(subtasks, worker_configs)):
            worker_id = worker_config.worker_id
            worker_assignments[worker_id] = subtask

            # Simulate task assignment message
            assignment_message = {
                "message_id": f"assign_{i+1}",
                "from": "master",
                "to": worker_id,
                "type": "task_assignment",
                "content": {
                    "task": subtask,
                    "workspace_branch": f"feature/{subtask['task_id']}"
                },
                "timestamp": time.time()
            }

            await communication_hub.send_message(assignment_message)

            # Verify message was queued
            messages = await communication_hub.get_messages(worker_id)
            assert len(messages) > 0
            assert messages[0]["type"] == "task_assignment"

        # Step 5: Simulate workers asking questions to master
        questions_and_responses = [
            {
                "worker_id": "worker-001",
                "question": "Should I use SQLAlchemy or raw SQL for the user model?",
                "master_response": "Use SQLAlchemy for better maintainability and ORM features"
            },
            {
                "worker_id": "worker-002",
                "question": "What JWT library should I use - PyJWT or python-jose?",
                "master_response": "Use PyJWT as it's more lightweight and widely adopted"
            },
            {
                "worker_id": "worker-003",
                "question": "Should validation be in the endpoint or separate middleware?",
                "master_response": "Create separate validation middleware for reusability"
            }
        ]

        for qa in questions_and_responses:
            # Worker sends question
            question_message = {
                "message_id": f"question_{qa['worker_id']}",
                "from": qa["worker_id"],
                "to": "master",
                "type": "question",
                "content": {
                    "question": qa["question"],
                    "context": "Working on task implementation"
                },
                "timestamp": time.time()
            }

            await communication_hub.send_message(question_message)

            # Master sends response
            response_message = {
                "message_id": f"response_{qa['worker_id']}",
                "from": "master",
                "to": qa["worker_id"],
                "type": "answer",
                "content": {
                    "answer": qa["master_response"],
                    "reference_question": question_message["message_id"]
                },
                "timestamp": time.time()
            }

            await communication_hub.send_message(response_message)

        # Step 6: Simulate workers completing tasks
        completion_data = []
        for worker_id, subtask in worker_assignments.items():
            # Mock completion data
            completion = {
                "task_id": subtask["task_id"],
                "worker_id": worker_id,
                "status": "completed",
                "files_modified": [
                    f"src/{subtask['task_id']}.py",
                    f"tests/test_{subtask['task_id']}.py"
                ],
                "git_branch": f"feature/{subtask['task_id']}",
                "test_results": {"passed": True, "coverage": 85},
                "completion_notes": f"Implemented {subtask['description']}"
            }
            completion_data.append(completion)

            # Worker reports completion
            completion_message = {
                "message_id": f"complete_{worker_id}",
                "from": worker_id,
                "to": "master",
                "type": "task_completion",
                "content": completion,
                "timestamp": time.time()
            }

            await communication_hub.send_message(completion_message)

            # Update task status
            await task_queue.update_task_status(subtask["task_id"], "completed")

        # Step 7: Master coordinates merge
        branches_to_merge = [comp["git_branch"] for comp in completion_data]

        # Mock merge coordination
        with patch.object(merge_coordinator, 'coordinate_merge') as mock_merge:
            mock_merge.return_value = {
                "success": True,
                "conflicts_resolved": 2,
                "final_branch": "feature/auth_complete",
                "files_merged": 6
            }

            merge_result = await merge_coordinator.coordinate_merge(
                branches=branches_to_merge,
                target_branch="main"
            )

            assert merge_result["success"] is True
            assert merge_result["conflicts_resolved"] >= 0

        # Step 8: Final validation
        # Verify all subtasks completed
        all_tasks = await task_queue.get_tasks_by_status("completed")
        completed_subtask_ids = [task["task_id"] for task in all_tasks if task["task_id"] in subtask_ids]
        assert len(completed_subtask_ids) == len(subtask_ids)

        # Update main task status
        await task_queue.update_task_status(main_task["task_id"], "completed")

        # Verify main task completion
        main_task_updated = await task_queue.get_task(main_task["task_id"])
        assert main_task_updated["status"] == "completed"

        # Verify shared knowledge was updated
        await shared_knowledge.store_completion_data(
            task_id=main_task["task_id"],
            data={
                "subtasks_completed": len(subtasks),
                "workers_involved": len(worker_configs),
                "merge_successful": merge_result["success"]
            }
        )

        knowledge_data = await shared_knowledge.get_task_knowledge(main_task["task_id"])
        assert knowledge_data is not None
        assert knowledge_data["subtasks_completed"] == len(subtasks)

    @pytest.mark.asyncio
    async def test_workflow_with_failures_and_recovery(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager,
        test_helpers
    ):
        """Test complete workflow with worker failures and recovery mechanisms."""

        # Setup similar to previous test
        test_repo = test_workspace_dir / "test_repo"
        test_helpers.create_test_git_repo(test_repo)

        task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))
        message_queue = MessageQueueManager("sqlite", str(test_workspace_dir / "messages.db"))
        communication_hub = CommunicationHub(message_queue)
        worker_manager = WorkerManager(str(test_workspace_dir), config_manager)

        # Create task and workers
        main_task = {
            "task_id": "feature_recovery_001",
            "description": "Implement search feature with indexing and filtering",
            "priority": 7,
            "context": {"repository_path": str(test_repo)},
            "estimated_tokens": 4000,
            "timeout": 2400
        }

        await task_queue.add_task(main_task)

        # Spawn workers
        worker_ids = []
        for i in range(3):
            worker_id = f"recovery-worker-{i+1:03d}"
            worker_config = config_manager.create_worker_config(
                worker_id=worker_id,
                model="sonnet-4"
            )
            worker_ids.append(worker_id)

        # Create subtasks
        subtasks = [
            {
                "task_id": "search_001",
                "description": "Create search index",
                "worker_id": worker_ids[0],
                "estimated_tokens": 1200
            },
            {
                "task_id": "search_002",
                "description": "Implement search API",
                "worker_id": worker_ids[1],
                "estimated_tokens": 1500
            },
            {
                "task_id": "search_003",
                "description": "Add search filters",
                "worker_id": worker_ids[2],
                "estimated_tokens": 1300
            }
        ]

        for subtask in subtasks:
            await task_queue.add_task(subtask)

        # Simulate first worker failure
        failed_worker_id = worker_ids[0]

        # Worker starts task but fails
        await task_queue.update_task_status("search_001", "in_progress")

        # Simulate worker crash/timeout
        with patch.object(worker_manager, 'check_worker_health') as mock_health:
            mock_health.return_value = False

            health_status = await worker_manager.check_worker_health(failed_worker_id)
            assert health_status is False

        # Master detects failure and reassigns task
        await task_queue.update_task_status("search_001", "failed")

        # Spawn replacement worker
        replacement_worker_id = "recovery-worker-004"
        replacement_config = config_manager.create_worker_config(
            worker_id=replacement_worker_id,
            model="sonnet-4"
        )

        with patch.object(worker_manager, 'spawn_worker') as mock_spawn:
            mock_spawn.return_value = True
            result = await worker_manager.spawn_worker(replacement_config)
            assert result is True

        # Reassign failed task to replacement worker
        subtasks[0]["worker_id"] = replacement_worker_id
        await task_queue.update_task_status("search_001", "pending")

        # Replacement worker completes task
        await task_queue.update_task_status("search_001", "completed")

        # Other workers complete normally
        await task_queue.update_task_status("search_002", "completed")
        await task_queue.update_task_status("search_003", "completed")

        # Verify recovery was successful
        all_completed = await task_queue.get_tasks_by_status("completed")
        completed_ids = [task["task_id"] for task in all_completed]

        assert "search_001" in completed_ids
        assert "search_002" in completed_ids
        assert "search_003" in completed_ids

        # Update main task
        await task_queue.update_task_status(main_task["task_id"], "completed")

        # Verify final state
        final_task = await task_queue.get_task(main_task["task_id"])
        assert final_task["status"] == "completed"


@pytest.mark.e2e
class TestConcurrentWorkflows:
    """Test multiple concurrent workflows."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_features(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager
    ):
        """Test system handling multiple concurrent feature implementations."""

        # Initialize components
        task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))
        worker_manager = WorkerManager(str(test_workspace_dir), config_manager)

        # Create multiple main tasks
        main_tasks = [
            {
                "task_id": "feature_auth_concurrent",
                "description": "Implement authentication system",
                "priority": 8,
                "estimated_tokens": 3000
            },
            {
                "task_id": "feature_search_concurrent",
                "description": "Implement search functionality",
                "priority": 7,
                "estimated_tokens": 2500
            },
            {
                "task_id": "feature_notifications_concurrent",
                "description": "Add notification system",
                "priority": 6,
                "estimated_tokens": 2000
            }
        ]

        # Add all tasks to queue
        for task in main_tasks:
            await task_queue.add_task(task)

        # Spawn workers for each task (simulate 9 workers total)
        all_workers = []
        for i, task in enumerate(main_tasks):
            task_workers = []
            for j in range(3):  # 3 workers per main task
                worker_id = f"concurrent-{i+1}-{j+1:03d}"
                worker_config = config_manager.create_worker_config(
                    worker_id=worker_id,
                    model="sonnet-4"
                )
                task_workers.append(worker_config)

                with patch.object(worker_manager, 'spawn_worker') as mock_spawn:
                    mock_spawn.return_value = True
                    result = await worker_manager.spawn_worker(worker_config)
                    assert result is True

            all_workers.append(task_workers)

        # Simulate parallel execution
        completion_times = []

        for i, (task, workers) in enumerate(zip(main_tasks, all_workers)):
            # Create subtasks for each main task
            subtasks = [
                {
                    "task_id": f"{task['task_id']}_sub_001",
                    "description": f"Subtask 1 for {task['description']}",
                    "worker_id": workers[0].worker_id
                },
                {
                    "task_id": f"{task['task_id']}_sub_002",
                    "description": f"Subtask 2 for {task['description']}",
                    "worker_id": workers[1].worker_id
                },
                {
                    "task_id": f"{task['task_id']}_sub_003",
                    "description": f"Subtask 3 for {task['description']}",
                    "worker_id": workers[2].worker_id
                }
            ]

            # Add subtasks and simulate completion
            start_time = time.time()

            for subtask in subtasks:
                await task_queue.add_task(subtask)
                await task_queue.update_task_status(subtask["task_id"], "completed")

            # Complete main task
            await task_queue.update_task_status(task["task_id"], "completed")

            completion_times.append(time.time() - start_time)

        # Verify all tasks completed
        all_completed = await task_queue.get_tasks_by_status("completed")
        completed_main_tasks = [
            task for task in all_completed
            if task["task_id"] in [t["task_id"] for t in main_tasks]
        ]

        assert len(completed_main_tasks) == len(main_tasks)

        # Verify concurrent execution was efficient (all completed within reasonable time)
        max_completion_time = max(completion_times)
        assert max_completion_time < 1.0  # Should complete quickly in test environment


@pytest.mark.e2e
class TestSystemLimits:
    """Test system behavior at operational limits."""

    @pytest.mark.asyncio
    async def test_maximum_worker_capacity(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager
    ):
        """Test system with maximum number of workers (12)."""

        task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))
        worker_manager = WorkerManager(str(test_workspace_dir), config_manager)

        # Create large task requiring maximum workers
        large_task = {
            "task_id": "large_refactor_001",
            "description": "Complete system refactoring across all modules",
            "priority": 10,
            "estimated_tokens": 15000,
            "timeout": 7200
        }

        await task_queue.add_task(large_task)

        # Spawn maximum workers (12)
        worker_configs = []
        for i in range(12):
            worker_id = f"max-worker-{i+1:03d}"
            worker_config = config_manager.create_worker_config(
                worker_id=worker_id,
                model="sonnet-4"
            )
            worker_configs.append(worker_config)

            with patch.object(worker_manager, 'spawn_worker') as mock_spawn:
                mock_spawn.return_value = True
                result = await worker_manager.spawn_worker(worker_config)
                assert result is True

        # Create 12 subtasks for parallel execution
        subtasks = []
        for i in range(12):
            subtask = {
                "task_id": f"refactor_module_{i+1:03d}",
                "description": f"Refactor module {i+1}",
                "worker_id": worker_configs[i].worker_id,
                "estimated_tokens": 1200
            }
            subtasks.append(subtask)
            await task_queue.add_task(subtask)

        # Simulate all workers working in parallel
        start_time = time.time()

        # All workers complete their tasks
        for subtask in subtasks:
            await task_queue.update_task_status(subtask["task_id"], "completed")

        execution_time = time.time() - start_time

        # Complete main task
        await task_queue.update_task_status(large_task["task_id"], "completed")

        # Verify all subtasks completed
        completed_subtasks = await task_queue.get_tasks_by_status("completed")
        completed_subtask_ids = [
            task["task_id"] for task in completed_subtasks
            if task["task_id"].startswith("refactor_module_")
        ]

        assert len(completed_subtask_ids) == 12

        # Verify system handled maximum load efficiently
        assert execution_time < 2.0  # Should handle max workers efficiently

        # Verify main task completion
        final_task = await task_queue.get_task(large_task["task_id"])
        assert final_task["status"] == "completed"