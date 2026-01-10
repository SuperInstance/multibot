# Enhanced Worker Lifecycle Management System

## Overview

The Enhanced Worker Lifecycle Management System provides comprehensive control over Claude Code worker processes with proper directory structure, configuration generation, terminal visualization, and state management. This system implements the complete worker lifecycle from spawning to termination with full process control and monitoring.

## Architecture

### Directory Structure

Each worker gets its own dedicated directory structure:

```
/workspace/workers/{worker_id}/
├── worktree/                    # Git worktree (isolated branch)
├── memory/                      # Context and state files
│   ├── worker_state.json        # Current worker state
│   ├── heartbeat.json          # Process health monitoring
│   └── *.json                  # Context memory files
├── logs/                       # Activity and error logs
│   ├── worker_{worker_id}.log  # Main worker log
│   └── activity.log            # Activity timeline
└── config/                     # Worker-specific configuration
    ├── claude_config.json      # Claude Code configuration
    ├── memory_server.py        # Memory MCP server
    └── communication_server.py # Communication MCP server
```

### Key Components

1. **WorkerLifecycleManager**: Main orchestration class
2. **TerminalManager**: Enhanced terminal visualization
3. **WorkerConfig**: Configuration management
4. **WorkerProcess**: Process state tracking
5. **Worker Launch Script**: Standalone process launcher

## Worker Spawning Process

### 1. Configuration Creation
```python
worker_config = WorkerConfig(
    worker_id="worker-001",
    model="sonnet",
    task_name="implement-feature-x",
    branch_name="worker-001-implement-feature-x",
    working_dir=Path("/workspace/workers/worker-001"),
    # ... other paths
)
```

### 2. Directory Structure Setup
- Creates complete directory hierarchy
- Sets proper permissions
- Initializes log files

### 3. Git Worktree Creation
```bash
git checkout -b worker-001-implement-feature-x main
git worktree add ./workers/worker-001/worktree worker-001-implement-feature-x
```

### 4. Claude Configuration Generation
Creates `claude_config.json` with worker-specific MCP servers:
- **worker-filesystem**: File operations in worktree
- **worker-memory**: Context management
- **worker-communication**: Master-worker messaging
- **worker-git**: Git operations

### 5. MCP Server Scripts Creation
Auto-generates Python MCP servers for:
- Memory management (`memory_server.py`)
- Communication (`communication_server.py`)

### 6. Process Launch
Uses the `launch_worker.py` script for proper subprocess management:
```bash
python3 launch_worker.py \
  --worker-id worker-001 \
  --config /path/to/claude_config.json \
  --working-dir /path/to/worktree \
  --memory-dir /path/to/memory \
  --logs-dir /path/to/logs
```

### 7. Terminal Visualization
Creates terminal session using:
- **tmux** (preferred): Full terminal multiplexer with monitoring
- **screen** (fallback): Basic terminal multiplexer
- **Basic terminal** (last resort): Simple terminal window

## Terminal Visualization Features

### tmux Integration
- Dedicated session per worker: `multibot-worker-{worker_id}`
- Split panes: main work area + monitoring pane
- Real-time status updates in title bar
- Worker information display
- Activity monitoring

### Terminal Layout
```
┌─ Worker-001-implement-feature-x [ACTIVE] ─────────────────┐
│ Main Claude Code session                                  │
│                                                           │
│ > claude                                                  │
│ Claude Code starting...                                   │
│                                                           │
├───────────────────────────────────────────────────────────┤
│ Worker: worker-001                                        │
│ Status: active                                           │
│ Created: 14:30:25                                        │
│ Last Activity: 14:45:12                                  │
│ Heartbeat: 14:45:10 - active                            │
└───────────────────────────────────────────────────────────┘
```

## Worker Process Management

### Process Lifecycle States
- **initializing**: Worker starting up
- **starting**: Process launched, waiting for ready signal
- **active**: Fully operational
- **paused**: Process suspended (SIGSTOP)
- **terminating**: Graceful shutdown in progress
- **dead**: Process terminated
- **error**: Error state

### Heartbeat Monitoring
Workers send heartbeat every 30 seconds:
```json
{
  "worker_id": "worker-001",
  "status": "active",
  "timestamp": 1697123456.789,
  "pid": 12345
}
```

### Resource Monitoring
Tracks per worker:
- CPU usage percentage
- Memory usage (MB and percentage)
- Number of threads
- Process status

## Memory and State Management

