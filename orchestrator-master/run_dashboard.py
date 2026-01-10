#!/usr/bin/env python3
"""
Dashboard Startup Script
Main entry point for running the monitoring dashboard.
"""

import argparse
import asyncio
import logging
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from typing import Optional

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dashboard_config import load_config, save_config
from dashboard_integration import IntegratedMonitoringDashboard
from monitoring_dashboard import MonitoringDashboard


def setup_logging(config):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format=config.log_format,
        datefmt=config.log_date_format
    )

    # Create logs directory
    config.logs_dir.mkdir(parents=True, exist_ok=True)

    # Add file handler
    log_file = config.logs_dir / "dashboard.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "[%(asctime)s] %(name)s - %(levelname)s: %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    # Add to root logger
    logging.getLogger().addHandler(file_handler)

    logger = logging.getLogger(__name__)
    logger.info("Dashboard logging initialized")
    logger.info(f"Log file: {log_file}")


def check_dependencies():
    """Check if required dependencies are available."""
    missing_deps = []

    try:
        import tkinter
    except ImportError:
        missing_deps.append("tkinter")

    try:
        import sqlite3
    except ImportError:
        missing_deps.append("sqlite3")

    if missing_deps:
        print(f"Missing required dependencies: {', '.join(missing_deps)}")
        print("Please install the missing dependencies and try again.")
        return False

    return True


def check_orchestrator_connection(config):
    """Check if orchestrator is running and accessible."""
    try:
        # Check if message queue database exists
        if not config.db_path.exists():
            logger.warning(f"Message queue database not found at {config.db_path}")
            logger.warning("Dashboard will run in demo mode without real data")
            return False

        # Check if base directory structure exists
        if not config.workers_dir.exists():
            logger.warning(f"Workers directory not found at {config.workers_dir}")
            config.workers_dir.mkdir(parents=True, exist_ok=True)

        return True

    except Exception as e:
        logger.error(f"Error checking orchestrator connection: {e}")
        return False


def create_demo_dashboard(config):
    """Create dashboard with demo data."""
    logger.info("Starting dashboard in demo mode")

    dashboard = MonitoringDashboard()
    dashboard.root.title(f"{config.window_title} (Demo Mode)")

    return dashboard


def create_integrated_dashboard(config, orchestrator=None):
    """Create dashboard with real orchestrator integration."""
    logger.info("Starting dashboard with orchestrator integration")

    dashboard = IntegratedMonitoringDashboard(orchestrator)
    dashboard.root.title(config.window_title)

    return dashboard


def handle_shutdown(dashboard, config):
    """Handle graceful shutdown."""
    logger.info("Shutting down dashboard")

    try:
        # Save configuration
        save_config(config)

        # Stop integration if running
        if hasattr(dashboard, 'data_provider'):
            asyncio.create_task(dashboard.stop_integration())

        # Close dashboard
        dashboard.root.quit()

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def run_dashboard_with_args(args):
    """Run dashboard with command line arguments."""
    global logger

    # Load configuration
    config = load_config(args.config)

    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)

    logger.info("Starting Multi-Agent Orchestrator Monitoring Dashboard")
    logger.info(f"Configuration: {config}")

    # Check dependencies
    if not check_dependencies():
        return 1

    # Override config with command line arguments
    if args.geometry:
        config.window_geometry = args.geometry
    if args.max_workers:
        config.max_workers = args.max_workers
    if args.update_interval:
        config.fast_update_interval = args.update_interval

    # Check orchestrator connection
    orchestrator_available = check_orchestrator_connection(config)

    try:
        # Create dashboard
        if args.demo or not orchestrator_available:
            dashboard = create_demo_dashboard(config)
        else:
            dashboard = create_integrated_dashboard(config)

        # Setup window properties
        dashboard.root.geometry(config.window_geometry)

        # Setup shutdown handler
        def on_closing():
            handle_shutdown(dashboard, config)

        dashboard.root.protocol("WM_DELETE_WINDOW", on_closing)

        # Start dashboard
        if hasattr(dashboard, 'run_integrated'):
            dashboard.run_integrated()
        else:
            dashboard.run()

        logger.info("Dashboard shutdown complete")
        return 0

    except KeyboardInterrupt:
        logger.info("Dashboard interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Orchestrator Monitoring Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run with default settings
  %(prog)s --demo                   # Run in demo mode
  %(prog)s --config custom.json     # Use custom config file
  %(prog)s --geometry 1600x1000     # Set window size
  %(prog)s --max-workers 8          # Limit to 8 workers max
        """
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Configuration file path (default: dashboard_config.json)"
    )

    parser.add_argument(
        "--demo", "-d",
        action="store_true",
        help="Run in demo mode with fake data"
    )

    parser.add_argument(
        "--geometry", "-g",
        type=str,
        help="Window geometry (e.g., 1400x900)"
    )

    parser.add_argument(
        "--max-workers", "-w",
        type=int,
        help="Maximum number of workers to display"
    )

    parser.add_argument(
        "--update-interval", "-u",
        type=float,
        help="Update interval in seconds (default: 1.0)"
    )

    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version="Multi-Agent Orchestrator Dashboard v1.0"
    )

    args = parser.parse_args()

    # Run dashboard
    return run_dashboard_with_args(args)


if __name__ == "__main__":
    sys.exit(main())