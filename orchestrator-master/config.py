"""
Configuration module for the Master Orchestrator.
Handles logging setup, error handling, and system configuration.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any


class OrchestratorConfig:
    """Configuration management for the orchestrator."""

    def __init__(self):
        # Base paths
        self.base_dir = Path(__file__).parent
        self.logs_dir = Path("/tmp/multibot/logs")
        self.state_dir = Path("/tmp/multibot/state")
        self.comm_dir = Path("/tmp/multibot/communication")

        # Create directories
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.comm_dir.mkdir(parents=True, exist_ok=True)

        # Logging configuration
        self.log_level = os.getenv("MULTIBOT_LOG_LEVEL", "INFO")
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.log_file = self.logs_dir / "orchestrator.log"

        # Server configuration
        self.server_host = os.getenv("MULTIBOT_HOST", "localhost")
        self.server_port = int(os.getenv("MULTIBOT_PORT", "8000"))

        # Worker configuration
        self.max_workers = int(os.getenv("MULTIBOT_MAX_WORKERS", "10"))
        self.worker_timeout = int(os.getenv("MULTIBOT_WORKER_TIMEOUT", "300"))
        self.heartbeat_interval = int(os.getenv("MULTIBOT_HEARTBEAT_INTERVAL", "30"))

        # Repository configuration
        self.repo_path = os.getenv("MULTIBOT_REPO_PATH", os.getcwd())
        self.worktree_cleanup = os.getenv("MULTIBOT_WORKTREE_CLEANUP", "true").lower() == "true"

        # Task configuration
        self.task_retry_limit = int(os.getenv("MULTIBOT_TASK_RETRY_LIMIT", "3"))
        self.task_timeout = int(os.getenv("MULTIBOT_TASK_TIMEOUT", "1800"))  # 30 minutes

        # Safety configuration
        self.enable_auto_merge = os.getenv("MULTIBOT_AUTO_MERGE", "false").lower() == "true"
        self.require_manual_approval = os.getenv("MULTIBOT_MANUAL_APPROVAL", "true").lower() == "true"

    def setup_logging(self) -> logging.Logger:
        """Set up comprehensive logging for the orchestrator."""
        # Create main logger
        logger = logging.getLogger("orchestrator")
        logger.setLevel(getattr(logging, self.log_level.upper()))

        # Clear any existing handlers
        logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, self.log_level.upper()))
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Error file handler for errors only
        error_handler = logging.handlers.RotatingFileHandler(
            self.logs_dir / "orchestrator_errors.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)

        # Set up module-specific loggers
        self._setup_module_loggers()

        logger.info("Logging system initialized")
        logger.info(f"Log level: {self.log_level}")
        logger.info(f"Log file: {self.log_file}")

        return logger

    def _setup_module_loggers(self):
        """Set up loggers for individual modules."""
        modules = [
            "worker_manager",
            "task_queue",
            "communication",
            "repo_manager",
            "monitoring_gui"
        ]

        for module in modules:
            module_logger = logging.getLogger(module)
            module_logger.setLevel(getattr(logging, self.log_level.upper()))

            # Module-specific file handler
            module_handler = logging.handlers.RotatingFileHandler(
                self.logs_dir / f"{module}.log",
                maxBytes=5*1024*1024,  # 5MB
                backupCount=3
            )
            module_handler.setLevel(getattr(logging, self.log_level.upper()))
            module_formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
            )
            module_handler.setFormatter(module_formatter)
            module_logger.addHandler(module_handler)

    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        return {
            "base_dir": str(self.base_dir),
            "logs_dir": str(self.logs_dir),
            "state_dir": str(self.state_dir),
            "comm_dir": str(self.comm_dir),
            "log_level": self.log_level,
            "server_host": self.server_host,
            "server_port": self.server_port,
            "max_workers": self.max_workers,
            "worker_timeout": self.worker_timeout,
            "heartbeat_interval": self.heartbeat_interval,
            "repo_path": self.repo_path,
            "worktree_cleanup": self.worktree_cleanup,
            "task_retry_limit": self.task_retry_limit,
            "task_timeout": self.task_timeout,
            "enable_auto_merge": self.enable_auto_merge,
            "require_manual_approval": self.require_manual_approval
        }

    def validate_config(self) -> bool:
        """Validate configuration settings."""
        errors = []

        # Check repository path
        if not Path(self.repo_path).exists():
            errors.append(f"Repository path does not exist: {self.repo_path}")

        if not (Path(self.repo_path) / ".git").exists():
            errors.append(f"Not a Git repository: {self.repo_path}")

        # Check port availability
        if not (1 <= self.server_port <= 65535):
            errors.append(f"Invalid port number: {self.server_port}")

        # Check worker limits
        if self.max_workers <= 0:
            errors.append(f"Invalid max_workers: {self.max_workers}")

        if self.worker_timeout <= 0:
            errors.append(f"Invalid worker_timeout: {self.worker_timeout}")

        # Check task limits
        if self.task_retry_limit < 0:
            errors.append(f"Invalid task_retry_limit: {self.task_retry_limit}")

        if self.task_timeout <= 0:
            errors.append(f"Invalid task_timeout: {self.task_timeout}")

        if errors:
            logger = logging.getLogger("orchestrator")
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return False

        return True


class ErrorHandler:
    """Centralized error handling for the orchestrator."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.error_counts: Dict[str, int] = {}
        self.critical_errors: List[Dict[str, Any]] = []

    def handle_error(
        self,
        error: Exception,
        context: str,
        critical: bool = False,
        reraise: bool = False
    ) -> Optional[str]:
        """Handle an error with appropriate logging and tracking."""
        error_key = f"{context}:{type(error).__name__}"

        # Track error frequency
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

        # Create error info
        error_info = {
            "error_type": type(error).__name__,
            "message": str(error),
            "context": context,
            "count": self.error_counts[error_key],
            "timestamp": logging.Formatter().formatTime(logging.LogRecord(
                "", logging.ERROR, "", 0, "", (), None
            ))
        }

        # Log based on severity
        if critical:
            self.logger.critical(f"CRITICAL ERROR in {context}: {str(error)}", exc_info=True)
            self.critical_errors.append(error_info)

            # Limit critical error history
            if len(self.critical_errors) > 100:
                self.critical_errors = self.critical_errors[-100:]

        else:
            if self.error_counts[error_key] == 1:
                # First occurrence - full details
                self.logger.error(f"Error in {context}: {str(error)}", exc_info=True)
            elif self.error_counts[error_key] <= 5:
                # Limited repetition
                self.logger.error(f"Error in {context} (#{self.error_counts[error_key]}): {str(error)}")
            elif self.error_counts[error_key] % 10 == 0:
                # Periodic logging for repeated errors
                self.logger.error(
                    f"Repeated error in {context} (#{self.error_counts[error_key]}): {str(error)}"
                )

        # Re-raise if requested
        if reraise:
            raise error

        return error_info["timestamp"]

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors."""
        total_errors = sum(self.error_counts.values())
        unique_errors = len(self.error_counts)

        return {
            "total_errors": total_errors,
            "unique_errors": unique_errors,
            "critical_errors": len(self.critical_errors),
            "most_common": sorted(
                self.error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            "recent_critical": self.critical_errors[-10:] if self.critical_errors else []
        }

    def reset_error_counts(self):
        """Reset error tracking."""
        self.error_counts.clear()
        self.critical_errors.clear()
        self.logger.info("Error counts reset")


class SafetyManager:
    """Safety checks and constraints for the orchestrator."""

    def __init__(self, config: OrchestratorConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

        # Safety limits
        self.max_concurrent_workers = config.max_workers
        self.max_worker_memory_mb = 2048  # 2GB per worker
        self.max_total_memory_mb = 8192   # 8GB total
        self.max_file_changes_per_worker = 100
        self.max_commits_per_hour = 50

        # Tracking
        self.worker_resource_usage: Dict[str, Dict[str, Any]] = {}
        self.recent_commits: List[Dict[str, Any]] = []

    def check_worker_limits(self, active_workers: int) -> bool:
        """Check if we can spawn more workers."""
        if active_workers >= self.max_concurrent_workers:
            self.logger.warning(f"Worker limit reached: {active_workers}/{self.max_concurrent_workers}")
            return False

        # Check system resources
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent

            if memory_percent > 80:
                self.logger.warning(f"High memory usage: {memory_percent}%")
                return False

        except ImportError:
            self.logger.warning("psutil not available for resource monitoring")

        return True

    def check_task_safety(self, task_description: str) -> bool:
        """Check if a task is safe to execute."""
        dangerous_patterns = [
            "rm -rf",
            "sudo",
            "format",
            "delete --force",
            "drop database",
            "truncate table"
        ]

        task_lower = task_description.lower()
        for pattern in dangerous_patterns:
            if pattern in task_lower:
                self.logger.error(f"Dangerous task detected: {task_description}")
                return False

        return True

    def check_merge_safety(self, worker_id: str, changes: List[str]) -> bool:
        """Check if merge is safe to proceed."""
        if not self.config.enable_auto_merge:
            self.logger.info(f"Auto-merge disabled for worker {worker_id}")
            return False

        # Check number of changes
        if len(changes) > self.max_file_changes_per_worker:
            self.logger.warning(
                f"Too many changes from worker {worker_id}: {len(changes)} files"
            )
            return False

        # Check for critical files
        critical_patterns = [
            ".github/workflows/",
            "docker",
            "requirements.txt",
            "package.json",
            ".env"
        ]

        for change in changes:
            for pattern in critical_patterns:
                if pattern in change.lower():
                    self.logger.warning(f"Critical file change detected: {change}")
                    if self.config.require_manual_approval:
                        return False

        return True

    def record_commit(self, worker_id: str, commit_hash: str):
        """Record a commit for rate limiting."""
        from datetime import datetime

        self.recent_commits.append({
            "worker_id": worker_id,
            "commit_hash": commit_hash,
            "timestamp": datetime.now()
        })

        # Clean old commits (keep last hour)
        cutoff = datetime.now() - timedelta(hours=1)
        self.recent_commits = [
            commit for commit in self.recent_commits
            if datetime.fromisoformat(commit["timestamp"]) > cutoff
        ]

    def check_commit_rate(self) -> bool:
        """Check if commit rate is within limits."""
        from datetime import datetime, timedelta

        if len(self.recent_commits) > self.max_commits_per_hour:
            self.logger.warning(f"Commit rate limit exceeded: {len(self.recent_commits)}/hour")
            return False

        return True


# Global configuration instance
config = OrchestratorConfig()

# Global error handler (initialized after logging setup)
error_handler: Optional[ErrorHandler] = None

# Global safety manager (initialized after logging setup)
safety_manager: Optional[SafetyManager] = None


def initialize_globals():
    """Initialize global configuration objects."""
    global error_handler, safety_manager

    # Set up logging
    logger = config.setup_logging()

    # Validate configuration
    if not config.validate_config():
        logger.critical("Configuration validation failed")
        sys.exit(1)

    # Initialize error handler and safety manager
    error_handler = ErrorHandler(logger)
    safety_manager = SafetyManager(config, logger)

    logger.info("Global configuration initialized")
    logger.info(f"Configuration: {config.get_config_dict()}")


# Utility functions for error handling
def handle_error(error: Exception, context: str, critical: bool = False, reraise: bool = False):
    """Convenience function for error handling."""
    if error_handler:
        return error_handler.handle_error(error, context, critical, reraise)
    else:
        # Fallback if error handler not initialized
        logger = logging.getLogger("orchestrator")
        logger.error(f"Error in {context}: {str(error)}", exc_info=True)
        if reraise:
            raise error


def check_safety(check_type: str, **kwargs) -> bool:
    """Convenience function for safety checks."""
    if not safety_manager:
        return True  # Fail open if safety manager not initialized

    if check_type == "worker_limits":
        return safety_manager.check_worker_limits(kwargs.get("active_workers", 0))
    elif check_type == "task_safety":
        return safety_manager.check_task_safety(kwargs.get("task_description", ""))
    elif check_type == "merge_safety":
        return safety_manager.check_merge_safety(
            kwargs.get("worker_id", ""),
            kwargs.get("changes", [])
        )
    elif check_type == "commit_rate":
        return safety_manager.check_commit_rate()
    else:
        return True