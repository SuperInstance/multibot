#!/usr/bin/env python3
"""
Web Dashboard Startup Script
Main entry point for running the web-based monitoring dashboard.
"""

import argparse
import asyncio
import logging
import os
import sys
import signal
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from web_dashboard_server import WebDashboardServer
from dashboard_config import load_config


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="[%(asctime)s] %(name)s - %(levelname)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    logger = logging.getLogger(__name__)
    logger.info("Web dashboard logging initialized")


def check_dependencies():
    """Check if required dependencies are available."""
    missing_deps = []

    try:
        import fastapi
    except ImportError:
        missing_deps.append("fastapi")

    try:
        import uvicorn
    except ImportError:
        missing_deps.append("uvicorn")

    try:
        import websockets
    except ImportError:
        missing_deps.append("websockets")

    if missing_deps:
        print(f"Missing required dependencies: {', '.join(missing_deps)}")
        print("Please install them with:")
        print("pip install -r web_requirements.txt")
        return False

    return True


async def run_web_dashboard(args):
    """Run the web dashboard with command line arguments."""
    logger = logging.getLogger(__name__)

    # Setup logging
    setup_logging(args.log_level)

    logger.info("Starting Multi-Agent Orchestrator Web Dashboard")

    # Check dependencies
    if not check_dependencies():
        return 1

    # Load configuration
    config = load_config(args.config)
    logger.info(f"Configuration loaded: {config}")

    try:
        # Create and configure web dashboard server
        server = WebDashboardServer()

        # Start background tasks
        await server.start()

        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            asyncio.create_task(server.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run the server
        logger.info(f"Web dashboard accessible at http://{args.host}:{args.port}")
        logger.info("Press Ctrl+C to stop the server")

        server.run(host=args.host, port=args.port)

        return 0

    except KeyboardInterrupt:
        logger.info("Web dashboard interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Web dashboard error: {e}", exc_info=True)
        return 1
    finally:
        try:
            await server.stop()
        except:
            pass


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Orchestrator Web Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Run with default settings
  %(prog)s --host 0.0.0.0 --port 8080   # Custom host and port
  %(prog)s --config custom.json         # Use custom config file
  %(prog)s --demo                       # Run in demo mode
        """
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)"
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Configuration file path (default: dashboard_config.json)"
    )

    parser.add_argument(
        "--demo", "-d",
        action="store_true",
        help="Run in demo mode with simulated data"
    )

    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version="Multi-Agent Orchestrator Web Dashboard v1.0"
    )

    args = parser.parse_args()

    # If demo mode, warn about limitations
    if args.demo:
        print("WARNING: Demo mode is not yet implemented for web dashboard")
        print("The web dashboard will connect to the actual orchestrator system")

    # Run the web dashboard
    if sys.platform.startswith('win'):
        # Windows-specific asyncio setup
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    return asyncio.run(run_web_dashboard(args))


if __name__ == "__main__":
    sys.exit(main())