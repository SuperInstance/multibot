# Multi-Agent Claude Code Orchestration System Architecture

## System Overview

This system creates a hierarchical multi-agent orchestration where a Master Claude Code instance (Opus) coordinates multiple Worker Claude Code instances (Sonnet/Haiku) working in parallel on the same Git repository using different branches/worktrees.

## Component Architecture

### Master Agent (Opus)
- **Role**: Orchestrator and coordinator
- **Responsibilities**:
  - Task decomposition and assignment
  - Worker lifecycle management (spawn/terminate)
  - Progress monitoring and coordination
  - Dependency resolution and merge coordination
  - Token optimization through Worker delegation
  - Re-prompting Workers when they deviate

### Worker Agents (Sonnet/Haiku)
- **Role**: Task executors
- **Responsibilities**:
  - Execute assigned tasks independently
  - Maintain context through memory files
  - Report progress to Master
  - Request clarification when needed
  - Work within assigned Git worktree

### User Interface
- **Role**: Human oversight and control
- **Capabilities**:
  - Visual monitoring of all terminal windows
  - Manual Worker pause/resume
  - Master decision override
  - Real-time system state visibility

## Communication Protocols

### Inter-Agent Communication

#### Message Types
```typescript
interface MasterToWorkerMessage {
  type: 'TASK_ASSIGNMENT' | 'STATUS_REQUEST' | 'TERMINATE' | 'CONTEXT_UPDATE';
  taskId: string;
  payload: TaskAssignment | StatusRequest | TerminationRequest | ContextUpdate;
  timestamp: number;
}

interface WorkerToMasterMessage {
  type: 'STATUS_UPDATE' | 'QUESTION' | 'TASK_COMPLETE' | 'ERROR';
  workerId: string;
  taskId?: string;
  payload: StatusUpdate | Question | TaskResult | ErrorReport;
  timestamp: number;
}

interface TaskAssignment {
  description: string;
  branch: string;
  workingDirectory: string;
  context: string[];
  dependencies: string[];
  priority: number;
  estimatedDuration: number;
}
```

#### Communication Channels
1. **File-based messaging**: JSON files in shared `/tmp/multibot/messages/` directory
2. **WebSocket fallback**: For real-time coordination when file-based is insufficient
3. **Git-based coordination**: Branch status and merge requests through Git metadata

### State Synchronization Protocol

#### Heartbeat System
- Workers send heartbeat every 30 seconds
- Master monitors Worker health and responsiveness
- Automatic Worker restart on failure detection

#### Task Coordination
```typescript
interface TaskCoordination {
  lockFile: string;           // Prevent concurrent access
  stateFile: string;          // Current system state
  messageQueue: string;       // Pending messages
  progressTracking: string;   // Task progress updates
}
```

## File Structure

```
multibot/
├── core/
│   ├── master/
│   │   ├── orchestrator.ts          # Main Master logic
│   │   ├── task-manager.ts          # Task decomposition and assignment
│   │   ├── worker-manager.ts        # Worker lifecycle management
│   │   └── coordination.ts          # Inter-agent coordination
│   ├── worker/
│   │   ├── agent.ts                 # Worker agent logic
│   │   ├── context-manager.ts       # Memory file management
│   │   └── communication.ts         # Master communication
│   └── shared/
│       ├── types.ts                 # Shared type definitions
│       ├── protocols.ts             # Communication protocols
│       └── utils.ts                 # Shared utilities
├── infrastructure/
│   ├── git-manager.ts               # Git worktree management
│   ├── terminal-manager.ts          # Terminal window management
│   └── mcp-configurator.ts          # MCP server setup
├── state/
│   ├── system-state.json            # Global system state
│   ├── workers/                     # Worker-specific state
│   │   ├── {workerId}-state.json
│   │   └── {workerId}-memory.json
│   └── tasks/
│       ├── active-tasks.json
│       ├── completed-tasks.json
│       └── task-dependencies.json
├── communication/
│   ├── messages/                    # Inter-agent messages
│   │   ├── master-to-worker/
│   │   └── worker-to-master/
│   └── locks/                       # Coordination locks
├── worktrees/                       # Git worktrees for each Worker
│   ├── worker-1/
│   ├── worker-2/
│   └── ...
├── config/
│   ├── master-config.json
│   ├── worker-template.json
│   └── mcp-configs/
│       ├── github-mcp.json
│       └── shared-mcp.json
└── scripts/
    ├── spawn-master.sh
    ├── spawn-worker.sh
    ├── setup-worktrees.sh
    └── cleanup.sh
```

## State Management

### Distributed State Architecture

