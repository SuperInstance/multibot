# Bidirectional Communication Protocol

## Overview

The Multi-Agent Communication Protocol provides a robust, SQLite-based message queue system for bidirectional communication between the Master orchestrator and Worker instances. The system includes priority handling, timeout management, and comprehensive message tracking.

## System Architecture

### Core Components

1. **MessageQueueManager**: SQLite-based message queue with persistence
2. **MasterCommunicationHandler**: Master-side message processing
3. **WorkerMCPServer**: Worker-side MCP tools for communication
4. **PriorityTimeoutHandler**: Advanced priority and timeout management

### Database Schema

#### Messages Table
```sql
CREATE TABLE messages (
    id TEXT PRIMARY KEY,              -- Unique message ID
    from_id TEXT NOT NULL,            -- Sender ID (master/worker-id)
    to_id TEXT NOT NULL,              -- Recipient ID (master/worker-id)
    message_type TEXT NOT NULL,       -- Message type enum
    content TEXT NOT NULL,            -- JSON message content
    priority INTEGER NOT NULL,        -- Priority level (1-9)
    created_at TEXT NOT NULL,         -- Creation timestamp
    expires_at TEXT,                  -- Optional expiration time
    status TEXT NOT NULL,             -- pending/delivered/acknowledged/failed
    retry_count INTEGER DEFAULT 0,    -- Number of retries
    max_retries INTEGER DEFAULT 3,    -- Maximum retry attempts
    response_to TEXT,                 -- ID of message this responds to
    metadata TEXT,                    -- Additional metadata JSON
    updated_at TEXT                   -- Last update timestamp
);
```

#### Task Assignments Table
```sql
CREATE TABLE task_assignments (
    task_id TEXT PRIMARY KEY,         -- Unique task ID
    worker_id TEXT NOT NULL,          -- Assigned worker
    description TEXT NOT NULL,        -- Task description
    context TEXT NOT NULL,            -- Task context JSON
    priority INTEGER NOT NULL,        -- Task priority
    created_at TEXT NOT NULL,         -- Creation timestamp
    assigned_at TEXT,                 -- Assignment timestamp
    started_at TEXT,                  -- Start timestamp
    completed_at TEXT,                -- Completion timestamp
    status TEXT NOT NULL,             -- assigned/accepted/in_progress/completed/failed
    result TEXT,                      -- Task result JSON
    error_message TEXT,               -- Error message if failed
    timeout_at TEXT,                  -- Task timeout
    dependencies TEXT                 -- Dependencies JSON array
);
```

## Message Types

### Master → Worker Messages

#### TASK_ASSIGN
Assign a new task to a worker.
```json
{
    "task_id": "task-123",
    "description": "Implement user authentication",
    "context": {
        "files": ["src/auth.py", "tests/test_auth.py"],
        "requirements": ["secure", "tested"],
        "dependencies": []
    },
    "priority": 7,
    "timeout_seconds": 3600
}
```

#### TASK_UPDATE
Modify an existing task.
```json
{
    "task_id": "task-123",
    "updates": {
        "priority": 9,
        "additional_requirements": ["performance optimized"],
        "deadline": "2024-01-01T18:00:00"
    }
}
```

#### CONTEXT_SHARE
Share information from other workers.
```json
{
    "context_type": "implementation_pattern",
    "context_data": {
        "pattern": "factory_method",
        "example_file": "src/user_factory.py",
        "documentation": "Use this pattern for user creation"
    },
    "source_worker": "worker-001"
}
```

#### GUIDANCE
Provide direction or correction.
```json
{
    "guidance_type": "correction",
    "guidance": "The authentication should use JWT tokens, not sessions",
    "context": {
        "file": "src/auth.py",
        "line_range": [45, 67],
        "reason": "Better scalability for microservices"
    }
}
```

#### PAUSE/RESUME
Control worker execution.
```json
{
    "reason": "resource_optimization",
    "timestamp": "2024-01-01T12:00:00",
    "duration": 300  // Optional: auto-resume after seconds
}
```

#### TERMINATE
Shutdown signal.
```json
{
    "reason": "task_completion",
    "graceful": true,
    "save_state": true,
    "commit_changes": true
}
```

### Worker → Master Messages

