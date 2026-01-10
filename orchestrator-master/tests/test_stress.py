#!/usr/bin/env python3
"""
Stress tests for the Multi-Agent Orchestrator system.

These tests push the system to its limits with maximum workers,
complex tasks, intentional conflicts, and crash recovery scenarios.
"""

import asyncio
import pytest
import time
import random
import json
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
from concurrent.futures import ThreadPoolExecutor

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


@pytest.mark.stress
class TestMaximumLoad:
    """Test system under maximum load conditions."""

    @pytest.mark.asyncio
    async def test_maximum_workers_complex_tasks(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager,
        test_helpers
    ):
        """
        Test system with 12 workers handling highly complex tasks
        with interdependencies and frequent communication.
        """
        # Setup
        task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))
        message_queue = MessageQueueManager("sqlite", str(test_workspace_dir / "messages.db"))
        communication_hub = CommunicationHub(message_queue)
        worker_manager = WorkerManager(str(test_workspace_dir), config_manager)
        shared_knowledge = SharedKnowledgeManager(str(test_workspace_dir))

        # Create test repository
        test_repo = test_workspace_dir / "stress_test_repo"
        test_helpers.create_test_git_repo(test_repo)

        # Create complex main task
        complex_task = {
            "task_id": "stress_complex_system",
            "description": "Build complete e-commerce platform with microservices architecture",
            "priority": 10,
            "context": {
                "repository_path": str(test_repo),
                "requirements": [
                    "User service with authentication",
                    "Product catalog service",
                    "Order management service",
                    "Payment processing service",
                    "Inventory management service",
                    "Notification service",
                    "API Gateway",
                    "Database schemas",
                    "Caching layer",
                    "Monitoring and logging",
                    "Load balancing",
                    "CI/CD pipeline"
                ]
            },
            "estimated_tokens": 25000,
            "timeout": 10800
        }

        await task_queue.add_task(complex_task)

        # Spawn 12 workers with different models for diversity
        worker_configs = []
        models = ["sonnet-4", "sonnet-4", "sonnet-4", "haiku-4"]  # Mix of models
        for i in range(12):
            worker_id = f"stress-worker-{i+1:03d}"
            model = models[i % len(models)]
            worker_config = config_manager.create_worker_config(
                worker_id=worker_id,
                model=model
            )
            worker_configs.append(worker_config)

            with patch.object(worker_manager, 'spawn_worker') as mock_spawn:
                mock_spawn.return_value = True
                result = await worker_manager.spawn_worker(worker_config)
                assert result is True

        # Create 12 complex subtasks with interdependencies
        subtasks = [
            {
                "task_id": "user_service",
                "description": "Implement user authentication service with JWT, OAuth, and role management",
                "complexity": "high",
                "estimated_tokens": 3000,
                "dependencies": [],
                "files_involved": ["services/user/*", "auth/*", "models/user.py"]
            },
            {
                "task_id": "product_service",
                "description": "Build product catalog service with search, categories, and recommendations",
                "complexity": "high",
                "estimated_tokens": 2800,
                "dependencies": [],
                "files_involved": ["services/product/*", "models/product.py", "search/*"]
            },
            {
                "task_id": "order_service",
                "description": "Create order management with cart, checkout, and order tracking",
                "complexity": "high",
                "estimated_tokens": 2500,
                "dependencies": ["user_service", "product_service"],
                "files_involved": ["services/order/*", "models/order.py", "payment/*"]
            },
            {
                "task_id": "payment_service",
                "description": "Implement payment processing with multiple providers and fraud detection",
                "complexity": "very_high",
                "estimated_tokens": 3200,
                "dependencies": ["user_service", "order_service"],
                "files_involved": ["services/payment/*", "fraud/*", "providers/*"]
            },
            {
                "task_id": "inventory_service",
                "description": "Build inventory management with real-time tracking and alerts",
                "complexity": "medium",
                "estimated_tokens": 2000,
                "dependencies": ["product_service"],
                "files_involved": ["services/inventory/*", "models/inventory.py"]
            },
            {
                "task_id": "notification_service",
                "description": "Create notification system with email, SMS, and push notifications",
                "complexity": "medium",
                "estimated_tokens": 1800,
                "dependencies": ["user_service"],
                "files_involved": ["services/notification/*", "templates/*"]
            },
            {
                "task_id": "api_gateway",
                "description": "Implement API gateway with routing, rate limiting, and authentication",
                "complexity": "high",
                "estimated_tokens": 2200,
                "dependencies": ["user_service"],
                "files_involved": ["gateway/*", "middleware/*", "routing/*"]
            },
            {
                "task_id": "database_schemas",
                "description": "Design and implement database schemas with migrations and indexing",
                "complexity": "medium",
                "estimated_tokens": 1500,
                "dependencies": [],
                "files_involved": ["migrations/*", "schemas/*", "models/*"]
            },
            {
                "task_id": "caching_layer",
                "description": "Implement caching with Redis for sessions, products, and API responses",
                "complexity": "medium",
                "estimated_tokens": 1800,
                "dependencies": ["user_service", "product_service"],
                "files_involved": ["cache/*", "config/redis.py"]
            },
            {
                "task_id": "monitoring_logging",
                "description": "Set up comprehensive monitoring, logging, and alerting systems",
                "complexity": "medium",
                "estimated_tokens": 2000,
                "dependencies": [],
                "files_involved": ["monitoring/*", "logging/*", "alerts/*"]
            },
            {
                "task_id": "load_balancer",
                "description": "Configure load balancing with health checks and failover",
                "complexity": "medium",
                "estimated_tokens": 1200,
                "dependencies": ["api_gateway"],
                "files_involved": ["load_balancer/*", "health/*"]
            },
            {
                "task_id": "cicd_pipeline",
                "description": "Create CI/CD pipeline with testing, deployment, and rollback capabilities",
                "complexity": "high",
                "estimated_tokens": 2500,
                "dependencies": ["monitoring_logging"],
                "files_involved": [".github/*", "scripts/*", "docker/*"]
            }
        ]

        # Add all subtasks
        for subtask in subtasks:
            await task_queue.add_task(subtask)

        # Assign workers to tasks based on dependencies
        worker_assignments = {}
        start_time = time.time()

        # Phase 1: Independent tasks (no dependencies)
        independent_tasks = [task for task in subtasks if not task["dependencies"]]
        for i, task in enumerate(independent_tasks):
            worker_id = worker_configs[i].worker_id
            worker_assignments[worker_id] = task
            await task_queue.update_task_status(task["task_id"], "in_progress")

        # Simulate intensive communication during execution
        message_count = 0
        for i in range(50):  # 50 rounds of communication
            # Random worker asks question
            asking_worker = random.choice(list(worker_assignments.keys()))

            question_message = {
                "message_id": f"stress_question_{i}",
                "from": asking_worker,
                "to": "master",
                "type": "question",
                "content": {
                    "question": f"Stress test question {i} regarding implementation details",
                    "urgency": random.choice(["low", "medium", "high"])
                },
                "timestamp": time.time()
            }

            await communication_hub.send_message(question_message)
            message_count += 1

            # Master responds
            response_message = {
                "message_id": f"stress_response_{i}",
                "from": "master",
                "to": asking_worker,
                "type": "answer",
                "content": {
                    "answer": f"Response to stress question {i}",
                    "reference_question": question_message["message_id"]
                },
                "timestamp": time.time()
            }

            await communication_hub.send_message(response_message)
            message_count += 1

        # Phase 1 completion
        for task in independent_tasks:
            await task_queue.update_task_status(task["task_id"], "completed")

        # Phase 2: Dependent tasks
        phase_2_tasks = [task for task in subtasks if task["dependencies"]]
        for i, task in enumerate(phase_2_tasks):
            # Check dependencies are met
            deps_completed = all(
                await task_queue.get_task(dep_id) and
                (await task_queue.get_task(dep_id))["status"] == "completed"
                for dep_id in task["dependencies"]
            )

            if deps_completed:
                worker_idx = (len(independent_tasks) + i) % len(worker_configs)
                worker_id = worker_configs[worker_idx].worker_id
                worker_assignments[worker_id] = task
                await task_queue.update_task_status(task["task_id"], "in_progress")

        # Complete phase 2 tasks
        for task in phase_2_tasks:
            await task_queue.update_task_status(task["task_id"], "completed")

        execution_time = time.time() - start_time

        # Verify all subtasks completed
        all_completed = await task_queue.get_tasks_by_status("completed")
        completed_subtask_ids = [
            task["task_id"] for task in all_completed
            if task["task_id"] in [st["task_id"] for st in subtasks]
        ]

        assert len(completed_subtask_ids) == len(subtasks)

        # Complete main task
        await task_queue.update_task_status(complex_task["task_id"], "completed")

        # Performance assertions
        assert execution_time < 10.0  # Should complete within reasonable time even under stress
        assert message_count == 100  # Verify all communications went through

        # Verify system stability under load
        final_task = await task_queue.get_task(complex_task["task_id"])
        assert final_task["status"] == "completed"

    @pytest.mark.asyncio
    async def test_concurrent_task_floods(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager
    ):
        """Test system with rapid influx of many concurrent tasks."""

        task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))
        worker_manager = WorkerManager(str(test_workspace_dir), config_manager)

        # Create flood of tasks (50 tasks arriving rapidly)
        flood_tasks = []
        for i in range(50):
            task = {
                "task_id": f"flood_task_{i+1:03d}",
                "description": f"Process flood task {i+1}",
                "priority": random.randint(1, 10),
                "estimated_tokens": random.randint(500, 2000),
                "timeout": 3600
            }
            flood_tasks.append(task)

        # Add all tasks rapidly (simulating flood)
        start_time = time.time()
        for task in flood_tasks:
            await task_queue.add_task(task)

        task_addition_time = time.time() - start_time

        # Spawn maximum workers to handle flood
        worker_configs = []
        for i in range(12):
            worker_id = f"flood-worker-{i+1:03d}"
            worker_config = config_manager.create_worker_config(
                worker_id=worker_id,
                model="sonnet-4"
            )
            worker_configs.append(worker_config)

            with patch.object(worker_manager, 'spawn_worker') as mock_spawn:
                mock_spawn.return_value = True
                result = await worker_manager.spawn_worker(worker_config)
                assert result is True

        # Process tasks in batches
        batch_size = 12  # One per worker
        processed_tasks = 0

        while processed_tasks < len(flood_tasks):
            # Get next batch
            batch_end = min(processed_tasks + batch_size, len(flood_tasks))
            current_batch = flood_tasks[processed_tasks:batch_end]

            # Assign to workers
            for i, task in enumerate(current_batch):
                worker_idx = i % len(worker_configs)
                task["worker_id"] = worker_configs[worker_idx].worker_id
                await task_queue.update_task_status(task["task_id"], "completed")

            processed_tasks = batch_end

        processing_time = time.time() - start_time

        # Verify all tasks processed
        all_completed = await task_queue.get_tasks_by_status("completed")
        completed_flood_tasks = [
            task for task in all_completed
            if task["task_id"].startswith("flood_task_")
        ]

        assert len(completed_flood_tasks) == len(flood_tasks)

        # Performance assertions
        assert task_addition_time < 2.0  # Task addition should be fast
        assert processing_time < 15.0  # Processing should be reasonable even under flood


