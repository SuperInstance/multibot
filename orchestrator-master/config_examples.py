#!/usr/bin/env python3
"""
Configuration Examples and Testing
Demonstrates configuration management functionality and validates configurations.
"""

import asyncio
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List
import yaml

from config_manager import ConfigurationManager, MasterConfiguration, WorkerConfiguration

logger = logging.getLogger(__name__)


class ConfigurationExamples:
    """Example configurations and scenarios for the orchestrator system."""

    def __init__(self):
        self.examples = self._load_example_scenarios()

    def _load_example_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """Load example configuration scenarios."""
        return {
            "development_setup": {
                "description": "Configuration optimized for development environment",
                "master_config": {
                    "orchestrator": {
                        "max_workers": 3,
                        "default_worker_model": "sonnet-4",
                        "master_model": "opus-4",
                        "auto_scale": False,
                        "heartbeat_interval": 15
                    },
                    "repository": {
                        "path": "/workspace/dev-project",
                        "main_branch": "develop",
                        "auto_commit": True,
                        "auto_push": False
                    },
                    "communication": {
                        "message_queue": "sqlite",
                        "websocket_port": 8765,
                        "http_port": 8080
                    },
                    "monitoring": {
                        "dashboard_type": "web",
                        "log_level": "DEBUG",
                        "metrics_enabled": True
                    }
                },
                "worker_overrides": {
                    "max_concurrent_tasks": 1,
                    "task_timeout": 900  # 15 minutes
                }
            },
            "production_setup": {
                "description": "Configuration optimized for production environment",
                "master_config": {
                    "orchestrator": {
                        "max_workers": 20,
                        "default_worker_model": "sonnet-4",
                        "master_model": "opus-4",
                        "auto_scale": True,
                        "heartbeat_interval": 60
                    },
                    "repository": {
                        "path": "/workspace/production",
                        "main_branch": "main",
                        "auto_commit": True,
                        "auto_push": True
                    },
                    "communication": {
                        "message_queue": "redis",
                        "websocket_port": 8765,
                        "http_port": 8080
                    },
                    "monitoring": {
                        "dashboard_type": "web",
                        "log_level": "INFO",
                        "metrics_enabled": True
                    }
                },
                "worker_overrides": {
                    "max_concurrent_tasks": 2,
                    "task_timeout": 3600  # 1 hour
                }
            },
            "high_throughput": {
                "description": "Configuration for high-throughput scenarios",
                "master_config": {
                    "orchestrator": {
                        "max_workers": 50,
                        "default_worker_model": "haiku-4",  # Faster model
                        "master_model": "opus-4",
                        "auto_scale": True,
                        "heartbeat_interval": 30
                    },
                    "communication": {
                        "message_queue": "redis",
                        "websocket_port": 8765,
                        "http_port": 8080
                    },
                    "monitoring": {
                        "dashboard_type": "web",
                        "log_level": "WARNING",  # Reduce logging overhead
                        "metrics_enabled": True
                    }
                },
                "worker_overrides": {
                    "max_concurrent_tasks": 3,
                    "memory": {
                        "auto_save_threshold": 30000,  # More frequent saves
                        "context_retention": 10000
                    }
                }
            },
            "minimal_setup": {
                "description": "Minimal configuration for simple projects",
                "master_config": {
                    "orchestrator": {
                        "max_workers": 2,
                        "default_worker_model": "haiku-4",
                        "master_model": "sonnet-4",
                        "auto_scale": False
                    },
                    "communication": {
                        "message_queue": "sqlite",
                        "websocket_port": 8765
                    },
                    "monitoring": {
                        "dashboard_type": "gui",
                        "log_level": "INFO",
                        "metrics_enabled": False
                    }
                },
                "worker_overrides": {
                    "max_concurrent_tasks": 1,
                    "memory": {
                        "max_memory_size_mb": 500
                    }
                }
            }
        }

    async def run_configuration_example(self, example_name: str) -> Dict[str, Any]:
        """Run a specific configuration example."""
        if example_name not in self.examples:
            raise ValueError(f"Example '{example_name}' not found")

        example = self.examples[example_name]
        logger.info(f"Running configuration example: {example_name}")

        try:
            # Create temporary directory for this example
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                config_manager = ConfigurationManager(temp_path / "config")

                # Create master configuration
                master_config_data = example["master_config"]
                master_config_file = config_manager.config_dir / "master_config.yaml"

                with open(master_config_file, 'w') as f:
                    yaml.dump(master_config_data, f, default_flow_style=False, indent=2)

                # Load the configuration
                master_config = config_manager.load_master_config()

                # Create worker configuration
                worker_config = config_manager.create_worker_config(
                    worker_id="example-worker",
                    model=master_config.orchestrator.default_worker_model,
                    **example.get("worker_overrides", {})
                )

                # Validate configurations
                from config_manager import ConfigurationValidator

                master_errors = ConfigurationValidator.validate_master_config(master_config)
                worker_errors = ConfigurationValidator.validate_worker_config(worker_config)

                return {
                    "status": "success",
                    "example_name": example_name,
                    "description": example["description"],
                    "master_config": {
                        "validation": "passed" if not master_errors else "failed",
                        "errors": master_errors,
                        "settings": {
                            "max_workers": master_config.orchestrator.max_workers,
                            "default_model": master_config.orchestrator.default_worker_model,
                            "dashboard_type": master_config.monitoring.dashboard_type,
                            "message_queue": master_config.communication.message_queue
                        }
                    },
                    "worker_config": {
                        "validation": "passed" if not worker_errors else "failed",
                        "errors": worker_errors,
                        "settings": {
                            "model": worker_config.worker.model,
                            "max_tasks": worker_config.worker.max_concurrent_tasks,
                            "memory_threshold": worker_config.memory.auto_save_threshold
                        }
                    },
                    "use_cases": self._get_use_cases_for_example(example_name)
                }

        except Exception as e:
            logger.error(f"Error running configuration example {example_name}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "example_name": example_name
            }

    def _get_use_cases_for_example(self, example_name: str) -> List[str]:
        """Get use cases for a specific example."""
        use_cases = {
            "development_setup": [
                "Local development and testing",
                "Debugging worker behavior",
                "Experimenting with new features",
                "Small team collaboration"
            ],
            "production_setup": [
                "Production deployments",
                "High-reliability environments",
                "Large team collaboration",
                "Continuous integration"
            ],
            "high_throughput": [
                "Bulk processing tasks",
                "Large-scale code generation",
                "Parallel documentation generation",
                "Mass code refactoring"
            ],
            "minimal_setup": [
                "Simple automation tasks",
                "Personal projects",
                "Learning and experimentation",
                "Resource-constrained environments"
            ]
        }
        return use_cases.get(example_name, [])

    async def run_all_examples(self) -> Dict[str, Any]:
        """Run all configuration examples."""
        logger.info("Running all configuration examples")

        results = {}
        summary = {
            "total_examples": len(self.examples),
            "successful_examples": 0,
            "failed_examples": 0,
            "validation_passed": 0,
            "validation_failed": 0
        }

        for example_name in self.examples:
            try:
                result = await self.run_configuration_example(example_name)
                results[example_name] = result

                if result["status"] == "success":
                    summary["successful_examples"] += 1

                    # Check validation status
                    master_valid = result["master_config"]["validation"] == "passed"
                    worker_valid = result["worker_config"]["validation"] == "passed"

                    if master_valid and worker_valid:
                        summary["validation_passed"] += 1
                    else:
                        summary["validation_failed"] += 1
                else:
                    summary["failed_examples"] += 1

            except Exception as e:
                logger.error(f"Error running example {example_name}: {e}")
                results[example_name] = {"status": "error", "error": str(e)}
                summary["failed_examples"] += 1

        return {
            "summary": summary,
            "results": results,
            "recommendations": self._generate_recommendations(results)
        }

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on example results."""
        recommendations = []

        # Analyze results and provide recommendations
        successful_examples = [name for name, result in results.items()
                             if result.get("status") == "success"]

        if "development_setup" in successful_examples:
            recommendations.append("Use development_setup for local development and testing")

        if "production_setup" in successful_examples:
            recommendations.append("Use production_setup for production deployments")

        if len(successful_examples) == len(results):
            recommendations.append("All configuration examples validated successfully")
        else:
            recommendations.append("Review failed examples and fix validation errors")

        return recommendations

    async def demonstrate_environment_variable_resolution(self) -> Dict[str, Any]:
        """Demonstrate environment variable resolution in configurations."""
        logger.info("Demonstrating environment variable resolution")

        import os

        # Set test environment variables
        test_env_vars = {
            "TEST_GITHUB_TOKEN": "test-token-123",
            "TEST_REDIS_URL": "redis://localhost:6379",
            "TEST_REPO_PATH": "/workspace/test-project"
        }

        # Store original values
        original_values = {}
        for key in test_env_vars:
            original_values[key] = os.getenv(key)

        try:
            # Set test values
            for key, value in test_env_vars.items():
                os.environ[key] = value

            # Create test configuration with environment variables
            test_config = {
                "github": {
                    "token": "${TEST_GITHUB_TOKEN}",
                    "repo_url": "https://github.com/test/repo"
                },
                "communication": {
                    "redis_url": "${TEST_REDIS_URL}",
                    "message_queue": "redis"
                },
                "repository": {
                    "path": "${TEST_REPO_PATH}",
                    "main_branch": "main"
                },
                "test_with_default": {
                    "missing_var": "${MISSING_VAR:default_value}",
                    "another_missing": "${ANOTHER_MISSING}"
                }
            }

            # Create temporary configuration manager
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                config_manager = ConfigurationManager(temp_path / "config")

                # Write test config
                config_file = config_manager.config_dir / "test_config.yaml"
                with open(config_file, 'w') as f:
                    yaml.dump(test_config, f)

                # Resolve environment variables
                from config_manager import EnvironmentVariableResolver

                with open(config_file, 'r') as f:
                    loaded_config = yaml.safe_load(f)

                resolved_config = EnvironmentVariableResolver.resolve_value(loaded_config)

                return {
                    "status": "success",
                    "original_config": test_config,
                    "resolved_config": resolved_config,
                    "environment_variables_used": list(test_env_vars.keys()),
                    "resolution_examples": {
                        "github_token": {
                            "original": "${TEST_GITHUB_TOKEN}",
                            "resolved": resolved_config["github"]["token"]
                        },
                        "redis_url": {
                            "original": "${TEST_REDIS_URL}",
                            "resolved": resolved_config["communication"]["redis_url"]
                        },
                        "with_default": {
                            "original": "${MISSING_VAR:default_value}",
                            "resolved": resolved_config["test_with_default"]["missing_var"]
                        }
                    }
                }

        finally:
            # Restore original environment variables
            for key, original_value in original_values.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value

    def generate_configuration_examples_report(self) -> str:
        """Generate configuration examples documentation."""
        report = """# Configuration Examples and Best Practices

