"""
Monitoring GUI Module
Provides visual dashboard for monitoring worker terminals and system status.
"""

import asyncio
import json
import logging
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import tkinter as tk
from tkinter import ttk, scrolledtext
import webbrowser
import tempfile

logger = logging.getLogger(__name__)


class WorkerTerminalInfo:
    """Information about a worker terminal."""

    def __init__(self, worker_id: str, terminal_title: str, process_id: Optional[int] = None):
        self.worker_id = worker_id
        self.terminal_title = terminal_title
        self.process_id = process_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.status = "active"
        self.activity_log: List[Dict[str, Any]] = []

    def log_activity(self, activity: str, level: str = "info"):
        """Log an activity for this worker."""
        self.activity_log.append({
            "timestamp": datetime.now().isoformat(),
            "activity": activity,
            "level": level
        })
        self.last_activity = datetime.now()

        # Keep only recent activities (last 1000)
        if len(self.activity_log) > 1000:
            self.activity_log = self.activity_log[-1000:]


class MonitoringDashboard:
    """GUI dashboard for monitoring the multi-agent system."""

    def __init__(self):
        self.worker_terminals: Dict[str, WorkerTerminalInfo] = {}
        self.activity_callbacks: List[Callable] = []
        self.dashboard_window: Optional[tk.Tk] = None
        self.is_dashboard_open = False

        # Dashboard state
        self.system_metrics = {
            "total_workers": 0,
            "active_tasks": 0,
            "completed_tasks": 0,
            "system_load": 0.0,
            "memory_usage": 0.0
        }

        # GUI components
        self.worker_tree: Optional[ttk.Treeview] = None
        self.activity_text: Optional[scrolledtext.ScrolledText] = None
        self.metrics_frame: Optional[ttk.Frame] = None
        self.control_frame: Optional[ttk.Frame] = None

        # Background thread for updates
        self._update_thread: Optional[threading.Thread] = None
        self._running = False

    def add_worker_terminal(self, worker_id: str, terminal_title: str = None) -> bool:
        """Add a worker terminal to monitoring."""
        if not terminal_title:
            terminal_title = f"Worker-{worker_id}"

        logger.info(f"Adding worker terminal {worker_id} to monitoring")

        terminal_info = WorkerTerminalInfo(worker_id, terminal_title)
        self.worker_terminals[worker_id] = terminal_info

        # Log the addition
        terminal_info.log_activity(f"Worker {worker_id} terminal added to monitoring", "info")

        # Update GUI if open
        if self.is_dashboard_open:
            self._update_worker_display()

        return True

    def remove_worker_terminal(self, worker_id: str) -> bool:
        """Remove a worker terminal from monitoring."""
        if worker_id not in self.worker_terminals:
            logger.warning(f"Worker terminal {worker_id} not found for removal")
            return False

        logger.info(f"Removing worker terminal {worker_id} from monitoring")

        # Mark as terminated
        self.worker_terminals[worker_id].status = "terminated"
        self.worker_terminals[worker_id].log_activity(f"Worker {worker_id} terminal removed", "warning")

        # Update GUI if open
        if self.is_dashboard_open:
            self._update_worker_display()

        return True

    async def log_activity(self, worker_id: str, activity: str, level: str = "info"):
        """Log activity for a specific worker."""
        if worker_id in self.worker_terminals:
            self.worker_terminals[worker_id].log_activity(activity, level)

            # Update GUI if open
            if self.is_dashboard_open:
                self._update_activity_display(worker_id, activity, level)

        # Trigger activity callbacks
        for callback in self.activity_callbacks:
            try:
                await callback(worker_id, activity, level)
            except Exception as e:
                logger.error(f"Activity callback failed: {str(e)}")

    async def get_activity_log(
        self,
        worker_id: str,
        since_timestamp: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Get activity log for a worker."""
        if worker_id not in self.worker_terminals:
            return []

        activities = self.worker_terminals[worker_id].activity_log

        if since_timestamp:
            cutoff = datetime.fromtimestamp(since_timestamp)
            activities = [
                activity for activity in activities
                if datetime.fromisoformat(activity["timestamp"]) >= cutoff
            ]

        return activities

    def open_dashboard(self) -> bool:
        """Open the monitoring GUI dashboard."""
        if self.is_dashboard_open:
            logger.info("Dashboard is already open")
            return True

        logger.info("Opening monitoring dashboard")

        try:
            # Create main window
            self.dashboard_window = tk.Tk()
            self.dashboard_window.title("Multibot Orchestrator - Monitoring Dashboard")
            self.dashboard_window.geometry("1200x800")

            # Set up window close handler
            self.dashboard_window.protocol("WM_DELETE_WINDOW", self._on_dashboard_close)

            # Create GUI layout
            self._create_dashboard_layout()

            # Start update thread
            self._running = True
            self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self._update_thread.start()

            self.is_dashboard_open = True

            # Start the GUI main loop in a separate thread
            gui_thread = threading.Thread(target=self.dashboard_window.mainloop, daemon=True)
            gui_thread.start()

            logger.info("Monitoring dashboard opened successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to open dashboard: {str(e)}")
            return False

    def close_dashboard(self):
        """Close the monitoring dashboard."""
        if not self.is_dashboard_open:
            return

        logger.info("Closing monitoring dashboard")

        self._running = False
        self.is_dashboard_open = False

        if self.dashboard_window:
            self.dashboard_window.quit()
            self.dashboard_window.destroy()
            self.dashboard_window = None

    def update_system_metrics(self, metrics: Dict[str, Any]):
        """Update system metrics display."""
        self.system_metrics.update(metrics)

        if self.is_dashboard_open:
            self._update_metrics_display()

    def register_activity_callback(self, callback: Callable):
        """Register a callback for activity events."""
        self.activity_callbacks.append(callback)

    def pause_worker_monitoring(self, worker_id: str) -> bool:
        """Pause monitoring for a specific worker."""
        if worker_id not in self.worker_terminals:
            return False

        self.worker_terminals[worker_id].status = "paused"
        self.worker_terminals[worker_id].log_activity(f"Monitoring paused", "warning")

        if self.is_dashboard_open:
            self._update_worker_display()

        return True

    def resume_worker_monitoring(self, worker_id: str) -> bool:
        """Resume monitoring for a specific worker."""
        if worker_id not in self.worker_terminals:
            return False

        self.worker_terminals[worker_id].status = "active"
        self.worker_terminals[worker_id].log_activity(f"Monitoring resumed", "info")

        if self.is_dashboard_open:
            self._update_worker_display()

        return True

    def _create_dashboard_layout(self):
        """Create the dashboard GUI layout."""
        # Main container
        main_frame = ttk.Frame(self.dashboard_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top metrics panel
        self.metrics_frame = ttk.LabelFrame(main_frame, text="System Metrics", padding=10)
        self.metrics_frame.pack(fill=tk.X, pady=(0, 10))

        self._create_metrics_display()

        # Middle section - split between worker list and activity log
        middle_frame = ttk.Frame(main_frame)
        middle_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Worker list (left side)
        worker_frame = ttk.LabelFrame(middle_frame, text="Worker Terminals", padding=10)
        worker_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self._create_worker_display(worker_frame)

        # Activity log (right side)
        activity_frame = ttk.LabelFrame(middle_frame, text="Activity Log", padding=10)
        activity_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self._create_activity_display(activity_frame)

        # Bottom control panel
        self.control_frame = ttk.LabelFrame(main_frame, text="Controls", padding=10)
        self.control_frame.pack(fill=tk.X)

        self._create_control_panel()

    def _create_metrics_display(self):
        """Create the system metrics display."""
        # Create metrics labels
        self.metrics_labels = {}

        metrics_grid = ttk.Frame(self.metrics_frame)
        metrics_grid.pack(fill=tk.X)

        # Row 1
        row1 = ttk.Frame(metrics_grid)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="Total Workers:").pack(side=tk.LEFT)
        self.metrics_labels["total_workers"] = ttk.Label(row1, text="0", font=("Arial", 10, "bold"))
        self.metrics_labels["total_workers"].pack(side=tk.LEFT, padx=10)

        ttk.Label(row1, text="Active Tasks:").pack(side=tk.LEFT, padx=(20, 0))
        self.metrics_labels["active_tasks"] = ttk.Label(row1, text="0", font=("Arial", 10, "bold"))
        self.metrics_labels["active_tasks"].pack(side=tk.LEFT, padx=10)

        ttk.Label(row1, text="Completed Tasks:").pack(side=tk.LEFT, padx=(20, 0))
        self.metrics_labels["completed_tasks"] = ttk.Label(row1, text="0", font=("Arial", 10, "bold"))
        self.metrics_labels["completed_tasks"].pack(side=tk.LEFT, padx=10)

        # Row 2
        row2 = ttk.Frame(metrics_grid)
        row2.pack(fill=tk.X, pady=2)

        ttk.Label(row2, text="System Load:").pack(side=tk.LEFT)
        self.metrics_labels["system_load"] = ttk.Label(row2, text="0.0%", font=("Arial", 10, "bold"))
        self.metrics_labels["system_load"].pack(side=tk.LEFT, padx=10)

        ttk.Label(row2, text="Memory Usage:").pack(side=tk.LEFT, padx=(20, 0))
        self.metrics_labels["memory_usage"] = ttk.Label(row2, text="0.0%", font=("Arial", 10, "bold"))
        self.metrics_labels["memory_usage"].pack(side=tk.LEFT, padx=10)

    def _create_worker_display(self, parent):
        """Create the worker list display."""
        # Worker tree view
        columns = ("Worker ID", "Status", "Last Activity", "Terminal")
        self.worker_tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)

        # Configure columns
        self.worker_tree.heading("Worker ID", text="Worker ID")
        self.worker_tree.heading("Status", text="Status")
        self.worker_tree.heading("Last Activity", text="Last Activity")
        self.worker_tree.heading("Terminal", text="Terminal")

        self.worker_tree.column("Worker ID", width=100)
        self.worker_tree.column("Status", width=80)
        self.worker_tree.column("Last Activity", width=150)
        self.worker_tree.column("Terminal", width=120)

        # Scrollbar for tree
        tree_scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.worker_tree.yview)
        self.worker_tree.configure(yscrollcommand=tree_scroll.set)

        # Pack tree and scrollbar
        self.worker_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to open terminal
        self.worker_tree.bind("<Double-1>", self._on_worker_double_click)

        # Context menu for worker actions
        self.worker_context_menu = tk.Menu(self.dashboard_window, tearoff=0)
        self.worker_context_menu.add_command(label="Open Terminal", command=self._open_worker_terminal)
        self.worker_context_menu.add_command(label="Pause Monitoring", command=self._pause_worker)
        self.worker_context_menu.add_command(label="Resume Monitoring", command=self._resume_worker)
        self.worker_context_menu.add_separator()
        self.worker_context_menu.add_command(label="View Activity Log", command=self._view_worker_activity)

        self.worker_tree.bind("<Button-3>", self._show_worker_context_menu)

    def _create_activity_display(self, parent):
        """Create the activity log display."""
        self.activity_text = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            height=15,
            font=("Consolas", 9)
        )
        self.activity_text.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for different log levels
        self.activity_text.tag_config("info", foreground="black")
        self.activity_text.tag_config("warning", foreground="orange")
        self.activity_text.tag_config("error", foreground="red")
        self.activity_text.tag_config("success", foreground="green")

    def _create_control_panel(self):
        """Create the control panel."""
        # Control buttons
        ttk.Button(
            self.control_frame,
            text="Refresh All",
            command=self._refresh_all
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            self.control_frame,
            text="Clear Activity Log",
            command=self._clear_activity_log
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            self.control_frame,
            text="Export Logs",
            command=self._export_logs
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            self.control_frame,
            text="Open Web Dashboard",
            command=self._open_web_dashboard
        ).pack(side=tk.LEFT, padx=5)

        # Status bar
        self.status_var = tk.StringVar(value="Dashboard Ready")
        status_label = ttk.Label(self.control_frame, textvariable=self.status_var)
        status_label.pack(side=tk.RIGHT, padx=10)

    def _update_worker_display(self):
        """Update the worker tree display."""
        if not self.worker_tree:
            return

        try:
            # Clear existing items
            for item in self.worker_tree.get_children():
                self.worker_tree.delete(item)

            # Add current workers
            for worker_id, terminal_info in self.worker_terminals.items():
                last_activity = terminal_info.last_activity.strftime("%H:%M:%S")

                self.worker_tree.insert("", tk.END, values=(
                    worker_id,
                    terminal_info.status,
                    last_activity,
                    terminal_info.terminal_title
                ))

        except Exception as e:
            logger.error(f"Failed to update worker display: {str(e)}")

    def _update_activity_display(self, worker_id: str, activity: str, level: str):
        """Update the activity log display."""
        if not self.activity_text:
            return

        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {worker_id}: {activity}\n"

            self.activity_text.insert(tk.END, log_entry, level)
            self.activity_text.see(tk.END)

            # Limit text widget size (keep last 1000 lines)
            lines = self.activity_text.get("1.0", tk.END).count('\n')
            if lines > 1000:
                self.activity_text.delete("1.0", "100.0")

        except Exception as e:
            logger.error(f"Failed to update activity display: {str(e)}")

    def _update_metrics_display(self):
        """Update the metrics display."""
        if not self.metrics_labels:
            return

        try:
            for metric, value in self.system_metrics.items():
                if metric in self.metrics_labels:
                    if metric in ["system_load", "memory_usage"]:
                        display_value = f"{value:.1f}%"
                    else:
                        display_value = str(value)

                    self.metrics_labels[metric].config(text=display_value)

        except Exception as e:
            logger.error(f"Failed to update metrics display: {str(e)}")

    def _update_loop(self):
        """Background update loop."""
        while self._running:
            try:
                if self.is_dashboard_open:
                    # Update displays
                    self.dashboard_window.after(0, self._update_worker_display)
                    self.dashboard_window.after(0, self._update_metrics_display)

                time.sleep(2)  # Update every 2 seconds

            except Exception as e:
                logger.error(f"Error in dashboard update loop: {str(e)}")
                time.sleep(5)

    def _on_dashboard_close(self):
        """Handle dashboard window close."""
        self.close_dashboard()

    def _on_worker_double_click(self, event):
        """Handle double-click on worker."""
        self._open_worker_terminal()

    def _show_worker_context_menu(self, event):
        """Show context menu for worker."""
        try:
            self.worker_context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            logger.error(f"Failed to show context menu: {str(e)}")

    def _open_worker_terminal(self):
        """Open terminal for selected worker."""
        selected = self.worker_tree.selection()
        if not selected:
            return

        worker_id = self.worker_tree.item(selected[0])["values"][0]
        logger.info(f"Opening terminal for worker {worker_id}")

        # Try to focus existing terminal or open new one
        try:
            if os.name == 'nt':  # Windows
                subprocess.run(["wt", "new-tab", "--title", f"Worker-{worker_id}"], check=False)
            else:  # Linux/macOS
                subprocess.run([
                    "gnome-terminal", "--title", f"Worker-{worker_id}",
                    "--", "bash", "-c", f"echo 'Worker {worker_id} terminal'; exec bash"
                ], check=False)

        except Exception as e:
            logger.error(f"Failed to open terminal for worker {worker_id}: {str(e)}")

    def _pause_worker(self):
        """Pause monitoring for selected worker."""
        selected = self.worker_tree.selection()
        if selected:
            worker_id = self.worker_tree.item(selected[0])["values"][0]
            self.pause_worker_monitoring(worker_id)

    def _resume_worker(self):
        """Resume monitoring for selected worker."""
        selected = self.worker_tree.selection()
        if selected:
            worker_id = self.worker_tree.item(selected[0])["values"][0]
            self.resume_worker_monitoring(worker_id)

    def _view_worker_activity(self):
        """View activity log for selected worker."""
        selected = self.worker_tree.selection()
        if not selected:
            return

        worker_id = self.worker_tree.item(selected[0])["values"][0]
        self._show_worker_activity_window(worker_id)

    def _show_worker_activity_window(self, worker_id: str):
        """Show detailed activity window for worker."""
        if worker_id not in self.worker_terminals:
            return

        # Create new window
        activity_window = tk.Toplevel(self.dashboard_window)
        activity_window.title(f"Activity Log - {worker_id}")
        activity_window.geometry("600x400")

        # Activity text widget
        activity_text = scrolledtext.ScrolledText(
            activity_window,
            wrap=tk.WORD,
            font=("Consolas", 9)
        )
        activity_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Load activity log
        terminal_info = self.worker_terminals[worker_id]
        for activity in terminal_info.activity_log:
            timestamp = activity["timestamp"]
            level = activity["level"]
            message = activity["activity"]

            log_entry = f"[{timestamp}] [{level.upper()}] {message}\n"
            activity_text.insert(tk.END, log_entry)

        activity_text.config(state=tk.DISABLED)

    def _refresh_all(self):
        """Refresh all displays."""
        self.status_var.set("Refreshing...")
        self._update_worker_display()
        self._update_metrics_display()
        self.status_var.set("Dashboard Ready")

    def _clear_activity_log(self):
        """Clear the activity log display."""
        if self.activity_text:
            self.activity_text.delete("1.0", tk.END)

    def _export_logs(self):
        """Export activity logs to file."""
        try:
            # Create export file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_file = Path(tempfile.gettempdir()) / f"multibot_logs_{timestamp}.txt"

            with open(export_file, "w") as f:
                f.write(f"Multibot Activity Log Export - {datetime.now().isoformat()}\n")
                f.write("=" * 50 + "\n\n")

                for worker_id, terminal_info in self.worker_terminals.items():
                    f.write(f"Worker: {worker_id}\n")
                    f.write(f"Status: {terminal_info.status}\n")
                    f.write(f"Created: {terminal_info.created_at.isoformat()}\n")
                    f.write(f"Last Activity: {terminal_info.last_activity.isoformat()}\n")
                    f.write("-" * 30 + "\n")

                    for activity in terminal_info.activity_log:
                        f.write(f"[{activity['timestamp']}] [{activity['level'].upper()}] {activity['activity']}\n")

                    f.write("\n" + "=" * 50 + "\n\n")

            self.status_var.set(f"Logs exported to {export_file}")
            logger.info(f"Activity logs exported to {export_file}")

        except Exception as e:
            logger.error(f"Failed to export logs: {str(e)}")
            self.status_var.set("Export failed")

    def _open_web_dashboard(self):
        """Open web-based dashboard."""
        try:
            # Create simple HTML dashboard
            html_content = self._generate_web_dashboard()
            html_file = Path(tempfile.gettempdir()) / "multibot_dashboard.html"

            with open(html_file, "w") as f:
                f.write(html_content)

            # Open in browser
            webbrowser.open(f"file://{html_file}")
            self.status_var.set("Web dashboard opened in browser")

        except Exception as e:
            logger.error(f"Failed to open web dashboard: {str(e)}")
            self.status_var.set("Failed to open web dashboard")

    def _generate_web_dashboard(self) -> str:
        """Generate HTML content for web dashboard."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Multibot Orchestrator Dashboard</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .metrics {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .worker-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
        .worker-table th, .worker-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        .worker-table th {{ background-color: #f2f2f2; }}
        .status-active {{ color: green; font-weight: bold; }}
        .status-paused {{ color: orange; font-weight: bold; }}
        .status-terminated {{ color: red; font-weight: bold; }}
        .activity-log {{ background: #f9f9f9; padding: 10px; border: 1px solid #ddd; height: 300px; overflow-y: scroll; font-family: monospace; }}
    </style>
    <script>
        function refreshPage() {{ location.reload(); }}
        setInterval(refreshPage, 30000); // Auto-refresh every 30 seconds
    </script>
</head>
<body>
    <h1>Multibot Orchestrator Dashboard</h1>
    <p>Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="metrics">
        <h2>System Metrics</h2>
        <p><strong>Total Workers:</strong> {self.system_metrics.get('total_workers', 0)}</p>
        <p><strong>Active Tasks:</strong> {self.system_metrics.get('active_tasks', 0)}</p>
        <p><strong>Completed Tasks:</strong> {self.system_metrics.get('completed_tasks', 0)}</p>
        <p><strong>System Load:</strong> {self.system_metrics.get('system_load', 0):.1f}%</p>
        <p><strong>Memory Usage:</strong> {self.system_metrics.get('memory_usage', 0):.1f}%</p>
    </div>

    <h2>Worker Terminals</h2>
    <table class="worker-table">
        <tr>
            <th>Worker ID</th>
            <th>Status</th>
            <th>Created</th>
            <th>Last Activity</th>
            <th>Terminal</th>
        </tr>
"""

        for worker_id, terminal_info in self.worker_terminals.items():
            status_class = f"status-{terminal_info.status}"
            html += f"""
        <tr>
            <td>{worker_id}</td>
            <td class="{status_class}">{terminal_info.status}</td>
            <td>{terminal_info.created_at.strftime('%H:%M:%S')}</td>
            <td>{terminal_info.last_activity.strftime('%H:%M:%S')}</td>
            <td>{terminal_info.terminal_title}</td>
        </tr>
"""

        html += """
    </table>

    <h2>Recent Activity</h2>
    <div class="activity-log">
"""

        # Add recent activities from all workers
        all_activities = []
        for worker_id, terminal_info in self.worker_terminals.items():
            for activity in terminal_info.activity_log[-50:]:  # Last 50 activities
                all_activities.append({
                    "worker_id": worker_id,
                    "timestamp": activity["timestamp"],
                    "activity": activity["activity"],
                    "level": activity["level"]
                })

        # Sort by timestamp
        all_activities.sort(key=lambda x: x["timestamp"], reverse=True)

        for activity in all_activities[:100]:  # Show last 100 activities
            html += f"""
        <div>[{activity['timestamp']}] {activity['worker_id']}: {activity['activity']}</div>
"""

        html += """
    </div>

    <p><small>This page auto-refreshes every 30 seconds. <a href="javascript:refreshPage()">Refresh Now</a></small></p>
</body>
</html>
"""

        return html