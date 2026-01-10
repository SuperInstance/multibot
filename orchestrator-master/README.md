# Master Orchestrator MCP Server

The Master Orchestrator is a FastMCP-based server that coordinates multiple Claude Code worker instances for parallel development in a shared Git repository.

## Features

### Core Functionality
- **Worker Management**: Spawn, terminate, pause, and resume Claude Code workers
- **Task Assignment**: Queue and assign tasks to workers with priority scheduling
- **Communication Hub**: Bidirectional messaging between Master and Workers
- **Repository Management**: Git worktree creation and branch management
- **Monitoring Dashboard**: Visual GUI for monitoring worker terminals and activity

### Safety Features
- Resource monitoring and limits
- Dangerous task detection
- Merge conflict resolution
- Auto-commit protection
- Rate limiting for commits

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables (optional):
```bash
export MULTIBOT_LOG_LEVEL=INFO
export MULTIBOT_MAX_WORKERS=10
export MULTIBOT_REPO_PATH=/path/to/your/repo
```

3. Run the server:
```bash
python orchestrator_master.py
```

## Configuration

The orchestrator can be configured via environment variables:

### Server Configuration
- `MULTIBOT_HOST`: Server host (default: localhost)
- `MULTIBOT_PORT`: Server port (default: 8000)
- `MULTIBOT_LOG_LEVEL`: Logging level (default: INFO)

### Worker Configuration
- `MULTIBOT_MAX_WORKERS`: Maximum concurrent workers (default: 10)
- `MULTIBOT_WORKER_TIMEOUT`: Worker timeout in seconds (default: 300)
- `MULTIBOT_HEARTBEAT_INTERVAL`: Heartbeat interval in seconds (default: 30)

### Repository Configuration
- `MULTIBOT_REPO_PATH`: Git repository path (default: current directory)
- `MULTIBOT_WORKTREE_CLEANUP`: Auto-cleanup worktrees (default: true)

### Task Configuration
- `MULTIBOT_TASK_RETRY_LIMIT`: Maximum task retries (default: 3)
- `MULTIBOT_TASK_TIMEOUT`: Task timeout in seconds (default: 1800)

### Safety Configuration
- `MULTIBOT_AUTO_MERGE`: Enable automatic merging (default: false)
- `MULTIBOT_MANUAL_APPROVAL`: Require manual approval for critical changes (default: true)

## API Reference

### Worker Management

#### spawn_worker
Spawn a new worker instance.

**Parameters:**
- `worker_id` (str): Unique identifier for the worker
- `model` (str): Claude model to use (default: "sonnet")
- `working_dir` (str): Working directory path
- `branch_name` (str): Git branch name

**Returns:**
```json
{
  "status": "success",
  "worker_id": "worker-1",
  "message": "Worker spawned successfully",
  "details": {
    "pid": 12345,
    "terminal_session": "worker-1-terminal"
  }
}
```

#### terminate_worker
Terminate a worker instance.

**Parameters:**
- `worker_id` (str): Worker identifier

#### pause_worker / resume_worker
Pause or resume a worker instance.

**Parameters:**
- `worker_id` (str): Worker identifier

#### list_workers
Get status of all workers.

**Returns:**
```json
{
  "status": "success",
  "workers": [
    {
      "worker_id": "worker-1",
      "status": "active",
      "current_task": "task-123",
      "branch": "worker-1-feature",
      "last_heartbeat": "2024-01-01T12:00:00"
    }
  ],
  "total_count": 1
}
```

### Task Management

#### assign_task
Assign a task to a specific worker.

**Parameters:**
- `worker_id` (str): Target worker
- `task_description` (str): Task description
- `context` (list): Context information
- `priority` (int): Task priority (1-10)

#### reassign_task
Reassign a task between workers.

**Parameters:**
- `task_id` (str): Task identifier
- `from_worker` (str): Source worker
- `to_worker` (str): Target worker

#### get_task_status
Get status of a specific task.

**Parameters:**
- `task_id` (str): Task identifier

### Communication

#### send_to_worker
Send a message to a specific worker.

**Parameters:**
- `worker_id` (str): Target worker
- `message` (str): Message content