## Overview
The configuration system supports flexible, environment-aware configuration management with YAML files and environment variable resolution.

## Configuration Structure

### Master Configuration (master_config.yaml)
Controls the main orchestrator behavior including worker management, communication, and monitoring.

### Worker Template (worker_config_template.yaml)
Template for generating individual worker configurations with variable substitution.

## Example Configurations

### Development Environment
```yaml
orchestrator:
  max_workers: 3
  default_worker_model: "sonnet-4"
  auto_scale: false
  heartbeat_interval: 15

monitoring:
  dashboard_type: "web"
  log_level: "DEBUG"
  metrics_enabled: true

communication:
  message_queue: "sqlite"
```

**Use Cases:**
- Local development and testing
- Debugging worker behavior
- Small team collaboration
- Feature experimentation

### Production Environment
```yaml
orchestrator:
  max_workers: 20
  default_worker_model: "sonnet-4"
  auto_scale: true
  heartbeat_interval: 60

monitoring:
  dashboard_type: "web"
  log_level: "INFO"
  metrics_enabled: true

communication:
  message_queue: "redis"
  redis_url: "${REDIS_URL}"
```

**Use Cases:**
- Production deployments
- High-reliability environments
- Large team collaboration
- Continuous integration

### High-Throughput Environment
```yaml
orchestrator:
  max_workers: 50
  default_worker_model: "haiku-4"  # Faster model
  auto_scale: true

monitoring:
  log_level: "WARNING"  # Reduce overhead

worker:
  max_concurrent_tasks: 3
  memory:
    auto_save_threshold: 30000  # More frequent saves
```

