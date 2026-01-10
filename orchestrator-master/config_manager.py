#!/usr/bin/env python3
"""
Configuration Manager
Comprehensive configuration loading and management for the orchestrator system.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Main orchestrator configuration."""
    max_workers: int = 12
    default_worker_model: str = "sonnet-4"
    master_model: str = "opus-4"
    worker_timeout: int = 3600  # seconds
    task_retry_attempts: int = 3
    auto_scale: bool = True
    heartbeat_interval: int = 30


@dataclass
class RepositoryConfig:
    """Repository configuration."""
    path: str = "/path/to/your/repo"
    main_branch: str = "main"
    worker_branch_prefix: str = "worker-"
    auto_commit: bool = True
    auto_push: bool = False
    max_branch_age_days: int = 30


@dataclass
class CommunicationConfig:
    """Communication configuration."""
    message_queue: str = "sqlite"  # or "redis"
    heartbeat_interval: int = 30
    websocket_port: int = 8765
    http_port: int = 8080
    redis_url: Optional[str] = None
    sqlite_path: str = "orchestrator.db"


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    dashboard_type: str = "gui"  # or "web"
    log_level: str = "INFO"
    log_file: str = "logs/orchestrator.log"
    metrics_enabled: bool = True
    web_dashboard_port: int = 8080
    gui_update_interval: int = 1000  # milliseconds


@dataclass
class GitHubConfig:
    """GitHub integration configuration."""
    token: Optional[str] = None
    repo_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    auto_pr: bool = False
    pr_template: Optional[str] = None


@dataclass
class WorkerConfig:
    """Worker configuration."""
    id: str = "{worker_id}"
    model: str = "{model}"
    working_dir: str = "/workspace/workers/{worker_id}/worktree"
    memory_dir: str = "/workspace/workers/{worker_id}/memory"
    max_concurrent_tasks: int = 1
    task_timeout: int = 1800  # seconds


@dataclass
class WorkerCommunicationConfig:
    """Worker communication configuration."""
    master_endpoint: str = "ws://localhost:8765"
    send_heartbeat: bool = True
    heartbeat_interval: int = 30
    reconnect_attempts: int = 5
    reconnect_delay: int = 5


@dataclass
class MemoryConfig:
    """Memory management configuration."""
    auto_save_threshold: int = 50000  # tokens
    context_retention: int = 20000
    cleanup_interval: int = 3600  # seconds
    max_memory_size_mb: int = 1000
    compression_enabled: bool = True


@dataclass
class MasterConfiguration:
    """Complete master configuration."""
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    repository: RepositoryConfig = field(default_factory=RepositoryConfig)
    communication: CommunicationConfig = field(default_factory=CommunicationConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)


@dataclass
class WorkerConfiguration:
    """Complete worker configuration."""
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    communication: WorkerCommunicationConfig = field(default_factory=WorkerCommunicationConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)


class EnvironmentVariableResolver:
    """Resolves environment variables in configuration values."""

    @staticmethod
    def resolve_value(value: Any) -> Any:
        """Resolve environment variables in a value."""
        if isinstance(value, str):
            return EnvironmentVariableResolver._resolve_string(value)
        elif isinstance(value, dict):
            return {k: EnvironmentVariableResolver.resolve_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [EnvironmentVariableResolver.resolve_value(item) for item in value]
        else:
            return value

    @staticmethod
    def _resolve_string(text: str) -> str:
        """Resolve environment variables in a string."""
        # Pattern: ${VAR_NAME} or ${VAR_NAME:default_value}
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'

        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2)

            env_value = os.getenv(var_name)
            if env_value is not None:
                return env_value
            elif default_value is not None:
                return default_value
            else:
                logger.warning(f"Environment variable {var_name} not found and no default provided")
                return match.group(0)  # Return original text

        return re.sub(pattern, replace_var, text)


