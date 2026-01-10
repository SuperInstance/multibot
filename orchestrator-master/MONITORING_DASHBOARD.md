# Multi-Terminal Monitoring Dashboard

## Overview

The Multi-Terminal Monitoring Dashboard provides real-time visual monitoring of the Master orchestrator and all Worker Claude Code instances. It features a comprehensive GUI with terminal windows, status displays, communication logs, and interactive controls.

## Features

### 📊 Visual Monitoring
- **Grid Layout**: Configurable terminal windows (default 4, max 12)
- **Real-time Updates**: Live terminal output and status indicators
- **Status Indicators**: Color-coded worker status (🟢 Active, 🟡 Waiting, 🔴 Paused, ⚫ Error)
- **Progress Bars**: Visual task completion progress
- **Expandable Terminals**: Click to expand any terminal full-screen

### 🎛️ Master Control Panel
- **System Overview**: Total workers active, tasks completed/in progress/queued
- **Master Activity**: Current Master orchestrator activity
- **Repository Status**: Branch information and pending merges
- **Control Buttons**: Spawn workers, pause/resume all, system status

### 📡 Communication Log
- **Master ↔ Worker Messages**: Real-time communication monitoring
- **Message Filtering**: Filter by worker, message type, or content
- **Export Functionality**: Save logs for analysis
- **Auto-scroll**: Latest messages always visible

### ⌨️ Keyboard Shortcuts
- **Space**: Pause/Resume selected worker
- **Ctrl+T**: Terminate selected worker
- **Ctrl+M**: Send message to Master
- **Ctrl+N**: Spawn new worker
- **F11**: Toggle fullscreen
- **F5**: Refresh all data

### 🖱️ Context Menus
Right-click on any worker terminal for:
- View full logs
- Send message to worker
- View worker's memory files
- View worker's git diff
- Copy worker ID

## Installation

### Prerequisites
- Python 3.8 or higher
- tkinter (usually included with Python)
- Required Python packages (installed automatically)

### Quick Setup

1. **Run the setup script:**
   ```bash
   python3 setup_dashboard.py
   ```

2. **Test in demo mode:**
   ```bash
   python3 run_dashboard.py --demo
   ```

3. **Run with orchestrator integration:**
   ```bash
   python3 run_dashboard.py
   ```

### Manual Installation

1. **Install dependencies:**
   ```bash
   pip install fastmcp psutil asyncio-throttle
   ```

2. **Create directory structure:**
   ```bash
   mkdir -p /tmp/multibot/{workers,logs,config}
   ```

3. **Run dashboard:**
   ```bash
   python3 run_dashboard.py
   ```

## Usage

### Starting the Dashboard

#### Demo Mode (No Orchestrator Required)
```bash
python3 run_dashboard.py --demo
```
- Shows sample workers with simulated data
- Perfect for testing and demonstration
- No real orchestrator connection needed

#### Production Mode (With Orchestrator)
```bash
python3 run_dashboard.py
```
- Connects to real orchestrator system
- Shows live worker data and communications
- Full interactive functionality

#### Custom Configuration
```bash
python3 run_dashboard.py --config my_config.json --geometry 1600x1000
```

### Command Line Options

```bash
python3 run_dashboard.py [OPTIONS]

Options:
  -h, --help              Show help message
  -d, --demo              Run in demo mode
  -c, --config FILE       Configuration file path
  -g, --geometry WxH      Window geometry (e.g., 1400x900)
  -w, --max-workers N     Maximum workers to display
  -u, --update-interval S Update interval in seconds
  -l, --log-level LEVEL   Logging level (DEBUG, INFO, WARNING, ERROR)
  -v, --version           Show version
```

### Worker Terminal Display

Each worker terminal shows:
- **Header**: Worker ID, model (Opus/Sonnet/Haiku), status icon
- **Branch Info**: Current Git branch
- **Task Info**: Current task title and description
- **Progress Bar**: Task completion percentage
- **Terminal Output**: Live scrolling output (last 100 lines)
- **Control Buttons**: Pause/Resume, Terminate, Expand

