#!/usr/bin/env python3
"""
Dashboard Integration Module
Connects the monitoring dashboard with the actual orchestrator system.
"""

import asyncio
import json
import logging
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import os

from monitoring_dashboard import MonitoringDashboard
from message_queue import MessageQueueManager
from worker_lifecycle import WorkerLifecycleManager

logger = logging.getLogger(__name__)


class DashboardDataProvider:
    """Provides real-time data to the monitoring dashboard."""

    def __init__(self, dashboard: MonitoringDashboard, orchestrator=None):
        self.dashboard = dashboard
        self.orchestrator = orchestrator
        self.message_queue = MessageQueueManager()
        self.worker_lifecycle = WorkerLifecycleManager() if not orchestrator else orchestrator.worker_lifecycle

        # Paths
        self.base_dir = Path("/tmp/multibot")
        self.workers_dir = self.base_dir / "workers"

        # Data tracking
        self.last_message_id = 0
        self.worker_logs = {}  # worker_id -> log lines
        self.worker_processes = {}  # worker_id -> process info

        # Update intervals
        self.fast_update_interval = 1.0  # seconds
        self.slow_update_interval = 5.0  # seconds

        self.running = True

    async def start(self):
        """Start the data provider."""
        logger.info("Starting dashboard data provider")

        # Start update tasks
        asyncio.create_task(self.fast_update_loop())
        asyncio.create_task(self.slow_update_loop())
        asyncio.create_task(self.message_monitor_loop())

    async def stop(self):
        """Stop the data provider."""
        self.running = False
        logger.info("Stopped dashboard data provider")

    async def fast_update_loop(self):
        """Fast update loop for real-time data."""
        while self.running:
            try:
                await self.update_worker_logs()
                await self.update_worker_status()
                await asyncio.sleep(self.fast_update_interval)
            except Exception as e:
                logger.error(f"Fast update loop error: {e}")
                await asyncio.sleep(1)

    async def slow_update_loop(self):
        """Slow update loop for less frequent data."""
        while self.running:
            try:
                await self.update_master_panel()
                await self.update_repository_status()
                await self.discover_workers()
                await asyncio.sleep(self.slow_update_interval)
            except Exception as e:
                logger.error(f"Slow update loop error: {e}")
                await asyncio.sleep(5)

    async def message_monitor_loop(self):
        """Monitor message queue for communication log."""
        while self.running:
            try:
                await self.check_new_messages()
                await asyncio.sleep(0.5)  # Check messages frequently
            except Exception as e:
                logger.error(f"Message monitor error: {e}")
                await asyncio.sleep(2)

    async def discover_workers(self):
        """Discover active workers and add them to dashboard."""
        try:
            # Get worker states
            if self.worker_lifecycle:
                worker_states = await self.worker_lifecycle.get_all_worker_states()

                for worker_id, state in worker_states.items():
                    if worker_id not in self.dashboard.workers:
                        # New worker discovered
                        worker_data = await self.get_worker_data(worker_id, state)
                        self.dashboard.root.after(0,
                            lambda wid=worker_id, data=worker_data:
                            self.dashboard.add_worker(wid, data)
                        )

                # Remove terminated workers
                for worker_id in list(self.dashboard.workers.keys()):
                    if worker_id not in worker_states:
                        self.dashboard.root.after(0,
                            lambda wid=worker_id:
                            self.dashboard.remove_worker(wid)
                        )

        except Exception as e:
            logger.error(f"Worker discovery error: {e}")

    async def get_worker_data(self, worker_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive worker data."""
        try:
            worker_dir = self.workers_dir / worker_id

            # Basic data from state
            worker_data = {
                "worker_id": worker_id,
                "model": state.get("model", "unknown"),
                "status": state.get("status", "unknown"),
                "task_title": "No task assigned",
                "progress": 0,
                "log_lines": [],
                "branch": "unknown"
            }

            # Get current task
            current_task = state.get("current_task")
            if current_task:
                worker_data["task_title"] = current_task.get("description", "Unknown task")
                worker_data["progress"] = current_task.get("progress", 0)

            # Get branch info
            if worker_dir.exists():
                try:
                    result = subprocess.run(
                        ["git", "branch", "--show-current"],
                        cwd=worker_dir,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        worker_data["branch"] = result.stdout.strip()
                except Exception:
                    pass

            # Get log lines
            log_lines = await self.get_worker_log_lines(worker_id)
            worker_data["log_lines"] = log_lines

            return worker_data

        except Exception as e:
            logger.error(f"Error getting worker data for {worker_id}: {e}")
            return {
                "worker_id": worker_id,
                "model": "unknown",
                "status": "error",
                "task_title": "Error loading data",
                "progress": 0,
                "log_lines": [f"Error: {str(e)}"],
                "branch": "unknown"
            }

    async def get_worker_log_lines(self, worker_id: str) -> List[str]:
        """Get log lines for a worker."""
        try:
            worker_dir = self.workers_dir / worker_id
            log_file = worker_dir / "logs" / "worker.log"

            if not log_file.exists():
                return ["Log file not found"]

            # Read last 100 lines
            with open(log_file, 'r') as f:
                lines = f.readlines()
                return [line.rstrip() for line in lines[-100:]]

        except Exception as e:
            logger.error(f"Error reading logs for {worker_id}: {e}")
            return [f"Error reading logs: {str(e)}"]

    async def update_worker_logs(self):
        """Update worker log displays."""
        for worker_id in self.dashboard.workers.keys():
            try:
                log_lines = await self.get_worker_log_lines(worker_id)

                # Check if logs have changed
                if worker_id not in self.worker_logs or self.worker_logs[worker_id] != log_lines:
                    self.worker_logs[worker_id] = log_lines

                    # Update dashboard
                    self.dashboard.root.after(0,
                        lambda wid=worker_id, lines=log_lines:
                        self.dashboard.update_worker_data(wid, {"log_lines": lines})
                    )

            except Exception as e:
                logger.error(f"Error updating logs for {worker_id}: {e}")

    async def update_worker_status(self):
        """Update worker status information."""
        if not self.worker_lifecycle:
            return

        try:
            worker_states = await self.worker_lifecycle.get_all_worker_states()

            for worker_id, state in worker_states.items():
                if worker_id in self.dashboard.workers:
                    worker_data = await self.get_worker_data(worker_id, state)

                    # Update dashboard
                    self.dashboard.root.after(0,
                        lambda wid=worker_id, data=worker_data:
                        self.dashboard.update_worker_data(wid, data)
                    )

        except Exception as e:
            logger.error(f"Error updating worker status: {e}")

    async def update_master_panel(self):
        """Update master control panel data."""
        try:
            # Get worker statistics
            worker_states = {}
            if self.worker_lifecycle:
                worker_states = await self.worker_lifecycle.get_all_worker_states()

            active_workers = len([s for s in worker_states.values()
                                if s.get("status") in ["active", "working"]])

            # Get task statistics
            task_stats = await self.get_task_statistics()

            # Get master activity
            master_activity = await self.get_master_activity()

            # Get repository status
            repo_status = await self.get_repository_status()

            master_data = {
                "active_workers": active_workers,
                "tasks_completed": task_stats.get("completed", 0),
                "tasks_in_progress": task_stats.get("in_progress", 0),
                "tasks_queued": task_stats.get("queued", 0),
                "current_activity": master_activity,
                "repository_status": repo_status
            }

            # Update dashboard
            self.dashboard.root.after(0,
                lambda data=master_data:
                self.dashboard.master_panel.update_data(data)
            )

        except Exception as e:
            logger.error(f"Error updating master panel: {e}")

    async def get_task_statistics(self) -> Dict[str, int]:
        """Get task statistics from database."""
        try:
            stats = await self.message_queue.get_task_stats()
            return stats
        except Exception as e:
            logger.error(f"Error getting task stats: {e}")
            return {"completed": 0, "in_progress": 0, "queued": 0}

    async def get_master_activity(self) -> str:
        """Get current master activity."""
        try:
            # This could be enhanced to track actual master activities
            return "Monitoring and coordinating workers"
        except Exception as e:
            logger.error(f"Error getting master activity: {e}")
            return "Unknown activity"

    async def get_repository_status(self) -> str:
        """Get repository status information."""
        try:
            # Get branch information
            result = subprocess.run(
                ["git", "branch", "-a"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                branches = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                local_branches = [b for b in branches if not b.startswith('remotes/')]
                return f"{len(local_branches)} active branches"
            else:
                return "Repository status unknown"

        except Exception as e:
            logger.error(f"Error getting repository status: {e}")
            return "Error getting repository status"

    async def update_repository_status(self):
        """Update repository status display."""
        try:
            repo_status = await self.get_repository_status()

            self.dashboard.root.after(0,
                lambda status=repo_status:
                self.dashboard.master_panel.update_data({"repository_status": status})
            )

        except Exception as e:
            logger.error(f"Error updating repository status: {e}")

    async def check_new_messages(self):
        """Check for new messages and update communication log."""
        try:
            # Get recent messages since last check
            messages = await self.message_queue.get_recent_messages(since_id=self.last_message_id)

            for message in messages:
                # Add to communication log
                timestamp = message.get("created_at", datetime.now().isoformat())
                from_id = message.get("from_id", "unknown")
                to_id = message.get("to_id", "unknown")
                message_type = message.get("message_type", "unknown")
                content = json.dumps(message.get("content", {}))

                self.dashboard.root.after(0,
                    lambda ts=timestamp, f=from_id, t=to_id, mt=message_type, c=content:
                    self.dashboard.comm_log.add_message(ts, f, t, mt, c)
                )

                # Update last message ID
                msg_id = message.get("id", 0)
                if isinstance(msg_id, str):
                    # If ID is string, use timestamp for ordering
                    self.last_message_id = max(self.last_message_id, hash(msg_id) % 1000000)
                else:
                    self.last_message_id = max(self.last_message_id, msg_id)

        except Exception as e:
            logger.error(f"Error checking new messages: {e}")

    # Worker action handlers
    async def pause_worker(self, worker_id: str):
        """Pause a worker."""
        try:
            if self.worker_lifecycle:
                await self.worker_lifecycle.pause_worker(worker_id)
                logger.info(f"Paused worker {worker_id}")
        except Exception as e:
            logger.error(f"Error pausing worker {worker_id}: {e}")

    async def resume_worker(self, worker_id: str):
        """Resume a worker."""
        try:
            if self.worker_lifecycle:
                await self.worker_lifecycle.resume_worker(worker_id)
                logger.info(f"Resumed worker {worker_id}")
        except Exception as e:
            logger.error(f"Error resuming worker {worker_id}: {e}")

    async def terminate_worker(self, worker_id: str):
        """Terminate a worker."""
        try:
            if self.worker_lifecycle:
                await self.worker_lifecycle.terminate_worker(
                    worker_id,
                    save_state=True,
                    commit_changes=True
                )
                logger.info(f"Terminated worker {worker_id}")
        except Exception as e:
            logger.error(f"Error terminating worker {worker_id}: {e}")

    async def send_message_to_worker(self, worker_id: str, message: str):
        """Send message to a worker."""
        try:
            await self.message_queue.send_message(
                from_id="dashboard",
                to_id=worker_id,
                message_type="guidance",
                content={"message": message},
                priority=5
            )
            logger.info(f"Sent message to worker {worker_id}: {message}")
        except Exception as e:
            logger.error(f"Error sending message to worker {worker_id}: {e}")

    async def spawn_new_worker(self, model: str, task_name: str, base_branch: str = "main") -> str:
        """Spawn a new worker."""
        try:
            if self.worker_lifecycle:
                worker_id = await self.worker_lifecycle.spawn_worker(
                    model=model,
                    task_name=task_name,
                    base_branch=base_branch
                )
                logger.info(f"Spawned new worker {worker_id}")
                return worker_id
        except Exception as e:
            logger.error(f"Error spawning worker: {e}")
            return ""

    def get_worker_memory_files(self, worker_id: str) -> List[Dict[str, Any]]:
        """Get worker's memory files."""
        try:
            worker_dir = self.workers_dir / worker_id
            memory_dir = worker_dir / "memory"

            if not memory_dir.exists():
                return []

            files = []
            for file_path in memory_dir.glob("*.json"):
                try:
                    stat = file_path.stat()
                    files.append({
                        "name": file_path.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "path": str(file_path)
                    })
                except Exception:
                    pass

            return sorted(files, key=lambda x: x["modified"], reverse=True)

        except Exception as e:
            logger.error(f"Error getting memory files for {worker_id}: {e}")
            return []

    def get_worker_git_diff(self, worker_id: str) -> str:
        """Get worker's git diff."""
        try:
            worker_dir = self.workers_dir / worker_id

            if not worker_dir.exists():
                return "Worker directory not found"

            result = subprocess.run(
                ["git", "diff"],
                cwd=worker_dir,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout if result.stdout else "No changes"
            else:
                return f"Error getting diff: {result.stderr}"

        except Exception as e:
            logger.error(f"Error getting git diff for {worker_id}: {e}")
            return f"Error: {str(e)}"


class IntegratedMonitoringDashboard(MonitoringDashboard):
    """Enhanced monitoring dashboard with real orchestrator integration."""

    def __init__(self, orchestrator=None):
        super().__init__()
        self.orchestrator = orchestrator
        self.data_provider = DashboardDataProvider(self, orchestrator)

        # Override action handlers to use real functionality
        self.setup_real_action_handlers()

    def setup_real_action_handlers(self):
        """Setup real action handlers that integrate with orchestrator."""
        # Override the worker action handler
        original_handler = self.handle_worker_action

        def integrated_handler(worker_id: str, action: str, data: Dict[str, Any] = None):
            # Handle actions asynchronously
            if action == "pause":
                asyncio.create_task(self.data_provider.pause_worker(worker_id))
            elif action == "resume":
                asyncio.create_task(self.data_provider.resume_worker(worker_id))
            elif action == "terminate":
                asyncio.create_task(self.data_provider.terminate_worker(worker_id))
            elif action == "send_message":
                message = data.get("message", "") if data else ""
                asyncio.create_task(self.data_provider.send_message_to_worker(worker_id, message))
            elif action == "view_memory":
                self.show_worker_memory(worker_id)
            elif action == "view_diff":
                self.show_worker_diff(worker_id)
            else:
                # Fall back to original handler for other actions
                original_handler(worker_id, action, data)

        self.handle_worker_action = integrated_handler

    def show_worker_memory(self, worker_id: str):
        """Show worker memory files in new window."""
        memory_files = self.data_provider.get_worker_memory_files(worker_id)

        memory_window = tk.Toplevel(self.root)
        memory_window.title(f"Memory Files - {worker_id}")
        memory_window.geometry("600x400")

        # Create treeview for files
        columns = ("name", "size", "modified")
        tree = ttk.Treeview(memory_window, columns=columns, show="tree headings")

        tree.heading("#0", text="File")
        tree.heading("name", text="Name")
        tree.heading("size", text="Size")
        tree.heading("modified", text="Modified")

        for file_info in memory_files:
            tree.insert("", "end", text=file_info["name"], values=(
                file_info["name"],
                f"{file_info['size']} bytes",
                file_info["modified"]
            ))

        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def show_worker_diff(self, worker_id: str):
        """Show worker git diff in new window."""
        diff_content = self.data_provider.get_worker_git_diff(worker_id)

        diff_window = tk.Toplevel(self.root)
        diff_window.title(f"Git Diff - {worker_id}")
        diff_window.geometry("800x600")

        diff_text = scrolledtext.ScrolledText(
            diff_window,
            font=('Consolas', 10),
            wrap=tk.NONE
        )
        diff_text.pack(fill="both", expand=True, padx=10, pady=10)

        diff_text.insert(tk.END, diff_content)
        diff_text.config(state="disabled")

    async def start_integration(self):
        """Start the integration with orchestrator."""
        await self.data_provider.start()

    async def stop_integration(self):
        """Stop the integration."""
        await self.data_provider.stop()

    def run_integrated(self):
        """Run the integrated dashboard."""
        # Start integration in background
        def start_integration():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start_integration())
            loop.run_forever()

        integration_thread = threading.Thread(target=start_integration, daemon=True)
        integration_thread.start()

        # Remove demo workers since we'll get real data
        self.workers.clear()

        # Run the GUI
        self.run()


def main():
    """Main entry point for integrated dashboard."""
    dashboard = IntegratedMonitoringDashboard()
    dashboard.run_integrated()


if __name__ == "__main__":
    main()