class ConfigurationValidator:
    """Validates configuration values."""

    @staticmethod
    def validate_master_config(config: MasterConfiguration) -> List[str]:
        """Validate master configuration and return list of errors."""
        errors = []

        # Validate orchestrator config
        if config.orchestrator.max_workers <= 0:
            errors.append("orchestrator.max_workers must be greater than 0")

        if config.orchestrator.heartbeat_interval <= 0:
            errors.append("orchestrator.heartbeat_interval must be greater than 0")

        # Validate repository config
        if not config.repository.path:
            errors.append("repository.path cannot be empty")

        if not config.repository.main_branch:
            errors.append("repository.main_branch cannot be empty")

        # Validate communication config
        valid_queues = ["sqlite", "redis"]
        if config.communication.message_queue not in valid_queues:
            errors.append(f"communication.message_queue must be one of: {valid_queues}")

        if config.communication.websocket_port <= 0 or config.communication.websocket_port > 65535:
            errors.append("communication.websocket_port must be between 1 and 65535")

        # Validate monitoring config
        valid_dashboards = ["gui", "web"]
        if config.monitoring.dashboard_type not in valid_dashboards:
            errors.append(f"monitoring.dashboard_type must be one of: {valid_dashboards}")

        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if config.monitoring.log_level not in valid_log_levels:
            errors.append(f"monitoring.log_level must be one of: {valid_log_levels}")

        return errors

    @staticmethod
    def validate_worker_config(config: WorkerConfiguration) -> List[str]:
        """Validate worker configuration and return list of errors."""
        errors = []

        # Validate worker config
        if not config.worker.id:
            errors.append("worker.id cannot be empty")

        if not config.worker.model:
            errors.append("worker.model cannot be empty")

        if config.worker.max_concurrent_tasks <= 0:
            errors.append("worker.max_concurrent_tasks must be greater than 0")

        # Validate memory config
        if config.memory.auto_save_threshold <= 0:
            errors.append("memory.auto_save_threshold must be greater than 0")

        if config.memory.context_retention <= 0:
            errors.append("memory.context_retention must be greater than 0")

        if config.memory.context_retention >= config.memory.auto_save_threshold:
            errors.append("memory.context_retention should be less than auto_save_threshold")

        return errors