#### QUESTION
Request clarification to save tokens.
```json
{
    "question": "Should I implement OAuth2 or JWT for authentication?",
    "context": {
        "current_task": "task-123",
        "current_file": "src/auth.py",
        "requirements": ["secure", "scalable"],
        "options_considered": ["OAuth2", "JWT", "sessions"]
    },
    "urgency": "medium",
    "blocking": true
}
```

#### STATUS_UPDATE
Progress report.
```json
{
    "status": "working",
    "current_task": "task-123",
    "progress": 65,
    "task_status": "in_progress",
    "notes": "Authentication logic implemented, working on tests",
    "estimated_completion": "2024-01-01T16:00:00",
    "resource_usage": {
        "cpu_percent": 45.2,
        "memory_mb": 512,
        "disk_usage": 23.1
    }
}
```

#### TASK_COMPLETE
Finished task notification.
```json
{
    "task_id": "task-123",
    "result": {
        "summary": "Authentication system implemented with JWT",
        "files_created": ["src/auth.py", "src/jwt_utils.py"],
        "files_modified": ["src/main.py", "requirements.txt"],
        "tests_added": ["tests/test_auth.py"],
        "documentation": ["docs/authentication.md"],
        "performance_metrics": {
            "login_time_ms": 45,
            "token_validation_ms": 12
        }
    },
    "quality_checks": {
        "tests_passing": true,
        "code_coverage": 95.2,
        "linting_score": 9.8
    }
}
```

#### ERROR
Report issue.
```json
{
    "error_type": "dependency_conflict",
    "error_message": "Version conflict between jwt==2.1.0 and pyjwt==2.4.0",
    "task_id": "task-123",
    "file": "requirements.txt",
    "suggested_solution": "Update to pyjwt==2.4.0 and remove jwt dependency",
    "blocking": true,
    "stack_trace": "..." // Optional
}
```

#### RESOURCE_REQUEST
Need more context/access.
```json
{
    "resource_type": "file_access",
    "details": {
        "file_path": "config/database.yaml",
        "access_type": "read",
        "reason": "Need database connection string for auth setup"
    },
    "urgency": "high"
}
```

## Priority System

### Priority Levels
- **1 (LOW)**: Background tasks, status updates
- **3 (NORMAL)**: Regular task assignments, progress reports
- **5 (HIGH)**: Important guidance, context sharing
- **7 (URGENT)**: Questions blocking progress, errors
- **9 (CRITICAL)**: System control (pause/resume/terminate)

### Priority Processing
- Higher priority messages processed first
- Same priority messages processed FIFO
- Urgent messages can preempt normal processing
- Critical messages bypass normal queue

## Timeout Management

### Default Timeouts
- **Questions**: 5 minutes (escalate to human)
- **Task Assignments**: 1 minute (retry up to 3 times)
- **Status Updates**: 30 seconds (fail silently)
- **Guidance**: 2 minutes (retry up to 2 times)
- **Control Messages**: 30 seconds (escalate immediately)
- **Errors**: 3 minutes (escalate for investigation)
- **Resource Requests**: 4 minutes (retry up to 2 times)

### Timeout Actions
- **RETRY**: Resend message with higher priority
- **ESCALATE**: Send to human operator or higher authority
- **FAIL**: Mark as failed and continue
- **CALLBACK**: Execute custom timeout handler

## API Reference

### Master Tools

#### Core Communication
```python
# Send task assignment
await master_communication.send_task_assignment(
    worker_id="worker-001",
    task_id="task-123",
    description="Implement user authentication",
    context={"requirements": ["secure", "tested"]},
    priority=7,
    timeout_seconds=3600
)

# Ask question and wait for response
response = await master_communication.send_question_and_wait(
    worker_id="worker-001",
    question="Should I use JWT or OAuth2?",
    context={"current_task": "auth_implementation"},
    timeout_seconds=300
)

# Send guidance
await master_communication.send_guidance(
    worker_id="worker-001",
    guidance_type="correction",
    guidance="Use JWT tokens instead of sessions",
    context={"file": "src/auth.py", "reason": "scalability"}
)
```