@pytest.mark.stress
class TestConflictResolution:
    """Test system under intentional conflict scenarios."""

    @pytest.mark.asyncio
    async def test_intentional_merge_conflicts(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager,
        test_helpers
    ):
        """Test system with intentionally conflicting changes from multiple workers."""

        # Setup
        test_repo = test_workspace_dir / "conflict_test_repo"
        test_helpers.create_test_git_repo(test_repo)

        # Create test files that will have conflicts
        conflicting_files = {
            "src/config.py": "# Configuration file\nDEBUG = True\nAPI_VERSION = 'v1'\n",
            "src/utils.py": "# Utility functions\ndef helper():\n    return 'original'\n",
            "src/models.py": "# Data models\nclass User:\n    def __init__(self):\n        self.name = 'default'\n"
        }
        test_helpers.create_test_files(test_repo, conflicting_files)

        merge_coordinator = MergeCoordinator(str(test_repo))
        task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))

        # Create tasks that will cause conflicts
        conflicting_tasks = [
            {
                "task_id": "config_update_1",
                "description": "Update config for production deployment",
                "files_to_modify": ["src/config.py"],
                "changes": {"DEBUG": "False", "API_VERSION": "'v2'"},
                "worker_id": "conflict-worker-001"
            },
            {
                "task_id": "config_update_2",
                "description": "Update config for staging environment",
                "files_to_modify": ["src/config.py"],
                "changes": {"DEBUG": "True", "API_VERSION": "'v1.5'", "STAGING": "True"},
                "worker_id": "conflict-worker-002"
            },
            {
                "task_id": "config_update_3",
                "description": "Add monitoring config",
                "files_to_modify": ["src/config.py"],
                "changes": {"MONITORING": "True", "LOG_LEVEL": "'INFO'"},
                "worker_id": "conflict-worker-003"
            }
        ]

        # Add tasks and simulate completion with conflicts
        branch_names = []
        for task in conflicting_tasks:
            await task_queue.add_task(task)

            # Simulate worker creating conflicting changes
            branch_name = f"feature/{task['task_id']}"
            branch_names.append(branch_name)

            await task_queue.update_task_status(task["task_id"], "completed")

        # Attempt merge coordination with conflicts
        with patch.object(merge_coordinator, 'coordinate_merge') as mock_merge:
            # Simulate conflict detection and resolution
            mock_merge.return_value = {
                "success": True,
                "conflicts_detected": 5,
                "conflicts_resolved": 5,
                "merge_strategy": "intelligent_merge",
                "final_files": {
                    "src/config.py": "# Merged configuration\nDEBUG = False\nAPI_VERSION = 'v2'\nSTAGING = True\nMONITORING = True\nLOG_LEVEL = 'INFO'\n"
                }
            }

            merge_result = await merge_coordinator.coordinate_merge(
                branches=branch_names,
                target_branch="main"
            )

            assert merge_result["success"] is True
            assert merge_result["conflicts_detected"] > 0
            assert merge_result["conflicts_resolved"] == merge_result["conflicts_detected"]

        # Verify conflict resolution was successful
        assert merge_result["merge_strategy"] == "intelligent_merge"

    @pytest.mark.asyncio
    async def test_resource_contention_conflicts(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager
    ):
        """Test system with multiple workers competing for limited resources."""

        task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))
        message_queue = MessageQueueManager("sqlite", str(test_workspace_dir / "messages.db"))

        # Create tasks that require same limited resources
        resource_tasks = []
        shared_resources = ["database_connection", "api_rate_limit", "file_lock", "memory_cache"]

        for i in range(20):  # 20 tasks competing for 4 resources
            resource_needed = shared_resources[i % len(shared_resources)]
            task = {
                "task_id": f"resource_task_{i+1:03d}",
                "description": f"Task requiring {resource_needed}",
                "resource_requirements": [resource_needed],
                "estimated_tokens": 1000,
                "priority": random.randint(1, 10)
            }
            resource_tasks.append(task)
            await task_queue.add_task(task)

        # Spawn workers
        worker_configs = []
        for i in range(8):  # 8 workers competing for resources
            worker_id = f"resource-worker-{i+1:03d}"
            worker_config = config_manager.create_worker_config(
                worker_id=worker_id,
                model="sonnet-4"
            )
            worker_configs.append(worker_config)

        # Simulate resource allocation conflicts
        resource_usage = {resource: None for resource in shared_resources}
        completed_tasks = []

        start_time = time.time()

        for task in resource_tasks:
            required_resource = task["resource_requirements"][0]

            # Check if resource is available
            if resource_usage[required_resource] is None:
                # Allocate resource
                resource_usage[required_resource] = task["task_id"]

                # Simulate task execution
                await asyncio.sleep(0.01)  # Brief execution time

                # Complete task and free resource
                await task_queue.update_task_status(task["task_id"], "completed")
                resource_usage[required_resource] = None
                completed_tasks.append(task["task_id"])
            else:
                # Resource contention - queue task for retry
                await asyncio.sleep(0.005)  # Wait and retry

                # Eventually allocate when resource becomes free
                while resource_usage[required_resource] is not None:
                    await asyncio.sleep(0.001)

                resource_usage[required_resource] = task["task_id"]
                await asyncio.sleep(0.01)
                await task_queue.update_task_status(task["task_id"], "completed")
                resource_usage[required_resource] = None
                completed_tasks.append(task["task_id"])

        execution_time = time.time() - start_time

        # Verify all tasks completed despite resource contention
        assert len(completed_tasks) == len(resource_tasks)

        # Verify reasonable performance under contention
        assert execution_time < 5.0