### Status Indicators

| Icon | Status | Description |
|------|--------|-------------|
| 🟢 | Active/Working | Worker is actively processing tasks |
| 🟡 | Waiting/Idle | Worker is waiting for tasks or dependencies |
| 🔴 | Paused | Worker is paused (can be resumed) |
| ⚫ | Error | Worker encountered an error |
| ⚪ | Terminated | Worker has been terminated |
| 🔵 | Initializing | Worker is starting up |

### Interactive Features

#### Worker Selection
- **Click** any worker terminal to select it
- **Selected worker** highlighted with thick border
- **Keyboard shortcuts** apply to selected worker

#### Expandable View
- **Double-click** or **Expand button** to show worker full-screen
- **Escape** or **Expand button** again to return to grid view
- **Expanded view** shows larger terminal and detailed information

#### Context Menu Actions
**Right-click** on any worker for:

**View Full Logs**
- Opens complete log history in new window
- Searchable and scrollable
- Can be saved to file

**Send Message to Worker**
- Direct communication with specific worker
- Message appears in worker's communication queue
- Useful for providing guidance or corrections

**View Memory Files**
- Shows worker's saved context files
- File sizes and modification dates
- Can open individual files for inspection

**View Git Diff**
- Shows current uncommitted changes
- Syntax-highlighted diff output
- Helps track worker progress

## Configuration

### Configuration File (dashboard_config.json)

```json
{
  "window_geometry": "1400x900",
  "max_workers": 12,
  "fast_update_interval": 1.0,
  "slow_update_interval": 5.0,
  "max_log_lines": 100,
  "terminal_font": ["Consolas", 8],
  "default_worker_model": "sonnet",
  "log_level": "INFO",
  "auto_discover_workers": true
}
```

### Environment Variables

```bash
# Base directory for multibot system
export MULTIBOT_BASE_DIR="/tmp/multibot"

# Dashboard configuration file
export DASHBOARD_CONFIG="my_dashboard_config.json"

# Worker discovery
export WORKER_DISCOVERY_INTERVAL="5.0"
```

### Customization Options

#### Themes
- **Default**: Light theme with standard colors
- **Dark**: Dark theme for reduced eye strain
- **High Contrast**: High contrast for accessibility

#### Layouts
- **Default**: 3x4 grid (12 workers max)
- **Compact**: 2x6 grid for wider screens
- **Expanded**: 4x3 grid for taller displays

#### Update Intervals
- **Fast Updates**: Terminal output and status (1 second)
- **Slow Updates**: Statistics and discovery (5 seconds)
- **Message Monitoring**: Communication log (0.5 seconds)

## Integration with Orchestrator

### Data Sources

The dashboard integrates with multiple orchestrator components:

**Message Queue Database**
- Real-time communication monitoring
- Message history and statistics
- Worker registration and heartbeats

**Worker Lifecycle Manager**
- Worker process states and controls
- Directory structure and file access
- Process management (pause/resume/terminate)

**File System Monitoring**
- Worker log files
- Memory and context files
- Git repository status

### Real-time Updates

**Worker Discovery**
- Automatically detects new workers
- Removes terminated workers from display
- Updates worker metadata and status

**Log Streaming**
- Monitors worker log files for changes
- Updates terminal displays in real-time
- Maintains scroll position and history

**Communication Monitoring**
- Displays Master ↔ Worker messages
- Shows message types, priorities, and content
- Updates communication statistics

### Action Integration

**Worker Controls**
```python
# Dashboard actions trigger real orchestrator commands
pause_worker(worker_id)     # → orchestrator.pause_worker()
resume_worker(worker_id)    # → orchestrator.resume_worker()
terminate_worker(worker_id) # → orchestrator.terminate_worker()
```

**Message Sending**
```python
# Send messages through orchestrator message queue
send_message_to_worker(worker_id, message)  # → message_queue.send_message()
```

**System Commands**
```python
# System-wide operations
spawn_new_worker(model, task)  # → orchestrator.spawn_worker()
pause_all_workers()            # → orchestrator.pause_all()
```

