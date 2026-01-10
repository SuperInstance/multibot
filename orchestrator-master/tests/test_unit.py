#!/usr/bin/env python3
"""
Unit Tests for Multi-Agent Orchestrator
Tests individual components in isolation.
"""

import pytest
import asyncio
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from config_manager import ConfigurationManager, MasterConfiguration, WorkerConfiguration
from worker_manager import WorkerManager
from task_queue import TaskQueue
from message_queue import MessageQueueManager
from communication import CommunicationHub
from memory_management import WorkerMemoryManager, ContextManager
from shared_knowledge import SharedKnowledgeManager
from task_decomposition import TaskDecomposer
from merge_coordination import MergeCoordinator


@pytest.mark.unit
class TestConfigurationManager:
    """Test configuration management functionality."""

    def test_create_default_configs(self, config_manager):
        """Test creation of default configuration files."""
        # Check that config files were created
        assert config_manager.master_config_file.exists()
        assert config_manager.worker_template_file.exists()

        # Check file contents
        master_content = config_manager.master_config_file.read_text()
        assert "orchestrator:" in master_content
        assert "max_workers:" in master_content

        worker_content = config_manager.worker_template_file.read_text()
        assert "worker:" in worker_content
        assert "{worker_id}" in worker_content

    def test_load_master_config(self, config_manager):
        """Test loading master configuration."""
        config = config_manager.load_master_config()

        assert isinstance(config, MasterConfiguration)
        assert config.orchestrator.max_workers == 12
        assert config.orchestrator.default_worker_model == "sonnet-4"
        assert config.communication.websocket_port == 8765

    def test_create_worker_config(self, config_manager):
        """Test creating worker configuration from template."""
        worker_config = config_manager.create_worker_config(
            worker_id="test-worker",
            model="opus-4",
            max_concurrent_tasks=2
        )

        assert isinstance(worker_config, WorkerConfiguration)
        assert worker_config.worker.id == "test-worker"
        assert worker_config.worker.model == "opus-4"
        assert worker_config.worker.max_concurrent_tasks == 2

    def test_environment_variable_resolution(self, config_manager, mock_environment_vars):
        """Test environment variable resolution in configs."""
        from config_manager import EnvironmentVariableResolver

        # Test basic resolution
        test_value = "${ANTHROPIC_API_KEY}"
        resolved = EnvironmentVariableResolver.resolve_value(test_value)
        assert resolved == "test-api-key-123"

        # Test with default value
        test_value = "${MISSING_VAR:default_value}"
        resolved = EnvironmentVariableResolver.resolve_value(test_value)
        assert resolved == "default_value"

        # Test nested resolution
        test_dict = {
            "api_key": "${ANTHROPIC_API_KEY}",
            "github": "${GITHUB_TOKEN}",
            "nested": {
                "repo": "${GITHUB_REPO_URL}"
            }
        }
        resolved = EnvironmentVariableResolver.resolve_value(test_dict)
        assert resolved["api_key"] == "test-api-key-123"
        assert resolved["github"] == "test-github-token-456"
        assert resolved["nested"]["repo"] == "https://github.com/test/repo"


@pytest.mark.unit
class TestTaskQueue:
    """Test task queue functionality."""

    @pytest.mark.asyncio
    async def test_add_task(self, task_queue, sample_task):
        """Test adding a task to the queue."""
        task_id = await task_queue.add_task(sample_task)
        assert task_id == sample_task["task_id"]

        # Verify task was added
        task = await task_queue.get_task(task_id)
        assert task is not None
        assert task["description"] == sample_task["description"]

    @pytest.mark.asyncio
    async def test_assign_task(self, task_queue, sample_task):
        """Test assigning a task to a worker."""
        # Add task
        await task_queue.add_task(sample_task)

        # Assign to worker
        success = await task_queue.assign_task(sample_task["task_id"], sample_task["worker_id"])
        assert success

        # Verify assignment
        task = await task_queue.get_task(sample_task["task_id"])
        assert task["worker_id"] == sample_task["worker_id"]
        assert task["status"] == "assigned"

    @pytest.mark.asyncio
    async def test_complete_task(self, task_queue, sample_task):
        """Test completing a task."""
        # Add and assign task
        await task_queue.add_task(sample_task)
        await task_queue.assign_task(sample_task["task_id"], sample_task["worker_id"])

        # Complete task
        completion_result = {
            "status": "completed",
            "result": "Authentication feature implemented successfully",
            "files_modified": ["src/auth.py", "src/models/user.py"]
        }
        success = await task_queue.complete_task(sample_task["task_id"], completion_result)
        assert success

        # Verify completion
        task = await task_queue.get_task(sample_task["task_id"])
        assert task["status"] == "completed"
        assert task["result"] == completion_result["result"]

    @pytest.mark.asyncio
    async def test_get_pending_tasks(self, task_queue):
        """Test retrieving pending tasks."""
        # Add multiple tasks
        tasks = [
            {"task_id": "task1", "description": "Task 1", "priority": 5, "status": "pending"},
            {"task_id": "task2", "description": "Task 2", "priority": 8, "status": "pending"},
            {"task_id": "task3", "description": "Task 3", "priority": 3, "status": "assigned"}
        ]

        for task in tasks:
            await task_queue.add_task(task)

        # Get pending tasks
        pending = await task_queue.get_pending_tasks()
        pending_ids = [task["task_id"] for task in pending]

        assert "task1" in pending_ids
        assert "task2" in pending_ids
        assert "task3" not in pending_ids  # This one is assigned