#### Enhanced Tools
```python
# Get pending questions
questions = await get_pending_questions()

# Answer worker question
await answer_worker_question(
    message_id="msg-456",
    answer="Use JWT for stateless authentication",
    additional_context={"docs": "https://jwt.io/"}
)

# Share context between workers
await share_context_between_workers(
    source_worker_id="worker-001",
    target_worker_ids=["worker-002", "worker-003"],
    context_type="auth_pattern",
    context_data=json.dumps({"pattern": "jwt", "implementation": "..."})
)

# Broadcast to multiple workers
await broadcast_to_workers(
    worker_ids=["worker-001", "worker-002"],
    message_type="guidance",
    content={"guidance": "Use new coding standards"},
    priority=5
)

# Send urgent message
await urgent_worker_message(
    worker_id="worker-001",
    message_type="pause",
    content="System maintenance in progress",
    timeout_seconds=30
)
```

### Worker Tools

#### Communication
```python
# Send message to master
message_id = await send_to_master(
    message_type="question",
    content=json.dumps({
        "question": "Should I implement rate limiting?",
        "context": {"current_task": "api_security", "file": "src/api.py"}
    }),
    priority=7
)

# Check for new messages
messages = await check_for_messages()
# Returns: {"messages": [...], "count": 3}

# Acknowledge message
await acknowledge_message("msg-789")
```

#### Memory Management
```python
# Save context
await save_context(
    key="auth_implementation",
    content=json.dumps({
        "approach": "jwt",
        "files": ["src/auth.py", "src/jwt_utils.py"],
        "status": "completed"
    })
)

# Load context
context = await load_context("auth_implementation")

# List all contexts
contexts = await list_contexts()

# Clean old contexts
await clear_old_contexts(days=7)
```

#### Task Management
```python
# Get current task
task = await get_current_task()

# Update progress
await update_task_progress(
    task_id="task-123",
    progress=75,
    notes="Authentication tests completed"
)

# Mark complete
await mark_task_complete(
    task_id="task-123",
    result=json.dumps({
        "summary": "JWT authentication implemented",
        "files": ["src/auth.py", "tests/test_auth.py"]
    })
)

# Report error
await report_task_error(
    task_id="task-123",
    error="Dependency conflict with jwt library"
)
```

#### Status & Repository
```python
# Report status
await report_status()

# Log activity
await log_worker_activity("Implementing authentication middleware")

# Get current branch
branch = await get_my_branch()

# Get changed files
changes = await get_changed_files()

# Commit progress
commit_hash = await commit_progress("Implemented JWT token validation")
```

## Usage Examples

### Example 1: Task Assignment with Question Flow
```python
# Master assigns task
await orchestrator.master_communication.send_task_assignment(
    worker_id="worker-001",
    task_id="auth-task",
    description="Implement authentication system",
    context={"requirements": ["secure", "scalable"]},
    priority=7
)

# Worker receives and starts task
# Worker encounters question and asks master
await send_to_master(
    message_type="question",
    content=json.dumps({
        "question": "Should I use bcrypt or argon2 for password hashing?",
        "context": {"security_requirements": ["OWASP_compliant"]}
    }),
    priority=7
)

# Master answers question
await answer_worker_question(
    message_id="question-id",
    answer="Use argon2 for better security and performance",
    additional_context={"documentation": "https://argon2.online/"}
)

# Worker completes task
await mark_task_complete(
    task_id="auth-task",
    result=json.dumps({
        "summary": "Authentication implemented with argon2",
        "files": ["src/auth.py", "tests/test_auth.py"]
    })
)
```

### Example 2: Error Handling and Escalation
```python
# Worker encounters error
await report_task_error(
    task_id="auth-task",
    error="Database connection failed during user verification"
)

# Master receives error and provides guidance
await send_guidance_to_worker(
    worker_id="worker-001",
    guidance_type="correction",
    guidance="Use connection pooling and retry logic",
    context=json.dumps({"pattern": "circuit_breaker"})
)

# If error persists, escalate
await escalate_worker_issue(
    worker_id="worker-001",
    issue_type="database_connectivity",
    description="Persistent database connection failures",
    severity="high"
)
```

