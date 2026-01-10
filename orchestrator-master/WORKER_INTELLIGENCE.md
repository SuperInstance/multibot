# Worker Intelligence Layer

## Overview

The Worker Intelligence Layer adds autonomous decision-making, context management, error recovery, and collaboration awareness to Worker Claude Code instances. This system enables workers to make intelligent decisions about when to ask for help versus solving problems independently, manage their context efficiently, and coordinate with other workers to avoid conflicts.

## Core Intelligence Features

### 1. SHOULD_ASK_MASTER Decision Logic

The intelligence layer implements sophisticated decision logic to determine when workers should ask the Master for guidance versus attempting to solve problems independently.

#### Decision Criteria

```python
def should_ask_master(question_type, estimated_token_cost, confidence_level, context):
    """
    Decision criteria:
    - If token cost > 5000 tokens, ask Master (resource optimization)
    - If confidence < 60%, ask Master (quality assurance)
    - If question about overall architecture/design, ask Master (coordination)
    - If question about other workers' areas, ask Master (collaboration)
    - If question about this worker's specific implementation, don't ask (independence)
    """
```

#### Question Types

**Always Ask Master:**
- `overall_architecture`: Architecture decisions affect entire system
- `design_patterns`: Patterns affect other workers
- `inter_worker_coordination`: Cross-worker coordination required
- `security_policy`: Security decisions need approval
- `performance_optimization`: May affect other components
- `database_schema`: Database changes affect multiple workers
- `api_design`: API design affects other workers and clients
- `deployment_strategy`: Deployment affects entire system

**Usually Work Independently:**
- `implementation_detail`: Local implementation decisions
- `local_debugging`: Debug issues independently first
- `code_formatting`: Worker's responsibility
- `local_testing`: Independent testing
- `documentation`: Independent documentation
- `refactoring`: Local refactoring decisions

#### Usage Example

```python
# Worker considering whether to ask about authentication implementation
decision = await should_ask_master_decision(
    question_type="implementation_detail",
    estimated_token_cost=2000,
    confidence_level=0.8,
    context='{"current_file": "auth.py", "task": "implement_login"}'
)

# Returns: {"should_ask_master": false, "reason": "Low cost and reasonable confidence"}
```

### 2. Automatic Context Management

#### Auto-Save Context
Workers automatically save conversation context when it exceeds 8000 tokens to prevent context overflow and maintain continuity.

```python
# Automatically triggered when context gets large
await auto_save_context_check(
    context_content="<long conversation>",
    context_key="authentication_implementation"
)
```

#### Intelligent Context Loading
Workers load relevant previous context based on current task keywords and file patterns.

```python
# Load context relevant to current task
await load_relevant_context_for_task('{"description": "implement user registration", "files": ["auth.py"]}')
```

#### Context Features
- **Automatic summarization**: Key points extracted from long contexts
- **Relevance matching**: Context loaded based on keyword overlap and file patterns
- **SQLite storage**: Persistent context with metadata
- **Token counting**: Rough estimation for context size management

### 3. Error Recovery System

#### Multi-Level Recovery
Workers attempt to recover from errors independently before escalating to Master:

1. **Attempt 1**: Automated recovery using error-specific strategies
2. **Attempt 2**: Alternative recovery approach
3. **Escalate**: Ask Master for help after 2 failed attempts

#### Error Recovery Strategies

**Import Errors:**
- Check for common typos in module names
- Suggest missing local modules
- Identify external dependencies

**Syntax Errors:**
- Missing colons in control structures
- F-string formatting issues
- Parentheses matching problems
- Indentation errors

**Test Failures:**
- Analyze assertion errors
- Check for missing dependencies
- Attribute and method verification

**Dependency Errors:**
- Version conflict detection
- Missing dependency identification

#### Usage Example

```python
# Attempt to recover from import error
recovery_result = await attempt_error_recovery(
    error_message="No module named 'auth_utils'",
    error_type="import_error",
    error_context='{"file": "login.py", "line": 15}'
)

# Returns recovery strategy or escalation recommendation
```

### 4. Collaboration Awareness

#### Worker Area Tracking
The system tracks which workers are working on which files/modules to prevent conflicts and coordinate work.

```python
# Update when starting work on a file
await update_my_work_area("src/auth.py", "editing")

# Check for potential conflicts before committing
conflicts = await check_collaboration_conflicts('["src/auth.py", "src/user.py"]')
```

#### Conflict Detection
- **Real-time tracking**: Which workers modified which files recently
- **Risk assessment**: High/medium/low risk based on timing and worker count
- **Automatic alerts**: High-risk conflicts automatically escalated to Master
- **Conflict database**: Persistent tracking of warnings and resolutions