@pytest.mark.unit
class TestMessageQueue:
    """Test message queue functionality."""

    @pytest.mark.asyncio
    async def test_send_receive_message(self, message_queue):
        """Test sending and receiving messages."""
        test_message = {
            "from": "master",
            "to": "worker-001",
            "type": "task_assignment",
            "content": {"task_id": "test_task", "description": "Test task"}
        }

        # Send message
        await message_queue.send_message(test_message)

        # Receive message
        messages = await message_queue.get_messages("worker-001")
        assert len(messages) == 1
        assert messages[0]["content"]["task_id"] == "test_task"

    @pytest.mark.asyncio
    async def test_broadcast_message(self, message_queue):
        """Test broadcasting messages to multiple recipients."""
        broadcast_message = {
            "from": "master",
            "to": "all_workers",
            "type": "broadcast",
            "content": {"announcement": "System maintenance in 10 minutes"}
        }

        await message_queue.broadcast_message(broadcast_message, ["worker-001", "worker-002"])

        # Check both workers received the message
        messages_1 = await message_queue.get_messages("worker-001")
        messages_2 = await message_queue.get_messages("worker-002")

        assert len(messages_1) == 1
        assert len(messages_2) == 1
        assert messages_1[0]["content"]["announcement"] == "System maintenance in 10 minutes"

    @pytest.mark.asyncio
    async def test_message_acknowledgment(self, message_queue):
        """Test message acknowledgment."""
        test_message = {
            "from": "worker-001",
            "to": "master",
            "type": "task_completion",
            "content": {"task_id": "completed_task"}
        }

        await message_queue.send_message(test_message)
        messages = await message_queue.get_messages("master")
        message_id = messages[0]["id"]

        # Acknowledge message
        await message_queue.acknowledge_message(message_id)

        # Verify message is acknowledged
        acknowledged = await message_queue.get_acknowledged_messages("master")
        assert len(acknowledged) == 1
        assert acknowledged[0]["id"] == message_id


@pytest.mark.unit
class TestWorkerMemoryManager:
    """Test worker memory management."""

    @pytest.mark.asyncio
    async def test_save_context(self, worker_memory_manager):
        """Test saving conversation context."""
        # Add some conversation content
        worker_memory_manager.context_manager.add_to_context("User asked about authentication", 150)
        worker_memory_manager.context_manager.add_to_context("I explained JWT token workflow", 200)
        worker_memory_manager.context_manager.add_to_context("User requested implementation details", 100)

        # Save context
        result = await worker_memory_manager.save_current_context()

        assert result["status"] == "success"
        assert result["tokens_saved"] == 450
        assert worker_memory_manager.current_context_file.exists()

    @pytest.mark.asyncio
    async def test_update_understanding(self, worker_memory_manager):
        """Test updating code understanding."""
        module_understanding = """
        The auth service handles user authentication using JWT tokens.
        It provides login, logout, and token refresh functionality.
        Dependencies: user model, password hashing, token generation.
        """

        result = await worker_memory_manager.update_understanding(
            module_name="auth_service",
            understanding=module_understanding,
            file_path="src/services/auth.py"
        )

        assert result["status"] == "success"
        assert result["module_name"] == "auth_service"
        assert worker_memory_manager.code_understanding_file.exists()

        # Verify understanding was saved
        content = worker_memory_manager.code_understanding_file.read_text()
        assert "auth_service" in content
        assert "JWT tokens" in content

    @pytest.mark.asyncio
    async def test_search_memory(self, worker_memory_manager):
        """Test searching across memory files."""
        # Add some understanding first
        await worker_memory_manager.update_understanding(
            "auth_service",
            "JWT token authentication service",
            "src/auth.py"
        )

        # Search for relevant content
        result = await worker_memory_manager.search_memory("JWT authentication")

        assert result["status"] == "success"
        assert result["results_found"] > 0
        assert any("auth_service" in str(r) for r in result["results"])


