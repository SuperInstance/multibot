#!/usr/bin/env python3
"""
Multi-Agent Orchestrator Setup Script
Automated installation and configuration of the complete system.
"""

import os
import sys
import json
import shutil
import subprocess
import platform
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SetupManager:
    """Main setup manager for the orchestrator system."""

    def __init__(self):
        self.system_platform = platform.system().lower()
        self.python_version = sys.version_info
        self.setup_dir = Path(__file__).parent
        self.orchestrator_dir = self.setup_dir.parent if self.setup_dir.name == "orchestrator-master" else self.setup_dir / "orchestrator"

        # Required versions
        self.min_python_version = (3, 8)
        self.min_node_version = (16, 0)

        # Setup tracking
        self.setup_status = {
            "prerequisites": False,
            "dependencies": False,
            "directory_structure": False,
            "mcp_config": False,
            "git_setup": False,
            "scripts": False
        }

    def run_full_setup(self) -> bool:
        """Run complete setup process."""
        logger.info("🚀 Starting Multi-Agent Orchestrator Setup")
        logger.info("=" * 60)

        try:
            # Check if this is a re-run
            if self.is_existing_installation():
                logger.info("⚠️ Existing installation detected")
                if not self.confirm_reinstall():
                    logger.info("Setup cancelled by user")
                    return False

            # Run setup steps
            steps = [
                ("Checking Prerequisites", self.check_prerequisites),
                ("Installing Dependencies", self.install_dependencies),
                ("Creating Directory Structure", self.create_directory_structure),
                ("Configuring MCP Servers", self.configure_mcp_servers),
                ("Initializing Git Repository", self.initialize_git_repository),
                ("Creating Start Scripts", self.create_start_scripts),
                ("Finalizing Setup", self.finalize_setup)
            ]

            for step_name, step_func in steps:
                logger.info(f"\n📋 {step_name}...")
                try:
                    success = step_func()
                    if success:
                        logger.info(f"✅ {step_name} completed successfully")
                    else:
                        logger.error(f"❌ {step_name} failed")
                        return False
                except Exception as e:
                    logger.error(f"❌ {step_name} failed with error: {e}")
                    return False

            # Final success message
            logger.info("\n🎉 Setup completed successfully!")
            self.print_next_steps()
            return True

        except KeyboardInterrupt:
            logger.info("\n⚠️ Setup interrupted by user")
            return False
        except Exception as e:
            logger.error(f"\n💥 Setup failed with unexpected error: {e}")
            return False

    def is_existing_installation(self) -> bool:
        """Check if orchestrator is already installed."""
        return (self.orchestrator_dir.exists() and
                (self.orchestrator_dir / "master").exists() and
                (self.orchestrator_dir / "master" / "orchestrator_master.py").exists())

    def confirm_reinstall(self) -> bool:
        """Ask user to confirm reinstallation."""
        response = input("Do you want to reinstall/update the existing setup? (y/N): ").lower()
        return response in ['y', 'yes']

    def check_prerequisites(self) -> bool:
        """Check all system prerequisites."""
        logger.info("Checking system prerequisites...")

        checks = [
            ("Python version", self.check_python_version),
            ("WSL (Windows only)", self.check_wsl),
            ("Claude Code CLI", self.check_claude_code_cli),
            ("Git", self.check_git),
            ("Node.js", self.check_nodejs),
            ("API Keys", self.check_api_keys)
        ]

        all_passed = True
        for check_name, check_func in checks:
            try:
                result, message = check_func()
                if result:
                    logger.info(f"  ✅ {check_name}: {message}")
                else:
                    logger.warning(f"  ⚠️ {check_name}: {message}")
                    if check_name in ["Python version", "Git"]:  # Critical checks
                        all_passed = False
            except Exception as e:
                logger.error(f"  ❌ {check_name}: Error - {e}")
                if check_name in ["Python version", "Git"]:  # Critical checks
                    all_passed = False

        if not all_passed:
            logger.error("Critical prerequisites not met. Please install missing components.")
            return False

        self.setup_status["prerequisites"] = True
        return True

    def check_python_version(self) -> Tuple[bool, str]:
        """Check Python version."""
        if self.python_version >= self.min_python_version:
            return True, f"Python {'.'.join(map(str, self.python_version[:2]))} (>= {'.'.join(map(str, self.min_python_version))})"
        else:
            return False, f"Python {'.'.join(map(str, self.python_version[:2]))} (need >= {'.'.join(map(str, self.min_python_version))})"

    def check_wsl(self) -> Tuple[bool, str]:
        """Check WSL installation (Windows only)."""
        if self.system_platform != "windows":
            return True, "Not Windows - WSL check skipped"

        try:
            result = subprocess.run(["wsl", "--status"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return True, "WSL is installed and available"
            else:
                return False, "WSL not properly configured"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, "WSL not found - please install WSL first"

    def check_claude_code_cli(self) -> Tuple[bool, str]:
        """Check Claude Code CLI installation."""
        try:
            result = subprocess.run(["claude-code", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, f"Claude Code CLI installed: {version}"
            else:
                return False, "Claude Code CLI not responding properly"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, "Claude Code CLI not found - please install from https://claude.ai/code"

    def check_git(self) -> Tuple[bool, str]:
        """Check Git installation."""
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, f"Git installed: {version}"
            else:
                return False, "Git not responding properly"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, "Git not found - please install Git"

    def check_nodejs(self) -> Tuple[bool, str]:
        """Check Node.js installation."""
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_str = result.stdout.strip().lstrip('v')
                version_parts = version_str.split('.')
                major, minor = int(version_parts[0]), int(version_parts[1])

                if (major, minor) >= self.min_node_version:
                    return True, f"Node.js v{version_str} (>= v{'.'.join(map(str, self.min_node_version))})"
                else:
                    return False, f"Node.js v{version_str} (need >= v{'.'.join(map(str, self.min_node_version))})"
            else:
                return False, "Node.js not responding properly"
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            return False, "Node.js not found - please install Node.js"

    def check_api_keys(self) -> Tuple[bool, str]:
        """Check for required API keys."""
        required_keys = ["ANTHROPIC_API_KEY"]
        missing_keys = []

        for key in required_keys:
            if not os.getenv(key):
                missing_keys.append(key)

        if missing_keys:
            return False, f"Missing API keys: {', '.join(missing_keys)}"
        else:
            return True, "All required API keys found"

    def install_dependencies(self) -> bool:
        """Install required Python and Node.js dependencies."""
        logger.info("Installing Python dependencies...")

        # Python dependencies
        python_packages = [
            "fastmcp>=0.1.0",
            "pydantic>=2.0.0",
            "aiofiles>=23.0.0",
            "asyncio-mqtt>=0.13.0",
            "watchdog>=3.0.0",
            "rich>=13.0.0",
            "typer>=0.9.0",
            "httpx>=0.24.0",
            "websockets>=11.0.0",
            "python-multipart>=0.0.6",
            "uvicorn>=0.23.0",
            "fastapi>=0.103.0"
        ]

        try:
            # Install Python packages
            for package in python_packages:
                logger.info(f"  Installing {package}...")
                result = subprocess.run([
                    sys.executable, "-m", "pip", "install", package
                ], capture_output=True, text=True)

                if result.returncode != 0:
                    logger.error(f"Failed to install {package}: {result.stderr}")
                    return False

            # Check if npm is available for optional Node.js packages
            try:
                subprocess.run(["npm", "--version"], capture_output=True, check=True)
                logger.info("Installing optional Node.js dependencies...")

                # Optional Node.js packages for web dashboard
                npm_packages = ["ws", "express", "socket.io"]

                for package in npm_packages:
                    logger.info(f"  Installing {package}...")
                    result = subprocess.run([
                        "npm", "install", "-g", package
                    ], capture_output=True, text=True)

                    if result.returncode != 0:
                        logger.warning(f"Failed to install {package} (optional): {result.stderr}")

            except (FileNotFoundError, subprocess.CalledProcessError):
                logger.info("npm not available - skipping Node.js packages")

            self.setup_status["dependencies"] = True
            return True

        except Exception as e:
            logger.error(f"Error installing dependencies: {e}")
            return False

    def create_directory_structure(self) -> bool:
        """Create the orchestrator directory structure."""
        logger.info("Creating directory structure...")

        # Define directory structure
        directories = [
            self.orchestrator_dir,
            self.orchestrator_dir / "master",
            self.orchestrator_dir / "master" / "config",
            self.orchestrator_dir / "master" / "logs",
            self.orchestrator_dir / "workers",
            self.orchestrator_dir / "workers" / "worker_template",
            self.orchestrator_dir / "shared_knowledge",
            self.orchestrator_dir / "monitoring",
            self.orchestrator_dir / "monitoring" / "web",
            self.orchestrator_dir / "scripts",
            self.orchestrator_dir / "docs",
            self.orchestrator_dir / "tests"
        ]

        try:
            # Create directories
            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"  Created: {directory.relative_to(self.orchestrator_dir.parent)}")

            # Copy Python files to master directory
            self.copy_orchestrator_files()

            # Create template files
            self.create_template_files()

            self.setup_status["directory_structure"] = True
            return True

        except Exception as e:
            logger.error(f"Error creating directory structure: {e}")
            return False

    def copy_orchestrator_files(self):
        """Copy orchestrator Python files to master directory."""
        master_dir = self.orchestrator_dir / "master"

        # Files to copy
        python_files = [
            "orchestrator_master.py",
            "worker_manager.py",
            "worker_lifecycle.py",
            "task_queue.py",
            "communication.py",
            "repo_manager.py",
            "monitoring_gui.py",
            "config.py",
            "message_queue.py",
            "master_communication.py",
            "priority_timeout_handler.py",
            "enhanced_orchestrator_tools.py",
            "task_decomposition.py",
            "task_orchestration_tools.py",
            "task_orchestration_examples.py",
            "merge_coordination.py",
            "merge_coordination_tools.py",
            "merge_coordination_examples.py",
            "memory_management.py",
            "memory_tools.py",
            "memory_examples.py",
            "shared_knowledge.py",
            "shared_knowledge_tools.py",
            "shared_knowledge_examples.py"
        ]

        for file_name in python_files:
            source_file = self.setup_dir / file_name
            if source_file.exists():
                target_file = master_dir / file_name
                shutil.copy2(source_file, target_file)
                logger.info(f"    Copied: {file_name}")
            else:
                logger.warning(f"    Missing: {file_name}")

    def create_template_files(self):
        """Create template configuration files."""

        # Create .gitignore
        gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
logs/
*.log

# Worker directories (except template)
workers/*/
!workers/worker_template/

# Environment variables
.env
.env.local

# Claude Code configs
claude_desktop_config.json.backup

# OS
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.temp
"""
        (self.orchestrator_dir / ".gitignore").write_text(gitignore_content.strip())

        # Create README
        readme_content = """# Multi-Agent Orchestrator

A sophisticated system for coordinating multiple Claude Code workers with intelligent task decomposition, merge coordination, and shared knowledge management.

## Quick Start

1. Start the master: `./scripts/start_master.sh`
2. Monitor via web dashboard: http://localhost:8080
3. Deploy workers as needed through the master interface

## Directory Structure

- `master/` - Master orchestrator and coordination logic
- `workers/` - Worker instances (created at runtime)
- `shared_knowledge/` - Cross-worker knowledge base
- `monitoring/` - Web dashboard and monitoring tools
- `scripts/` - Start/stop scripts

## Documentation

See `docs/` directory for detailed documentation.
"""
        (self.orchestrator_dir / "README.md").write_text(readme_content.strip())

        # Create requirements.txt
        requirements_content = """fastmcp>=0.1.0
pydantic>=2.0.0
aiofiles>=23.0.0
asyncio-mqtt>=0.13.0
watchdog>=3.0.0
rich>=13.0.0
typer>=0.9.0
httpx>=0.24.0
websockets>=11.0.0
python-multipart>=0.0.6
uvicorn>=0.23.0
fastapi>=0.103.0
"""
        (self.orchestrator_dir / "requirements.txt").write_text(requirements_content.strip())

    def configure_mcp_servers(self) -> bool:
        """Configure MCP servers for Master and workers."""
        logger.info("Configuring MCP servers...")

        try:
            # Configure Master MCP
            self.configure_master_mcp()

            # Create worker template config
            self.create_worker_template_config()

            # Setup GitHub MCP integration
            self.setup_github_mcp()

            self.setup_status["mcp_config"] = True
            return True

        except Exception as e:
            logger.error(f"Error configuring MCP servers: {e}")
            return False

    def configure_master_mcp(self):
        """Configure MCP for the master orchestrator."""
        config_dir = self.orchestrator_dir / "master" / "config"

        # Master Claude desktop config
        claude_config = {
            "mcpServers": {
                "orchestrator-master": {
                    "command": "python",
                    "args": [str(self.orchestrator_dir / "master" / "orchestrator_master.py")],
                    "env": {
                        "ORCHESTRATOR_HOST": "localhost",
                        "ORCHESTRATOR_PORT": "8765",
                        "LOG_LEVEL": "INFO"
                    }
                }
            }
        }

        claude_config_file = config_dir / "claude_desktop_config.json"
        with open(claude_config_file, 'w') as f:
            json.dump(claude_config, f, indent=2)

        logger.info(f"    Created master MCP config: {claude_config_file}")

        # Master orchestrator config
        master_config = {
            "server": {
                "host": "localhost",
                "port": 8765,
                "max_workers": 10,
                "log_level": "INFO"
            },
            "workers": {
                "default_model": "sonnet",
                "max_concurrent_tasks": 5,
                "timeout_minutes": 30,
                "auto_scale": True
            },
            "repositories": {
                "max_concurrent_ops": 3,
                "default_branch": "main",
                "auto_commit": False
            },
            "monitoring": {
                "web_port": 8080,
                "metrics_enabled": True,
                "log_retention_days": 30
            },
            "shared_knowledge": {
                "auto_share_completion": True,
                "conflict_detection": True,
                "knowledge_retention_days": 90
            }
        }

        master_config_file = config_dir / "orchestrator_config.json"
        with open(master_config_file, 'w') as f:
            json.dump(master_config, f, indent=2)

        logger.info(f"    Created master config: {master_config_file}")

    def create_worker_template_config(self):
        """Create worker template configuration."""
        template_dir = self.orchestrator_dir / "workers" / "worker_template"

        # Worker config template
        worker_config = {
            "worker": {
                "id": "{{WORKER_ID}}",
                "model": "{{MODEL}}",
                "task_name": "{{TASK_NAME}}",
                "master_host": "localhost",
                "master_port": 8765
            },
            "git": {
                "branch": "{{BRANCH_NAME}}",
                "base_branch": "main",
                "auto_commit": True,
                "commit_message_prefix": "[{{WORKER_ID}}]"
            },
            "memory": {
                "max_context_tokens": 20000,
                "save_threshold_tokens": 50000,
                "auto_save_context": True
            },
            "shared_knowledge": {
                "auto_load_context": True,
                "share_completion": True,
                "check_conflicts": True
            }
        }

        worker_config_file = template_dir / "worker_config.json"
        with open(worker_config_file, 'w') as f:
            json.dump(worker_config, f, indent=2)

        logger.info(f"    Created worker template config: {worker_config_file}")

        # Worker Claude desktop config template
        worker_claude_config = {
            "mcpServers": {
                "worker-{{WORKER_ID}}": {
                    "command": "python",
                    "args": [str(self.orchestrator_dir / "workers" / "{{WORKER_ID}}" / "worker_client.py")],
                    "env": {
                        "WORKER_ID": "{{WORKER_ID}}",
                        "MASTER_HOST": "localhost",
                        "MASTER_PORT": "8765"
                    }
                }
            }
        }

        worker_claude_file = template_dir / "claude_desktop_config_template.json"
        with open(worker_claude_file, 'w') as f:
            json.dump(worker_claude_config, f, indent=2)

        logger.info(f"    Created worker Claude config template: {worker_claude_file}")

    def setup_github_mcp(self):
        """Setup GitHub MCP integration."""
        config_dir = self.orchestrator_dir / "master" / "config"

        # GitHub MCP config (if API key available)
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            github_config = {
                "mcpServers": {
                    "github": {
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-github"],
                        "env": {
                            "GITHUB_PERSONAL_ACCESS_TOKEN": github_token
                        }
                    }
                }
            }

            github_config_file = config_dir / "github_mcp_config.json"
            with open(github_config_file, 'w') as f:
                json.dump(github_config, f, indent=2)

            logger.info(f"    Created GitHub MCP config: {github_config_file}")
        else:
            logger.info("    GitHub token not found - skipping GitHub MCP setup")

    def initialize_git_repository(self) -> bool:
        """Initialize Git repository with proper configuration."""
        logger.info("Initializing Git repository...")

        try:
            os.chdir(self.orchestrator_dir)

            # Initialize git repo if not already initialized
            if not (self.orchestrator_dir / ".git").exists():
                subprocess.run(["git", "init"], check=True, capture_output=True)
                logger.info("    Initialized Git repository")
            else:
                logger.info("    Git repository already exists")

            # Configure git worktree settings
            git_configs = [
                ("core.worktree", str(self.orchestrator_dir)),
                ("push.default", "simple"),
                ("pull.rebase", "false")
            ]

            for key, value in git_configs:
                try:
                    subprocess.run(["git", "config", key, value], check=True, capture_output=True)
                    logger.info(f"    Set git config: {key} = {value}")
                except subprocess.CalledProcessError:
                    logger.warning(f"    Failed to set git config: {key}")

            # Create initial commit if repository is empty
            try:
                subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True)
                logger.info("    Repository has existing commits")
            except subprocess.CalledProcessError:
                # Repository is empty, create initial commit
                subprocess.run(["git", "add", "."], check=True, capture_output=True)
                subprocess.run([
                    "git", "commit", "-m", "Initial setup of Multi-Agent Orchestrator"
                ], check=True, capture_output=True)
                logger.info("    Created initial commit")

            # Ensure main branch exists
            try:
                subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                try:
                    subprocess.run(["git", "checkout", "-b", "main"], check=True, capture_output=True)
                    logger.info("    Created main branch")
                except subprocess.CalledProcessError:
                    logger.warning("    Could not create/checkout main branch")

            self.setup_status["git_setup"] = True
            return True

        except Exception as e:
            logger.error(f"Error initializing Git repository: {e}")
            return False

    def create_start_scripts(self) -> bool:
        """Create start/stop scripts."""
        logger.info("Creating start scripts...")

        try:
            scripts_dir = self.orchestrator_dir / "scripts"

            # Make scripts executable
            def make_executable(script_path):
                os.chmod(script_path, 0o755)

            # Create start_master.sh
            start_master_content = f"""#!/bin/bash
set -e

ORCHESTRATOR_DIR="{self.orchestrator_dir}"
MASTER_DIR="$ORCHESTRATOR_DIR/master"

echo "🚀 Starting Multi-Agent Orchestrator Master..."

# Check if master directory exists
if [ ! -d "$MASTER_DIR" ]; then
    echo "❌ Master directory not found: $MASTER_DIR"
    exit 1
fi

# Change to master directory
cd "$MASTER_DIR"

# Check if Python environment is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi

# Check if required packages are installed
if ! python3 -c "import fastmcp" &> /dev/null; then
    echo "⚠️ FastMCP not installed, installing dependencies..."
    pip install -r ../requirements.txt
fi

# Start the orchestrator master
echo "📡 Starting orchestrator master server..."
export PYTHONPATH="$MASTER_DIR:$PYTHONPATH"
python3 orchestrator_master.py

echo "✅ Master orchestrator started successfully"
"""

            start_master_script = scripts_dir / "start_master.sh"
            start_master_script.write_text(start_master_content)
            make_executable(start_master_script)
            logger.info(f"    Created: {start_master_script}")

            # Create start_worker.sh template
            start_worker_content = f"""#!/bin/bash
set -e

# Usage: ./start_worker.sh <worker_id> [model] [task_name]

WORKER_ID=${{1:-worker-001}}
MODEL=${{2:-sonnet}}
TASK_NAME="${{3:-general-task}}"

ORCHESTRATOR_DIR="{self.orchestrator_dir}"
WORKERS_DIR="$ORCHESTRATOR_DIR/workers"
TEMPLATE_DIR="$WORKERS_DIR/worker_template"
WORKER_DIR="$WORKERS_DIR/$WORKER_ID"

echo "🤖 Starting worker: $WORKER_ID (model: $MODEL)"

# Create worker directory from template
if [ ! -d "$WORKER_DIR" ]; then
    echo "📁 Creating worker directory: $WORKER_DIR"
    cp -r "$TEMPLATE_DIR" "$WORKER_DIR"

    # Replace template variables in config
    sed -i "s/{{{{WORKER_ID}}}}/$WORKER_ID/g" "$WORKER_DIR"/*.json
    sed -i "s/{{{{MODEL}}}}/$MODEL/g" "$WORKER_DIR"/*.json
    sed -i "s/{{{{TASK_NAME}}}}/$TASK_NAME/g" "$WORKER_DIR"/*.json
    sed -i "s/{{{{BRANCH_NAME}}}}/worker-$WORKER_ID/g" "$WORKER_DIR"/*.json
fi

# Change to worker directory
cd "$WORKER_DIR"

# Start Claude Code with worker config
echo "🚀 Starting Claude Code for worker $WORKER_ID..."
claude-code --config claude_desktop_config_template.json

echo "✅ Worker $WORKER_ID started successfully"
"""

            start_worker_script = scripts_dir / "start_worker.sh"
            start_worker_script.write_text(start_worker_content)
            make_executable(start_worker_script)
            logger.info(f"    Created: {start_worker_script}")

            # Create stop_all.sh
            stop_all_content = f"""#!/bin/bash
set -e

echo "⏹️ Stopping Multi-Agent Orchestrator..."

# Find and stop all orchestrator processes
ORCHESTRATOR_PIDS=$(pgrep -f "orchestrator_master.py" || true)
WORKER_PIDS=$(pgrep -f "claude-code.*worker" || true)

if [ ! -z "$ORCHESTRATOR_PIDS" ]; then
    echo "🛑 Stopping orchestrator master processes..."
    echo "$ORCHESTRATOR_PIDS" | xargs kill -TERM
    sleep 2

    # Force kill if still running
    REMAINING_PIDS=$(pgrep -f "orchestrator_master.py" || true)
    if [ ! -z "$REMAINING_PIDS" ]; then
        echo "$REMAINING_PIDS" | xargs kill -KILL
    fi
fi

if [ ! -z "$WORKER_PIDS" ]; then
    echo "🤖 Stopping worker processes..."
    echo "$WORKER_PIDS" | xargs kill -TERM
    sleep 2

    # Force kill if still running
    REMAINING_WORKER_PIDS=$(pgrep -f "claude-code.*worker" || true)
    if [ ! -z "$REMAINING_WORKER_PIDS" ]; then
        echo "$REMAINING_WORKER_PIDS" | xargs kill -KILL
    fi
fi

echo "✅ All orchestrator processes stopped"
"""

            stop_all_script = scripts_dir / "stop_all.sh"
            stop_all_script.write_text(stop_all_content)
            make_executable(stop_all_script)
            logger.info(f"    Created: {stop_all_script}")

            # Create monitoring script
            monitor_content = f"""#!/bin/bash

ORCHESTRATOR_DIR="{self.orchestrator_dir}"

echo "📊 Multi-Agent Orchestrator Status"
echo "================================="

# Check master status
if pgrep -f "orchestrator_master.py" > /dev/null; then
    echo "✅ Master: Running"
    echo "   📡 Web Dashboard: http://localhost:8080"
    echo "   🔌 MCP Server: localhost:8765"
else
    echo "❌ Master: Not running"
fi

# Check worker status
WORKER_COUNT=$(pgrep -f "claude-code.*worker" | wc -l)
echo "🤖 Workers: $WORKER_COUNT active"

# Show active workers
if [ $WORKER_COUNT -gt 0 ]; then
    echo "   Active workers:"
    pgrep -f "claude-code.*worker" | while read pid; do
        cmd=$(ps -p $pid -o cmd --no-headers)
        echo "   - PID $pid: $cmd"
    done
fi

# Check logs
echo ""
echo "📋 Recent logs:"
if [ -f "$ORCHESTRATOR_DIR/master/logs/orchestrator.log" ]; then
    tail -5 "$ORCHESTRATOR_DIR/master/logs/orchestrator.log"
else
    echo "   No log file found"
fi
"""

            monitor_script = scripts_dir / "monitor.sh"
            monitor_script.write_text(monitor_content)
            make_executable(monitor_script)
            logger.info(f"    Created: {monitor_script}")

            self.setup_status["scripts"] = True
            return True

        except Exception as e:
            logger.error(f"Error creating start scripts: {e}")
            return False

    def finalize_setup(self) -> bool:
        """Finalize setup and create status file."""
        logger.info("Finalizing setup...")

        try:
            # Create setup status file
            setup_info = {
                "setup_completed": True,
                "setup_date": str(datetime.now().isoformat()),
                "setup_version": "1.0.0",
                "orchestrator_path": str(self.orchestrator_dir),
                "python_version": f"{self.python_version.major}.{self.python_version.minor}.{self.python_version.micro}",
                "platform": self.system_platform,
                "setup_status": self.setup_status
            }

            setup_file = self.orchestrator_dir / ".setup_info.json"
            with open(setup_file, 'w') as f:
                json.dump(setup_info, f, indent=2)

            logger.info(f"    Created setup info: {setup_file}")

            # Create quick reference guide
            self.create_quick_reference()

            return True

        except Exception as e:
            logger.error(f"Error finalizing setup: {e}")
            return False

    def create_quick_reference(self):
        """Create quick reference guide."""
        quick_ref_content = f"""# Multi-Agent Orchestrator - Quick Reference

## Setup Information
- Installation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Installation Path: {self.orchestrator_dir}
- Platform: {self.system_platform}

## Quick Start Commands

### Start the Master
```bash
cd {self.orchestrator_dir}
./scripts/start_master.sh
```

### Monitor Status
```bash
./scripts/monitor.sh
```

### Start a Worker
```bash
./scripts/start_worker.sh worker-001 sonnet "authentication task"
```

### Stop Everything
```bash
./scripts/stop_all.sh
```

## Web Interfaces
- **Main Dashboard**: http://localhost:8080
- **Master MCP**: localhost:8765

## Directory Structure
```
{self.orchestrator_dir.name}/
├── master/              # Master orchestrator
├── workers/             # Worker instances
├── shared_knowledge/    # Cross-worker knowledge
├── monitoring/          # Web dashboard
├── scripts/             # Start/stop scripts
└── docs/               # Documentation
```

## Configuration Files
- Master config: `master/config/orchestrator_config.json`
- Worker template: `workers/worker_template/worker_config.json`
- MCP configs: `master/config/claude_desktop_config.json`

## Troubleshooting
1. Check logs: `master/logs/orchestrator.log`
2. Verify processes: `./scripts/monitor.sh`
3. Check API keys: Ensure ANTHROPIC_API_KEY is set
4. Port conflicts: Default ports 8765 (MCP), 8080 (web)

## Next Steps
1. Set your API keys (ANTHROPIC_API_KEY)
2. Start the master: `./scripts/start_master.sh`
3. Access the web dashboard at http://localhost:8080
4. Deploy workers through the dashboard interface
"""

        quick_ref_file = self.orchestrator_dir / "QUICK_START.md"
        quick_ref_file.write_text(quick_ref_content)
        logger.info(f"    Created quick reference: {quick_ref_file}")

    def print_next_steps(self):
        """Print next steps for the user."""
        print(f"""
🎯 Next Steps:

1. Set your API keys:
   export ANTHROPIC_API_KEY="your-api-key-here"

2. Start the master orchestrator:
   cd {self.orchestrator_dir}
   ./scripts/start_master.sh

3. Open the web dashboard:
   http://localhost:8080

4. Deploy workers through the dashboard or manually:
   ./scripts/start_worker.sh worker-001 sonnet "my-task"

📚 Documentation:
   - Quick start guide: {self.orchestrator_dir}/QUICK_START.md
   - Full README: {self.orchestrator_dir}/README.md

🔧 Useful commands:
   - Monitor status: ./scripts/monitor.sh
   - Stop all: ./scripts/stop_all.sh

Happy orchestrating! 🎉
""")


def main():
    """Main setup function."""
    setup_manager = SetupManager()

    try:
        success = setup_manager.run_full_setup()
        if success:
            sys.exit(0)
        else:
            logger.error("Setup failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Setup failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()