## Architecture

### Core Components

```
monitoring_dashboard.py      # Main GUI components and layout
├── WorkerTerminalWidget     # Individual worker display
├── MasterControlPanel       # System overview and controls
├── CommunicationLogPanel    # Message log display
└── MonitoringDashboard      # Main application class

dashboard_integration.py     # Orchestrator integration
├── DashboardDataProvider    # Real-time data collection
├── IntegratedDashboard      # Enhanced dashboard with real data
└── Action handlers          # Worker control integration

dashboard_config.py          # Configuration management
├── DashboardConfig          # Configuration class
├── Theme management         # UI themes and layouts
└── Validation               # Config validation and defaults

run_dashboard.py            # Main entry point and CLI
├── Argument parsing        # Command line interface
├── Integration setup       # Orchestrator connection
└── Error handling          # Graceful error management
```

### Data Flow

```
Orchestrator System → DashboardDataProvider → MonitoringDashboard → GUI Updates
                   ↓                        ↓                    ↑
             Message Queue              Worker Data          User Actions
                   ↓                        ↓                    ↓
             Communication Log        Terminal Updates    Action Handlers
```

### Threading Model

**Main Thread**: GUI event loop and user interactions
**Update Thread**: Data collection and dashboard updates
**Integration Thread**: Async orchestrator communication
**File Monitoring**: Worker log file watching

## Troubleshooting

### Common Issues

**Dashboard won't start**
```bash
# Check Python version
python3 --version  # Should be 3.8+

# Check tkinter
python3 -c "import tkinter; print('tkinter OK')"

# Check dependencies
python3 -c "import fastmcp, psutil; print('deps OK')"
```

**No workers showing**
```bash
# Check orchestrator is running
ls /tmp/multibot/workers/

# Check message queue database
ls /tmp/multibot/message_queue.db

# Run in demo mode to test GUI
python3 run_dashboard.py --demo
```

**Slow performance**
```bash
# Increase update intervals
python3 run_dashboard.py --update-interval 2.0

# Reduce max workers
python3 run_dashboard.py --max-workers 6

# Check system resources
top  # Look for high CPU/memory usage
```

**Communication log empty**
```bash
# Check message queue
sqlite3 /tmp/multibot/message_queue.db "SELECT COUNT(*) FROM messages;"

# Check permissions
ls -la /tmp/multibot/

# Restart with debug logging
python3 run_dashboard.py --log-level DEBUG
```

### Debug Mode

```bash
# Run with maximum debug information
python3 run_dashboard.py --log-level DEBUG

# Check log file
tail -f /tmp/multibot/logs/dashboard.log

# Test individual components
python3 -c "from monitoring_dashboard import MonitoringDashboard; print('GUI OK')"
python3 -c "from dashboard_integration import DashboardDataProvider; print('Integration OK')"
```

### Performance Tuning

**For slower systems:**
```json
{
  "fast_update_interval": 2.0,
  "slow_update_interval": 10.0,
  "max_log_lines": 50,
  "gui_update_batch_size": 5
}
```

**For faster systems:**
```json
{
  "fast_update_interval": 0.5,
  "slow_update_interval": 2.0,
  "max_log_lines": 200,
  "max_concurrent_updates": 10
}
```

## Extension Points

### Custom Themes
Add new themes in `dashboard_config.py`:
```python
themes["my_theme"] = {
    "bg": "#custom_bg",
    "fg": "#custom_fg",
    "terminal_bg": "#custom_terminal"
}
```

### Additional Widgets
Extend `MonitoringDashboard` class:
```python
class CustomDashboard(MonitoringDashboard):
    def create_custom_panel(self):
        # Add your custom monitoring panel
        pass
```

### Data Sources
Extend `DashboardDataProvider`:
```python
class CustomDataProvider(DashboardDataProvider):
    async def get_custom_metrics(self):
        # Add custom data collection
        pass
```

This monitoring dashboard provides comprehensive visual oversight of the multi-agent orchestration system, enabling real-time monitoring, control, and debugging of all system components.