**Use Cases:**
- Bulk processing tasks
- Large-scale code generation
- Mass code refactoring
- Parallel documentation

### Minimal Setup
```yaml
orchestrator:
  max_workers: 2
  default_worker_model: "haiku-4"
  auto_scale: false

monitoring:
  dashboard_type: "gui"
  metrics_enabled: false

communication:
  message_queue: "sqlite"
```

**Use Cases:**
- Simple automation tasks
- Personal projects
- Learning environments
- Resource constraints

## Environment Variables

### Required Variables
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### Optional Variables
```bash
export GITHUB_TOKEN="your-github-token"
export GITHUB_REPO_URL="https://github.com/user/repo"
export REDIS_URL="redis://localhost:6379"
```

### Variable Resolution
Variables are resolved using `${VAR_NAME}` or `${VAR_NAME:default}` syntax:

```yaml
github:
  token: "${GITHUB_TOKEN}"
  repo_url: "${GITHUB_REPO_URL:https://github.com/default/repo}"

communication:
  redis_url: "${REDIS_URL:redis://localhost:6379}"
```

## Configuration Validation

### Master Configuration Validation
- `max_workers` must be > 0
- `websocket_port` must be valid port (1-65535)
- `log_level` must be valid log level
- `message_queue` must be "sqlite" or "redis"