### Worker State Persistence
```json
{
  "config": { ... },
  "pid": 12345,
  "tmux_session": "multibot-worker-worker-001",
  "start_time": "2024-01-01T12:00:00",
  "status": "active",
  "current_task": "task-123",
  "memory_state": {
    "current_task": {
      "task_id": "task-123",
      "description": "Implement user authentication",
      "started_at": "2024-01-01T12:30:00"
    }
  }
}
```

### Context Memory
Workers maintain context through MCP memory server:
```python
# Save context
save_context("current_files", {
    "main_file": "src/auth.py",
    "test_file": "tests/test_auth.py",
    "config_file": "config/auth.yaml"
})

# Load context
files = load_context("current_files")
```

## Communication System

### Master-Worker Messaging
File-based reliable messaging:
```
/tmp/multibot/communication/
├── workers/
│   └── worker-001/
│       ├── inbox/           # Messages from Master
│       ├── outbox/          # Messages to Master
│       └── processed/       # Archived messages
```

### Message Types
- **TASK_ASSIGNMENT**: New task assignment
- **STATUS_REQUEST**: Status inquiry
- **QUESTION**: Worker asking Master
- **PROGRESS**: Task progress update
- **TERMINATE**: Shutdown signal

### Communication MCP Server
Workers can communicate with Master:
```python
# Ask question to Master
ask_master_question("Should I use async/await for this API?", {
    "context": "building REST endpoints",
    "current_file": "src/api.py"
})

# Report progress
report_progress("task-123", "in_progress", {
    "completed": ["authentication", "validation"],
    "working_on": "authorization",
    "next": ["testing", "documentation"]
})
```

## Worker Termination Process

### Graceful Termination
1. **Save Current State**: Persist memory and configuration
2. **Commit Changes**: Auto-commit with detailed message
3. **Process Shutdown**: SIGTERM → wait → SIGKILL if needed
4. **Archive Logs**: Copy logs to central archive
5. **Terminal Cleanup**: Destroy terminal sessions
6. **Worktree Cleanup**: Remove or preserve as requested

### Termination Options
```python
await terminate_worker(
    worker_id="worker-001",
    save_state=True,        # Save final state
    commit_changes=True,    # Git commit changes
    preserve_worktree=False # Keep worktree after termination
)
```

### Commit Message Format
```
Worker worker-001 final commit

Task: implement-feature-x
Model: sonnet
Duration: 1800s
Last Task: task-123

Auto-committed by multibot orchestrator
```

## API Reference

### Core Methods

#### `spawn_worker(worker_id, model, task_name, base_branch="main")`
Spawn a new worker with full lifecycle management.

**Parameters:**
- `worker_id`: Unique identifier
- `model`: Claude model ("sonnet", "haiku", etc.)
- `task_name`: Human-readable task description
- `base_branch`: Git branch to branch from

**Returns:**
```json
{
  "worker_id": "worker-001",
  "model": "sonnet",
  "task_name": "implement-feature-x",
  "branch": "worker-001-implement-feature-x",
  "working_dir": "/workspace/workers/worker-001/worktree",
  "pid": 12345,
  "tmux_session": "multibot-worker-worker-001",
  "status": "active"
}
```

#### `terminate_worker(worker_id, save_state=True, commit_changes=True, preserve_worktree=False)`
Gracefully terminate a worker.

#### `pause_worker(worker_id)` / `resume_worker(worker_id)`
Suspend/resume worker process (SIGSTOP/SIGCONT).

#### `get_worker_status(worker_id)`
Get comprehensive worker status including resource usage.

#### `update_worker_task(worker_id, task_id, task_description)`
Update worker's current task assignment.

### Terminal Management

#### `focus_terminal(worker_id)`
Bring worker's terminal to foreground.

#### `send_to_terminal(worker_id, text)`
Send text to worker's terminal.

#### `capture_terminal_output(worker_id)`
Capture current terminal contents.

## Configuration

### Environment Variables
- `MULTIBOT_WORKSPACE`: Base workspace directory (default: `/workspace`)
- `MULTIBOT_WORKER_TIMEOUT`: Worker initialization timeout (default: 60s)
- `MULTIBOT_HEARTBEAT_INTERVAL`: Heartbeat frequency (default: 30s)

### Worker Configuration Template
```json
{
  "worker_id": "{worker_id}",
  "model": "{model}",
  "working_directory": "{worktree_dir}",
  "memory_directory": "{memory_dir}",
  "mcpServers": {
    "worker-filesystem": { ... },
    "worker-memory": { ... },
    "worker-communication": { ... },
    "worker-git": { ... }
  },
  "experimental": {
    "controllerMode": "worker",
    "workerId": "{worker_id}",
    "autoSave": true,
    "contextPreservation": true
  }
}
```

