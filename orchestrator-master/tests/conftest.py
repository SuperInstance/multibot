#!/usr/bin/env python3
"""
Pytest configuration and fixtures for orchestrator tests.
"""

import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Generator
import logging
import os

# Import test dependencies
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import ConfigurationManager, MasterConfiguration, WorkerConfiguration
from worker_manager import WorkerManager
from task_queue import TaskQueue
from message_queue import MessageQueueManager
from communication import CommunicationHub
from memory_management import WorkerMemoryManager
from shared_knowledge import SharedKnowledgeManager


# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp(prefix="orchestrator_test_"))
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_config_dir(temp_dir: Path) -> Path:
    """Create test configuration directory."""
    config_dir = temp_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def test_workspace_dir(temp_dir: Path) -> Path:
    """Create test workspace directory."""
    workspace_dir = temp_dir / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (workspace_dir / "workers").mkdir(exist_ok=True)
    (workspace_dir / "shared_knowledge").mkdir(exist_ok=True)
    (workspace_dir / "logs").mkdir(exist_ok=True)

    return workspace_dir


@pytest.fixture
def config_manager(test_config_dir: Path) -> ConfigurationManager:
    """Create test configuration manager."""
    config_mgr = ConfigurationManager(test_config_dir)
    config_mgr.create_default_configs()
    return config_mgr


@pytest.fixture
def master_config(config_manager: ConfigurationManager) -> MasterConfiguration:
    """Load test master configuration."""
    return config_manager.load_master_config()


@pytest.fixture
def worker_config(config_manager: ConfigurationManager) -> WorkerConfiguration:
    """Create test worker configuration."""
    return config_manager.create_worker_config(
        worker_id="test-worker-001",
        model="sonnet-4"
    )


@pytest.fixture
def task_queue(temp_dir: Path) -> TaskQueue:
    """Create test task queue."""
    db_path = temp_dir / "test_tasks.db"
    return TaskQueue(str(db_path))


@pytest.fixture
def message_queue(temp_dir: Path) -> MessageQueueManager:
    """Create test message queue."""
    db_path = temp_dir / "test_messages.db"
    return MessageQueueManager(queue_type="sqlite", sqlite_path=str(db_path))


@pytest.fixture
def communication_hub(message_queue: MessageQueueManager) -> CommunicationHub:
    """Create test communication hub."""
    return CommunicationHub(message_queue)


@pytest.fixture
def worker_manager(test_workspace_dir: Path, config_manager: ConfigurationManager) -> WorkerManager:
    """Create test worker manager."""
    return WorkerManager(
        workspace_path=str(test_workspace_dir),
        config_manager=config_manager
    )


@pytest.fixture
def worker_memory_manager(test_workspace_dir: Path) -> WorkerMemoryManager:
    """Create test worker memory manager."""
    return WorkerMemoryManager(
        worker_id="test-worker-001",
        workspace_path=str(test_workspace_dir)
    )


@pytest.fixture
def shared_knowledge_manager(test_workspace_dir: Path) -> SharedKnowledgeManager:
    """Create test shared knowledge manager."""
    return SharedKnowledgeManager(str(test_workspace_dir))


@pytest.fixture
def sample_task() -> Dict[str, Any]:
    """Create sample test task."""
    return {
        "task_id": "test_task_001",
        "description": "Add user authentication feature",
        "priority": 5,
        "worker_id": "test-worker-001",
        "context": {
            "files": ["src/auth.py", "src/models/user.py"],
            "requirements": ["JWT tokens", "password hashing", "session management"]
        },
        "estimated_tokens": 2500,
        "timeout": 1800
    }


@pytest.fixture
def sample_subtasks() -> list[Dict[str, Any]]:
    """Create sample subtasks for testing."""
    return [
        {
            "task_id": "auth_001",
            "title": "Create User Model",
            "description": "Create User model with authentication fields",
            "complexity": "medium",
            "estimated_tokens": 800,
            "files_involved": ["src/models/user.py"],
            "dependencies": []
        },
        {
            "task_id": "auth_002",
            "title": "Implement JWT Service",
            "description": "Create JWT token generation and validation service",
            "complexity": "medium",
            "estimated_tokens": 1000,
            "files_involved": ["src/services/jwt.py"],
            "dependencies": []
        },
        {
            "task_id": "auth_003",
            "title": "Create Authentication Middleware",
            "description": "Implement middleware for request authentication",
            "complexity": "complex",
            "estimated_tokens": 1200,
            "files_involved": ["src/middleware/auth.py"],
            "dependencies": ["auth_001", "auth_002"]
        }
    ]