@pytest.mark.unit
class TestSharedKnowledgeManager:
    """Test shared knowledge management."""

    @pytest.mark.asyncio
    async def test_acquire_module_lock(self, shared_knowledge_manager):
        """Test acquiring module locks."""
        result = await shared_knowledge_manager.acquire_module_lock(
            worker_id="worker-001",
            task_id="auth_task",
            module_name="user_model",
            dependencies=[]
        )

        assert result["status"] == "success"
        assert result["module_name"] == "user_model"
        assert result["worker_id"] == "worker-001"

        # Test conflict detection
        conflict_result = await shared_knowledge_manager.acquire_module_lock(
            worker_id="worker-002",
            task_id="another_task",
            module_name="user_model",
            dependencies=[]
        )

        assert conflict_result["status"] == "conflict"
        assert len(conflict_result["conflicts"]) > 0

    @pytest.mark.asyncio
    async def test_share_task_completion(self, shared_knowledge_manager, sample_completion_data):
        """Test sharing task completion context."""
        result = await shared_knowledge_manager.share_task_completion(
            worker_id="worker-001",
            task_id="auth_001",
            completion_data=sample_completion_data
        )

        assert result["status"] == "success"
        assert result["shared_count"] > 0
        assert "API: User Registration API" in result["shared_items"]

    @pytest.mark.asyncio
    async def test_get_relevant_context(self, shared_knowledge_manager, sample_completion_data):
        """Test getting relevant context for a task."""
        # First share some context
        await shared_knowledge_manager.share_task_completion(
            "worker-001", "auth_001", sample_completion_data
        )

        # Now get relevant context for related task
        result = await shared_knowledge_manager.get_relevant_context(
            worker_id="worker-002",
            task_description="Implement user login functionality",
            modules_involved=["user_model", "auth_service"]
        )

        assert result["status"] == "success"
        assert result["total_items"] > 0
        assert len(result["context"]["api_contracts"]) > 0


@pytest.mark.unit
class TestTaskDecomposer:
    """Test task decomposition functionality."""

    @pytest.mark.asyncio
    async def test_decompose_simple_task(self):
        """Test decomposing a simple task."""
        decomposer = TaskDecomposer()

        task_description = "Add user registration feature"
        context = {
            "framework": "fastapi",
            "database": "postgresql",
            "requirements": ["email validation", "password hashing"]
        }

        task_graph = await decomposer.decompose_task(task_description, context)

        assert task_graph is not None
        assert len(task_graph.tasks) > 0
        assert task_graph.total_estimated_tokens > 0
        assert len(task_graph.phases) > 0

        # Check that tasks have required fields
        for task in task_graph.tasks.values():
            assert task.task_id
            assert task.title
            assert task.description
            assert task.complexity
            assert task.estimated_tokens > 0

    @pytest.mark.asyncio
    async def test_dependency_analysis(self):
        """Test dependency analysis in task decomposition."""
        decomposer = TaskDecomposer()

        # Use a complex task that should generate dependencies
        task_description = "Implement complete authentication system with user management"
        context = {"type": "authentication_system"}

        task_graph = await decomposer.decompose_task(task_description, context)

        # Check for dependencies
        dependent_tasks = [task for task in task_graph.tasks.values() if task.dependencies]
        assert len(dependent_tasks) > 0

        # Verify dependency integrity
        all_task_ids = set(task_graph.tasks.keys())
        for task in dependent_tasks:
            for dep_id in task.dependencies:
                assert dep_id in all_task_ids, f"Dependency {dep_id} not found in task list"


@pytest.mark.unit
class TestMergeCoordinator:
    """Test merge coordination functionality."""

    @pytest.mark.asyncio
    async def test_merge_coordination(self, sample_worker_branches):
        """Test coordinating merge of worker branches."""
        coordinator = MergeCoordinator()

        result = await coordinator.coordinate_merge_phase(
            graph_id="test_graph_001",
            worker_branches=sample_worker_branches
        )

        assert result.status in ["completed", "in_progress", "conflict"]
        assert result.graph_id == "test_graph_001"
        assert len(result.branches_merged) >= 0

    @pytest.mark.asyncio
    async def test_conflict_detection(self, sample_worker_branches):
        """Test conflict detection between branches."""
        coordinator = MergeCoordinator()

        # Create conflicting branches (same file modified)
        conflicting_branches = [
            {
                "worker_id": "worker-001",
                "branch_name": "feature/conflict-1",
                "files_modified": ["src/shared/config.py"],
                "test_status": "passed",
                "dependencies": [],
                "merge_priority": 1
            },
            {
                "worker_id": "worker-002",
                "branch_name": "feature/conflict-2",
                "files_modified": ["src/shared/config.py"],  # Same file
                "test_status": "passed",
                "dependencies": [],
                "merge_priority": 2
            }
        ]

        # Convert to WorkerBranch objects
        branches = [coordinator._create_worker_branch(branch) for branch in conflicting_branches]

        # Analyze conflicts
        conflicts = await coordinator.conflict_analyzer.analyze_conflicts(branches)

        assert len(conflicts) > 0
        assert any(conflict.conflict_type.value == "file_conflict" for conflict in conflicts)


