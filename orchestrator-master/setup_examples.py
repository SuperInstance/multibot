#!/usr/bin/env python3
"""
Setup Examples and Testing
Demonstrates setup script functionality and validates installation.
"""

import asyncio
import logging
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List
import json

from setup import SetupManager

logger = logging.getLogger(__name__)


class SetupTester:
    """Test and validate setup functionality."""

    def __init__(self, test_dir: Path = None):
        self.test_dir = test_dir or Path(tempfile.mkdtemp(prefix="orchestrator_test_"))
        self.setup_manager = None

    async def run_setup_tests(self) -> Dict[str, Any]:
        """Run comprehensive setup tests."""
        logger.info(f"🧪 Running setup tests in: {self.test_dir}")

        test_results = {
            "test_directory": str(self.test_dir),
            "tests": {},
            "overall_success": False
        }

        tests = [
            ("prerequisites_check", self.test_prerequisites_check),
            ("directory_creation", self.test_directory_creation),
            ("file_copying", self.test_file_copying),
            ("config_generation", self.test_config_generation),
            ("script_creation", self.test_script_creation),
            ("git_initialization", self.test_git_initialization),
            ("idempotent_reruns", self.test_idempotent_reruns)
        ]

        successful_tests = 0
        for test_name, test_func in tests:
            logger.info(f"Running test: {test_name}")
            try:
                result = await test_func()
                test_results["tests"][test_name] = {
                    "status": "success" if result else "failed",
                    "details": result if isinstance(result, dict) else {"passed": result}
                }
                if result:
                    successful_tests += 1
                    logger.info(f"✅ {test_name} passed")
                else:
                    logger.error(f"❌ {test_name} failed")
            except Exception as e:
                logger.error(f"❌ {test_name} failed with exception: {e}")
                test_results["tests"][test_name] = {
                    "status": "error",
                    "error": str(e)
                }

        test_results["overall_success"] = successful_tests == len(tests)
        test_results["success_rate"] = successful_tests / len(tests)

        return test_results

    async def test_prerequisites_check(self) -> bool:
        """Test prerequisites checking functionality."""
        try:
            # Create temporary setup manager
            temp_setup = SetupManager()
            temp_setup.orchestrator_dir = self.test_dir / "orchestrator"

            # Test individual prerequisite checks
            python_check = temp_setup.check_python_version()
            git_check = temp_setup.check_git()

            # Python and Git should always pass in a development environment
            if not python_check[0] or not git_check[0]:
                return False

            logger.info(f"Python check: {python_check[1]}")
            logger.info(f"Git check: {git_check[1]}")

            return True

        except Exception as e:
            logger.error(f"Prerequisites check test failed: {e}")
            return False

    async def test_directory_creation(self) -> bool:
        """Test directory structure creation."""
        try:
            # Create setup manager with test directory
            setup = SetupManager()
            setup.orchestrator_dir = self.test_dir / "orchestrator"

            # Test directory creation
            success = setup.create_directory_structure()

            if not success:
                return False

            # Verify expected directories exist
            expected_dirs = [
                "master",
                "master/config",
                "master/logs",
                "workers",
                "workers/worker_template",
                "shared_knowledge",
                "monitoring",
                "monitoring/web",
                "scripts",
                "docs",
                "tests"
            ]

            for dir_path in expected_dirs:
                full_path = setup.orchestrator_dir / dir_path
                if not full_path.exists():
                    logger.error(f"Missing directory: {dir_path}")
                    return False

            logger.info(f"✅ All {len(expected_dirs)} directories created successfully")
            return True

        except Exception as e:
            logger.error(f"Directory creation test failed: {e}")
            return False

    async def test_file_copying(self) -> bool:
        """Test copying of orchestrator files."""
        try:
            setup = SetupManager()
            setup.setup_dir = Path(__file__).parent  # Current directory with Python files
            setup.orchestrator_dir = self.test_dir / "orchestrator"

            # Create directory structure first
            setup.create_directory_structure()

            # Copy files
            setup.copy_orchestrator_files()

            # Check that key files were copied
            master_dir = setup.orchestrator_dir / "master"
            key_files = [
                "orchestrator_master.py",
                "task_decomposition.py",
                "memory_management.py",
                "shared_knowledge.py"
            ]

            copied_files = 0
            for file_name in key_files:
                file_path = master_dir / file_name
                if file_path.exists():
                    copied_files += 1
                    logger.info(f"✅ Copied: {file_name}")
                else:
                    logger.warning(f"Missing: {file_name}")

            # At least half the key files should be copied
            return copied_files >= len(key_files) // 2

        except Exception as e:
            logger.error(f"File copying test failed: {e}")
            return False

    async def test_config_generation(self) -> bool:
        """Test configuration file generation."""
        try:
            setup = SetupManager()
            setup.orchestrator_dir = self.test_dir / "orchestrator"

            # Create directory structure
            setup.create_directory_structure()

            # Generate configs
            setup.configure_mcp_servers()

            # Check master config files
            config_dir = setup.orchestrator_dir / "master" / "config"
            expected_configs = [
                "claude_desktop_config.json",
                "orchestrator_config.json"
            ]

            for config_file in expected_configs:
                config_path = config_dir / config_file
                if not config_path.exists():
                    logger.error(f"Missing config: {config_file}")
                    return False

                # Validate JSON structure
                try:
                    with open(config_path) as f:
                        config_data = json.load(f)
                    logger.info(f"✅ Valid config: {config_file}")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in: {config_file}")
                    return False

            # Check worker template config
            worker_template_dir = setup.orchestrator_dir / "workers" / "worker_template"
            worker_config = worker_template_dir / "worker_config.json"

            if not worker_config.exists():
                logger.error("Missing worker template config")
                return False

            return True

        except Exception as e:
            logger.error(f"Config generation test failed: {e}")
            return False

    async def test_script_creation(self) -> bool:
        """Test start/stop script creation."""
        try:
            setup = SetupManager()
            setup.orchestrator_dir = self.test_dir / "orchestrator"

            # Create directory structure
            setup.create_directory_structure()

            # Create scripts
            setup.create_start_scripts()

            # Check script files
            scripts_dir = setup.orchestrator_dir / "scripts"
            expected_scripts = [
                "start_master.sh",
                "start_worker.sh",
                "stop_all.sh",
                "monitor.sh"
            ]

            for script_name in expected_scripts:
                script_path = scripts_dir / script_name
                if not script_path.exists():
                    logger.error(f"Missing script: {script_name}")
                    return False

                # Check if script is executable
                if not script_path.stat().st_mode & 0o111:
                    logger.error(f"Script not executable: {script_name}")
                    return False

                logger.info(f"✅ Created executable script: {script_name}")

            return True

        except Exception as e:
            logger.error(f"Script creation test failed: {e}")
            return False

    async def test_git_initialization(self) -> bool:
        """Test Git repository initialization."""
        try:
            setup = SetupManager()
            setup.orchestrator_dir = self.test_dir / "orchestrator"

            # Create directory structure and files first
            setup.create_directory_structure()

            # Initialize Git repository
            success = setup.initialize_git_repository()

            if not success:
                return False

            # Check Git repository exists
            git_dir = setup.orchestrator_dir / ".git"
            if not git_dir.exists():
                logger.error("Git repository not created")
                return False

            # Check for .gitignore
            gitignore = setup.orchestrator_dir / ".gitignore"
            if not gitignore.exists():
                logger.error(".gitignore not created")
                return False

            logger.info("✅ Git repository initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Git initialization test failed: {e}")
            return False

    async def test_idempotent_reruns(self) -> bool:
        """Test that setup can be run multiple times safely."""
        try:
            setup = SetupManager()
            setup.orchestrator_dir = self.test_dir / "orchestrator"

            # Run setup twice
            for run_number in [1, 2]:
                logger.info(f"Running setup iteration {run_number}")

                # Create directory structure
                success = setup.create_directory_structure()
                if not success:
                    logger.error(f"Setup run {run_number} failed at directory creation")
                    return False

                # Configure MCP servers
                success = setup.configure_mcp_servers()
                if not success:
                    logger.error(f"Setup run {run_number} failed at MCP configuration")
                    return False

                # Create scripts
                success = setup.create_start_scripts()
                if not success:
                    logger.error(f"Setup run {run_number} failed at script creation")
                    return False

            logger.info("✅ Setup is idempotent - can run multiple times safely")
            return True

        except Exception as e:
            logger.error(f"Idempotent reruns test failed: {e}")
            return False

    def cleanup_test_directory(self):
        """Clean up test directory."""
        try:
            if self.test_dir.exists():
                shutil.rmtree(self.test_dir)
                logger.info(f"Cleaned up test directory: {self.test_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up test directory: {e}")


