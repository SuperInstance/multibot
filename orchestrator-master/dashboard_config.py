#!/usr/bin/env python3
"""
Dashboard Configuration
Configuration settings for the monitoring dashboard.
"""

import os
from pathlib import Path
from typing import Dict, Any


class DashboardConfig:
    """Configuration class for the monitoring dashboard."""

    def __init__(self):
        # Paths
        self.base_dir = Path(os.environ.get("MULTIBOT_BASE_DIR", "/tmp/multibot"))
        self.workers_dir = self.base_dir / "workers"
        self.logs_dir = self.base_dir / "logs"
        self.db_path = self.base_dir / "message_queue.db"

        # Dashboard settings
        self.window_title = "Multi-Agent Orchestrator Monitoring Dashboard"
        self.window_geometry = "1400x900"
        self.max_workers = 12
        self.default_grid_size = (3, 4)  # rows, columns

        # Update intervals (seconds)
        self.fast_update_interval = 1.0
        self.slow_update_interval = 5.0
        self.message_check_interval = 0.5

        # Display settings
        self.max_log_lines = 100
        self.max_communication_log_lines = 500
        self.terminal_font = ("Consolas", 8)
        self.header_font = ("Arial", 10, "bold")

        # Colors
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

        # Terminal colors
        self.terminal_bg = "#1e1e1e"
        self.terminal_fg = "#ffffff"
        self.terminal_cursor = "#ffffff"

        # Communication log colors
        self.comm_log_bg = "#f8f9fa"
        self.comm_log_fg = "#333333"

        # Keyboard shortcuts
        self.shortcuts = {
            "toggle_pause": "<space>",
            "terminate_worker": "<Control-t>",
            "message_to_master": "<Control-m>",
            "spawn_worker": "<Control-n>",
            "fullscreen": "<F11>",
            "refresh": "<F5>",
            "expand_worker": "<Return>",
            "close_expanded": "<Escape>"
        }

        # Worker spawn settings
        self.default_worker_model = "sonnet"
        self.available_models = ["opus", "sonnet", "haiku"]
        self.default_base_branch = "main"

        # Log settings
        self.log_level = "INFO"
        self.log_format = "[%(asctime)s] %(levelname)s: %(message)s"
        self.log_date_format = "%H:%M:%S"

        # Auto-discovery settings
        self.auto_discover_workers = True
        self.discovery_interval = 5.0

        # Performance settings
        self.gui_update_batch_size = 10
        self.max_concurrent_updates = 5

    def load_from_file(self, config_file: Path) -> None:
        """Load configuration from file."""
        if not config_file.exists():
            return

        try:
            import json
            with open(config_file) as f:
                config_data = json.load(f)

            # Update configuration from file
            for key, value in config_data.items():
                if hasattr(self, key):
                    setattr(self, key, value)

        except Exception as e:
            print(f"Warning: Failed to load config from {config_file}: {e}")

    def save_to_file(self, config_file: Path) -> None:
        """Save configuration to file."""
        try:
            import json
            config_data = {}

            # Save configurable attributes
            configurable_attrs = [
                "window_geometry", "max_workers", "fast_update_interval",
                "slow_update_interval", "max_log_lines", "terminal_font",
                "default_worker_model", "log_level", "auto_discover_workers"
            ]

            for attr in configurable_attrs:
                if hasattr(self, attr):
                    config_data[attr] = getattr(self, attr)

            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)

        except Exception as e:
            print(f"Warning: Failed to save config to {config_file}: {e}")

    def get_worker_log_file(self, worker_id: str) -> Path:
        """Get log file path for a worker."""
        return self.workers_dir / worker_id / "logs" / "worker.log"

    def get_worker_memory_dir(self, worker_id: str) -> Path:
        """Get memory directory for a worker."""
        return self.workers_dir / worker_id / "memory"

    def get_worker_working_dir(self, worker_id: str) -> Path:
        """Get working directory for a worker."""
        return self.workers_dir / worker_id / "working"

    def validate_config(self) -> bool:
        """Validate configuration settings."""
        try:
            # Check paths
            if not self.base_dir.exists():
                self.base_dir.mkdir(parents=True, exist_ok=True)

            # Check numeric values
            assert self.max_workers > 0 and self.max_workers <= 20
            assert self.fast_update_interval > 0
            assert self.slow_update_interval > 0
            assert self.max_log_lines > 0

            # Check grid size
            rows, cols = self.default_grid_size
            assert rows * cols >= 4  # Minimum 4 workers

            return True

        except Exception as e:
            print(f"Configuration validation failed: {e}")
            return False

    def get_theme_config(self, theme_name: str = "default") -> Dict[str, Any]:
        """Get theme configuration."""
        themes = {
            "default": {
                "bg": "#ffffff",
                "fg": "#000000",
                "select_bg": "#0078d4",
                "select_fg": "#ffffff"
            },
            "dark": {
                "bg": "#2d2d2d",
                "fg": "#ffffff",
                "select_bg": "#404040",
                "select_fg": "#ffffff",
                "terminal_bg": "#1e1e1e",
                "terminal_fg": "#ffffff"
            },
            "high_contrast": {
                "bg": "#000000",
                "fg": "#ffffff",
                "select_bg": "#ffffff",
                "select_fg": "#000000",
                "terminal_bg": "#000000",
                "terminal_fg": "#ffff00"
            }
        }

        return themes.get(theme_name, themes["default"])

    def get_layout_config(self, layout_name: str = "default") -> Dict[str, Any]:
        """Get layout configuration."""
        layouts = {
            "default": {
                "grid_rows": 3,
                "grid_cols": 4,
                "master_panel_height": 150,
                "comm_log_height": 200
            },
            "compact": {
                "grid_rows": 2,
                "grid_cols": 6,
                "master_panel_height": 100,
                "comm_log_height": 150
            },
            "expanded": {
                "grid_rows": 4,
                "grid_cols": 3,
                "master_panel_height": 200,
                "comm_log_height": 250
            }
        }

        return layouts.get(layout_name, layouts["default"])

    def __str__(self) -> str:
        """String representation of configuration."""
        return f"DashboardConfig(base_dir={self.base_dir}, max_workers={self.max_workers})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"DashboardConfig(base_dir='{self.base_dir}', "
                f"max_workers={self.max_workers}, "
                f"update_intervals=({self.fast_update_interval}, {self.slow_update_interval}))")


# Global configuration instance
config = DashboardConfig()


def load_config(config_file: str = None) -> DashboardConfig:
    """Load configuration from file or environment."""
    if config_file is None:
        config_file = os.environ.get("DASHBOARD_CONFIG", "dashboard_config.json")

    config_path = Path(config_file)
    config.load_from_file(config_path)

    # Validate configuration
    if not config.validate_config():
        print("Warning: Configuration validation failed, using defaults")

    return config


def save_config(config_obj: DashboardConfig = None, config_file: str = None) -> None:
    """Save configuration to file."""
    if config_obj is None:
        config_obj = config

    if config_file is None:
        config_file = os.environ.get("DASHBOARD_CONFIG", "dashboard_config.json")

    config_path = Path(config_file)
    config_obj.save_to_file(config_path)


if __name__ == "__main__":
    # Test configuration
    test_config = load_config()
    print(f"Loaded configuration: {test_config}")
    print(f"Base directory: {test_config.base_dir}")
    print(f"Max workers: {test_config.max_workers}")
    print(f"Update intervals: {test_config.fast_update_interval}s, {test_config.slow_update_interval}s")