### Example 3: Context Sharing
```python
# Worker 1 implements a pattern
await save_context(
    key="database_pattern",
    content=json.dumps({
        "pattern": "repository_pattern",
        "implementation": "src/repositories/user_repository.py",
        "benefits": ["testability", "maintainability"]
    })
)

# Master shares this pattern with other workers
await share_context_between_workers(
    source_worker_id="worker-001",
    target_worker_ids=["worker-002", "worker-003"],
    context_type="database_pattern",
    context_data=await worker_001.load_context("database_pattern")
)
```

## Monitoring and Metrics

### Message Queue Statistics
```python
stats = await get_message_queue_stats()
```

Returns:
```json
{
    "queue_stats": {
        "message_stats": {
            "pending": 5,
            "delivered": 120,
            "acknowledged": 115,
            "failed": 2
        },
        "task_stats": {
            "assigned": 3,
            "in_progress": 2,
            "completed": 45,
            "failed": 1
        },
        "recent_messages_1h": 28
    },
    "priority_metrics": {
        "messages_processed": 142,
        "messages_timed_out": 3,
        "messages_retried": 7,
        "messages_escalated": 1,
        "priority_queue_size": 2
    }
}
```

### Worker Communication Status
```python
status = await get_worker_communication_status()
```

Returns:
```json
{
    "worker_count": 3,
    "workers": [
        {
            "worker_id": "worker-001",
            "last_update": "2024-01-01T12:30:00",
            "status": "working",
            "current_task": "auth-implementation",
            "progress": 75,
            "resource_usage": {
                "cpu_percent": 45.2,
                "memory_mb": 512
            }
        }
    ]
}
```

## Configuration

### Environment Variables
- `MESSAGE_QUEUE_DB`: SQLite database path (default: `/tmp/multibot/message_queue.db`)
- `WORKER_ID`: Unique worker identifier
- `WORKER_MODEL`: Claude model being used
- `WORKER_MEMORY_DIR`: Worker memory directory
- `WORKER_WORKING_DIR`: Worker working directory

### Timeout Configuration
```python
# Set custom timeout rules
priority_handler.set_timeout_rule(
    MessageType.QUESTION,
    TimeoutRule(
        message_type=MessageType.QUESTION,
        timeout_seconds=600,  # 10 minutes
        action=TimeoutAction.ESCALATE,
        max_retries=1
    )
)
```

## Best Practices

### For Masters
1. **Ask Specific Questions**: Instead of making assumptions, ask workers for clarification
2. **Provide Context**: Include relevant context when sharing information
3. **Use Appropriate Priorities**: Reserve high priorities for truly urgent messages
4. **Monitor Timeouts**: Watch for workers that consistently timeout
5. **Share Learnings**: Distribute useful patterns and solutions between workers

### For Workers
1. **Ask Early and Often**: Don't waste tokens on uncertain implementations
2. **Provide Rich Context**: Include relevant files, requirements, and constraints
3. **Update Progress Regularly**: Keep the master informed of your status
4. **Save Important Context**: Store reusable patterns and solutions
5. **Report Errors Promptly**: Don't struggle silently with issues

### Performance Optimization
1. **Batch Operations**: Use batch processing for multiple messages
2. **Appropriate Timeouts**: Don't set timeouts too short or too long
3. **Clean Up Old Data**: Regularly clean old messages and contexts
4. **Monitor Queue Size**: Watch for message queue buildup
5. **Use Priority Wisely**: Avoid priority inflation

## Troubleshooting

### Common Issues

1. **Message Not Delivered**
   - Check worker is active and responsive
   - Verify message queue database accessibility
   - Check for network connectivity issues

2. **Timeout Issues**
   - Review timeout settings for message type
   - Check worker processing capabilities
   - Monitor system resource usage

3. **Database Lock Issues**
   - Ensure proper connection handling
   - Check for long-running transactions
   - Monitor concurrent access patterns

4. **Priority Queue Backup**
   - Monitor queue size metrics
   - Check for stuck message processors
   - Review timeout and retry settings

### Debugging Tools
```python
# Get detailed message queue metrics
metrics = await orchestrator.priority_handler.get_metrics()

# Check pending timeouts
pending = len(orchestrator.priority_handler.pending_timeouts)

# Review recent escalations
escalations = await orchestrator.message_queue.get_message_stats()
```

This communication protocol provides a robust foundation for coordinated multi-agent development with proper error handling, timeout management, and scalable message processing.