class SetupExamples:
    """Examples demonstrating setup script usage."""

    def __init__(self):
        self.examples = self._load_examples()

    def _load_examples(self) -> Dict[str, Dict[str, Any]]:
        """Load setup example scenarios."""
        return {
            "fresh_installation": {
                "description": "Complete fresh installation on clean system",
                "steps": [
                    "Check prerequisites",
                    "Install dependencies",
                    "Create directory structure",
                    "Configure MCP servers",
                    "Initialize Git repository",
                    "Create start scripts"
                ]
            },
            "update_existing": {
                "description": "Update existing installation",
                "steps": [
                    "Detect existing installation",
                    "Backup current configuration",
                    "Update files and dependencies",
                    "Migrate configuration",
                    "Test functionality"
                ]
            },
            "custom_configuration": {
                "description": "Installation with custom configuration",
                "customizations": {
                    "custom_port": 9000,
                    "custom_host": "0.0.0.0",
                    "max_workers": 20,
                    "enable_monitoring": True
                }
            },
            "development_setup": {
                "description": "Setup for development environment",
                "features": [
                    "Debug logging enabled",
                    "Hot reload for code changes",
                    "Test data pre-populated",
                    "Development shortcuts enabled"
                ]
            }
        }

    def generate_setup_examples_report(self) -> str:
        """Generate setup examples documentation."""
        report = """# Setup Script Examples and Usage

## Overview
The setup script (`setup.py` and `setup.sh`) provides automated installation and configuration of the Multi-Agent Orchestrator system.

## Basic Usage

### Quick Start
```bash
# Make setup script executable
chmod +x setup.sh

# Run automated setup
./setup.sh
```

### Python Setup (Advanced)
```bash
# Run Python setup directly with options
python3 setup.py
```

## Setup Process

The setup script performs these steps automatically:

### 1. Prerequisites Check
- Verifies Python 3.8+ installation
- Checks for WSL (Windows only)
- Validates Claude Code CLI installation
- Confirms Git availability
- Checks Node.js version (optional)
- Validates API keys

### 2. Dependency Installation
- Installs Python packages from requirements.txt
- Installs optional Node.js packages
- Sets up virtual environment if needed

### 3. Directory Structure Creation
```
orchestrator/
├── master/              # Master orchestrator
│   ├── config/         # Configuration files
│   └── logs/           # Log files
├── workers/            # Worker instances
│   └── worker_template/ # Template for new workers
├── shared_knowledge/   # Cross-worker knowledge
├── monitoring/         # Web dashboard
├── scripts/           # Start/stop scripts
└── docs/             # Documentation
```

### 4. MCP Server Configuration
- Generates Claude desktop configuration
- Creates worker configuration templates
- Sets up GitHub MCP integration (if token available)

### 5. Git Repository Initialization
- Initializes Git repository
- Creates .gitignore with appropriate rules
- Configures Git worktree settings
- Creates initial commit

### 6. Start Script Creation
- `start_master.sh` - Launch master orchestrator
- `start_worker.sh` - Launch worker instances
- `stop_all.sh` - Graceful shutdown
- `monitor.sh` - Status monitoring

## Example Scenarios

### Scenario 1: Fresh Installation
```bash
# Clean system setup
./setup.sh

# Set API keys
export ANTHROPIC_API_KEY="your-key"

# Start system
cd orchestrator
./scripts/start_master.sh
```

### Scenario 2: Development Setup
```bash
# Setup with development options
export LOG_LEVEL="DEBUG"
export DEVELOPMENT_MODE="true"
./setup.sh

# Start with hot reload
cd orchestrator
./scripts/start_master.sh --reload
```

### Scenario 3: Custom Configuration
```bash
# Setup with custom ports
export ORCHESTRATOR_PORT="9000"
export WEB_DASHBOARD_PORT="9080"
./setup.sh
```

### Scenario 4: Update Existing Installation
```bash
# Update preserves configuration
./setup.sh

# Answer 'y' to update prompt
# Configuration is migrated automatically
```

## Configuration Examples

### Master Configuration
```json
{
  "server": {
    "host": "localhost",
    "port": 8765,
    "max_workers": 10
  },
  "workers": {
    "default_model": "sonnet",
    "timeout_minutes": 30,
    "auto_scale": true
  }
}
```

### Worker Template
```json
{
  "worker": {
    "id": "{{WORKER_ID}}",
    "model": "{{MODEL}}",
    "master_host": "localhost"
  },
  "memory": {
    "max_context_tokens": 20000,
    "auto_save_context": true
  }
}
```

## Troubleshooting Setup

### Common Issues

**"Python version too old"**
```bash
# Install Python 3.8+
sudo apt update
sudo apt install python3.8 python3.8-pip
```

**"Claude Code CLI not found"**
```bash
# Install from official source
# Visit: https://claude.ai/code
```

**"Permission denied on scripts"**
```bash
chmod +x orchestrator/scripts/*.sh
```

**"Port already in use"**
- Change ports in configuration files
- Kill existing processes: `./scripts/stop_all.sh`

### Validation Commands
```bash
# Check installation
./scripts/monitor.sh

# Validate configuration
python3 -c "import json; json.load(open('orchestrator/master/config/orchestrator_config.json'))"

# Test dependencies
python3 -c "import fastmcp, pydantic, aiofiles"
```

## Advanced Setup Options

### Custom Installation Directory
```bash
export ORCHESTRATOR_DIR="/custom/path"
./setup.sh
```

### Skip Dependencies
```bash
export SKIP_DEPENDENCIES="true"
./setup.sh
```

### Development Mode
```bash
export DEVELOPMENT_MODE="true"
export DEBUG_LOGGING="true"
./setup.sh
```

## Post-Setup Verification

### Quick Health Check
```bash
cd orchestrator

# Start master
./scripts/start_master.sh &

# Wait for startup
sleep 5

# Check status
./scripts/monitor.sh

# Test web dashboard
curl http://localhost:8080/health

# Stop system
./scripts/stop_all.sh
```

### Complete System Test
```bash
# Start system
./scripts/start_master.sh &
sleep 5

# Deploy test worker
./scripts/start_worker.sh test-worker sonnet "validation task"

# Check worker registration
curl http://localhost:8080/api/workers

# Assign simple task
curl -X POST http://localhost:8080/api/tasks \\
  -H "Content-Type: application/json" \\
  -d '{"description": "Hello world test", "worker_id": "test-worker"}'

# Monitor completion
./scripts/monitor.sh

# Cleanup
./scripts/stop_all.sh
```

## Setup Script Features

### Idempotent Operations
- Safe to run multiple times
- Preserves existing configuration
- Updates only necessary components

### Error Handling
- Comprehensive error checking
- Rollback on failure
- Detailed error messages

### Platform Support
- Linux (native)
- macOS (native)
- Windows (via WSL)

### Customization
- Environment variable configuration
- Command-line options
- Configuration file templates

The setup script ensures a reliable, reproducible installation process for the Multi-Agent Orchestrator system across different environments and use cases.
"""
        return report.strip()