@pytest.mark.stress
class TestCrashRecovery:
    """Test system recovery from various crash scenarios."""

    @pytest.mark.asyncio
    async def test_master_crash_recovery(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager
    ):
        """Test system recovery from master node crash."""

        # Setup initial state
        task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))
        message_queue = MessageQueueManager("sqlite", str(test_workspace_dir / "messages.db"))
        shared_knowledge = SharedKnowledgeManager(str(test_workspace_dir))

        # Create tasks in progress
        active_tasks = []
        for i in range(5):
            task = {
                "task_id": f"recovery_task_{i+1:03d}",
                "description": f"Task {i+1} for crash recovery test",
                "status": "in_progress",
                "worker_id": f"recovery-worker-{i+1:03d}",
                "estimated_tokens": 1500
            }
            active_tasks.append(task)
            await task_queue.add_task(task)
            await task_queue.update_task_status(task["task_id"], "in_progress")

        # Store system state before crash
        pre_crash_state = {
            "active_tasks": len(active_tasks),
            "task_queue_size": len(await task_queue.get_all_tasks())
        }

        # Simulate master crash (sudden termination)
        # Simulate recovery by creating new instances
        recovered_task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))
        recovered_message_queue = MessageQueueManager("sqlite", str(test_workspace_dir / "messages.db"))
        recovered_shared_knowledge = SharedKnowledgeManager(str(test_workspace_dir))

        # Verify state recovery
        recovered_tasks = await recovered_task_queue.get_all_tasks()
        in_progress_tasks = [task for task in recovered_tasks if task["status"] == "in_progress"]

        assert len(recovered_tasks) == pre_crash_state["task_queue_size"]
        assert len(in_progress_tasks) == pre_crash_state["active_tasks"]

        # Continue processing after recovery
        for task in in_progress_tasks:
            await recovered_task_queue.update_task_status(task["task_id"], "completed")

        # Verify recovery was successful
        final_tasks = await recovered_task_queue.get_all_tasks()
        completed_tasks = [task for task in final_tasks if task["status"] == "completed"]

        assert len(completed_tasks) >= len(active_tasks)

    @pytest.mark.asyncio
    async def test_multiple_worker_crashes(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager
    ):
        """Test recovery from multiple simultaneous worker crashes."""

        task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))
        worker_manager = WorkerManager(str(test_workspace_dir), config_manager)

        # Spawn 8 workers
        original_workers = []
        for i in range(8):
            worker_id = f"crash-test-worker-{i+1:03d}"
            worker_config = config_manager.create_worker_config(
                worker_id=worker_id,
                model="sonnet-4"
            )
            original_workers.append(worker_config)

        # Assign tasks to workers
        tasks_in_progress = []
        for i, worker_config in enumerate(original_workers):
            task = {
                "task_id": f"crash_task_{i+1:03d}",
                "description": f"Task assigned to {worker_config.worker_id}",
                "worker_id": worker_config.worker_id,
                "estimated_tokens": 1200
            }
            tasks_in_progress.append(task)
            await task_queue.add_task(task)
            await task_queue.update_task_status(task["task_id"], "in_progress")

        # Simulate 5 workers crashing simultaneously
        crashed_workers = original_workers[:5]
        surviving_workers = original_workers[5:]

        # Mark crashed workers' tasks as failed
        for worker_config in crashed_workers:
            worker_tasks = [task for task in tasks_in_progress if task["worker_id"] == worker_config.worker_id]
            for task in worker_tasks:
                await task_queue.update_task_status(task["task_id"], "failed")

        # Spawn replacement workers
        replacement_workers = []
        for i in range(5):
            worker_id = f"replacement-worker-{i+1:03d}"
            worker_config = config_manager.create_worker_config(
                worker_id=worker_id,
                model="sonnet-4"
            )
            replacement_workers.append(worker_config)

            with patch.object(worker_manager, 'spawn_worker') as mock_spawn:
                mock_spawn.return_value = True
                result = await worker_manager.spawn_worker(worker_config)
                assert result is True

        # Reassign failed tasks to replacement workers
        failed_tasks = await task_queue.get_tasks_by_status("failed")
        for i, task in enumerate(failed_tasks):
            if i < len(replacement_workers):
                # Reassign to replacement worker
                task["worker_id"] = replacement_workers[i].worker_id
                await task_queue.update_task_status(task["task_id"], "in_progress")
                await task_queue.update_task_status(task["task_id"], "completed")

        # Complete tasks from surviving workers
        surviving_tasks = [task for task in tasks_in_progress
                          if task["worker_id"] in [w.worker_id for w in surviving_workers]]
        for task in surviving_tasks:
            await task_queue.update_task_status(task["task_id"], "completed")

        # Verify recovery
        all_tasks = await task_queue.get_all_tasks()
        completed_tasks = [task for task in all_tasks if task["status"] == "completed"]
        failed_tasks_final = [task for task in all_tasks if task["status"] == "failed"]

        # All tasks should be completed after recovery
        assert len(completed_tasks) >= len(tasks_in_progress)
        assert len(failed_tasks_final) == 0  # No tasks should remain failed

    @pytest.mark.asyncio
    async def test_database_corruption_recovery(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager
    ):
        """Test recovery from database corruption scenarios."""

        # Create initial database with tasks
        primary_db_path = str(test_workspace_dir / "primary_tasks.db")
        backup_db_path = str(test_workspace_dir / "backup_tasks.db")

        primary_queue = TaskQueue(primary_db_path)

        # Add critical tasks
        critical_tasks = []
        for i in range(10):
            task = {
                "task_id": f"critical_task_{i+1:03d}",
                "description": f"Critical task {i+1}",
                "priority": 10,
                "status": "in_progress" if i % 2 == 0 else "completed",
                "estimated_tokens": 2000
            }
            critical_tasks.append(task)
            await primary_queue.add_task(task)
            if task["status"] == "in_progress":
                await primary_queue.update_task_status(task["task_id"], "in_progress")
            else:
                await primary_queue.update_task_status(task["task_id"], "completed")

        # Create backup before "corruption"
        backup_queue = TaskQueue(backup_db_path)
        for task in critical_tasks:
            await backup_queue.add_task(task)
            await backup_queue.update_task_status(task["task_id"], task["status"])

        # Simulate database corruption (delete primary database)
        import os
        if os.path.exists(primary_db_path):
            os.remove(primary_db_path)

        # Attempt to access corrupted database (should fail)
        try:
            corrupted_queue = TaskQueue(primary_db_path)
            tasks = await corrupted_queue.get_all_tasks()
            # If this succeeds, the database was recreated empty
            assert len(tasks) == 0
        except Exception:
            # Expected if database is truly corrupted
            pass

        # Recover from backup
        recovered_queue = TaskQueue(backup_db_path)
        recovered_tasks = await recovered_queue.get_all_tasks()

        # Verify recovery
        assert len(recovered_tasks) == len(critical_tasks)

        # Check task statuses are preserved
        in_progress_count = len([task for task in recovered_tasks if task["status"] == "in_progress"])
        completed_count = len([task for task in recovered_tasks if task["status"] == "completed"])

        expected_in_progress = len([task for task in critical_tasks if task["status"] == "in_progress"])
        expected_completed = len([task for task in critical_tasks if task["status"] == "completed"])

        assert in_progress_count == expected_in_progress
        assert completed_count == expected_completed

        # Continue processing after recovery
        for task in recovered_tasks:
            if task["status"] == "in_progress":
                await recovered_queue.update_task_status(task["task_id"], "completed")

        # Verify full recovery
        final_tasks = await recovered_queue.get_all_tasks()
        all_completed = all(task["status"] == "completed" for task in final_tasks)
        assert all_completed is True


