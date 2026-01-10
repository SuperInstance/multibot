"""
Worker Manager Module
Handles lifecycle management of Claude Code worker instances.
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class WorkerInfo:
    """Information about a worker instance."""

    def __init__(self, worker_id: str, model: str, working_dir: str, branch_name: str):
        self.worker_id = worker_id
        self.model = model
        self.working_dir = working_dir
        self.branch_name = branch_name
        self.status = "initializing"
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.created_at = datetime.now()
        self.last_heartbeat = datetime.now()
        self.current_task: Optional[str] = None
        self.terminal_session: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert worker info to dictionary."""
        return {
            "worker_id": self.worker_id,
            "model": self.model,
            "working_dir": self.working_dir,
            "branch_name": self.branch_name,
            "status": self.status,
            "pid": self.pid,
            "created_at": self.created_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "current_task": self.current_task,
            "terminal_session": self.terminal_session
        }


class WorkerManager:
    """Manages the lifecycle of Claude Code worker instances."""

    def __init__(self):
        self.workers: Dict[str, WorkerInfo] = {}
        self.state_dir = Path("/tmp/multibot/workers")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.heartbeat_timeout = 300  # 5 minutes
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize the worker manager."""
        logger.info("Initializing Worker Manager")

        # Load existing worker state
        await self._load_worker_state()

        # Start heartbeat monitoring
        self._heartbeat_task = asyncio.create_task(self._monitor_heartbeats())

        logger.info(f"Worker Manager initialized with {len(self.workers)} workers")

    async def spawn_worker(self, worker_id: str, model: str, working_dir: str, branch_name: str) -> Dict[str, Any]:
        """Spawn a new Claude Code worker instance."""
        if worker_id in self.workers:
            raise ValueError(f"Worker {worker_id} already exists")

        logger.info(f"Spawning worker {worker_id} with model {model}")

        # Create worker info
        worker = WorkerInfo(worker_id, model, working_dir, branch_name)

        # Prepare environment for worker
        env = os.environ.copy()
        env.update({
            "WORKER_ID": worker_id,
            "WORKER_MODEL": model,
            "WORKER_BRANCH": branch_name,
            "MULTIBOT_ROLE": "worker"
        })

        # Create worker-specific directories
        worker_state_dir = self.state_dir / worker_id
        worker_state_dir.mkdir(exist_ok=True)

        # Create worker startup script
        startup_script = self._create_worker_startup_script(worker, worker_state_dir)

        try:
            # Launch Claude Code worker in new terminal
            if os.name == 'nt':  # Windows
                cmd = [
                    "wt", "new-tab", "--title", f"Worker-{worker_id}",
                    "bash", "-c", f"cd {working_dir} && {startup_script}"
                ]
            else:  # Linux/macOS
                cmd = [
                    "gnome-terminal", "--title", f"Worker-{worker_id}",
                    "--", "bash", "-c", f"cd {working_dir} && {startup_script}; exec bash"
                ]

            # Start the process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            worker.process = process
            worker.pid = process.pid
            worker.status = "starting"
            worker.terminal_session = f"worker-{worker_id}-terminal"

            # Register worker
            self.workers[worker_id] = worker

            # Save state
            await self._save_worker_state(worker_id)

            # Wait for worker to initialize
            await self._wait_for_worker_ready(worker_id)

            logger.info(f"Worker {worker_id} spawned successfully with PID {worker.pid}")

            return {
                "worker_id": worker_id,
                "pid": worker.pid,
                "terminal_session": worker.terminal_session,
                "status": worker.status
            }

        except Exception as e:
            # Cleanup on failure
            if worker_id in self.workers:
                del self.workers[worker_id]
            raise Exception(f"Failed to spawn worker {worker_id}: {str(e)}")

    async def terminate_worker(self, worker_id: str) -> Dict[str, Any]:
        """Terminate a specific worker instance."""
        if worker_id not in self.workers:
            raise ValueError(f"Worker {worker_id} not found")

        worker = self.workers[worker_id]
        logger.info(f"Terminating worker {worker_id} (PID: {worker.pid})")

        try:
            worker.status = "terminating"

            # Send graceful shutdown signal
            if worker.process and worker.pid:
                try:
                    # Send SIGTERM first
                    os.kill(worker.pid, signal.SIGTERM)

                    # Wait for graceful shutdown
                    await asyncio.wait_for(worker.process.wait(), timeout=10.0)

                except (ProcessLookupError, asyncio.TimeoutError):
                    # Force kill if graceful shutdown fails
                    try:
                        os.kill(worker.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Process already dead

            # Cleanup worker state
            worker_state_dir = self.state_dir / worker_id
            if worker_state_dir.exists():
                import shutil
                shutil.rmtree(worker_state_dir)

            # Remove from registry
            terminated_worker = self.workers.pop(worker_id)

            logger.info(f"Worker {worker_id} terminated successfully")

            return {
                "worker_id": worker_id,
                "terminated_at": datetime.now().isoformat(),
                "final_status": terminated_worker.status
            }

        except Exception as e:
            logger.error(f"Error terminating worker {worker_id}: {str(e)}")
            raise

    async def pause_worker(self, worker_id: str) -> Dict[str, Any]:
        """Pause a worker instance."""
        if worker_id not in self.workers:
            raise ValueError(f"Worker {worker_id} not found")

        worker = self.workers[worker_id]

        if worker.status == "paused":
            return {"worker_id": worker_id, "message": "Worker already paused"}

        if worker.process and worker.pid:
            try:
                os.kill(worker.pid, signal.SIGSTOP)
                worker.status = "paused"
                await self._save_worker_state(worker_id)

                logger.info(f"Worker {worker_id} paused")
                return {
                    "worker_id": worker_id,
                    "status": "paused",
                    "paused_at": datetime.now().isoformat()
                }

            except ProcessLookupError:
                worker.status = "error"
                raise Exception(f"Worker process {worker_id} not found")

        else:
            raise Exception(f"No active process for worker {worker_id}")

    async def resume_worker(self, worker_id: str) -> Dict[str, Any]:
        """Resume a paused worker instance."""
        if worker_id not in self.workers:
            raise ValueError(f"Worker {worker_id} not found")

        worker = self.workers[worker_id]

        if worker.status != "paused":
            return {"worker_id": worker_id, "message": "Worker is not paused"}

        if worker.process and worker.pid:
            try:
                os.kill(worker.pid, signal.SIGCONT)
                worker.status = "active"
                await self._save_worker_state(worker_id)

                logger.info(f"Worker {worker_id} resumed")
                return {
                    "worker_id": worker_id,
                    "status": "active",
                    "resumed_at": datetime.now().isoformat()
                }

            except ProcessLookupError:
                worker.status = "error"
                raise Exception(f"Worker process {worker_id} not found")

        else:
            raise Exception(f"No active process for worker {worker_id}")

    async def list_workers(self) -> List[Dict[str, Any]]:
        """Get list of all workers and their status."""
        workers_list = []

        for worker_id, worker in self.workers.items():
            # Check if process is still alive
            await self._update_worker_status(worker_id)
            workers_list.append(worker.to_dict())

        return workers_list

    async def get_worker_status(self, worker_id: str) -> Dict[str, Any]:
        """Get detailed status of a specific worker."""
        if worker_id not in self.workers:
            raise ValueError(f"Worker {worker_id} not found")

        worker = self.workers[worker_id]

        # Update status
        await self._update_worker_status(worker_id)

        return worker.to_dict()

    async def update_worker_heartbeat(self, worker_id: str, task_info: Optional[Dict[str, Any]] = None):
        """Update worker heartbeat and task information."""
        if worker_id in self.workers:
            worker = self.workers[worker_id]
            worker.last_heartbeat = datetime.now()

            if task_info:
                worker.current_task = task_info.get("task_id")

            await self._save_worker_state(worker_id)

    def _create_worker_startup_script(self, worker: WorkerInfo, state_dir: Path) -> str:
        """Create startup script for worker."""
        script_path = state_dir / "startup.sh"

        startup_script = f"""#!/bin/bash
