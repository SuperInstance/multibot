#!/usr/bin/env python3
"""
Multi-Terminal Monitoring Dashboard
Real-time visual monitoring of Master orchestrator and Worker instances.
"""

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, font
import queue

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkerTerminalWidget(ttk.Frame):
    """Individual worker terminal display widget."""

    def __init__(self, parent, worker_id: str, on_select_callback=None, on_action_callback=None):
        super().__init__(parent, relief='ridge', borderwidth=2)
        self.parent = parent
        self.worker_id = worker_id
        self.on_select_callback = on_select_callback
        self.on_action_callback = on_action_callback

        # Worker state
        self.worker_data = {
            "worker_id": worker_id,
            "model": "unknown",
            "status": "initializing",
            "branch": "unknown",
            "task_title": "No task assigned",
            "progress": 0,
            "last_activity": "Starting up...",
            "log_lines": [],
            "is_expanded": False
        }

        # Colors for status
        self.status_colors = {
            "active": "#4CAF50",     # Green
            "working": "#4CAF50",    # Green
            "waiting": "#FFC107",    # Yellow
            "idle": "#FFC107",       # Yellow
            "paused": "#FF9800",     # Orange
            "error": "#F44336",      # Red
            "terminated": "#9E9E9E", # Gray
            "initializing": "#2196F3" # Blue
        }

        self.status_icons = {
            "active": "🟢",
            "working": "🟢",
            "waiting": "🟡",
            "idle": "🟡",
            "paused": "🔴",
            "error": "⚫",
            "terminated": "⚪",
            "initializing": "🔵"
        }

        self.create_widgets()
        self.bind_events()

    def create_widgets(self):
        """Create the terminal widget UI."""
        # Configure grid weights
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header frame
        self.header_frame = ttk.Frame(self)
        self.header_frame.grid(row=0, column=0, sticky='ew', padx=2, pady=2)
        self.header_frame.grid_columnconfigure(1, weight=1)

        # Worker info
        self.status_label = ttk.Label(self.header_frame, text="🔵", font=('Arial', 12))
        self.status_label.grid(row=0, column=0, padx=(2, 5))

        self.worker_label = ttk.Label(
            self.header_frame,
            text=f"{self.worker_id} (unknown)",
            font=('Arial', 10, 'bold')
        )
        self.worker_label.grid(row=0, column=1, sticky='w')

        # Branch and task info
        self.branch_label = ttk.Label(
            self.header_frame,
            text="Branch: unknown",
            font=('Arial', 8)
        )
        self.branch_label.grid(row=1, column=0, columnspan=2, sticky='w')

        self.task_label = ttk.Label(
            self.header_frame,
            text="Task: No task assigned",
            font=('Arial', 8),
            foreground='gray'
        )
        self.task_label.grid(row=2, column=0, columnspan=2, sticky='w')

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.header_frame,
            variable=self.progress_var,
            maximum=100,
            length=150
        )
        self.progress_bar.grid(row=3, column=0, columnspan=2, sticky='ew', pady=2)

        # Terminal output
        self.terminal_frame = ttk.Frame(self)
        self.terminal_frame.grid(row=1, column=0, sticky='nsew', padx=2, pady=2)
        self.terminal_frame.grid_rowconfigure(0, weight=1)
        self.terminal_frame.grid_columnconfigure(0, weight=1)

        self.terminal_text = scrolledtext.ScrolledText(
            self.terminal_frame,
            height=8,
            font=('Consolas', 8),
            bg='black',
            fg='white',
            wrap=tk.WORD
        )
        self.terminal_text.grid(row=0, column=0, sticky='nsew')

        # Control buttons
        self.button_frame = ttk.Frame(self)
        self.button_frame.grid(row=2, column=0, sticky='ew', padx=2, pady=2)

        self.pause_button = ttk.Button(
            self.button_frame,
            text="Pause",
            command=self.toggle_pause,
            width=8
        )
        self.pause_button.pack(side='left', padx=2)

        self.terminate_button = ttk.Button(
            self.button_frame,
            text="Terminate",
            command=self.terminate_worker,
            width=10
        )
        self.terminate_button.pack(side='left', padx=2)

        self.expand_button = ttk.Button(
            self.button_frame,
            text="Expand",
            command=self.toggle_expand,
            width=8
        )
        self.expand_button.pack(side='right', padx=2)

    def bind_events(self):
        """Bind mouse and keyboard events."""
        # Click to select
        self.bind('<Button-1>', self.on_click)
        self.header_frame.bind('<Button-1>', self.on_click)
        self.terminal_text.bind('<Button-1>', self.on_click)

        # Right-click context menu
        self.bind('<Button-3>', self.show_context_menu)
        self.terminal_text.bind('<Button-3>', self.show_context_menu)

        # Double-click to expand
        self.bind('<Double-Button-1>', self.toggle_expand)
        self.terminal_text.bind('<Double-Button-1>', self.toggle_expand)

    def on_click(self, event=None):
        """Handle click selection."""
        if self.on_select_callback:
            self.on_select_callback(self.worker_id)

    def show_context_menu(self, event):
        """Show right-click context menu."""
        context_menu = tk.Menu(self, tearoff=0)
        context_menu.add_command(label="View Full Logs", command=self.view_full_logs)
        context_menu.add_command(label="Send Message to Worker", command=self.send_message)
        context_menu.add_command(label="View Memory Files", command=self.view_memory_files)
        context_menu.add_command(label="View Git Diff", command=self.view_git_diff)
        context_menu.add_separator()
        context_menu.add_command(label="Copy Worker ID", command=self.copy_worker_id)

        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def update_worker_data(self, data: Dict[str, Any]):
        """Update worker data and refresh display."""
        self.worker_data.update(data)
        self.refresh_display()

    def refresh_display(self):
        """Refresh the visual display with current data."""
        data = self.worker_data

        # Update status icon and color
        status = data.get('status', 'unknown')
        icon = self.status_icons.get(status, '⚪')
        color = self.status_colors.get(status, '#9E9E9E')

        self.status_label.config(text=icon)
        self.configure(highlightbackground=color, highlightthickness=2)

        # Update worker info
        model = data.get('model', 'unknown')
        self.worker_label.config(text=f"{self.worker_id} ({model})")

        # Update branch
        branch = data.get('branch', 'unknown')
        self.branch_label.config(text=f"Branch: {branch}")

        # Update task
        task_title = data.get('task_title', 'No task assigned')
        self.task_label.config(text=f"Task: {task_title}")

        # Update progress
        progress = data.get('progress', 0)
        self.progress_var.set(progress)

        # Update terminal output
        log_lines = data.get('log_lines', [])
        if log_lines:
            self.terminal_text.delete(1.0, tk.END)
            # Show last 20 lines
            recent_lines = log_lines[-20:] if len(log_lines) > 20 else log_lines
            for line in recent_lines:
                self.terminal_text.insert(tk.END, line + '\n')
            self.terminal_text.see(tk.END)

        # Update button states
        if status == 'paused':
            self.pause_button.config(text="Resume")
        else:
            self.pause_button.config(text="Pause")

        if status in ['terminated', 'error']:
            self.pause_button.config(state='disabled')
        else:
            self.pause_button.config(state='normal')

    def toggle_pause(self):
        """Toggle worker pause/resume."""
        if self.on_action_callback:
            action = "resume" if self.worker_data.get('status') == 'paused' else "pause"
            self.on_action_callback(self.worker_id, action)

    def terminate_worker(self):
        """Terminate worker with confirmation."""
        if messagebox.askyesno(
            "Confirm Termination",
            f"Are you sure you want to terminate worker {self.worker_id}?"
        ):
            if self.on_action_callback:
                self.on_action_callback(self.worker_id, "terminate")

    def toggle_expand(self, event=None):
        """Toggle expanded view."""
        if self.on_action_callback:
            self.on_action_callback(self.worker_id, "toggle_expand")

    def view_full_logs(self):
        """Open full logs in new window."""
        log_window = tk.Toplevel(self)
        log_window.title(f"Full Logs - {self.worker_id}")
        log_window.geometry("800x600")

        log_text = scrolledtext.ScrolledText(
            log_window,
            font=('Consolas', 10),
            bg='black',
            fg='white'
        )
        log_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Load full logs
        all_lines = self.worker_data.get('log_lines', [])
        for line in all_lines:
            log_text.insert(tk.END, line + '\n')
        log_text.see(tk.END)

    def send_message(self):
        """Send message to worker."""
        message = simpledialog.askstring(
            "Send Message",
            f"Enter message to send to {self.worker_id}:"
        )
        if message and self.on_action_callback:
            self.on_action_callback(self.worker_id, "send_message", {"message": message})

    def view_memory_files(self):
        """View worker's memory files."""
        if self.on_action_callback:
            self.on_action_callback(self.worker_id, "view_memory")

    def view_git_diff(self):
        """View worker's git diff."""
        if self.on_action_callback:
            self.on_action_callback(self.worker_id, "view_diff")

    def copy_worker_id(self):
        """Copy worker ID to clipboard."""
        self.clipboard_clear()
        self.clipboard_append(self.worker_id)