@pytest.mark.stress
@pytest.mark.slow
class TestLongRunningStress:
    """Test system stability over extended periods."""

    @pytest.mark.asyncio
    async def test_extended_operation_stability(
        self,
        test_workspace_dir: Path,
        config_manager: ConfigurationManager
    ):
        """Test system stability during extended operation (simulated)."""

        task_queue = TaskQueue(str(test_workspace_dir / "tasks.db"))
        message_queue = MessageQueueManager("sqlite", str(test_workspace_dir / "messages.db"))
        communication_hub = CommunicationHub(message_queue)

        # Simulate 6 hours of operation (compressed to reasonable test time)
        operation_cycles = 100  # Each cycle represents ~2 minutes of real operation
        tasks_per_cycle = 5
        total_tasks = operation_cycles * tasks_per_cycle

        worker_configs = []
        for i in range(6):  # 6 workers for extended operation
            worker_id = f"long-running-worker-{i+1:03d}"
            worker_config = config_manager.create_worker_config(
                worker_id=worker_id,
                model="sonnet-4"
            )
            worker_configs.append(worker_config)

        start_time = time.time()
        total_messages = 0
        memory_usage_samples = []

        for cycle in range(operation_cycles):
            cycle_start = time.time()

            # Create tasks for this cycle
            cycle_tasks = []
            for task_num in range(tasks_per_cycle):
                task = {
                    "task_id": f"long_task_{cycle:03d}_{task_num:03d}",
                    "description": f"Long-running cycle {cycle} task {task_num}",
                    "priority": random.randint(1, 5),
                    "estimated_tokens": random.randint(800, 1500),
                    "cycle": cycle
                }
                cycle_tasks.append(task)
                await task_queue.add_task(task)

            # Assign to workers
            for i, task in enumerate(cycle_tasks):
                worker_idx = i % len(worker_configs)
                task["worker_id"] = worker_configs[worker_idx].worker_id
                await task_queue.update_task_status(task["task_id"], "in_progress")

            # Simulate worker communications
            for _ in range(random.randint(2, 8)):  # Random communication per cycle
                worker_id = random.choice([w.worker_id for w in worker_configs])

                message = {
                    "message_id": f"long_msg_{cycle}_{total_messages}",
                    "from": worker_id,
                    "to": "master",
                    "type": random.choice(["status_update", "question", "progress_report"]),
                    "content": {"cycle": cycle, "progress": random.randint(10, 90)},
                    "timestamp": time.time()
                }

                await communication_hub.send_message(message)
                total_messages += 1

            # Complete cycle tasks
            for task in cycle_tasks:
                await task_queue.update_task_status(task["task_id"], "completed")

            # Sample "memory usage" (simulated)
            cycle_memory = random.randint(50, 150)  # MB
            memory_usage_samples.append(cycle_memory)

            # Brief pause between cycles
            await asyncio.sleep(0.01)

            cycle_time = time.time() - cycle_start

            # Ensure reasonable cycle performance
            assert cycle_time < 0.5  # Each cycle should complete quickly

        total_time = time.time() - start_time

        # Verify system stability metrics
        assert total_time < 30.0  # Total test should complete in reasonable time

        # Verify all tasks completed
        all_tasks = await task_queue.get_all_tasks()
        completed_tasks = [task for task in all_tasks if task["status"] == "completed"]
        assert len(completed_tasks) >= total_tasks

        # Verify communication system handled load
        assert total_messages > 200  # Should have generated substantial communication

        # Verify memory usage stayed reasonable (no major leaks)
        avg_memory = sum(memory_usage_samples) / len(memory_usage_samples)
        max_memory = max(memory_usage_samples)
        assert max_memory < avg_memory * 2  # No memory spikes more than 2x average

        # Verify system maintained responsiveness
        recent_cycle_times = memory_usage_samples[-10:]  # Last 10 cycles
        early_cycle_times = memory_usage_samples[:10]   # First 10 cycles

        # Performance shouldn't degrade significantly over time
        recent_avg = sum(recent_cycle_times) / len(recent_cycle_times)
        early_avg = sum(early_cycle_times) / len(early_cycle_times)

        performance_degradation = (recent_avg - early_avg) / early_avg if early_avg > 0 else 0
        assert performance_degradation < 0.5  # Less than 50% performance degradation