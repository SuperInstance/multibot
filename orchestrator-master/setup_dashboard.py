#!/usr/bin/env python3
"""
Dashboard Setup Script
Sets up the monitoring dashboard with dependencies and configuration.
"""

import os
import subprocess
import sys
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    return True


def check_tkinter():
    """Check if tkinter is available."""
    try:
        import tkinter
        print("✓ tkinter is available")
        return True
    except ImportError:
        print("✗ tkinter not found")
        print("Please install tkinter:")
        print("  Ubuntu/Debian: sudo apt-get install python3-tk")
        print("  CentOS/RHEL: sudo yum install tkinter")
        print("  macOS: tkinter should be included with Python")
        print("  Windows: tkinter should be included with Python")
        return False


def install_dependencies():
    """Install required Python packages."""
    requirements = [
        "fastmcp",
        "psutil",
        "asyncio-throttle"
    ]

    for package in requirements:
        try:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✓ {package} installed successfully")
        except subprocess.CalledProcessError:
            print(f"✗ Failed to install {package}")
            return False

    return True


def create_directory_structure():
    """Create necessary directory structure."""
    base_dir = Path("/tmp/multibot")
    directories = [
        base_dir,
        base_dir / "workers",
        base_dir / "logs",
        base_dir / "config"
    ]

    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"✓ Created directory: {directory}")
        except Exception as e:
            print(f"✗ Failed to create directory {directory}: {e}")
            return False

    return True


def create_sample_config():
    """Create sample configuration file."""
    config_content = """{
  "window_geometry": "1400x900",
  "max_workers": 12,
  "fast_update_interval": 1.0,
  "slow_update_interval": 5.0,
  "max_log_lines": 100,
  "terminal_font": ["Consolas", 8],
  "default_worker_model": "sonnet",
  "log_level": "INFO",
  "auto_discover_workers": true
}"""

    config_file = Path("dashboard_config.json")
    if not config_file.exists():
        try:
            with open(config_file, 'w') as f:
                f.write(config_content)
            print(f"✓ Created sample config: {config_file}")
        except Exception as e:
            print(f"✗ Failed to create config file: {e}")
            return False
    else:
        print(f"✓ Config file already exists: {config_file}")

    return True


def create_launch_scripts():
    """Create convenient launch scripts."""
    # Demo mode script
    demo_script = """#!/bin/bash
# Launch dashboard in demo mode
python3 run_dashboard.py --demo
"""

    # Production mode script
    prod_script = """#!/bin/bash
# Launch dashboard with orchestrator integration
python3 run_dashboard.py
"""

    # Windows batch files
    demo_bat = """@echo off
REM Launch dashboard in demo mode
python run_dashboard.py --demo
pause
"""

    prod_bat = """@echo off
REM Launch dashboard with orchestrator integration
python run_dashboard.py
pause
"""

    scripts = [
        ("demo_dashboard.sh", demo_script),
        ("run_dashboard.sh", prod_script),
        ("demo_dashboard.bat", demo_bat),
        ("run_dashboard.bat", prod_bat)
    ]

    for script_name, script_content in scripts:
        try:
            script_path = Path(script_name)
            with open(script_path, 'w') as f:
                f.write(script_content)

            # Make shell scripts executable on Unix systems
            if script_name.endswith('.sh') and os.name != 'nt':
                os.chmod(script_path, 0o755)

            print(f"✓ Created launch script: {script_name}")
        except Exception as e:
            print(f"✗ Failed to create script {script_name}: {e}")

    return True


def test_dashboard():
    """Test if dashboard can be imported and started."""
    try:
        print("Testing dashboard import...")
        from monitoring_dashboard import MonitoringDashboard
        print("✓ Dashboard module imported successfully")

        print("Testing configuration...")
        from dashboard_config import load_config
        config = load_config()
        print("✓ Configuration loaded successfully")

        return True
    except Exception as e:
        print(f"✗ Dashboard test failed: {e}")
        return False


def main():
    """Main setup function."""
    print("Multi-Agent Orchestrator Dashboard Setup")
    print("=" * 50)

    success = True

    # Check Python version
    print("\n1. Checking Python version...")
    if not check_python_version():
        success = False

    # Check tkinter
    print("\n2. Checking tkinter availability...")
    if not check_tkinter():
        success = False

    # Install dependencies
    print("\n3. Installing Python dependencies...")
    if not install_dependencies():
        success = False

    # Create directory structure
    print("\n4. Creating directory structure...")
    if not create_directory_structure():
        success = False

    # Create sample config
    print("\n5. Creating sample configuration...")
    if not create_sample_config():
        success = False

    # Create launch scripts
    print("\n6. Creating launch scripts...")
    if not create_launch_scripts():
        success = False

    # Test dashboard
    print("\n7. Testing dashboard...")
    if not test_dashboard():
        success = False

    # Summary
    print("\n" + "=" * 50)
    if success:
        print("✓ Setup completed successfully!")
        print("\nNext steps:")
        print("1. Run 'python3 run_dashboard.py --demo' to test the dashboard")
        print("2. Start the orchestrator system")
        print("3. Run 'python3 run_dashboard.py' for full integration")
        print("\nOr use the convenience scripts:")
        print("  ./demo_dashboard.sh    # Demo mode (Unix)")
        print("  ./run_dashboard.sh     # Full mode (Unix)")
        print("  demo_dashboard.bat     # Demo mode (Windows)")
        print("  run_dashboard.bat      # Full mode (Windows)")
    else:
        print("✗ Setup encountered errors")
        print("Please resolve the issues above and run setup again")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())