### Worker Configuration Validation
- `worker.id` cannot be empty
- `memory.auto_save_threshold` must be > 0
- `memory.context_retention` < `auto_save_threshold`
- `max_concurrent_tasks` must be > 0

## Best Practices

### 1. Environment-Specific Configurations
- Use separate config files for dev/staging/prod
- Leverage environment variables for sensitive data
- Version control configuration templates, not secrets

### 2. Resource Planning
- Start with conservative worker limits
- Monitor resource usage and adjust
- Use auto-scaling for variable workloads

### 3. Monitoring and Logging
- Use DEBUG level for development
- Use INFO/WARNING for production
- Enable metrics for performance monitoring

### 4. Worker Configuration
- Match worker model to task complexity
- Tune memory thresholds based on usage patterns
- Set appropriate timeouts for task types

### 5. Communication
- Use SQLite for simple deployments
- Use Redis for distributed/high-load scenarios
- Configure appropriate heartbeat intervals

## Configuration Tools

### Load Configuration
```python
# Load master configuration
config = await load_configuration({
    "config_type": "master",
    "config_file": "config/master_config.yaml"
})

# Create worker configuration
worker_config = await create_worker_configuration({
    "worker_id": "worker-001",
    "model": "sonnet-4",
    "overrides": {"max_concurrent_tasks": 2}
})
```

### Validate Configuration
```python
# Validate master configuration
validation = await validate_configuration("master")

# Check for errors
if validation["validation_result"] == "failed":
    print("Errors:", validation["errors"])
```

### Environment Variables
```python
# Check environment variables
env_status = await get_environment_variables()

if not env_status["all_required_set"]:
    print("Missing:", env_status["missing_required"])
```

## Troubleshooting

### Common Issues

**"Validation failed: max_workers must be greater than 0"**
- Check orchestrator.max_workers value in master_config.yaml

**"Environment variable ANTHROPIC_API_KEY not found"**
- Set the API key: `export ANTHROPIC_API_KEY="your-key"`

**"Port already in use"**
- Change websocket_port or http_port in configuration
- Kill existing processes on those ports

**"Redis connection failed"**
- Verify Redis is running: `redis-cli ping`
- Check REDIS_URL environment variable
- Consider using SQLite instead for simple setups

### Validation Commands
```bash
# Validate all configurations
python -c "
from config_tools import register_config_tools
import asyncio
tools = register_config_tools(None)
result = asyncio.run(tools['validate_configuration']('master'))
print('Master config:', result['validation_result'])
"

# Check environment variables
python -c "
from config_tools import register_config_tools
import asyncio
tools = register_config_tools(None)
result = asyncio.run(tools['get_environment_variables']())
print('Missing vars:', result['missing_required'])
"
```

The configuration system provides flexible, validated, and environment-aware configuration management for all orchestrator deployments.
"""
        return report.strip()


async def run_configuration_examples_demo():
    """Run demonstration of configuration examples."""
    examples = ConfigurationExamples()

    print("⚙️ Configuration Management Examples Demo")
    print("=" * 50)

    # Run all configuration examples
    print("\n📋 Running all configuration examples...")
    all_results = await examples.run_all_examples()

    print(f"\n📊 Summary:")
    summary = all_results["summary"]
    print(f"  • Total examples: {summary['total_examples']}")
    print(f"  • Successful: {summary['successful_examples']}")
    print(f"  • Failed: {summary['failed_examples']}")
    print(f"  • Validation passed: {summary['validation_passed']}")
    print(f"  • Validation failed: {summary['validation_failed']}")

    # Show individual results
    for example_name, result in all_results["results"].items():
        if result.get("status") == "success":
            master_status = "✅" if result["master_config"]["validation"] == "passed" else "❌"
            worker_status = "✅" if result["worker_config"]["validation"] == "passed" else "❌"
            print(f"    {example_name}: Master {master_status} Worker {worker_status}")
        else:
            print(f"    {example_name}: ❌ Failed")

    # Demonstrate environment variable resolution
    print("\n🌍 Environment Variable Resolution Demo...")
    env_demo = await examples.demonstrate_environment_variable_resolution()

    if env_demo["status"] == "success":
        print("✅ Environment variable resolution working correctly")
        for example_name, example_data in env_demo["resolution_examples"].items():
            print(f"  • {example_name}: '{example_data['original']}' → '{example_data['resolved']}'")

    # Show recommendations
    print("\n💡 Recommendations:")
    for rec in all_results["recommendations"]:
        print(f"  • {rec}")

    print("\n✅ Configuration examples demo completed!")
    return all_results, env_demo


if __name__ == "__main__":
    # Configure logging for demo
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Run the demo
    asyncio.run(run_configuration_examples_demo())