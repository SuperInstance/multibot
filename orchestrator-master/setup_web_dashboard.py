#!/usr/bin/env python3
"""
Web Dashboard Setup Script
Sets up the web-based monitoring dashboard with dependencies and configuration.
"""

import os
import subprocess
import sys
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3.8):
        print("Error: Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    return True


def install_web_dependencies():
    """Install required Python packages for web dashboard."""
    print("Installing web dashboard dependencies...")

    try:
        # Install from requirements file
        requirements_file = Path(__file__).parent / "web_requirements.txt"
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ])
        print("✓ Web dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install web dependencies: {e}")
        return False


def create_web_static_directory():
    """Create static files directory structure."""
    static_dir = Path(__file__).parent / "web_static"
    templates_dir = Path(__file__).parent / "web_templates"

    try:
        static_dir.mkdir(exist_ok=True)
        templates_dir.mkdir(exist_ok=True)
        print(f"✓ Created static directory: {static_dir}")
        print(f"✓ Created templates directory: {templates_dir}")
        return True
    except Exception as e:
        print(f"✗ Failed to create directories: {e}")
        return False


def test_web_dashboard():
    """Test if web dashboard can be imported and started."""
    try:
        print("Testing web dashboard import...")
        from web_dashboard_server import WebDashboardServer
        print("✓ Web dashboard module imported successfully")

        print("Testing FastAPI import...")
        import fastapi
        import uvicorn
        print("✓ FastAPI and uvicorn imported successfully")

        return True
    except Exception as e:
        print(f"✗ Web dashboard test failed: {e}")
        return False


def create_web_launch_scripts():
    """Create convenient launch scripts for web dashboard."""
    # Unix shell script
    web_script = """#!/bin/bash
# Launch web dashboard
echo "Starting Multi-Agent Orchestrator Web Dashboard..."
python3 run_web_dashboard.py --host 0.0.0.0 --port 8000
"""

    # Advanced web dashboard script
    advanced_web_script = """#!/bin/bash
# Launch advanced web dashboard
echo "Starting Advanced Multi-Agent Orchestrator Web Dashboard..."
python3 -c "from advanced_web_dashboard import AdvancedWebDashboard; import asyncio; asyncio.run(AdvancedWebDashboard().run())"
"""

    # Windows batch files
    web_bat = """@echo off
REM Launch web dashboard
echo Starting Multi-Agent Orchestrator Web Dashboard...
python run_web_dashboard.py --host 0.0.0.0 --port 8000
pause
"""

    advanced_web_bat = """@echo off
REM Launch advanced web dashboard
echo Starting Advanced Multi-Agent Orchestrator Web Dashboard...
python -c "from advanced_web_dashboard import AdvancedWebDashboard; import asyncio; asyncio.run(AdvancedWebDashboard().run())"
pause
"""

    scripts = [
        ("run_web_dashboard.sh", web_script),
        ("run_advanced_web_dashboard.sh", advanced_web_script),
        ("run_web_dashboard.bat", web_bat),
        ("run_advanced_web_dashboard.bat", advanced_web_bat)
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


def create_web_config():
    """Create web dashboard configuration file."""
    web_config = {
        "server": {
            "host": "127.0.0.1",
            "port": 8000,
            "reload": False,
            "workers": 1
        },
        "dashboard": {
            "title": "Multi-Agent Orchestrator Dashboard",
            "update_interval": 2.0,
            "max_log_lines": 100,
            "terminal_theme": "dark"
        },
        "security": {
            "enable_auth": False,
            "cors_origins": ["*"],
            "rate_limiting": {
                "enabled": False,
                "requests_per_minute": 60
            }
        },
        "features": {
            "xterm_js": True,
            "chart_js": True,
            "bootstrap": True,
            "font_awesome": True
        }
    }

    try:
        import json
        config_file = Path("web_dashboard_config.json")
        with open(config_file, 'w') as f:
            json.dump(web_config, f, indent=2)
        print(f"✓ Created web config: {config_file}")
        return True
    except Exception as e:
        print(f"✗ Failed to create web config: {e}")
        return False


def check_port_availability(port=8000):
    """Check if the default port is available."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
            print(f"✓ Port {port} is available")
            return True
    except OSError:
        print(f"⚠ Port {port} is in use, you may need to use a different port")
        return False


def main():
    """Main setup function."""
    print("Multi-Agent Orchestrator Web Dashboard Setup")
    print("=" * 55)

    success = True

    # Check Python version
    print("\n1. Checking Python version...")
    if not check_python_version():
        success = False

    # Install web dependencies
    print("\n2. Installing web dependencies...")
    if not install_web_dependencies():
        success = False

    # Create directory structure
    print("\n3. Creating directory structure...")
    if not create_web_static_directory():
        success = False

    # Create configuration
    print("\n4. Creating web configuration...")
    if not create_web_config():
        success = False

    # Create launch scripts
    print("\n5. Creating launch scripts...")
    if not create_web_launch_scripts():
        success = False

    # Test web dashboard
    print("\n6. Testing web dashboard...")
    if not test_web_dashboard():
        success = False

    # Check port availability
    print("\n7. Checking port availability...")
    check_port_availability()

    # Summary
    print("\n" + "=" * 55)
    if success:
        print("✓ Web dashboard setup completed successfully!")
        print("\nNext steps:")
        print("1. Start the orchestrator system if not already running")
        print("2. Run 'python3 run_web_dashboard.py' to start the web dashboard")
        print("3. Open your browser to http://localhost:8000")
        print("\nAlternative options:")
        print("• Advanced dashboard: python3 advanced_web_dashboard.py")
        print("• Custom host/port: python3 run_web_dashboard.py --host 0.0.0.0 --port 8080")
        print("• Demo mode (if available): python3 run_web_dashboard.py --demo")
        print("\nConvenience scripts:")
        print("  ./run_web_dashboard.sh         # Basic web dashboard (Unix)")
        print("  ./run_advanced_web_dashboard.sh # Advanced features (Unix)")
        print("  run_web_dashboard.bat          # Basic web dashboard (Windows)")
        print("  run_advanced_web_dashboard.bat # Advanced features (Windows)")
    else:
        print("✗ Web dashboard setup encountered errors")
        print("Please resolve the issues above and run setup again")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())