#### receive_from_worker
Receive messages from a worker.

**Parameters:**
- `worker_id` (str): Source worker

#### broadcast_to_workers
Broadcast a message to all workers.

**Parameters:**
- `message` (str): Message content

### Repository Management

#### create_worktree
Create a Git worktree for a worker.

**Parameters:**
- `worker_id` (str): Worker identifier
- `branch_name` (str): Branch name

#### merge_worker_branch
Merge a worker's branch into target branch.

**Parameters:**
- `worker_id` (str): Worker identifier
- `target_branch` (str): Target branch (default: "main")

#### resolve_conflicts
Resolve conflicts between worker branches.

**Parameters:**
- `worker_branches` (list): List of worker branch names

### Monitoring

#### open_monitoring_dashboard
Open the visual monitoring dashboard.

#### log_activity
Log activity for a worker.

**Parameters:**
- `worker_id` (str): Worker identifier
- `activity` (str): Activity description

#### get_activity_log
Get activity log for a worker.

**Parameters:**
- `worker_id` (str): Worker identifier
- `since_timestamp` (float, optional): Timestamp filter

## File Structure

```
orchestrator-master/
├── orchestrator_master.py    # Main MCP server
├── worker_manager.py         # Worker lifecycle management
├── task_queue.py            # Task scheduling and management
├── communication.py         # Master-Worker messaging
├── repo_manager.py          # Git operations
├── monitoring_gui.py        # Visual dashboard
├── config.py               # Configuration and error handling
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Error Handling

The orchestrator includes comprehensive error handling:

- **Automatic retry**: Failed tasks are automatically retried up to the configured limit
- **Worker recovery**: Dead workers are detected and can be automatically restarted
- **Resource monitoring**: System resources are monitored to prevent overload
- **Safety checks**: Dangerous operations are blocked or require manual approval

## Monitoring and Logging

### Logging
- Logs are written to `/tmp/multibot/logs/`
- Separate log files for each module
- Rotating log files to prevent disk space issues
- Error-specific logs for debugging

### Monitoring Dashboard
- Visual GUI showing all worker terminals
- Real-time activity feed
- System metrics display
- Worker status and controls
- Web dashboard export capability

## Safety Features

### Resource Protection
- Maximum worker limits
- Memory usage monitoring
- Disk space checks
- Process monitoring

### Git Safety
- Worktree isolation
- Branch protection
- Merge conflict detection
- Auto-commit with safety checks

### Task Safety
- Dangerous command detection
- File change limits
- Commit rate limiting
- Manual approval requirements

## Troubleshooting

### Common Issues

1. **Worker fails to spawn**
   - Check Git repository validity
   - Verify Claude Code is installed
   - Check system resources

2. **Communication failures**
   - Check file permissions in `/tmp/multibot/`
   - Verify worker heartbeat files
   - Check network connectivity

3. **Merge conflicts**
   - Use `resolve_conflicts` tool
   - Check for file permission issues
   - Verify Git configuration

4. **Performance issues**
   - Reduce `MULTIBOT_MAX_WORKERS`
   - Increase system resources
   - Check disk space

### Log Analysis
```bash
# View main orchestrator logs
tail -f /tmp/multibot/logs/orchestrator.log

# View worker-specific logs
tail -f /tmp/multibot/logs/worker_manager.log

# View error logs
tail -f /tmp/multibot/logs/orchestrator_errors.log
```

### State Recovery
```bash
# Check system state
ls -la /tmp/multibot/state/

# Check communication state
ls -la /tmp/multibot/communication/

# Clean up if needed
rm -rf /tmp/multibot/state/*
rm -rf /tmp/multibot/communication/*
```

## Development

### Adding New Features
1. Create feature branch
2. Add tests if applicable
3. Update documentation
4. Test with multiple workers
5. Ensure safety compliance

### Testing
```bash
# Run basic functionality test
python -c "
import asyncio
from orchestrator_master import orchestrator
asyncio.run(orchestrator.initialize())
print('Orchestrator initialized successfully')
"
```

## License

This software is part of the multibot orchestration system. See main project license for details.