class MasterControlPanel(ttk.Frame):
    """Master control panel showing system overview."""

    def __init__(self, parent):
        super().__init__(parent, relief='ridge', borderwidth=2)
        self.master_data = {
            "active_workers": 0,
            "tasks_completed": 0,
            "tasks_in_progress": 0,
            "tasks_queued": 0,
            "current_activity": "Idle",
            "repository_status": "Unknown"
        }
        self.create_widgets()

    def create_widgets(self):
        """Create the master control panel UI."""
        # Title
        title_label = ttk.Label(
            self,
            text="🎯 Master Orchestrator Control Panel",
            font=('Arial', 12, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=4, pady=5)

        # Statistics frame
        stats_frame = ttk.LabelFrame(self, text="System Statistics", padding=10)
        stats_frame.grid(row=1, column=0, columnspan=4, sticky='ew', padx=5, pady=5)
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Active workers
        self.workers_label = ttk.Label(stats_frame, text="Active Workers: 0", font=('Arial', 10))
        self.workers_label.grid(row=0, column=0, sticky='w')

        # Tasks completed
        self.completed_label = ttk.Label(stats_frame, text="Completed: 0", font=('Arial', 10))
        self.completed_label.grid(row=0, column=1, sticky='w')

        # Tasks in progress
        self.progress_label = ttk.Label(stats_frame, text="In Progress: 0", font=('Arial', 10))
        self.progress_label.grid(row=0, column=2, sticky='w')

        # Tasks queued
        self.queued_label = ttk.Label(stats_frame, text="Queued: 0", font=('Arial', 10))
        self.queued_label.grid(row=0, column=3, sticky='w')

        # Current activity
        activity_frame = ttk.LabelFrame(self, text="Master Activity", padding=10)
        activity_frame.grid(row=2, column=0, columnspan=4, sticky='ew', padx=5, pady=5)

        self.activity_label = ttk.Label(
            activity_frame,
            text="Current Activity: Idle",
            font=('Arial', 10),
            wraplength=400
        )
        self.activity_label.grid(row=0, column=0, sticky='w')

        # Repository status
        repo_frame = ttk.LabelFrame(self, text="Repository Status", padding=10)
        repo_frame.grid(row=3, column=0, columnspan=4, sticky='ew', padx=5, pady=5)

        self.repo_label = ttk.Label(
            repo_frame,
            text="Repository: Unknown",
            font=('Arial', 10)
        )
        self.repo_label.grid(row=0, column=0, sticky='w')

        # Control buttons
        button_frame = ttk.Frame(self)
        button_frame.grid(row=4, column=0, columnspan=4, pady=10)

        ttk.Button(
            button_frame,
            text="Spawn New Worker",
            command=self.spawn_worker
        ).pack(side='left', padx=5)

        ttk.Button(
            button_frame,
            text="Pause All Workers",
            command=self.pause_all
        ).pack(side='left', padx=5)

        ttk.Button(
            button_frame,
            text="Resume All Workers",
            command=self.resume_all
        ).pack(side='left', padx=5)

        ttk.Button(
            button_frame,
            text="System Status",
            command=self.show_system_status
        ).pack(side='left', padx=5)

    def update_data(self, data: Dict[str, Any]):
        """Update master control panel data."""
        self.master_data.update(data)
        self.refresh_display()

    def refresh_display(self):
        """Refresh the display with current data."""
        data = self.master_data

        # Update statistics
        self.workers_label.config(text=f"Active Workers: {data.get('active_workers', 0)}")
        self.completed_label.config(text=f"Completed: {data.get('tasks_completed', 0)}")
        self.progress_label.config(text=f"In Progress: {data.get('tasks_in_progress', 0)}")
        self.queued_label.config(text=f"Queued: {data.get('tasks_queued', 0)}")

        # Update activity
        activity = data.get('current_activity', 'Idle')
        self.activity_label.config(text=f"Current Activity: {activity}")

        # Update repository status
        repo_status = data.get('repository_status', 'Unknown')
        self.repo_label.config(text=f"Repository: {repo_status}")

    def spawn_worker(self):
        """Spawn new worker dialog."""
        # Implementation would integrate with orchestrator
        messagebox.showinfo("Spawn Worker", "Spawn worker functionality would be implemented here")

    def pause_all(self):
        """Pause all workers."""
        messagebox.showinfo("Pause All", "Pause all workers functionality would be implemented here")

    def resume_all(self):
        """Resume all workers."""
        messagebox.showinfo("Resume All", "Resume all workers functionality would be implemented here")

    def show_system_status(self):
        """Show detailed system status."""
        messagebox.showinfo("System Status", "Detailed system status would be shown here")


class CommunicationLogPanel(ttk.Frame):
    """Panel showing Master↔Worker communication log."""

    def __init__(self, parent):
        super().__init__(parent, relief='ridge', borderwidth=2)
        self.create_widgets()
        self.message_queue = queue.Queue()

    def create_widgets(self):
        """Create the communication log UI."""
        # Title
        title_label = ttk.Label(
            self,
            text="📡 Master ↔ Worker Communication Log",
            font=('Arial', 10, 'bold')
        )
        title_label.pack(pady=5)

        # Log display
        self.log_text = scrolledtext.ScrolledText(
            self,
            height=12,
            font=('Consolas', 9),
            bg='#f8f9fa',
            fg='#333'
        )
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Control frame
        control_frame = ttk.Frame(self)
        control_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(
            control_frame,
            text="Clear Log",
            command=self.clear_log
        ).pack(side='left')

        ttk.Button(
            control_frame,
            text="Save Log",
            command=self.save_log
        ).pack(side='left', padx=5)

        ttk.Button(
            control_frame,
            text="Filter",
            command=self.filter_log
        ).pack(side='left', padx=5)

    def add_message(self, timestamp: str, from_id: str, to_id: str, message_type: str, content: str):
        """Add a message to the communication log."""
        # Format message
        formatted_message = f"[{timestamp}] {from_id} → {to_id} ({message_type}): {content[:100]}...\n"

        # Add to queue for thread-safe updates
        self.message_queue.put(formatted_message)

    def update_display(self):
        """Update the display with queued messages."""
        while not self.message_queue.empty():
            try:
                message = self.message_queue.get_nowait()
                self.log_text.insert(tk.END, message)
                self.log_text.see(tk.END)

                # Keep only last 500 lines
                lines = self.log_text.get(1.0, tk.END).split('\n')
                if len(lines) > 500:
                    self.log_text.delete(1.0, f"{len(lines) - 500}.0")

            except queue.Empty:
                break

    def clear_log(self):
        """Clear the communication log."""
        self.log_text.delete(1.0, tk.END)

    def save_log(self):
        """Save the communication log to file."""
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt")]
        )
        if filename:
            with open(filename, 'w') as f:
                f.write(self.log_text.get(1.0, tk.END))
            messagebox.showinfo("Saved", f"Log saved to {filename}")

    def filter_log(self):
        """Filter log messages."""
        filter_text = simpledialog.askstring("Filter Log", "Enter filter text:")
        if filter_text:
            # Implementation for filtering
            messagebox.showinfo("Filter", f"Filtering by: {filter_text}")


