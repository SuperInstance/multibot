#!/usr/bin/env python3
"""
Configuration Management MCP Tools
MCP tool integration for configuration management functionality.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from config_manager import get_config_manager, MasterConfiguration, WorkerConfiguration

logger = logging.getLogger(__name__)


@dataclass
class LoadConfigRequest:
    """Request to load configuration."""
    config_type: str  # "master" or "worker_template"
    config_file: Optional[str] = None


@dataclass
class CreateWorkerConfigRequest:
    """Request to create worker configuration."""
    worker_id: str
    model: str
    overrides: Dict[str, Any] = None


@dataclass
class UpdateConfigRequest:
    """Request to update configuration values."""
    config_type: str  # "master" or "worker_template"
    section: str  # e.g., "orchestrator", "communication"
    updates: Dict[str, Any]


@dataclass
class ExportConfigRequest:
    """Request to export configuration."""
    output_file: str
    format: str = "yaml"  # "yaml" or "json"
    include_templates: bool = True


def register_config_tools(mcp, orchestrator=None):
    """Register configuration management tools with MCP server."""

    @mcp.tool()
    async def load_configuration(request: LoadConfigRequest) -> Dict[str, Any]:
        """
        Load configuration from file.

        Loads master configuration or worker template configuration from
        YAML files, resolving environment variables and validating settings.

        Args:
            request: LoadConfigRequest specifying config type and optional file path

        Returns:
            Loaded configuration data and validation results
        """
        try:
            config_manager = get_config_manager()

            if request.config_type == "master":
                config_file = Path(request.config_file) if request.config_file else None
                config = config_manager.load_master_config(config_file)

                return {
                    "status": "success",
                    "config_type": "master",
                    "config": {
                        "orchestrator": config.orchestrator.__dict__,
                        "repository": config.repository.__dict__,
                        "communication": config.communication.__dict__,
                        "monitoring": config.monitoring.__dict__,
                        "github": config.github.__dict__
                    },
                    "config_file": str(config_file or config_manager.master_config_file),
                    "validation": "passed"
                }

            elif request.config_type == "worker_template":
                template_file = Path(request.config_file) if request.config_file else None
                config = config_manager.load_worker_template(template_file)

                return {
                    "status": "success",
                    "config_type": "worker_template",
                    "config": {
                        "worker": config.worker.__dict__,
                        "communication": config.communication.__dict__,
                        "memory": config.memory.__dict__
                    },
                    "config_file": str(template_file or config_manager.worker_template_file),
                    "validation": "passed"
                }
            else:
                return {
                    "status": "error",
                    "error": f"Invalid config_type: {request.config_type}. Must be 'master' or 'worker_template'"
                }

        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return {
                "status": "error",
                "error": str(e),
                "config_type": request.config_type
            }

    @mcp.tool()
    async def create_worker_configuration(request: CreateWorkerConfigRequest) -> Dict[str, Any]:
        """
        Create worker configuration from template.

        Generates a worker-specific configuration by substituting template
        variables with actual values and applying any overrides.

        Args:
            request: CreateWorkerConfigRequest with worker details and overrides

        Returns:
            Generated worker configuration
        """
        try:
            config_manager = get_config_manager()

            # Load template if not already loaded
            if not config_manager.worker_config_template:
                config_manager.load_worker_template()

            # Create worker config
            worker_config = config_manager.create_worker_config(
                worker_id=request.worker_id,
                model=request.model,
                **(request.overrides or {})
            )

            return {
                "status": "success",
                "worker_id": request.worker_id,
                "model": request.model,
                "config": {
                    "worker": worker_config.worker.__dict__,
                    "communication": worker_config.communication.__dict__,
                    "memory": worker_config.memory.__dict__
                },
                "overrides_applied": list((request.overrides or {}).keys()),
                "validation": "passed"
            }

        except Exception as e:
            logger.error(f"Error creating worker configuration: {e}")
            return {
                "status": "error",
                "error": str(e),
                "worker_id": request.worker_id
            }

    @mcp.tool()
    async def get_config_summary() -> Dict[str, Any]:
        """
        Get configuration summary and status.

        Returns overview of current configuration state, including which
        files are loaded, validation status, and key settings.

        Returns:
            Configuration summary and status information
        """
        try:
            config_manager = get_config_manager()
            summary = config_manager.get_config_summary()

            # Add runtime information
            summary["runtime_info"] = {
                "environment_variables": {
                    "ANTHROPIC_API_KEY": "set" if os.getenv("ANTHROPIC_API_KEY") else "not_set",
                    "GITHUB_TOKEN": "set" if os.getenv("GITHUB_TOKEN") else "not_set",
                    "REDIS_URL": "set" if os.getenv("REDIS_URL") else "not_set"
                }
            }

            return {
                "status": "success",
                "summary": summary
            }

        except Exception as e:
            logger.error(f"Error getting config summary: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    async def validate_configuration(config_type: str) -> Dict[str, Any]:
        """
        Validate configuration for errors and warnings.

        Performs comprehensive validation of configuration values,
        checking for required fields, valid ranges, and logical consistency.

        Args:
            config_type: Type of configuration to validate ("master" or "worker_template")

        Returns:
            Validation results with errors and warnings
        """
        try:
            config_manager = get_config_manager()

            if config_type == "master":
                if not config_manager.master_config:
                    config_manager.load_master_config()

                from config_manager import ConfigurationValidator
                errors = ConfigurationValidator.validate_master_config(config_manager.master_config)

                return {
                    "status": "success",
                    "config_type": "master",
                    "validation_result": "passed" if not errors else "failed",
                    "errors": errors,
                    "warnings": [],  # Could add warnings for deprecated settings
                    "checked_settings": [
                        "orchestrator.max_workers",
                        "communication.websocket_port",
                        "monitoring.log_level",
                        "repository.path"
                    ]
                }

            elif config_type == "worker_template":
                if not config_manager.worker_config_template:
                    config_manager.load_worker_template()

                from config_manager import ConfigurationValidator
                errors = ConfigurationValidator.validate_worker_config(config_manager.worker_config_template)

                return {
                    "status": "success",
                    "config_type": "worker_template",
                    "validation_result": "passed" if not errors else "failed",
                    "errors": errors,
                    "warnings": [],
                    "checked_settings": [
                        "worker.id",
                        "memory.auto_save_threshold",
                        "communication.master_endpoint"
                    ]
                }
            else:
                return {
                    "status": "error",
                    "error": f"Invalid config_type: {config_type}"
                }

        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            return {
                "status": "error",
                "error": str(e),
                "config_type": config_type
            }

    @mcp.tool()
    async def reload_configurations() -> Dict[str, Any]:
        """
        Reload all configuration files from disk.

        Reloads master configuration and worker template from their
        respective files, useful after manual configuration changes.

        Returns:
            Reload results for each configuration type
        """
        try:
            config_manager = get_config_manager()
            results = config_manager.reload_configurations()

            return {
                "status": "success",
                "reload_results": results,
                "reloaded_at": config_manager.get_config_summary()["last_loaded"],
                "summary": {
                    "master_config": "reloaded" if results["master_config"] else "failed",
                    "worker_template": "reloaded" if results["worker_template"] else "failed"
                }
            }

        except Exception as e:
            logger.error(f"Error reloading configurations: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    async def export_configuration(request: ExportConfigRequest) -> Dict[str, Any]:
        """
        Export current configuration to file.

        Exports the current in-memory configuration to a file in YAML or JSON
        format, useful for backup or sharing configurations.

        Args:
            request: ExportConfigRequest with output file and format details

        Returns:
            Export operation results
        """
        try:
            config_manager = get_config_manager()
            output_path = Path(request.output_file)

            # Ensure master config is loaded
            if not config_manager.master_config:
                config_manager.load_master_config()

            # Load worker template if requested
            if request.include_templates and not config_manager.worker_config_template:
                config_manager.load_worker_template()

            # Export configuration
            config_manager.export_config(output_path, request.format)

            return {
                "status": "success",
                "output_file": str(output_path),
                "format": request.format,
                "include_templates": request.include_templates,
                "file_size_bytes": output_path.stat().st_size,
                "exported_sections": [
                    "master.orchestrator",
                    "master.repository",
                    "master.communication",
                    "master.monitoring",
                    "master.github"
                ] + (["worker_template"] if request.include_templates else [])
            }

        except Exception as e:
            logger.error(f"Error exporting configuration: {e}")
            return {
                "status": "error",
                "error": str(e),
                "output_file": request.output_file
            }

    @mcp.tool()
    async def create_default_configs(force_recreate: bool = False) -> Dict[str, Any]:
        """
        Create default configuration files.

        Creates default master_config.yaml and worker_config_template.yaml
        files with sensible defaults. Optionally overwrites existing files.

        Args:
            force_recreate: Whether to overwrite existing configuration files

        Returns:
            Results of configuration file creation
        """
        try:
            config_manager = get_config_manager()

            created_files = []
            skipped_files = []

            # Check master config
            if not config_manager.master_config_file.exists() or force_recreate:
                config_manager.create_default_master_config()
                created_files.append("master_config.yaml")
            else:
                skipped_files.append("master_config.yaml")

            # Check worker template
            if not config_manager.worker_template_file.exists() or force_recreate:
                config_manager.create_default_worker_template()
                created_files.append("worker_config_template.yaml")
            else:
                skipped_files.append("worker_config_template.yaml")

            return {
                "status": "success",
                "created_files": created_files,
                "skipped_files": skipped_files,
                "force_recreate": force_recreate,
                "config_directory": str(config_manager.config_dir),
                "next_steps": [
                    "Review and customize the configuration files",
                    "Set required environment variables",
                    "Validate configuration with validate_configuration tool"
                ]
            }

        except Exception as e:
            logger.error(f"Error creating default configs: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    async def get_environment_variables() -> Dict[str, Any]:
        """
        Get current environment variables relevant to configuration.

        Returns the status of environment variables used in configuration
        files, helping identify missing or incorrectly set variables.

        Returns:
            Environment variable status and recommendations
        """
        try:
            import os

            # Define expected environment variables
            env_vars = {
                "ANTHROPIC_API_KEY": {
                    "required": True,
                    "description": "API key for Anthropic Claude models",
                    "example": "sk-ant-api03-..."
                },
                "GITHUB_TOKEN": {
                    "required": False,
                    "description": "GitHub personal access token for repository integration",
                    "example": "ghp_..."
                },
                "GITHUB_REPO_URL": {
                    "required": False,
                    "description": "GitHub repository URL for integration",
                    "example": "https://github.com/user/repo"
                },
                "REDIS_URL": {
                    "required": False,
                    "description": "Redis connection URL (if using Redis message queue)",
                    "example": "redis://localhost:6379"
                },
                "ORCHESTRATOR_HOST": {
                    "required": False,
                    "description": "Host for orchestrator server",
                    "example": "localhost"
                },
                "ORCHESTRATOR_PORT": {
                    "required": False,
                    "description": "Port for orchestrator server",
                    "example": "8765"
                }
            }

            env_status = {}
            missing_required = []

            for var_name, var_info in env_vars.items():
                value = os.getenv(var_name)
                env_status[var_name] = {
                    "set": value is not None,
                    "required": var_info["required"],
                    "description": var_info["description"],
                    "example": var_info["example"],
                    "masked_value": f"{value[:8]}..." if value and len(value) > 8 else ("set" if value else "not_set")
                }

                if var_info["required"] and not value:
                    missing_required.append(var_name)

            return {
                "status": "success",
                "environment_variables": env_status,
                "missing_required": missing_required,
                "all_required_set": len(missing_required) == 0,
                "recommendations": [
                    f"Set {var}" for var in missing_required
                ] if missing_required else ["All required environment variables are set"]
            }

        except Exception as e:
            logger.error(f"Error getting environment variables: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    return {
        "load_configuration": load_configuration,
        "create_worker_configuration": create_worker_configuration,
        "get_config_summary": get_config_summary,
        "validate_configuration": validate_configuration,
        "reload_configurations": reload_configurations,
        "export_configuration": export_configuration,
        "create_default_configs": create_default_configs,
        "get_environment_variables": get_environment_variables
    }