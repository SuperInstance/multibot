#!/usr/bin/env python3
"""
Worker Launch Script
Standalone script for launching individual Claude Code workers.
Used by the worker lifecycle manager to spawn worker processes.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path


def setup_worker_logging(worker_id: str, logs_dir: Path):
    """Set up logging for the worker."""
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / f"worker_{worker_id}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(f"worker_{worker_id}")


def create_heartbeat_file(worker_id: str, memory_dir: Path, status: str = "starting"):
    """Create heartbeat file to signal worker status."""
    heartbeat_data = {
        "worker_id": worker_id,
        "status": status,
        "timestamp": time.time(),
        "pid": os.getpid()
    }

    heartbeat_file = memory_dir / "heartbeat.json"
    with open(heartbeat_file, "w") as f:
        json.dump(heartbeat_data, f, indent=2)


def update_heartbeat(worker_id: str, memory_dir: Path, status: str = "active"):
    """Update heartbeat file."""
    try:
        create_heartbeat_file(worker_id, memory_dir, status)
    except Exception as e:
        print(f"Failed to update heartbeat: {e}")


def load_worker_config(config_file: Path):
    """Load worker configuration."""
    try:
        with open(config_file) as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load worker config: {e}")
        sys.exit(1)


def prepare_environment(config: dict, worker_id: str):
    """Prepare environment for Claude Code."""
    env = os.environ.copy()

    # Worker-specific environment
    env.update({
        "WORKER_ID": worker_id,
        "WORKER_MODEL": config.get("model", "sonnet"),
        "MULTIBOT_ROLE": "worker",
        "WORKER_MEMORY_DIR": config.get("memory_directory", ""),
        "WORKER_WORKING_DIR": config.get("working_directory", "")
    })

    return env


def start_heartbeat_monitor(worker_id: str, memory_dir: Path):
    """Start background heartbeat monitoring."""
    import threading
    import signal

    def heartbeat_loop():
        while True:
            try:
                update_heartbeat(worker_id, memory_dir, "active")
                time.sleep(30)  # Update every 30 seconds
            except Exception as e:
                print(f"Heartbeat error: {e}")
                time.sleep(5)

    def signal_handler(signum, frame):
        update_heartbeat(worker_id, memory_dir, "terminating")
        sys.exit(0)

    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()


def launch_claude(config_file: Path, working_dir: Path):
    """Launch Claude Code with the specified configuration."""
    import subprocess

    # Build Claude command
    claude_cmd = [
        "claude",
        "--config", str(config_file)
    ]

    try:
        # Change to working directory
        os.chdir(working_dir)

        # Execute Claude Code
        result = subprocess.run(
            claude_cmd,
            check=False,
            capture_output=False
        )

        return result.returncode

    except Exception as e:
        print(f"Failed to launch Claude: {e}")
        return 1


def main():
    """Main entry point for worker launch."""
    parser = argparse.ArgumentParser(description="Launch Claude Code worker")
    parser.add_argument("--worker-id", required=True, help="Worker ID")
    parser.add_argument("--config", required=True, help="Path to Claude config file")
    parser.add_argument("--working-dir", required=True, help="Working directory")
    parser.add_argument("--memory-dir", required=True, help="Memory directory")
    parser.add_argument("--logs-dir", required=True, help="Logs directory")

    args = parser.parse_args()

    worker_id = args.worker_id
    config_file = Path(args.config)
    working_dir = Path(args.working_dir)
    memory_dir = Path(args.memory_dir)
    logs_dir = Path(args.logs_dir)

    # Set up logging
    logger = setup_worker_logging(worker_id, logs_dir)
    logger.info(f"Starting worker {worker_id}")

    try:
        # Load configuration
        config = load_worker_config(config_file)
        logger.info(f"Loaded configuration for worker {worker_id}")

        # Prepare environment
        env = prepare_environment(config, worker_id)
        os.environ.update(env)

        # Create initial heartbeat
        create_heartbeat_file(worker_id, memory_dir, "starting")
        logger.info(f"Created initial heartbeat for worker {worker_id}")

        # Start heartbeat monitoring
        start_heartbeat_monitor(worker_id, memory_dir)
        logger.info(f"Started heartbeat monitoring for worker {worker_id}")

        # Signal ready status
        update_heartbeat(worker_id, memory_dir, "ready")
        logger.info(f"Worker {worker_id} is ready")

        # Launch Claude Code
        logger.info(f"Launching Claude Code for worker {worker_id}")
        exit_code = launch_claude(config_file, working_dir)

        logger.info(f"Claude Code exited with code {exit_code} for worker {worker_id}")

        # Final heartbeat
        update_heartbeat(worker_id, memory_dir, "completed")

        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Worker {worker_id} failed: {str(e)}")

        try:
            update_heartbeat(worker_id, memory_dir, "error")
        except:
            pass

        sys.exit(1)


if __name__ == "__main__":
    main()