#### Collaboration Features
- **Worker area database**: SQLite tracking of file ownership
- **Activity monitoring**: Track recent worker activities per file
- **Conflict warnings**: Alert when multiple workers modify same files
- **Master escalation**: Automatic escalation for high-risk conflicts

### 5. Intelligent Progress Reporting

#### Smart Summaries
Workers generate concise, informative progress summaries that include:

```python
# Generate intelligent progress summary
summary = await smart_progress_summary()
# Returns: "Task auth-123: 75% complete | 3 files modified | Recent: Implemented JWT validation"
```

#### Summary Components
- **Task progress**: Current completion percentage
- **File changes**: Count of modified files
- **Recent activity**: Latest significant action
- **Context awareness**: Relevant details based on task type

## MCP Tools Reference

### Decision Making Tools

#### `should_ask_master_decision`
```python
await should_ask_master_decision(
    question_type="implementation_detail",
    estimated_token_cost=2000,
    confidence_level=0.8,
    context='{"current_file": "auth.py"}'
)
```

### Context Management Tools

#### `auto_save_context_check`
```python
await auto_save_context_check(
    context_content="<conversation content>",
    context_key="task_context"
)
```

#### `load_relevant_context_for_task`
```python
await load_relevant_context_for_task(
    '{"description": "implement auth", "files": ["auth.py"]}'
)
```

### Error Recovery Tools

#### `attempt_error_recovery`
```python
await attempt_error_recovery(
    error_message="ImportError: No module named 'utils'",
    error_type="import_error",
    error_context='{"file": "main.py", "line": 10}'
)
```

### Collaboration Tools

#### `update_my_work_area`
```python
await update_my_work_area("src/auth.py", "editing")
```

#### `check_collaboration_conflicts`
```python
await check_collaboration_conflicts('["src/auth.py", "src/user.py"]')
```

#### `get_collaboration_status`
```python
await get_collaboration_status()
```

### Reporting Tools

#### `smart_progress_summary`
```python
await smart_progress_summary()
```

## Integration with Existing Tools

### Enhanced Status Reports
Status reports now include intelligent progress summaries:

```python
status_data = {
    "worker_id": "worker-001",
    "status": "working",
    "current_task": {...},
    "progress_summary": "Task auth-123: 75% complete | 3 files modified | Recent: JWT validation",
    # ... other status fields
}
```

### Worker Capabilities
Workers now register with enhanced capabilities:

```python
"capabilities": [
    "communication", "memory_management", "task_execution",
    "repository_awareness", "status_reporting", "intelligent_decisions",
    "error_recovery", "collaboration_awareness", "context_management"
]
```

## Database Schema

### Collaboration Database Tables

#### worker_areas
```sql
CREATE TABLE worker_areas (
    worker_id TEXT,
    file_path TEXT,
    module_name TEXT,
    last_activity TEXT,
    activity_type TEXT,
    PRIMARY KEY (worker_id, file_path)
);
```

#### conflict_warnings
```sql
CREATE TABLE conflict_warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT,
    conflicting_workers TEXT,
    warning_type TEXT,
    created_at TEXT,
    resolved INTEGER DEFAULT 0
);
```

#### conversation_summaries
```sql
CREATE TABLE conversation_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_key TEXT UNIQUE,
    summary TEXT,
    token_count INTEGER,
    created_at TEXT,
    last_updated TEXT
);
```

## Best Practices

### For Workers Using Intelligence Layer

1. **Use Decision Logic**: Always check `should_ask_master_decision` before asking questions
2. **Update Work Areas**: Call `update_my_work_area` when starting work on files
3. **Check Conflicts**: Use `check_collaboration_conflicts` before committing
4. **Attempt Recovery**: Try `attempt_error_recovery` before escalating errors
5. **Save Context**: Let auto-save handle long conversations, but manually save important milestones

### Configuration

Environment variables:
- `WORKER_ID`: Unique worker identifier
- `WORKER_MEMORY_DIR`: Directory for worker memory and intelligence data
- `WORKER_WORKING_DIR`: Worker's Git working directory
- `MESSAGE_QUEUE_DB`: Path to shared message queue database

### Error Handling

The intelligence layer includes comprehensive error handling:
- All tools return JSON with error information on failure
- Failed operations are logged with appropriate severity levels
- Graceful degradation when intelligence features are unavailable
- Fallback to asking Master when decision logic fails

This intelligence layer significantly enhances worker autonomy while maintaining coordination and quality through intelligent decision-making and collaboration awareness.