#### Master State
```typescript
interface MasterState {
  workers: {
    [workerId: string]: WorkerInfo;
  };
  tasks: {
    active: Task[];
    pending: Task[];
    completed: Task[];
  };
  gitState: {
    branches: BranchInfo[];
    mergeQueue: MergeRequest[];
  };
  systemMetrics: SystemMetrics;
}

interface WorkerInfo {
  id: string;
  status: 'idle' | 'working' | 'blocked' | 'error';
  currentTask?: string;
  branch: string;
  workingDirectory: string;
  lastHeartbeat: number;
  capabilities: string[];
}
```

#### Worker State
```typescript
interface WorkerState {
  id: string;
  currentTask?: Task;
  context: ContextMemory;
  gitState: {
    branch: string;
    lastCommit: string;
    uncommittedChanges: boolean;
  };
  communication: {
    lastMasterContact: number;
    pendingQuestions: Question[];
  };
}

interface ContextMemory {
  files: string[];              // Recently accessed files
  concepts: string[];           // Key concepts learned
  decisions: Decision[];        // Important decisions made
  blockers: string[];          // Current blockers
}
```

### State Persistence Strategy

1. **Atomic Updates**: All state changes use atomic file operations
2. **Versioning**: State files include version numbers for conflict resolution
3. **Recovery**: Automatic state recovery from backups on corruption
4. **Cleanup**: Periodic cleanup of stale state and temporary files

## Required MCP Servers

### Core MCP Servers

#### 1. GitHub MCP Server (Per Worker)
```json
{
  "name": "github-worker-{workerId}",
  "type": "github",
  "config": {
    "repository": "{owner}/{repo}",
    "branch": "worker-{workerId}-branch",
    "token": "{github_token}",
    "permissions": ["read", "write", "pull_request"]
  }
}
```

#### 2. Shared Filesystem MCP
```json
{
  "name": "shared-fs",
  "type": "filesystem",
  "config": {
    "allowed_paths": [
      "/mnt/c/Users/casey/multibot/state",
      "/mnt/c/Users/casey/multibot/communication",
      "/mnt/c/Users/casey/multibot/worktrees"
    ],
    "permissions": ["read", "write"]
  }
}
```

#### 3. Git Coordination MCP
```json
{
  "name": "git-coordinator",
  "type": "git",
  "config": {
    "repository_path": "/mnt/c/Users/casey/multibot",
    "worktree_management": true,
    "branch_permissions": {
      "master": ["read"],
      "worker-*": ["read", "write"]
    }
  }
}
```

#### 4. Terminal Management MCP
```json
{
  "name": "terminal-manager",
  "type": "terminal",
  "config": {
    "session_management": true,
    "window_creation": true,
    "process_monitoring": true
  }
}
```

### Advanced MCP Servers

#### 5. Task Queue MCP
```json
{
  "name": "task-queue",
  "type": "queue",
  "config": {
    "storage": "file",
    "persistence": true,
    "priority_support": true
  }
}
```

#### 6. Metrics and Monitoring MCP
```json
{
  "name": "metrics",
  "type": "monitoring",
  "config": {
    "metrics_collection": true,
    "performance_tracking": true,
    "health_checks": true
  }
}
```

## Implementation Guidelines

### Phase 1: Core Infrastructure
1. Set up Git worktree management
2. Implement file-based communication system
3. Create basic Master-Worker spawning
4. Implement state management foundation

### Phase 2: Agent Intelligence
1. Develop task decomposition algorithms
2. Implement context memory management
3. Create Worker question/answer system
4. Add progress monitoring and recovery

### Phase 3: Advanced Coordination
1. Implement merge coordination
2. Add dependency resolution
3. Create visual monitoring interface
4. Implement user override capabilities

### Phase 4: Optimization
1. Add load balancing
2. Implement intelligent Worker selection
3. Add predictive scaling
4. Optimize token usage

## Deployment Strategy

### Local Development Setup
```bash
# 1. Initialize worktrees
./scripts/setup-worktrees.sh

# 2. Configure MCP servers
./scripts/configure-mcp.sh

# 3. Start Master
./scripts/spawn-master.sh

# 4. Workers spawn automatically based on workload
```

### Production Considerations
- Docker containerization for isolation
- Kubernetes orchestration for scaling
- Persistent volume management for state
- Network security for inter-agent communication
- Monitoring and alerting for system health

## Security and Safety

### Access Controls
- Worker sandboxing within Git worktrees
- MCP permission boundaries
- File system access restrictions
- Network isolation between Workers

### Error Handling
- Automatic Worker recovery
- State corruption detection
- Graceful degradation strategies
- Manual intervention protocols

### Monitoring
- Real-time system health dashboards
- Performance metrics collection
- Error rate tracking
- Resource utilization monitoring