class MonitoringDashboard:
    """Main monitoring dashboard application."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Multi-Agent Orchestrator Monitoring Dashboard")
        self.root.geometry("1400x900")

        # Data
        self.workers = {}  # worker_id -> WorkerTerminalWidget
        self.selected_worker = None
        self.expanded_worker = None
        self.update_interval = 1000  # ms

        # Database connection
        self.db_path = "/tmp/multibot/message_queue.db"

        # Create UI
        self.create_menu()
        self.create_main_layout()
        self.setup_keyboard_shortcuts()

        # Start update thread
        self.start_update_thread()

    def create_menu(self):
        """Create the application menu."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Worker", command=self.spawn_worker)
        file_menu.add_separator()
        file_menu.add_command(label="Export Logs", command=self.export_logs)
        file_menu.add_command(label="Settings", command=self.show_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh", command=self.refresh_all)
        view_menu.add_command(label="Full Screen", command=self.toggle_fullscreen)

        # Workers menu
        workers_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Workers", menu=workers_menu)
        workers_menu.add_command(label="Pause All", command=self.pause_all_workers)
        workers_menu.add_command(label="Resume All", command=self.resume_all_workers)
        workers_menu.add_command(label="Terminate All", command=self.terminate_all_workers)

    def create_main_layout(self):
        """Create the main dashboard layout."""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Top frame for master control panel
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill='x', pady=(0, 5))

        self.master_panel = MasterControlPanel(top_frame)
        self.master_panel.pack(fill='x')

        # Middle frame for worker terminals
        middle_frame = ttk.Frame(main_frame)
        middle_frame.pack(fill='both', expand=True, pady=5)

        # Create notebook for different views
        self.notebook = ttk.Notebook(middle_frame)
        self.notebook.pack(fill='both', expand=True)

        # Workers grid view
        self.workers_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.workers_frame, text="Workers Grid")

        # Expanded view frame
        self.expanded_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.expanded_frame, text="Expanded View")

        # Configure grid for workers
        for i in range(3):  # 3 rows
            self.workers_frame.grid_rowconfigure(i, weight=1)
        for j in range(4):  # 4 columns (max 12 workers in 3x4 grid)
            self.workers_frame.grid_columnconfigure(j, weight=1)

        # Bottom frame for communication log
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill='x', pady=(5, 0))

        self.comm_log = CommunicationLogPanel(bottom_frame)
        self.comm_log.pack(fill='both', expand=True)

    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts."""
        self.root.bind('<space>', self.toggle_selected_worker)
        self.root.bind('<Control-t>', self.terminate_selected_worker)
        self.root.bind('<Control-m>', self.send_message_to_master)
        self.root.bind('<Control-n>', self.spawn_worker)
        self.root.bind('<F11>', self.toggle_fullscreen)
        self.root.bind('<F5>', self.refresh_all)

    def add_worker(self, worker_id: str, worker_data: Dict[str, Any]):
        """Add a new worker to the monitoring dashboard."""
        if worker_id in self.workers:
            return  # Worker already exists

        # Calculate position in grid
        worker_count = len(self.workers)
        row = worker_count // 4
        col = worker_count % 4

        if worker_count >= 12:  # Max 12 workers
            logger.warning(f"Maximum worker limit reached, cannot add {worker_id}")
            return

        # Create worker widget
        worker_widget = WorkerTerminalWidget(
            self.workers_frame,
            worker_id,
            on_select_callback=self.select_worker,
            on_action_callback=self.handle_worker_action
        )

        worker_widget.grid(row=row, column=col, sticky='nsew', padx=2, pady=2)
        worker_widget.update_worker_data(worker_data)

        self.workers[worker_id] = worker_widget
        logger.info(f"Added worker {worker_id} to monitoring dashboard")

    def remove_worker(self, worker_id: str):
        """Remove a worker from the monitoring dashboard."""
        if worker_id in self.workers:
            self.workers[worker_id].destroy()
            del self.workers[worker_id]

            # Reorganize grid
            self.reorganize_worker_grid()
            logger.info(f"Removed worker {worker_id} from monitoring dashboard")

    def reorganize_worker_grid(self):
        """Reorganize worker widgets in grid after removal."""
        for i, (worker_id, widget) in enumerate(self.workers.items()):
            row = i // 4
            col = i % 4
            widget.grid(row=row, column=col, sticky='nsew', padx=2, pady=2)

    def update_worker_data(self, worker_id: str, data: Dict[str, Any]):
        """Update data for a specific worker."""
        if worker_id in self.workers:
            self.workers[worker_id].update_worker_data(data)

    def select_worker(self, worker_id: str):
        """Select a worker for keyboard shortcuts."""
        self.selected_worker = worker_id

        # Visual feedback - highlight selected worker
        for wid, widget in self.workers.items():
            if wid == worker_id:
                widget.configure(relief='solid', borderwidth=3)
            else:
                widget.configure(relief='ridge', borderwidth=2)

    def handle_worker_action(self, worker_id: str, action: str, data: Dict[str, Any] = None):
        """Handle worker action from UI."""
        logger.info(f"Worker action: {worker_id} - {action}")

        if action == "pause":
            self.pause_worker(worker_id)
        elif action == "resume":
            self.resume_worker(worker_id)
        elif action == "terminate":
            self.terminate_worker(worker_id)
        elif action == "toggle_expand":
            self.toggle_expand_worker(worker_id)
        elif action == "send_message":
            self.send_message_to_worker(worker_id, data.get("message", ""))
        elif action == "view_memory":
            self.view_worker_memory(worker_id)
        elif action == "view_diff":
            self.view_worker_diff(worker_id)

    def toggle_expand_worker(self, worker_id: str):
        """Toggle expanded view for a worker."""
        if self.expanded_worker == worker_id:
            # Collapse - switch back to grid view
            self.expanded_worker = None
            self.notebook.select(0)  # Workers grid tab
        else:
            # Expand - show in expanded view
            self.expanded_worker = worker_id

            # Clear expanded frame
            for widget in self.expanded_frame.winfo_children():
                widget.destroy()

            # Create expanded worker view
            if worker_id in self.workers:
                worker_widget = WorkerTerminalWidget(
                    self.expanded_frame,
                    worker_id,
                    on_select_callback=self.select_worker,
                    on_action_callback=self.handle_worker_action
                )
                worker_widget.pack(fill='both', expand=True)
                worker_widget.update_worker_data(self.workers[worker_id].worker_data)

                # Switch to expanded view tab
                self.notebook.select(1)

    def pause_worker(self, worker_id: str):
        """Pause a specific worker."""
        # Implementation would send pause command to orchestrator
        logger.info(f"Pausing worker {worker_id}")

    def resume_worker(self, worker_id: str):
        """Resume a specific worker."""
        # Implementation would send resume command to orchestrator
        logger.info(f"Resuming worker {worker_id}")

    def terminate_worker(self, worker_id: str):
        """Terminate a specific worker."""
        # Implementation would send terminate command to orchestrator
        logger.info(f"Terminating worker {worker_id}")

    def send_message_to_worker(self, worker_id: str, message: str):
        """Send message to a specific worker."""
        # Implementation would send message through orchestrator
        logger.info(f"Sending message to {worker_id}: {message}")

    def view_worker_memory(self, worker_id: str):
        """View worker's memory files."""
        # Implementation would fetch and display worker memory files
        messagebox.showinfo("Worker Memory", f"Memory files for {worker_id} would be shown here")

    def view_worker_diff(self, worker_id: str):
        """View worker's git diff."""
        # Implementation would fetch and display worker's git diff
        messagebox.showinfo("Worker Diff", f"Git diff for {worker_id} would be shown here")

    def toggle_selected_worker(self, event=None):
        """Toggle pause/resume for selected worker."""
        if self.selected_worker:
            worker_data = self.workers[self.selected_worker].worker_data
            if worker_data.get('status') == 'paused':
                self.resume_worker(self.selected_worker)
            else:
                self.pause_worker(self.selected_worker)

    def terminate_selected_worker(self, event=None):
        """Terminate selected worker."""
        if self.selected_worker:
            self.terminate_worker(self.selected_worker)

    def send_message_to_master(self, event=None):
        """Send message to master."""
        message = simpledialog.askstring("Send to Master", "Enter message for Master:")
        if message:
            logger.info(f"Sending message to Master: {message}")

    def spawn_worker(self, event=None):
        """Spawn new worker dialog."""
        # Implementation would show dialog and spawn worker
        messagebox.showinfo("Spawn Worker", "Spawn worker dialog would be shown here")

    def pause_all_workers(self):
        """Pause all workers."""
        for worker_id in self.workers:
            self.pause_worker(worker_id)

    def resume_all_workers(self):
        """Resume all workers."""
        for worker_id in self.workers:
            self.resume_worker(worker_id)

    def terminate_all_workers(self):
        """Terminate all workers with confirmation."""
        if messagebox.askyesno("Confirm", "Terminate all workers?"):
            for worker_id in self.workers:
                self.terminate_worker(worker_id)

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode."""
        self.root.attributes('-fullscreen', not self.root.attributes('-fullscreen'))

    def refresh_all(self, event=None):
        """Refresh all data."""
        logger.info("Refreshing all data")

    def export_logs(self):
        """Export all logs."""
        messagebox.showinfo("Export Logs", "Log export functionality would be implemented here")

    def show_settings(self):
        """Show settings dialog."""
        messagebox.showinfo("Settings", "Settings dialog would be shown here")

    def start_update_thread(self):
        """Start the background update thread."""
        def update_loop():
            while True:
                try:
                    # Update communication log display
                    self.comm_log.update_display()

                    # Schedule data updates
                    self.root.after(0, self.update_data)

                    time.sleep(1)  # Update every second
                except Exception as e:
                    logger.error(f"Update thread error: {e}")
                    time.sleep(5)  # Wait longer on error

        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()

    def update_data(self):
        """Update data from database and orchestrator."""
        try:
            # This would fetch real data from the orchestrator
            # For now, simulate some data updates

            # Update master panel
            self.master_panel.update_data({
                "active_workers": len(self.workers),
                "tasks_completed": 5,
                "tasks_in_progress": 3,
                "tasks_queued": 2,
                "current_activity": "Coordinating worker tasks",
                "repository_status": "3 branches active, 2 pending merges"
            })

            # Simulate worker updates
            for worker_id, widget in self.workers.items():
                # This would fetch real worker data
                pass

        except Exception as e:
            logger.error(f"Data update error: {e}")

    def run(self):
        """Run the monitoring dashboard."""
        logger.info("Starting Multi-Agent Orchestrator Monitoring Dashboard")

        # Add some demo workers
        self.add_demo_workers()

        self.root.mainloop()

    def add_demo_workers(self):
        """Add demo workers for testing."""
        demo_workers = [
            {
                "worker_id": "worker-001",
                "model": "opus",
                "status": "working",
                "branch": "feature/auth",
                "task_title": "Implement user authentication",
                "progress": 75,
                "log_lines": [
                    "[12:34:56] Starting authentication implementation",
                    "[12:35:10] Created auth.py module",
                    "[12:35:25] Implementing JWT token validation",
                    "[12:35:40] Adding password hashing with argon2",
                    "[12:35:55] Writing unit tests for auth module"
                ]
            },
            {
                "worker_id": "worker-002",
                "model": "sonnet",
                "status": "waiting",
                "branch": "feature/api",
                "task_title": "Build REST API endpoints",
                "progress": 30,
                "log_lines": [
                    "[12:30:15] Received API task assignment",
                    "[12:30:30] Setting up FastAPI structure",
                    "[12:31:00] Waiting for authentication module completion"
                ]
            },
            {
                "worker_id": "worker-003",
                "model": "haiku",
                "status": "active",
                "branch": "feature/tests",
                "task_title": "Write integration tests",
                "progress": 50,
                "log_lines": [
                    "[12:32:00] Creating test fixtures",
                    "[12:32:15] Setting up test database",
                    "[12:32:30] Writing API integration tests"
                ]
            }
        ]

        for worker_data in demo_workers:
            self.add_worker(worker_data["worker_id"], worker_data)


def main():
    """Main entry point."""
    dashboard = MonitoringDashboard()
    dashboard.run()


if __name__ == "__main__":
    main()