@pytest.fixture
def sample_worker_branches() -> list[Dict[str, Any]]:
    """Create sample worker branches for merge testing."""
    return [
        {
            "worker_id": "worker-001",
            "branch_name": "feature/user-model",
            "task_ids": ["auth_001"],
            "files_modified": ["src/models/user.py", "tests/test_user.py"],
            "test_status": "passed",
            "dependencies": [],
            "merge_priority": 1
        },
        {
            "worker_id": "worker-002",
            "branch_name": "feature/jwt-service",
            "task_ids": ["auth_002"],
            "files_modified": ["src/services/jwt.py", "tests/test_jwt.py"],
            "test_status": "passed",
            "dependencies": [],
            "merge_priority": 2
        },
        {
            "worker_id": "worker-003",
            "branch_name": "feature/auth-middleware",
            "task_ids": ["auth_003"],
            "files_modified": ["src/middleware/auth.py", "tests/test_auth.py"],
            "test_status": "passed",
            "dependencies": ["worker-001", "worker-002"],
            "merge_priority": 3
        }
    ]


@pytest.fixture
def sample_completion_data() -> Dict[str, Any]:
    """Create sample task completion data."""
    return {
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
                "description": "Register new user account",
                "dependencies": ["email_service"]
            }
        ],
        "decisions_made": [
            {
                "title": "Email as Primary Identifier",
                "decision": "Use email address as primary user identifier",
                "rationale": "Email is unique and supports password recovery",
                "alternatives": ["username", "phone number"],
                "consequences": ["Email validation required", "Unique constraint needed"],
                "affects_modules": ["user_model", "auth_service"]
            }
        ],
        "learnings": [
            {
                "title": "Email Validation Performance",
                "description": "Email regex validation can be expensive for large batches",
                "type": "performance",
                "severity": "medium",
                "solution": "Use async validation with domain caching",
                "module": "user_model",
                "tags": ["validation", "performance", "email"]
            }
        ]
    }


@pytest.fixture
def mock_environment_vars():
    """Set up mock environment variables for testing."""
    original_values = {}
    test_vars = {
        "ANTHROPIC_API_KEY": "test-api-key-123",
        "GITHUB_TOKEN": "test-github-token-456",
        "GITHUB_REPO_URL": "https://github.com/test/repo"
    }

    # Store original values
    for key in test_vars:
        original_values[key] = os.getenv(key)

    # Set test values
    for key, value in test_vars.items():
        os.environ[key] = value

    yield test_vars

    # Restore original values
    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture
async def async_context():
    """Provide async context for tests that need it."""
    # Setup async resources
    yield
    # Cleanup async resources


# Test helpers
class TestHelpers:
    """Helper methods for tests."""

    @staticmethod
    def create_test_git_repo(repo_path: Path) -> None:
        """Create a test git repository."""
        import subprocess

        repo_path.mkdir(parents=True, exist_ok=True)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)

        # Create initial file
        test_file = repo_path / "README.md"
        test_file.write_text("# Test Repository\n")

        # Initial commit
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
        subprocess.run([
            "git", "commit", "-m", "Initial commit"
        ], cwd=repo_path, check=True, capture_output=True)

    @staticmethod
    def create_test_files(base_dir: Path, files: Dict[str, str]) -> None:
        """Create test files with content."""
        for file_path, content in files.items():
            full_path = base_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

    @staticmethod
    async def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1) -> bool:
        """Wait for a condition to become true."""
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            if await condition_func() if asyncio.iscoroutinefunction(condition_func) else condition_func():
                return True
            await asyncio.sleep(interval)

        return False


@pytest.fixture
def test_helpers() -> TestHelpers:
    """Provide test helper methods."""
    return TestHelpers()


# Marks for test categorization
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.e2e = pytest.mark.e2e
pytest.mark.stress = pytest.mark.stress
pytest.mark.slow = pytest.mark.slow