# Worker {worker.worker_id} startup script

echo "Starting Claude Code Worker {worker.worker_id}"
echo "Model: {worker.model}"
echo "Branch: {worker.branch_name}"
echo "Working Directory: {worker.working_dir}"

# Set worker environment
export WORKER_ID="{worker.worker_id}"
export WORKER_MODEL="{worker.model}"
export WORKER_BRANCH="{worker.branch_name}"
export MULTIBOT_ROLE="worker"

# Create heartbeat script
cat > {state_dir}/heartbeat.py << 'EOF'
import json
import time
from pathlib import Path

state_file = Path("{state_dir}/heartbeat.json")

while True:
    heartbeat = {{
        "worker_id": "{worker.worker_id}",
        "timestamp": time.time(),
        "status": "active"
    }}

    with open(state_file, "w") as f:
        json.dump(heartbeat, f)

    time.sleep(30)
EOF

# Start heartbeat in background
python3 {state_dir}/heartbeat.py &

# Start Claude Code worker
claude-code --model {worker.model} --config worker-config.json

# Cleanup on exit
echo "Worker {worker.worker_id} shutting down"
"""

        with open(script_path, "w") as f:
            f.write(startup_script)

        os.chmod(script_path, 0o755)
        return str(script_path)

    async def _wait_for_worker_ready(self, worker_id: str, timeout: int = 60):
        """Wait for worker to be ready."""
        worker = self.workers[worker_id]
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check for heartbeat file
            heartbeat_file = self.state_dir / worker_id / "heartbeat.json"
            if heartbeat_file.exists():
                try:
                    with open(heartbeat_file) as f:
                        heartbeat = json.load(f)

                    if heartbeat.get("status") == "active":
                        worker.status = "active"
                        await self._save_worker_state(worker_id)
                        return

                except (json.JSONDecodeError, KeyError):
                    pass

            await asyncio.sleep(2)

        # Timeout reached
        worker.status = "timeout"
        raise Exception(f"Worker {worker_id} failed to start within {timeout} seconds")

    async def _update_worker_status(self, worker_id: str):
        """Update worker status based on process and heartbeat."""
        worker = self.workers[worker_id]

        # Check if process is alive
        if worker.process and worker.pid:
            try:
                # Check if process exists
                os.kill(worker.pid, 0)
                process_alive = True
            except ProcessLookupError:
                process_alive = False
                worker.status = "dead"
        else:
            process_alive = False

        # Check heartbeat
        if process_alive:
            heartbeat_file = self.state_dir / worker_id / "heartbeat.json"
            if heartbeat_file.exists():
                try:
                    with open(heartbeat_file) as f:
                        heartbeat = json.load(f)

                    heartbeat_time = datetime.fromtimestamp(heartbeat["timestamp"])
                    time_since_heartbeat = (datetime.now() - heartbeat_time).total_seconds()

                    if time_since_heartbeat > self.heartbeat_timeout:
                        worker.status = "unresponsive"
                    else:
                        worker.status = heartbeat.get("status", "unknown")

                except (json.JSONDecodeError, KeyError, ValueError):
                    worker.status = "error"

    async def _monitor_heartbeats(self):
        """Monitor worker heartbeats and handle failures."""
        while True:
            try:
                for worker_id in list(self.workers.keys()):
                    await self._update_worker_status(worker_id)

                    worker = self.workers[worker_id]
                    if worker.status in ["dead", "unresponsive"]:
                        logger.warning(f"Worker {worker_id} is {worker.status}, attempting recovery")
                        # Could implement auto-restart logic here

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error in heartbeat monitoring: {str(e)}")
                await asyncio.sleep(30)

    async def _save_worker_state(self, worker_id: str):
        """Save worker state to disk."""
        if worker_id not in self.workers:
            return

        worker = self.workers[worker_id]
        state_file = self.state_dir / f"{worker_id}-state.json"

        try:
            with open(state_file, "w") as f:
                json.dump(worker.to_dict(), f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save state for worker {worker_id}: {str(e)}")

    async def _load_worker_state(self):
        """Load worker state from disk."""
        if not self.state_dir.exists():
            return

        for state_file in self.state_dir.glob("*-state.json"):
            try:
                with open(state_file) as f:
                    state = json.load(f)

                worker_id = state["worker_id"]
                worker = WorkerInfo(
                    worker_id=worker_id,
                    model=state["model"],
                    working_dir=state["working_dir"],
                    branch_name=state["branch_name"]
                )

                # Restore state
                worker.status = state.get("status", "unknown")
                worker.pid = state.get("pid")
                worker.current_task = state.get("current_task")
                worker.terminal_session = state.get("terminal_session")

                if state.get("created_at"):
                    worker.created_at = datetime.fromisoformat(state["created_at"])
                if state.get("last_heartbeat"):
                    worker.last_heartbeat = datetime.fromisoformat(state["last_heartbeat"])

                # Verify worker is still alive
                if worker.pid:
                    try:
                        os.kill(worker.pid, 0)
                        # Process exists, but we need to reconnect
                        worker.status = "recovered"
                    except ProcessLookupError:
                        # Process is dead
                        worker.status = "dead"

                self.workers[worker_id] = worker
                logger.info(f"Recovered worker {worker_id} with status {worker.status}")

            except Exception as e:
                logger.error(f"Failed to load worker state from {state_file}: {str(e)}")

    async def cleanup(self):
        """Cleanup resources."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Terminate all workers
        for worker_id in list(self.workers.keys()):
            try:
                await self.terminate_worker(worker_id)
            except Exception as e:
                logger.error(f"Error terminating worker {worker_id} during cleanup: {str(e)}")

        logger.info("Worker Manager cleanup completed")