class ConfigurationManager:
    """Main configuration manager for the orchestrator system."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.cwd() / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Initialize default configurations
        self.master_config: Optional[MasterConfiguration] = None
        self.worker_config_template: Optional[WorkerConfiguration] = None

        # Configuration file paths
        self.master_config_file = self.config_dir / "master_config.yaml"
        self.worker_template_file = self.config_dir / "worker_config_template.yaml"

    def create_default_configs(self) -> None:
        """Create default configuration files if they don't exist."""
        # Create master config
        if not self.master_config_file.exists():
            self.create_default_master_config()

        # Create worker template
        if not self.worker_template_file.exists():
            self.create_default_worker_template()

        logger.info("Default configuration files created")

    def create_default_master_config(self) -> None:
        """Create default master configuration file."""
        default_config = {
            "orchestrator": {
                "max_workers": 12,
                "default_worker_model": "sonnet-4",
                "master_model": "opus-4",
                "worker_timeout": 3600,
                "task_retry_attempts": 3,
                "auto_scale": True,
                "heartbeat_interval": 30
            },
            "repository": {
                "path": "/path/to/your/repo",
                "main_branch": "main",
                "worker_branch_prefix": "worker-",
                "auto_commit": True,
                "auto_push": False,
                "max_branch_age_days": 30
            },
            "communication": {
                "message_queue": "sqlite",
                "heartbeat_interval": 30,
                "websocket_port": 8765,
                "http_port": 8080,
                "redis_url": "${REDIS_URL}",
                "sqlite_path": "orchestrator.db"
            },
            "monitoring": {
                "dashboard_type": "gui",
                "log_level": "INFO",
                "log_file": "logs/orchestrator.log",
                "metrics_enabled": True,
                "web_dashboard_port": 8080,
                "gui_update_interval": 1000
            },
            "github": {
                "token": "${GITHUB_TOKEN}",
                "repo_url": "${GITHUB_REPO_URL}",
                "webhook_secret": "${GITHUB_WEBHOOK_SECRET}",
                "auto_pr": False,
                "pr_template": None
            }
        }

        with open(self.master_config_file, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)

        logger.info(f"Created default master config: {self.master_config_file}")

    def create_default_worker_template(self) -> None:
        """Create default worker configuration template."""
        default_config = {
            "worker": {
                "id": "{worker_id}",
                "model": "{model}",
                "working_dir": "/workspace/workers/{worker_id}/worktree",
                "memory_dir": "/workspace/workers/{worker_id}/memory",
                "max_concurrent_tasks": 1,
                "task_timeout": 1800
            },
            "communication": {
                "master_endpoint": "ws://localhost:8765",
                "send_heartbeat": True,
                "heartbeat_interval": 30,
                "reconnect_attempts": 5,
                "reconnect_delay": 5
            },
            "memory": {
                "auto_save_threshold": 50000,
                "context_retention": 20000,
                "cleanup_interval": 3600,
                "max_memory_size_mb": 1000,
                "compression_enabled": True
            }
        }

        with open(self.worker_template_file, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)

        logger.info(f"Created default worker template: {self.worker_template_file}")

    def load_master_config(self, config_file: Optional[Path] = None) -> MasterConfiguration:
        """Load master configuration from file."""
        config_file = config_file or self.master_config_file

        if not config_file.exists():
            logger.warning(f"Master config file not found: {config_file}, creating default")
            self.create_default_master_config()

        try:
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)

            # Resolve environment variables
            config_data = EnvironmentVariableResolver.resolve_value(config_data)

            # Create configuration objects
            master_config = MasterConfiguration(
                orchestrator=OrchestratorConfig(**config_data.get("orchestrator", {})),
                repository=RepositoryConfig(**config_data.get("repository", {})),
                communication=CommunicationConfig(**config_data.get("communication", {})),
                monitoring=MonitoringConfig(**config_data.get("monitoring", {})),
                github=GitHubConfig(**config_data.get("github", {}))
            )

            # Validate configuration
            errors = ConfigurationValidator.validate_master_config(master_config)
            if errors:
                raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

            self.master_config = master_config
            logger.info(f"Loaded master configuration from: {config_file}")
            return master_config

        except Exception as e:
            logger.error(f"Failed to load master configuration: {e}")
            raise

    def load_worker_template(self, template_file: Optional[Path] = None) -> WorkerConfiguration:
        """Load worker configuration template."""
        template_file = template_file or self.worker_template_file

        if not template_file.exists():
            logger.warning(f"Worker template not found: {template_file}, creating default")
            self.create_default_worker_template()

        try:
            with open(template_file, 'r') as f:
                config_data = yaml.safe_load(f)

            # Resolve environment variables (except template variables)
            config_data = EnvironmentVariableResolver.resolve_value(config_data)

            # Create configuration objects
            worker_config = WorkerConfiguration(
                worker=WorkerConfig(**config_data.get("worker", {})),
                communication=WorkerCommunicationConfig(**config_data.get("communication", {})),
                memory=MemoryConfig(**config_data.get("memory", {}))
            )

            self.worker_config_template = worker_config
            logger.info(f"Loaded worker template from: {template_file}")
            return worker_config

        except Exception as e:
            logger.error(f"Failed to load worker template: {e}")
            raise

    def create_worker_config(self, worker_id: str, model: str, **overrides) -> WorkerConfiguration:
        """Create worker configuration from template with specific values."""
        if not self.worker_config_template:
            self.load_worker_template()

        # Create a copy of the template
        template = self.worker_config_template

        # Template substitutions
        substitutions = {
            "worker_id": worker_id,
            "model": model,
            **overrides
        }

        # Create worker config with substitutions
        worker_config = WorkerConfiguration(
            worker=WorkerConfig(
                id=worker_id,
                model=model,
                working_dir=self._substitute_template(template.worker.working_dir, substitutions),
                memory_dir=self._substitute_template(template.worker.memory_dir, substitutions),
                max_concurrent_tasks=template.worker.max_concurrent_tasks,
                task_timeout=template.worker.task_timeout
            ),
            communication=WorkerCommunicationConfig(
                master_endpoint=template.communication.master_endpoint,
                send_heartbeat=template.communication.send_heartbeat,
                heartbeat_interval=template.communication.heartbeat_interval,
                reconnect_attempts=template.communication.reconnect_attempts,
                reconnect_delay=template.communication.reconnect_delay
            ),
            memory=MemoryConfig(
                auto_save_threshold=template.memory.auto_save_threshold,
                context_retention=template.memory.context_retention,
                cleanup_interval=template.memory.cleanup_interval,
                max_memory_size_mb=template.memory.max_memory_size_mb,
                compression_enabled=template.memory.compression_enabled
            )
        )

        # Apply any additional overrides
        for key, value in overrides.items():
            if hasattr(worker_config.worker, key):
                setattr(worker_config.worker, key, value)
            elif hasattr(worker_config.communication, key):
                setattr(worker_config.communication, key, value)
            elif hasattr(worker_config.memory, key):
                setattr(worker_config.memory, key, value)

        # Validate configuration
        errors = ConfigurationValidator.validate_worker_config(worker_config)
        if errors:
            raise ValueError(f"Worker configuration validation failed: {'; '.join(errors)}")

        return worker_config

    def save_worker_config(self, worker_config: WorkerConfiguration, worker_dir: Path) -> Path:
        """Save worker configuration to file."""
        config_file = worker_dir / "worker_config.yaml"
        worker_dir.mkdir(parents=True, exist_ok=True)

        # Convert to dictionary
        config_dict = {
            "worker": {
                "id": worker_config.worker.id,
                "model": worker_config.worker.model,
                "working_dir": worker_config.worker.working_dir,
                "memory_dir": worker_config.worker.memory_dir,
                "max_concurrent_tasks": worker_config.worker.max_concurrent_tasks,
                "task_timeout": worker_config.worker.task_timeout
            },
            "communication": {
                "master_endpoint": worker_config.communication.master_endpoint,
                "send_heartbeat": worker_config.communication.send_heartbeat,
                "heartbeat_interval": worker_config.communication.heartbeat_interval,
                "reconnect_attempts": worker_config.communication.reconnect_attempts,
                "reconnect_delay": worker_config.communication.reconnect_delay
            },
            "memory": {
                "auto_save_threshold": worker_config.memory.auto_save_threshold,
                "context_retention": worker_config.memory.context_retention,
                "cleanup_interval": worker_config.memory.cleanup_interval,
                "max_memory_size_mb": worker_config.memory.max_memory_size_mb,
                "compression_enabled": worker_config.memory.compression_enabled
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)

        logger.info(f"Saved worker configuration: {config_file}")
        return config_file

    def _substitute_template(self, template: str, substitutions: Dict[str, str]) -> str:
        """Substitute template variables in a string."""
        result = template
        for key, value in substitutions.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of current configuration."""
        summary = {
            "config_dir": str(self.config_dir),
            "config_files": {
                "master_config": {
                    "path": str(self.master_config_file),
                    "exists": self.master_config_file.exists(),
                    "loaded": self.master_config is not None
                },
                "worker_template": {
                    "path": str(self.worker_template_file),
                    "exists": self.worker_template_file.exists(),
                    "loaded": self.worker_config_template is not None
                }
            },
            "last_loaded": datetime.now().isoformat()
        }

        if self.master_config:
            summary["master_config"] = {
                "max_workers": self.master_config.orchestrator.max_workers,
                "default_model": self.master_config.orchestrator.default_worker_model,
                "dashboard_type": self.master_config.monitoring.dashboard_type,
                "websocket_port": self.master_config.communication.websocket_port
            }

        return summary

    def reload_configurations(self) -> Dict[str, bool]:
        """Reload all configuration files."""
        results = {}

        try:
            self.load_master_config()
            results["master_config"] = True
        except Exception as e:
            logger.error(f"Failed to reload master config: {e}")
            results["master_config"] = False

        try:
            self.load_worker_template()
            results["worker_template"] = True
        except Exception as e:
            logger.error(f"Failed to reload worker template: {e}")
            results["worker_template"] = False

        return results

    def export_config(self, output_file: Path, format: str = "yaml") -> None:
        """Export current configuration to file."""
        if not self.master_config:
            raise ValueError("No master configuration loaded")

        config_data = {
            "master": {
                "orchestrator": self.master_config.orchestrator.__dict__,
                "repository": self.master_config.repository.__dict__,
                "communication": self.master_config.communication.__dict__,
                "monitoring": self.master_config.monitoring.__dict__,
                "github": self.master_config.github.__dict__
            }
        }

        if self.worker_config_template:
            config_data["worker_template"] = {
                "worker": self.worker_config_template.worker.__dict__,
                "communication": self.worker_config_template.communication.__dict__,
                "memory": self.worker_config_template.memory.__dict__
            }

        if format.lower() == "yaml":
            with open(output_file, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
        elif format.lower() == "json":
            with open(output_file, 'w') as f:
                json.dump(config_data, f, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Exported configuration to: {output_file}")


# Global configuration manager instance
config_manager = ConfigurationManager()


def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager instance."""
    return config_manager


def load_master_config(config_file: Optional[Path] = None) -> MasterConfiguration:
    """Load master configuration (convenience function)."""
    return config_manager.load_master_config(config_file)


def create_worker_config(worker_id: str, model: str, **overrides) -> WorkerConfiguration:
    """Create worker configuration (convenience function)."""
    return config_manager.create_worker_config(worker_id, model, **overrides)