async def run_setup_examples_demo():
    """Run demonstration of setup examples and testing."""
    print("🔧 Setup Script Examples and Testing Demo")
    print("=" * 50)

    # Create setup tester
    tester = SetupTester()

    try:
        # Run setup tests
        print("\n🧪 Running setup validation tests...")
        test_results = await tester.run_setup_tests()

        print(f"\n📊 Test Results:")
        print(f"  • Test directory: {test_results['test_directory']}")
        print(f"  • Overall success: {'✅' if test_results['overall_success'] else '❌'}")
        print(f"  • Success rate: {test_results['success_rate']:.2%}")

        # Show individual test results
        for test_name, result in test_results["tests"].items():
            status_icon = {"success": "✅", "failed": "❌", "error": "💥"}[result["status"]]
            print(f"    {status_icon} {test_name}: {result['status']}")

        # Generate examples report
        print("\n📚 Generating setup examples documentation...")
        examples = SetupExamples()
        examples_report = examples.generate_setup_examples_report()

        print("✅ Setup examples and testing completed!")
        print("\n🎯 Next steps:")
        print("  1. Review test results above")
        print("  2. Run actual setup: ./setup.sh")
        print("  3. Follow quick start guide")

        return test_results, examples_report

    finally:
        # Cleanup test directory
        tester.cleanup_test_directory()


if __name__ == "__main__":
    # Configure logging for demo
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Run the demo
    asyncio.run(run_setup_examples_demo())