## Monitoring and Debugging

### Log Files
- **Main log**: `/workspace/workers/{worker_id}/logs/worker_{worker_id}.log`
- **Activity log**: `/workspace/workers/{worker_id}/logs/activity.log`
- **Orchestrator log**: `/tmp/multibot/logs/orchestrator.log`

### Worker Archives
Terminated workers are archived to:
```
/tmp/multibot/worker_archives/{worker_id}/
├── final_state.json     # Final worker state
├── logs/               # Copied log files
└── memory/            # Copied memory files
```

### Health Monitoring
```python
# Check worker health
status = await get_worker_status("worker-001")
print(f"CPU: {status['resource_usage']['cpu_percent']}%")
print(f"Memory: {status['resource_usage']['memory_mb']}MB")
print(f"Status: {status['status']}")
```

### Terminal Session Management
```python
# List all terminal sessions
sessions = await terminal_manager.list_sessions()

# Focus worker terminal
await terminal_manager.focus_terminal("worker-001")

# Send command to worker
await terminal_manager.send_to_terminal("worker-001", "ls -la")
```

## Error Handling and Recovery

### Automatic Recovery
- Dead process detection
- Stale worktree cleanup
- Orphaned terminal cleanup
- State file corruption recovery

### Manual Intervention
```python
# Force cleanup failed worker
await force_cleanup_worker(worker_process)

# Recover from previous session
await recover_existing_workers()

# Manual terminal cleanup
await terminal_manager.destroy_terminal("worker-001")
```

### Common Issues and Solutions

1. **Worker fails to start**
   - Check Git repository validity
   - Verify Claude Code installation
   - Check workspace permissions
   - Review launch script logs

2. **Terminal not showing**
   - Verify tmux/screen installation
   - Check terminal manager logs
   - Test basic terminal creation

3. **Communication failures**
   - Check message directory permissions
   - Verify heartbeat files
   - Test MCP server connectivity

4. **Git worktree issues**
   - Check branch conflicts
   - Verify Git repository state
   - Manual worktree cleanup if needed

## Best Practices

### Worker Management
1. Always use descriptive task names
2. Monitor resource usage regularly
3. Clean up terminated workers
4. Use preserve_worktree for debugging only

### Terminal Usage
1. Use tmux when available for best experience
2. Monitor worker terminals regularly
3. Use focus_terminal for quick access
4. Capture terminal output for debugging

### Memory Management
1. Save important context frequently
2. Use structured context keys
3. Clean up old context periodically
4. Monitor memory usage per worker

### Error Handling
1. Always check worker status before operations
2. Use graceful termination when possible
3. Archive logs before cleanup
4. Monitor system resources

## Performance Considerations

### Resource Usage
- Each worker uses ~100-500MB RAM
- Terminal sessions add ~10MB overhead
- Git worktrees use minimal disk space
- MCP servers are lightweight

### Scalability
- Tested with up to 20 concurrent workers
- Linear resource scaling
- Network I/O minimal (file-based communication)
- CPU usage depends on worker tasks

### Optimization Tips
1. Use heartbeat monitoring to detect issues early
2. Clean up unused workers promptly
3. Monitor system resources continuously
4. Use appropriate models for task complexity

## Integration Examples

### Basic Worker Spawn
```python
result = await orchestrator.worker_lifecycle.spawn_worker(
    worker_id="feature-worker-1",
    model="sonnet",
    task_name="implement-user-auth",
    base_branch="develop"
)
print(f"Worker spawned: {result['tmux_session']}")
```

### Task Assignment with Monitoring
```python
# Assign task
task_id = await orchestrator.task_queue.assign_task(
    worker_id="feature-worker-1",
    task_description="Implement OAuth2 authentication",
    context=["src/auth/", "docs/auth.md"],
    priority=7
)

# Monitor progress
while True:
    status = await orchestrator.worker_lifecycle.get_worker_status("feature-worker-1")
    if status["status"] == "completed":
        break
    await asyncio.sleep(30)
```

### Graceful Shutdown
```python
# Save state and commit before shutdown
result = await orchestrator.worker_lifecycle.terminate_worker(
    worker_id="feature-worker-1",
    save_state=True,
    commit_changes=True,
    preserve_worktree=True  # Keep for review
)
print(f"Final commit: {result.get('final_commit', 'none')}")
```

This enhanced worker lifecycle system provides complete control over Claude Code worker processes while maintaining isolation, monitoring, and proper resource management.