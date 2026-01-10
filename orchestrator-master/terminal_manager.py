"""
Enhanced Terminal Management
Provides comprehensive terminal visualization and management for worker processes.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import shlex

logger = logging.getLogger(__name__)


class TerminalSession:
    """Represents a terminal session for a worker."""

    def __init__(self, worker_id: str, session_type: str = "tmux"):
        self.worker_id = worker_id
        self.session_type = session_type
        self.session_id: Optional[str] = None
        self.window_id: Optional[str] = None
        self.process_id: Optional[int] = None
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.status = "initializing"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "worker_id": self.worker_id,
            "session_type": self.session_type,
            "session_id": self.session_id,
            "window_id": self.window_id,
            "process_id": self.process_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "status": self.status
        }


class TerminalManager:
    """Enhanced terminal management for worker visualization."""

    def __init__(self):
        self.active_sessions: Dict[str, TerminalSession] = {}
        self.tmux_available = False
        self.screen_available = False
        self.session_prefix = "multibot-worker"

        # Terminal configurations
        self.tmux_config = {
            "status-bg": "black",
            "status-fg": "green",
            "pane-border-style": "fg=white",
            "pane-active-border-style": "fg=green",
            "window-status-current-style": "fg=black,bg=green"
        }

    async def initialize(self):
        """Initialize terminal manager."""
        logger.info("Initializing Terminal Manager")

        # Check available terminal multiplexers
        self.tmux_available = await self._check_command_available("tmux")
        self.screen_available = await self._check_command_available("screen")

        if self.tmux_available:
            logger.info("tmux detected - using tmux for terminal management")
            await self._setup_tmux_environment()
        elif self.screen_available:
            logger.info("screen detected - using screen for terminal management")
        else:
            logger.warning("No terminal multiplexer detected - using basic terminal support")

        logger.info("Terminal Manager initialized")

    async def create_worker_terminal(
        self,
        worker_id: str,
        working_dir: Path,
        title: str = None,
        command: List[str] = None
    ) -> TerminalSession:
        """Create a new terminal session for a worker."""
        if worker_id in self.active_sessions:
            raise ValueError(f"Terminal session for worker {worker_id} already exists")

        logger.info(f"Creating terminal session for worker {worker_id}")

        if not title:
            title = f"Worker-{worker_id}"

        try:
            if self.tmux_available:
                session = await self._create_tmux_session(worker_id, working_dir, title, command)
            elif self.screen_available:
                session = await self._create_screen_session(worker_id, working_dir, title, command)
            else:
                session = await self._create_basic_terminal(worker_id, working_dir, title, command)

            self.active_sessions[worker_id] = session
            logger.info(f"Created terminal session {session.session_id} for worker {worker_id}")

            return session

        except Exception as e:
            logger.error(f"Failed to create terminal for worker {worker_id}: {str(e)}")
            raise

    async def update_terminal_status(
        self,
        worker_id: str,
        status: str,
        task_info: Optional[Dict[str, Any]] = None
    ):
        """Update terminal status display."""
        if worker_id not in self.active_sessions:
            logger.warning(f"No terminal session found for worker {worker_id}")
            return

        session = self.active_sessions[worker_id]
        session.status = status
        session.last_activity = datetime.now()

        try:
            if session.session_type == "tmux":
                await self._update_tmux_status(session, status, task_info)
            elif session.session_type == "screen":
                await self._update_screen_status(session, status, task_info)

        except Exception as e:
            logger.warning(f"Failed to update terminal status for {worker_id}: {str(e)}")

    async def send_to_terminal(self, worker_id: str, text: str):
        """Send text to worker terminal."""
        if worker_id not in self.active_sessions:
            logger.warning(f"No terminal session found for worker {worker_id}")
            return

        session = self.active_sessions[worker_id]

        try:
            if session.session_type == "tmux":
                await self._send_to_tmux_session(session, text)
            elif session.session_type == "screen":
                await self._send_to_screen_session(session, text)

        except Exception as e:
            logger.error(f"Failed to send text to terminal {worker_id}: {str(e)}")

    async def capture_terminal_output(self, worker_id: str) -> str:
        """Capture current terminal output."""
        if worker_id not in self.active_sessions:
            return ""

        session = self.active_sessions[worker_id]

        try:
            if session.session_type == "tmux":
                return await self._capture_tmux_output(session)
            elif session.session_type == "screen":
                return await self._capture_screen_output(session)

        except Exception as e:
            logger.error(f"Failed to capture terminal output for {worker_id}: {str(e)}")
            return ""

        return ""

    async def destroy_terminal(self, worker_id: str):
        """Destroy terminal session for worker."""
        if worker_id not in self.active_sessions:
            logger.warning(f"No terminal session found for worker {worker_id}")
            return

        session = self.active_sessions[worker_id]
        logger.info(f"Destroying terminal session for worker {worker_id}")

        try:
            if session.session_type == "tmux":
                await self._destroy_tmux_session(session)
            elif session.session_type == "screen":
                await self._destroy_screen_session(session)

            del self.active_sessions[worker_id]

        except Exception as e:
            logger.error(f"Failed to destroy terminal for {worker_id}: {str(e)}")

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active terminal sessions."""
        sessions = []

        for worker_id, session in self.active_sessions.items():
            session_info = session.to_dict()

            # Add current session info
            if session.session_type == "tmux" and session.session_id:
                session_info["tmux_info"] = await self._get_tmux_session_info(session.session_id)

            sessions.append(session_info)

        return sessions

    async def focus_terminal(self, worker_id: str):
        """Focus/bring to front the worker's terminal."""
        if worker_id not in self.active_sessions:
            logger.warning(f"No terminal session found for worker {worker_id}")
            return

        session = self.active_sessions[worker_id]

        try:
            if session.session_type == "tmux":
                await self._focus_tmux_session(session)
            elif session.session_type == "screen":
                await self._focus_screen_session(session)

        except Exception as e:
            logger.warning(f"Failed to focus terminal for {worker_id}: {str(e)}")

    # tmux implementation methods

    async def _create_tmux_session(
        self,
        worker_id: str,
        working_dir: Path,
        title: str,
        command: Optional[List[str]] = None
    ) -> TerminalSession:
        """Create tmux session for worker."""
        session_name = f"{self.session_prefix}-{worker_id}"

        # Create tmux session
        cmd = [
            "tmux", "new-session", "-d", "-s", session_name,
            "-c", str(working_dir),
            "-x", "120", "-y", "30"  # Set initial size
        ]

        if command:
            cmd.extend(command)

        result = await self._run_command(cmd)

        if result.returncode != 0:
            raise Exception(f"Failed to create tmux session: {result.stderr}")

        session = TerminalSession(worker_id, "tmux")
        session.session_id = session_name
        session.status = "active"

        # Configure tmux session
        await self._configure_tmux_session(session, title)

        return session

    async def _configure_tmux_session(self, session: TerminalSession, title: str):
        """Configure tmux session with worker-specific settings."""
        session_name = session.session_id

        # Set window title
        await self._run_command([
            "tmux", "rename-window", "-t", session_name, title
        ])

        # Apply configuration
        for option, value in self.tmux_config.items():
            await self._run_command([
                "tmux", "set-option", "-t", session_name, option, value
            ])

        # Set up status line
        status_left = f"#{session.worker_id} [%s]"
        await self._run_command([
            "tmux", "set-option", "-t", session_name, "status-left", status_left
        ])

        # Create monitoring pane (split bottom 25%)
        await self._run_command([
            "tmux", "split-window", "-t", session_name, "-v", "-p", "25"
        ])

        # Set up monitoring in bottom pane
        monitor_cmd = f"""
watch -n 2 '
echo "Worker: {session.worker_id}"
echo "Status: {session.status}"
echo "Created: {session.created_at.strftime("%H:%M:%S")}"
echo "Last Activity: {session.last_activity.strftime("%H:%M:%S")}"
echo "Session: {session.session_id}"
echo "---"
if [ -f /workspace/workers/{session.worker_id}/memory/heartbeat.json ]; then
    echo "Heartbeat:"
    cat /workspace/workers/{session.worker_id}/memory/heartbeat.json | jq -r "(.timestamp | strftime(\"%H:%M:%S\")) + \" - \" + .status"
fi
'
        """

        await self._run_command([
            "tmux", "send-keys", "-t", f"{session_name}:0.1",
            monitor_cmd, "Enter"
        ])

        # Focus main pane
        await self._run_command([
            "tmux", "select-pane", "-t", f"{session_name}:0.0"
        ])

    async def _update_tmux_status(
        self,
        session: TerminalSession,
        status: str,
        task_info: Optional[Dict[str, Any]] = None
    ):
        """Update tmux session status."""
        session_name = session.session_id

        # Update status in title
        title_text = f"Worker-{session.worker_id} [{status.upper()}]"
        if task_info and task_info.get("task_id"):
            title_text += f" - Task: {task_info['task_id']}"

        await self._run_command([
            "tmux", "rename-window", "-t", session_name, title_text
        ])

        # Update status line
        status_text = f"[{session.worker_id}] {status} | {datetime.now().strftime('%H:%M:%S')}"
        await self._run_command([
            "tmux", "set-option", "-t", session_name, "status-right", status_text
        ])

    async def _send_to_tmux_session(self, session: TerminalSession, text: str):
        """Send text to tmux session."""
        session_name = session.session_id

        # Send to main pane (0.0)
        await self._run_command([
            "tmux", "send-keys", "-t", f"{session_name}:0.0", text
        ])

    async def _capture_tmux_output(self, session: TerminalSession) -> str:
        """Capture tmux session output."""
        session_name = session.session_id

        result = await self._run_command([
            "tmux", "capture-pane", "-t", f"{session_name}:0.0", "-p"
        ])

        if result.returncode == 0:
            return result.stdout
        else:
            return ""

    async def _destroy_tmux_session(self, session: TerminalSession):
        """Destroy tmux session."""
        session_name = session.session_id

        await self._run_command([
            "tmux", "kill-session", "-t", session_name
        ])

    async def _focus_tmux_session(self, session: TerminalSession):
        """Focus tmux session."""
        session_name = session.session_id

        # Try to attach if in terminal environment
        try:
            # Check if we're in a tmux session
            current_session = os.environ.get("TMUX_PANE")
            if current_session:
                # Switch to session
                await self._run_command([
                    "tmux", "switch-client", "-t", session_name
                ])
            else:
                # Open new terminal with tmux attach
                if os.name == 'nt':  # Windows
                    await self._run_command([
                        "wt", "new-tab", "--title", f"Worker-{session.worker_id}",
                        "bash", "-c", f"tmux attach-session -t {session_name}"
                    ])
                else:  # Linux/macOS
                    await self._run_command([
                        "gnome-terminal", "--title", f"Worker-{session.worker_id}",
                        "--", "tmux", "attach-session", "-t", session_name
                    ])

        except Exception as e:
            logger.warning(f"Could not focus tmux session: {str(e)}")

    async def _get_tmux_session_info(self, session_name: str) -> Dict[str, Any]:
        """Get tmux session information."""
        try:
            result = await self._run_command([
                "tmux", "list-sessions", "-F", "#{session_name},#{session_windows},#{session_created}"
            ])

            for line in result.stdout.split('\n'):
                if line.startswith(session_name):
                    parts = line.split(',')
                    return {
                        "name": parts[0],
                        "windows": int(parts[1]) if len(parts) > 1 else 0,
                        "created": parts[2] if len(parts) > 2 else ""
                    }

        except Exception as e:
            logger.debug(f"Failed to get tmux session info: {str(e)}")

        return {}

    # screen implementation methods

    async def _create_screen_session(
        self,
        worker_id: str,
        working_dir: Path,
        title: str,
        command: Optional[List[str]] = None
    ) -> TerminalSession:
        """Create screen session for worker."""
        session_name = f"{self.session_prefix}-{worker_id}"

        cmd = [
            "screen", "-dmS", session_name,
            "-c", str(working_dir)
        ]

        if command:
            cmd.extend(command)

        result = await self._run_command(cmd)

        if result.returncode != 0:
            raise Exception(f"Failed to create screen session: {result.stderr}")

        session = TerminalSession(worker_id, "screen")
        session.session_id = session_name
        session.status = "active"

        return session

    async def _update_screen_status(
        self,
        session: TerminalSession,
        status: str,
        task_info: Optional[Dict[str, Any]] = None
    ):
        """Update screen session status."""
        # Screen has limited status update capabilities
        pass

    async def _send_to_screen_session(self, session: TerminalSession, text: str):
        """Send text to screen session."""
        session_name = session.session_id

        await self._run_command([
            "screen", "-S", session_name, "-X", "stuff", text + "\n"
        ])

    async def _capture_screen_output(self, session: TerminalSession) -> str:
        """Capture screen session output."""
        # Screen output capture is more limited
        return ""

    async def _destroy_screen_session(self, session: TerminalSession):
        """Destroy screen session."""
        session_name = session.session_id

        await self._run_command([
            "screen", "-S", session_name, "-X", "quit"
        ])

    async def _focus_screen_session(self, session: TerminalSession):
        """Focus screen session."""
        session_name = session.session_id

        try:
            if os.name == 'nt':  # Windows
                await self._run_command([
                    "wt", "new-tab", "--title", f"Worker-{session.worker_id}",
                    "bash", "-c", f"screen -r {session_name}"
                ])
            else:  # Linux/macOS
                await self._run_command([
                    "gnome-terminal", "--title", f"Worker-{session.worker_id}",
                    "--", "screen", "-r", session_name
                ])

        except Exception as e:
            logger.warning(f"Could not focus screen session: {str(e)}")

    # Basic terminal implementation

    async def _create_basic_terminal(
        self,
        worker_id: str,
        working_dir: Path,
        title: str,
        command: Optional[List[str]] = None
    ) -> TerminalSession:
        """Create basic terminal for worker."""
        try:
            if os.name == 'nt':  # Windows
                cmd = [
                    "wt", "new-tab", "--title", title,
                    "--startingDirectory", str(working_dir)
                ]

                if command:
                    cmd.extend(["--", "bash", "-c", shlex.join(command)])

            else:  # Linux/macOS
                cmd = [
                    "gnome-terminal", "--title", title,
                    "--working-directory", str(working_dir)
                ]

                if command:
                    cmd.extend(["--", "bash", "-c", shlex.join(command)])

            result = await self._run_command(cmd)

            session = TerminalSession(worker_id, "basic")
            session.session_id = f"basic-{worker_id}"
            session.status = "active"

            return session

        except Exception as e:
            logger.error(f"Failed to create basic terminal: {str(e)}")
            raise

    # Utility methods

    async def _check_command_available(self, command: str) -> bool:
        """Check if a command is available."""
        try:
            result = await self._run_command([command, "--version"])
            return result.returncode == 0
        except FileNotFoundError:
            return False

    async def _run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run a command asynchronously."""
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()

            return subprocess.CompletedProcess(
                cmd, result.returncode,
                stdout=stdout.decode() if stdout else "",
                stderr=stderr.decode() if stderr else ""
            )

        except Exception as e:
            logger.debug(f"Command failed: {' '.join(cmd)} - {str(e)}")
            return subprocess.CompletedProcess(
                cmd, 1, "", str(e)
            )

    async def _setup_tmux_environment(self):
        """Set up tmux environment and global settings."""
        try:
            # Set global tmux options
            global_options = {
                "mouse": "on",
                "history-limit": "10000",
                "default-terminal": "screen-256color",
                "escape-time": "0"
            }

            for option, value in global_options.items():
                await self._run_command([
                    "tmux", "set-option", "-g", option, value
                ])

        except Exception as e:
            logger.warning(f"Failed to setup tmux environment: {str(e)}")

    async def cleanup(self):
        """Cleanup all terminal sessions."""
        logger.info("Cleaning up terminal sessions")

        for worker_id in list(self.active_sessions.keys()):
            try:
                await self.destroy_terminal(worker_id)
            except Exception as e:
                logger.error(f"Failed to cleanup terminal for {worker_id}: {str(e)}")

        logger.info("Terminal Manager cleanup completed")