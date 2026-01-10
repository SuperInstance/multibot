"""
Enhanced Worker Lifecycle Management
Comprehensive system for managing Claude Code worker processes with proper directory structure,
configuration generation, terminal visualization, and state management.
"""

import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import uuid
import tempfile

from terminal_manager import TerminalManager

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """Configuration for a worker instance."""
    worker_id: str
    model: str
    task_name: str
    branch_name: str
    working_dir: Path
    memory_dir: Path
    logs_dir: Path
    config_dir: Path
    worktree_dir: Path

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with string paths."""
        return {
            "worker_id": self.worker_id,
            "model": self.model,
            "task_name": self.task_name,
            "branch_name": self.branch_name,
            "working_dir": str(self.working_dir),
            "memory_dir": str(self.memory_dir),
            "logs_dir": str(self.logs_dir),
            "config_dir": str(self.config_dir),
            "worktree_dir": str(self.worktree_dir)
        }


@dataclass
class WorkerProcess:
    """Information about a running worker process."""
    config: WorkerConfig
    process: Optional[subprocess.Popen] = None
    pid: Optional[int] = None
    tmux_session: Optional[str] = None
    start_time: Optional[datetime] = None
    status: str = "initializing"
    current_task: Optional[str] = None
    last_activity: Optional[datetime] = None
    memory_state: Dict[str, Any] = None

    def __post_init__(self):
        if self.memory_state is None:
            self.memory_state = {}


class WorkerLifecycleManager:
    """Enhanced worker lifecycle management with full process control."""

    def __init__(self, base_workspace: str = "/workspace"):
        self.base_workspace = Path(base_workspace)
        self.workers_dir = self.base_workspace / "workers"
        self.active_workers: Dict[str, WorkerProcess] = {}

        # Create base directories
        self.workers_dir.mkdir(parents=True, exist_ok=True)

        # Terminal management
        self.terminal_manager = TerminalManager()

        # Process monitoring
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

    async def initialize(self):
        """Initialize the worker lifecycle manager."""
        logger.info("Initializing Enhanced Worker Lifecycle Manager")

        # Initialize terminal manager
        await self.terminal_manager.initialize()

        # Start process monitoring
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_workers())

        # Recovery: check for existing workers
        await self._recover_existing_workers()

        logger.info(f"Worker Lifecycle Manager initialized with {len(self.active_workers)} workers")

    async def spawn_worker(
        self,
        worker_id: str,
        model: str,
        task_name: str,
        base_branch: str = "main"
    ) -> Dict[str, Any]:
        """Spawn a new Claude Code worker with full lifecycle management."""
        if worker_id in self.active_workers:
            raise ValueError(f"Worker {worker_id} already exists")

        logger.info(f"Spawning worker {worker_id} for task '{task_name}' with model {model}")

        try:
            # Create worker configuration
            worker_config = await self._create_worker_config(worker_id, model, task_name)

            # Create directory structure
            await self._create_worker_directories(worker_config)

            # Create Git worktree
            await self._create_worker_worktree(worker_config, base_branch)

            # Generate Claude configuration
            await self._generate_claude_config(worker_config)

            # Initialize worker memory
            await self._initialize_worker_memory(worker_config)

            # Launch Claude Code process
            worker_process = await self._launch_claude_process(worker_config)

            # Set up terminal visualization
            terminal_session = await self._setup_terminal_visualization(worker_process)
            worker_process.tmux_session = terminal_session.session_id

            # Register worker
            self.active_workers[worker_id] = worker_process

            # Save worker state
            await self._save_worker_state(worker_process)

            logger.info(f"Worker {worker_id} spawned successfully")

            return {
                "worker_id": worker_id,
                "model": model,
                "task_name": task_name,
                "branch": worker_config.branch_name,
                "working_dir": str(worker_config.worktree_dir),
                "pid": worker_process.pid,
                "tmux_session": worker_process.tmux_session,
                "status": worker_process.status
            }

        except Exception as e:
            # Cleanup on failure
            await self._cleanup_failed_worker(worker_id)
            logger.error(f"Failed to spawn worker {worker_id}: {str(e)}")
            raise

    async def terminate_worker(
        self,
        worker_id: str,
        save_state: bool = True,
        commit_changes: bool = True,
        preserve_worktree: bool = False
    ) -> Dict[str, Any]:
        """Gracefully terminate a worker with full cleanup."""
        if worker_id not in self.active_workers:
            raise ValueError(f"Worker {worker_id} not found")

        worker_process = self.active_workers[worker_id]
        logger.info(f"Terminating worker {worker_id}")

        try:
            termination_info = {
                "worker_id": worker_id,
                "terminated_at": datetime.now().isoformat(),
                "final_status": worker_process.status,
                "actions_performed": []
            }

            # Save current state if requested
            if save_state:
                await self._save_worker_final_state(worker_process)
                termination_info["actions_performed"].append("state_saved")

            # Commit and push changes if requested
            if commit_changes:
                commit_hash = await self._commit_worker_changes(worker_process)
                if commit_hash:
                    termination_info["final_commit"] = commit_hash
                    termination_info["actions_performed"].append("changes_committed")

            # Gracefully shutdown Claude Code process
            await self._shutdown_claude_process(worker_process)
            termination_info["actions_performed"].append("process_terminated")

            # Archive logs
            await self._archive_worker_logs(worker_process)
            termination_info["actions_performed"].append("logs_archived")

            # Clean up terminal
            await self._cleanup_terminal_visualization(worker_process)
            termination_info["actions_performed"].append("terminal_cleaned")

            # Handle worktree
            if preserve_worktree:
                termination_info["worktree_preserved"] = str(worker_process.config.worktree_dir)
            else:
                await self._cleanup_worker_worktree(worker_process)
                termination_info["actions_performed"].append("worktree_removed")

            # Remove from active workers
            del self.active_workers[worker_id]

            logger.info(f"Worker {worker_id} terminated successfully")
            return termination_info

        except Exception as e:
            logger.error(f"Error during worker {worker_id} termination: {str(e)}")
            # Force cleanup
            await self._force_cleanup_worker(worker_process)
            raise

    async def pause_worker(self, worker_id: str) -> bool:
        """Pause a worker process."""
        if worker_id not in self.active_workers:
            return False

        worker_process = self.active_workers[worker_id]

        if worker_process.process and worker_process.pid:
            try:
                os.kill(worker_process.pid, signal.SIGSTOP)
                worker_process.status = "paused"
                await self._save_worker_state(worker_process)

                # Update terminal status
                await self._update_terminal_status(worker_process)

                logger.info(f"Worker {worker_id} paused")
                return True
            except ProcessLookupError:
                worker_process.status = "dead"
                return False

        return False

    async def resume_worker(self, worker_id: str) -> bool:
        """Resume a paused worker process."""
        if worker_id not in self.active_workers:
            return False

        worker_process = self.active_workers[worker_id]

        if worker_process.process and worker_process.pid:
            try:
                os.kill(worker_process.pid, signal.SIGCONT)
                worker_process.status = "active"
                worker_process.last_activity = datetime.now()
                await self._save_worker_state(worker_process)

                # Update terminal status
                await self._update_terminal_status(worker_process)

                logger.info(f"Worker {worker_id} resumed")
                return True
            except ProcessLookupError:
                worker_process.status = "dead"
                return False

        return False

    async def get_worker_status(self, worker_id: str) -> Dict[str, Any]:
        """Get comprehensive worker status."""
        if worker_id not in self.active_workers:
            raise ValueError(f"Worker {worker_id} not found")

        worker_process = self.active_workers[worker_id]

        # Update process status
        await self._update_worker_status(worker_process)

        # Get resource usage
        resource_usage = await self._get_worker_resource_usage(worker_process)

        # Get recent activity
        recent_activity = await self._get_worker_recent_activity(worker_process)

        return {
            "worker_id": worker_id,
            "status": worker_process.status,
            "model": worker_process.config.model,
            "task_name": worker_process.config.task_name,
            "branch": worker_process.config.branch_name,
            "pid": worker_process.pid,
            "start_time": worker_process.start_time.isoformat() if worker_process.start_time else None,
            "last_activity": worker_process.last_activity.isoformat() if worker_process.last_activity else None,
            "current_task": worker_process.current_task,
            "tmux_session": worker_process.tmux_session,
            "working_dir": str(worker_process.config.worktree_dir),
            "resource_usage": resource_usage,
            "recent_activity": recent_activity,
            "memory_state": worker_process.memory_state
        }

    async def list_workers(self) -> List[Dict[str, Any]]:
        """List all active workers with their status."""
        workers = []

        for worker_id in list(self.active_workers.keys()):
            try:
                status = await self.get_worker_status(worker_id)
                workers.append(status)
            except Exception as e:
                logger.error(f"Failed to get status for worker {worker_id}: {str(e)}")
                # Mark as error state
                workers.append({
                    "worker_id": worker_id,
                    "status": "error",
                    "error": str(e)
                })

        return workers

    async def update_worker_task(self, worker_id: str, task_id: str, task_description: str):
        """Update worker's current task."""
        if worker_id in self.active_workers:
            worker_process = self.active_workers[worker_id]
            worker_process.current_task = task_id
            worker_process.last_activity = datetime.now()

            # Save to memory
            worker_process.memory_state["current_task"] = {
                "task_id": task_id,
                "description": task_description,
                "started_at": datetime.now().isoformat()
            }

            await self._save_worker_state(worker_process)
            await self._update_terminal_status(worker_process)

    async def _create_worker_config(self, worker_id: str, model: str, task_name: str) -> WorkerConfig:
        """Create worker configuration."""
        # Sanitize task name for filesystem
        safe_task_name = "".join(c for c in task_name if c.isalnum() or c in ('-', '_'))[:30]

        worker_dir = self.workers_dir / worker_id
        branch_name = f"worker-{worker_id}-{safe_task_name}"

        return WorkerConfig(
            worker_id=worker_id,
            model=model,
            task_name=task_name,
            branch_name=branch_name,
            working_dir=worker_dir,
            memory_dir=worker_dir / "memory",
            logs_dir=worker_dir / "logs",
            config_dir=worker_dir / "config",
            worktree_dir=worker_dir / "worktree"
        )

    async def _create_worker_directories(self, config: WorkerConfig):
        """Create complete directory structure for worker."""
        directories = [
            config.working_dir,
            config.memory_dir,
            config.logs_dir,
            config.config_dir
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Created directory structure for worker {config.worker_id}")

    async def _create_worker_worktree(self, config: WorkerConfig, base_branch: str):
        """Create Git worktree for worker."""
        try:
            # Create new branch from base branch
            await self._run_git_command([
                "checkout", "-b", config.branch_name, base_branch
            ])

            # Create worktree
            await self._run_git_command([
                "worktree", "add", str(config.worktree_dir), config.branch_name
            ])

            logger.info(f"Created worktree for {config.worker_id} at {config.worktree_dir}")

        except Exception as e:
            logger.error(f"Failed to create worktree for {config.worker_id}: {str(e)}")
            raise

    async def _generate_claude_config(self, config: WorkerConfig):
        """Generate Claude Code configuration for worker."""
        claude_config = {
            "worker_id": config.worker_id,
            "model": config.model,
            "working_directory": str(config.worktree_dir),
            "memory_directory": str(config.memory_dir),
            "mcpServers": {
                "worker-filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                    "env": {
                        "MCP_FILESYSTEM_ROOT": str(config.worktree_dir)
                    }
                },
                "worker-memory": {
                    "command": "python",
                    "args": [str(config.config_dir / "memory_server.py")],
                    "env": {
                        "WORKER_ID": config.worker_id,
                        "MEMORY_DIR": str(config.memory_dir)
                    }
                },
                "worker-communication": {
                    "command": "python",
                    "args": [str(config.config_dir / "communication_server.py")],
                    "env": {
                        "WORKER_ID": config.worker_id,
                        "MASTER_COMM_DIR": "/tmp/multibot/communication"
                    }
                },
                "worker-git": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-git"],
                    "env": {
                        "MCP_GIT_ROOT": str(config.worktree_dir)
                    }
                }
            },
            "experimental": {
                "controllerMode": "worker",
                "workerId": config.worker_id,
                "autoSave": True,
                "contextPreservation": True
            }
        }

        # Save main config
        config_file = config.config_dir / "claude_config.json"
        with open(config_file, "w") as f:
            json.dump(claude_config, f, indent=2)

        # Create MCP server scripts
        await self._create_mcp_servers(config)

        logger.debug(f"Generated Claude config for worker {config.worker_id}")

    async def _create_mcp_servers(self, config: WorkerConfig):
        """Create worker-specific MCP server scripts."""

        # Memory server
        memory_server_code = f'''#!/usr/bin/env python3
"""
Worker Memory MCP Server
Manages context memory for worker {config.worker_id}
"""

import json
import os
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("Worker Memory - {config.worker_id}")
memory_dir = Path("{config.memory_dir}")

@mcp.tool()
def save_context(key: str, data: dict) -> str:
    """Save context data to memory."""
    memory_file = memory_dir / f"{{key}}.json"
    with open(memory_file, "w") as f:
        json.dump(data, f, indent=2)
    return f"Context saved to {{key}}"

@mcp.tool()
def load_context(key: str) -> dict:
    """Load context data from memory."""
    memory_file = memory_dir / f"{{key}}.json"
    if memory_file.exists():
        with open(memory_file) as f:
            return json.load(f)
    return {{}}

@mcp.tool()
def list_contexts() -> list:
    """List available context keys."""
    return [f.stem for f in memory_dir.glob("*.json")]

if __name__ == "__main__":
    mcp.run()
'''

        memory_server_path = config.config_dir / "memory_server.py"
        with open(memory_server_path, "w") as f:
            f.write(memory_server_code)
        os.chmod(memory_server_path, 0o755)

        # Communication server
        comm_server_code = f'''#!/usr/bin/env python3
"""
Worker Communication MCP Server
Handles communication with master for worker {config.worker_id}
"""

import json
import time
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("Worker Communication - {config.worker_id}")
worker_id = "{config.worker_id}"
comm_dir = Path("/tmp/multibot/communication")
worker_outbox = comm_dir / "workers" / worker_id / "outbox"
worker_inbox = comm_dir / "workers" / worker_id / "inbox"

@mcp.tool()
def send_to_master(message_type: str, content: dict) -> str:
    """Send message to master."""
    message = {{
        "worker_id": worker_id,
        "type": message_type,
        "content": content,
        "timestamp": time.time()
    }}

    message_file = worker_outbox / f"{{int(time.time() * 1000)}}.json"
    worker_outbox.mkdir(parents=True, exist_ok=True)

    with open(message_file, "w") as f:
        json.dump(message, f, indent=2)

    return f"Message sent to master: {{message_type}}"

@mcp.tool()
def ask_master_question(question: str, context: dict = None) -> str:
    """Ask a question to the master."""
    return send_to_master("question", {{
        "question": question,
        "context": context or {{}}
    }})

@mcp.tool()
def report_progress(task_id: str, status: str, details: dict = None) -> str:
    """Report task progress to master."""
    return send_to_master("progress", {{
        "task_id": task_id,
        "status": status,
        "details": details or {{}}
    }})

@mcp.tool()
def check_messages() -> list:
    """Check for messages from master."""
    messages = []
    if worker_inbox.exists():
        for msg_file in worker_inbox.glob("*.json"):
            try:
                with open(msg_file) as f:
                    message = json.load(f)
                messages.append(message)
                # Move to processed
                processed_dir = worker_inbox.parent / "processed"
                processed_dir.mkdir(exist_ok=True)
                msg_file.rename(processed_dir / msg_file.name)
            except Exception as e:
                print(f"Error processing message {{msg_file}}: {{e}}")
    return messages

if __name__ == "__main__":
    mcp.run()
'''

        comm_server_path = config.config_dir / "communication_server.py"
        with open(comm_server_path, "w") as f:
            f.write(comm_server_code)
        os.chmod(comm_server_path, 0o755)

    async def _initialize_worker_memory(self, config: WorkerConfig):
        """Initialize worker memory with initial context."""
        initial_memory = {
            "worker_info": {
                "worker_id": config.worker_id,
                "model": config.model,
                "task_name": config.task_name,
                "branch": config.branch_name,
                "created_at": datetime.now().isoformat(),
                "working_directory": str(config.worktree_dir)
            },
            "task_history": [],
            "learned_concepts": [],
            "important_files": [],
            "decisions_made": [],
            "blockers_encountered": []
        }

        memory_file = config.memory_dir / "worker_state.json"
        with open(memory_file, "w") as f:
            json.dump(initial_memory, f, indent=2)

    async def _launch_claude_process(self, config: WorkerConfig) -> WorkerProcess:
        """Launch Claude Code process for worker."""

        # Prepare environment
        env = os.environ.copy()
        env.update({
            "WORKER_ID": config.worker_id,
            "WORKER_MODEL": config.model,
            "WORKER_BRANCH": config.branch_name,
            "MULTIBOT_ROLE": "worker"
        })

        # Use the worker launch script for proper process management
        launch_script = Path(__file__).parent / "launch_worker.py"
        launch_cmd = [
            "python3", str(launch_script),
            "--worker-id", config.worker_id,
            "--config", str(config.config_dir / "claude_config.json"),
            "--working-dir", str(config.worktree_dir),
            "--memory-dir", str(config.memory_dir),
            "--logs-dir", str(config.logs_dir)
        ]

        # For WSL environment, wrap with WSL command
        if os.name == 'nt':  # Windows
            full_cmd = [
                "wsl.exe", "bash", "-c",
                f"cd {config.worktree_dir} && {' '.join(launch_cmd)}"
            ]
        else:  # Linux/macOS
            full_cmd = launch_cmd

        try:
            # Start process
            process = await asyncio.create_subprocess_exec(
                *full_cmd,
                cwd=config.worktree_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE
            )

            worker_process = WorkerProcess(
                config=config,
                process=process,
                pid=process.pid,
                start_time=datetime.now(),
                status="starting"
            )

            # Wait for initialization
            await self._wait_for_worker_initialization(worker_process)

            logger.info(f"Claude process launched for worker {config.worker_id} (PID: {process.pid})")
            return worker_process

        except Exception as e:
            logger.error(f"Failed to launch Claude process for {config.worker_id}: {str(e)}")
            raise

    async def _setup_terminal_visualization(self, worker_process: WorkerProcess):
        """Set up terminal visualization for worker."""
        try:
            # Create terminal session using the terminal manager
            terminal_session = await self.terminal_manager.create_worker_terminal(
                worker_id=worker_process.config.worker_id,
                working_dir=worker_process.config.worktree_dir,
                title=f"Worker-{worker_process.config.worker_id}-{worker_process.config.task_name}",
                command=None  # The worker launch script will handle the command
            )

            logger.info(f"Created terminal session for worker {worker_process.config.worker_id}")
            return terminal_session

        except Exception as e:
            logger.warning(f"Failed to setup terminal visualization for {worker_process.config.worker_id}: {str(e)}")
            return None

    async def _create_tmux_session(self, worker_process: WorkerProcess):
        """Create tmux session for worker."""
        session_name = f"{self.tmux_session_prefix}-{worker_process.config.worker_id}"

        # Create tmux session
        cmd = [
            "tmux", "new-session", "-d", "-s", session_name,
            "-c", str(worker_process.config.worktree_dir)
        ]

        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        await result.communicate()

        if result.returncode == 0:
            worker_process.tmux_session = session_name

            # Set up window title and status
            await self._configure_tmux_session(worker_process)

            logger.info(f"Created tmux session {session_name} for worker {worker_process.config.worker_id}")
        else:
            logger.warning(f"Failed to create tmux session for worker {worker_process.config.worker_id}")

    async def _configure_tmux_session(self, worker_process: WorkerProcess):
        """Configure tmux session with status and monitoring."""
        session_name = worker_process.tmux_session
        worker_id = worker_process.config.worker_id

        commands = [
            # Set window title
            ["tmux", "rename-window", "-t", session_name, f"Worker-{worker_id}"],

            # Set status line
            ["tmux", "set-option", "-t", session_name, "status-left",
             f"[{worker_id}] "],

            # Create monitoring pane
            ["tmux", "split-window", "-t", session_name, "-v", "-p", "30"],

            # Start worker monitoring in bottom pane
            ["tmux", "send-keys", "-t", f"{session_name}:0.1",
             f"watch -n 2 'echo \"Worker: {worker_id}\"; echo \"Status: {worker_process.status}\"; echo \"Task: {worker_process.current_task or 'None'}\"; echo \"Branch: {worker_process.config.branch_name}\"'",
             "Enter"]
        ]

        for cmd in commands:
            try:
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await result.communicate()
            except Exception as e:
                logger.debug(f"Tmux command failed: {' '.join(cmd)} - {str(e)}")

    async def _create_basic_terminal(self, worker_process: WorkerProcess):
        """Create basic terminal for worker (fallback)."""
        worker_id = worker_process.config.worker_id

        try:
            if os.name == 'nt':  # Windows
                cmd = [
                    "wt", "new-tab", "--title", f"Worker-{worker_id}",
                    "--profile", "Command Prompt",
                    "--startingDirectory", str(worker_process.config.worktree_dir)
                ]
            else:  # Linux/macOS
                cmd = [
                    "gnome-terminal", "--title", f"Worker-{worker_id}",
                    "--working-directory", str(worker_process.config.worktree_dir),
                    "--", "bash"
                ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )

            worker_process.tmux_session = f"basic-terminal-{worker_id}"

        except Exception as e:
            logger.warning(f"Failed to create basic terminal for {worker_id}: {str(e)}")

    async def _wait_for_worker_initialization(self, worker_process: WorkerProcess, timeout: int = 60):
        """Wait for worker to initialize properly."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if process is still alive
            if worker_process.process.returncode is not None:
                raise Exception(f"Worker process {worker_process.config.worker_id} died during initialization")

            # Check for initialization signal (heartbeat file)
            heartbeat_file = worker_process.config.memory_dir / "heartbeat.json"
            if heartbeat_file.exists():
                try:
                    with open(heartbeat_file) as f:
                        heartbeat = json.load(f)

                    if heartbeat.get("status") == "ready":
                        worker_process.status = "active"
                        worker_process.last_activity = datetime.now()
                        return

                except (json.JSONDecodeError, KeyError):
                    pass

            await asyncio.sleep(2)

        # Timeout reached
        worker_process.status = "initialization_timeout"
        raise Exception(f"Worker {worker_process.config.worker_id} failed to initialize within {timeout} seconds")

    async def _save_worker_state(self, worker_process: WorkerProcess):
        """Save worker state to disk."""
        state_data = {
            "config": worker_process.config.to_dict(),
            "pid": worker_process.pid,
            "tmux_session": worker_process.tmux_session,
            "start_time": worker_process.start_time.isoformat() if worker_process.start_time else None,
            "status": worker_process.status,
            "current_task": worker_process.current_task,
            "last_activity": worker_process.last_activity.isoformat() if worker_process.last_activity else None,
            "memory_state": worker_process.memory_state,
            "saved_at": datetime.now().isoformat()
        }

        state_file = worker_process.config.working_dir / "worker_state.json"
        with open(state_file, "w") as f:
            json.dump(state_data, f, indent=2)

    async def _save_worker_final_state(self, worker_process: WorkerProcess):
        """Save worker's final state before termination."""
        # Enhanced final state with more details
        final_state = {
            "worker_id": worker_process.config.worker_id,
            "termination_time": datetime.now().isoformat(),
            "total_runtime": (datetime.now() - worker_process.start_time).total_seconds() if worker_process.start_time else None,
            "final_status": worker_process.status,
            "last_task": worker_process.current_task,
            "memory_state": worker_process.memory_state,
            "branch": worker_process.config.branch_name,
            "model_used": worker_process.config.model
        }

        # Save to both worker directory and central archive
        final_state_file = worker_process.config.working_dir / "final_state.json"
        with open(final_state_file, "w") as f:
            json.dump(final_state, f, indent=2)

        # Archive copy
        archive_dir = Path("/tmp/multibot/worker_archives")
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_file = archive_dir / f"{worker_process.config.worker_id}_final_state.json"
        with open(archive_file, "w") as f:
            json.dump(final_state, f, indent=2)

    async def _commit_worker_changes(self, worker_process: WorkerProcess) -> Optional[str]:
        """Commit worker's changes and return commit hash."""
        try:
            worktree_dir = worker_process.config.worktree_dir

            # Check for changes
            status_result = await self._run_git_command_in_dir(
                ["status", "--porcelain"], worktree_dir
            )

            if not status_result.strip():
                logger.info(f"No changes to commit for worker {worker_process.config.worker_id}")
                return None

            # Add all changes
            await self._run_git_command_in_dir(["add", "."], worktree_dir)

            # Commit with detailed message
            commit_message = f"""Worker {worker_process.config.worker_id} final commit

Task: {worker_process.config.task_name}
Model: {worker_process.config.model}
Duration: {(datetime.now() - worker_process.start_time).total_seconds():.0f}s
Last Task: {worker_process.current_task or 'None'}

Auto-committed by multibot orchestrator
"""

            await self._run_git_command_in_dir(
                ["commit", "-m", commit_message], worktree_dir
            )

            # Get commit hash
            commit_hash = await self._run_git_command_in_dir(
                ["rev-parse", "HEAD"], worktree_dir
            )

            logger.info(f"Committed changes for worker {worker_process.config.worker_id}: {commit_hash[:8]}")
            return commit_hash.strip()

        except Exception as e:
            logger.error(f"Failed to commit changes for worker {worker_process.config.worker_id}: {str(e)}")
            return None

    async def _shutdown_claude_process(self, worker_process: WorkerProcess):
        """Gracefully shutdown Claude Code process."""
        if not worker_process.process:
            return

        try:
            # Send graceful termination signal
            worker_process.process.terminate()

            # Wait for graceful shutdown
            try:
                await asyncio.wait_for(worker_process.process.wait(), timeout=10.0)
                logger.info(f"Worker {worker_process.config.worker_id} process terminated gracefully")
            except asyncio.TimeoutError:
                # Force kill if graceful shutdown fails
                worker_process.process.kill()
                await worker_process.process.wait()
                logger.warning(f"Worker {worker_process.config.worker_id} process force killed")

        except Exception as e:
            logger.error(f"Error shutting down worker {worker_process.config.worker_id} process: {str(e)}")

    async def _archive_worker_logs(self, worker_process: WorkerProcess):
        """Archive worker logs."""
        try:
            logs_dir = worker_process.config.logs_dir
            archive_dir = Path("/tmp/multibot/worker_archives") / worker_process.config.worker_id
            archive_dir.mkdir(parents=True, exist_ok=True)

            # Copy logs to archive
            if logs_dir.exists():
                shutil.copytree(logs_dir, archive_dir / "logs", dirs_exist_ok=True)

            # Copy memory state
            memory_dir = worker_process.config.memory_dir
            if memory_dir.exists():
                shutil.copytree(memory_dir, archive_dir / "memory", dirs_exist_ok=True)

            logger.info(f"Archived logs for worker {worker_process.config.worker_id}")

        except Exception as e:
            logger.error(f"Failed to archive logs for worker {worker_process.config.worker_id}: {str(e)}")

    async def _cleanup_terminal_visualization(self, worker_process: WorkerProcess):
        """Clean up terminal visualization."""
        try:
            # Use terminal manager to clean up
            await self.terminal_manager.destroy_terminal(worker_process.config.worker_id)
            logger.debug(f"Cleaned up terminal for worker {worker_process.config.worker_id}")

        except Exception as e:
            logger.warning(f"Failed to cleanup terminal: {str(e)}")

    async def _cleanup_worker_worktree(self, worker_process: WorkerProcess):
        """Clean up worker's Git worktree."""
        try:
            # Remove worktree
            await self._run_git_command([
                "worktree", "remove", str(worker_process.config.worktree_dir), "--force"
            ])

            # Delete branch (optional - keep for history)
            # await self._run_git_command([
            #     "branch", "-D", worker_process.config.branch_name
            # ])

            logger.info(f"Cleaned up worktree for worker {worker_process.config.worker_id}")

        except Exception as e:
            logger.error(f"Failed to cleanup worktree for worker {worker_process.config.worker_id}: {str(e)}")

    async def _force_cleanup_worker(self, worker_process: WorkerProcess):
        """Force cleanup of worker resources."""
        logger.warning(f"Force cleaning up worker {worker_process.config.worker_id}")

        try:
            # Kill process if still running
            if worker_process.process and worker_process.pid:
                try:
                    os.kill(worker_process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

            # Remove terminal
            await self._cleanup_terminal_visualization(worker_process)

            # Force remove worktree
            if worker_process.config.worktree_dir.exists():
                shutil.rmtree(worker_process.config.worktree_dir, ignore_errors=True)

            # Remove from active workers if still there
            if worker_process.config.worker_id in self.active_workers:
                del self.active_workers[worker_process.config.worker_id]

        except Exception as e:
            logger.error(f"Error in force cleanup: {str(e)}")

    async def _cleanup_failed_worker(self, worker_id: str):
        """Cleanup resources for a failed worker spawn."""
        worker_dir = self.workers_dir / worker_id
        if worker_dir.exists():
            shutil.rmtree(worker_dir, ignore_errors=True)

    # Utility methods

    async def _check_tmux_available(self) -> bool:
        """Check if tmux is available."""
        try:
            result = await asyncio.create_subprocess_exec(
                "tmux", "-V",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await result.communicate()
            return result.returncode == 0
        except FileNotFoundError:
            return False

    async def _run_git_command(self, args: List[str], cwd: Optional[Path] = None) -> str:
        """Run a Git command."""
        cmd = ["git"] + args
        work_dir = cwd or Path.cwd()

        result = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=work_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, stderr=stderr.decode()
            )

        return stdout.decode().strip()

    async def _run_git_command_in_dir(self, args: List[str], directory: Path) -> str:
        """Run Git command in specific directory."""
        return await self._run_git_command(args, directory)

    async def _update_worker_status(self, worker_process: WorkerProcess):
        """Update worker process status."""
        if worker_process.process:
            returncode = worker_process.process.returncode
            if returncode is not None:
                worker_process.status = "dead" if returncode != 0 else "completed"
            elif worker_process.status not in ["paused"]:
                worker_process.status = "active"

    async def _get_worker_resource_usage(self, worker_process: WorkerProcess) -> Dict[str, Any]:
        """Get worker resource usage."""
        try:
            import psutil

            if worker_process.pid:
                try:
                    process = psutil.Process(worker_process.pid)
                    return {
                        "cpu_percent": process.cpu_percent(),
                        "memory_mb": process.memory_info().rss / 1024 / 1024,
                        "memory_percent": process.memory_percent(),
                        "num_threads": process.num_threads(),
                        "status": process.status()
                    }
                except psutil.NoSuchProcess:
                    return {"status": "process_not_found"}

        except ImportError:
            pass

        return {"status": "unavailable"}

    async def _get_worker_recent_activity(self, worker_process: WorkerProcess) -> List[Dict[str, Any]]:
        """Get worker's recent activity."""
        activity_file = worker_process.config.logs_dir / "activity.log"

        if activity_file.exists():
            try:
                with open(activity_file) as f:
                    lines = f.readlines()

                # Return last 10 lines
                recent_lines = lines[-10:] if len(lines) > 10 else lines

                return [
                    {
                        "timestamp": line.split(" ", 2)[0] if " " in line else "",
                        "activity": line.strip()
                    }
                    for line in recent_lines if line.strip()
                ]

            except Exception as e:
                logger.debug(f"Failed to read activity log: {str(e)}")

        return []

    async def _update_terminal_status(self, worker_process: WorkerProcess):
        """Update terminal status display."""
        try:
            # Prepare task information
            task_info = None
            if worker_process.current_task:
                task_info = {
                    "task_id": worker_process.current_task,
                    "status": worker_process.status
                }

            # Use terminal manager to update status
            await self.terminal_manager.update_terminal_status(
                worker_process.config.worker_id,
                worker_process.status,
                task_info
            )

        except Exception as e:
            logger.debug(f"Failed to update terminal status: {str(e)}")

    async def _monitor_workers(self):
        """Monitor all active workers."""
        while self._running:
            try:
                for worker_id in list(self.active_workers.keys()):
                    worker_process = self.active_workers[worker_id]
                    await self._update_worker_status(worker_process)

                    # Check for dead workers
                    if worker_process.status == "dead":
                        logger.warning(f"Worker {worker_id} has died unexpectedly")
                        # Could implement auto-restart logic here

                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Error in worker monitoring: {str(e)}")
                await asyncio.sleep(30)

    async def _recover_existing_workers(self):
        """Recover existing workers from previous runs."""
        if not self.workers_dir.exists():
            return

        for worker_dir in self.workers_dir.iterdir():
            if worker_dir.is_dir():
                state_file = worker_dir / "worker_state.json"
                if state_file.exists():
                    try:
                        with open(state_file) as f:
                            state_data = json.load(f)

                        worker_id = state_data["config"]["worker_id"]

                        # Check if process is still alive
                        pid = state_data.get("pid")
                        if pid:
                            try:
                                os.kill(pid, 0)  # Check if process exists
                                logger.info(f"Recovered running worker {worker_id} (PID: {pid})")
                                # Could restore worker_process object here
                            except ProcessLookupError:
                                logger.info(f"Found dead worker {worker_id}, cleaning up")
                                # Clean up dead worker

                    except Exception as e:
                        logger.error(f"Failed to recover worker from {worker_dir}: {str(e)}")

    async def cleanup(self):
        """Cleanup lifecycle manager resources."""
        logger.info("Cleaning up Worker Lifecycle Manager")

        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Terminate all active workers
        for worker_id in list(self.active_workers.keys()):
            try:
                await self.terminate_worker(worker_id, save_state=True, commit_changes=True)
            except Exception as e:
                logger.error(f"Error terminating worker {worker_id} during cleanup: {str(e)}")

        # Cleanup terminal manager
        await self.terminal_manager.cleanup()

        logger.info("Worker Lifecycle Manager cleanup completed")