@pytest.mark.unit
class TestGitWorktreeOperations:
    """Test Git worktree operations."""

    def test_create_git_worktree(self, temp_dir, test_helpers):
        """Test creating a Git worktree."""
        # Create main repository
        main_repo = temp_dir / "main_repo"
        test_helpers.create_test_git_repo(main_repo)

        # Create worktree
        worktree_path = temp_dir / "worker_worktree"

        try:
            result = subprocess.run([
                "git", "worktree", "add", str(worktree_path), "-b", "worker-branch"
            ], cwd=main_repo, check=True, capture_output=True)

            assert result.returncode == 0
            assert worktree_path.exists()
            assert (worktree_path / ".git").exists()

            # Verify worktree is on correct branch
            result = subprocess.run([
                "git", "branch", "--show-current"
            ], cwd=worktree_path, capture_output=True, text=True)

            assert "worker-branch" in result.stdout

        except subprocess.CalledProcessError as e:
            pytest.fail(f"Git worktree creation failed: {e}")

    def test_remove_git_worktree(self, temp_dir, test_helpers):
        """Test removing a Git worktree."""
        # Create main repository and worktree
        main_repo = temp_dir / "main_repo"
        test_helpers.create_test_git_repo(main_repo)

        worktree_path = temp_dir / "worker_worktree"

        # Add worktree
        subprocess.run([
            "git", "worktree", "add", str(worktree_path), "-b", "worker-branch"
        ], cwd=main_repo, check=True, capture_output=True)

        # Remove worktree
        result = subprocess.run([
            "git", "worktree", "remove", str(worktree_path)
        ], cwd=main_repo, check=True, capture_output=True)

        assert result.returncode == 0
        assert not worktree_path.exists()

        # Verify worktree is removed from list
        result = subprocess.run([
            "git", "worktree", "list"
        ], cwd=main_repo, capture_output=True, text=True)

        assert str(worktree_path) not in result.stdout


@pytest.mark.unit
class TestContextManager:
    """Test conversation context management."""

    def test_add_to_context(self):
        """Test adding content to context."""
        context_mgr = ContextManager()

        context_mgr.add_to_context("First message", 100)
        context_mgr.add_to_context("Second message", 150)

        assert context_mgr.current_token_count == 250
        assert len(context_mgr.conversation_history) == 2

    def test_should_save_context(self):
        """Test context save threshold detection."""
        context_mgr = ContextManager(save_threshold=1000)

        # Below threshold
        context_mgr.add_to_context("Small message", 500)
        assert not context_mgr.should_save_context()

        # Above threshold
        context_mgr.add_to_context("Large message", 600)
        assert context_mgr.should_save_context()

    def test_trim_context(self):
        """Test trimming context to fit token limits."""
        context_mgr = ContextManager(max_active_tokens=500)

        # Add content exceeding limit
        context_mgr.add_to_context("Message 1", 200)
        context_mgr.add_to_context("Message 2", 200)
        context_mgr.add_to_context("Message 3", 200)  # Total: 600

        # Trim context
        removed = context_mgr.trim_context()

        assert context_mgr.current_token_count <= 500
        assert len(removed) > 0  # Some content was removed

    def test_create_context_summary(self):
        """Test creating context summary."""
        context_mgr = ContextManager()

        # Add diverse content
        content = [
            "User asked about implementing JWT authentication",
            "Decision: Use RS256 algorithm for token signing",
            "Question: Should we implement refresh tokens?",
            "Working on src/auth.py module",
            "Important: Remember to hash passwords before storing"
        ]

        for i, msg in enumerate(content):
            context_mgr.add_to_context(msg, 50 + i * 10)

        summary = context_mgr.create_context_summary()

        assert summary.token_count == context_mgr.current_token_count
        assert len(summary.key_points) > 0
        assert len(summary.code_areas_touched) > 0
        assert "auth" in summary.summary.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])