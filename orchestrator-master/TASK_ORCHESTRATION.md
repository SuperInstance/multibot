# Task Orchestration System

## Overview

The Task Orchestration System is the brain of the Multi-Agent Orchestrator that intelligently decomposes complex development tasks into manageable subtasks, analyzes dependencies, and coordinates execution across multiple Claude Code workers. This system enables efficient parallel development by breaking down large projects into smaller, independent work units.

## Core Components

### 🧠 Task Decomposer
Analyzes task descriptions and breaks them down into subtasks using:
- **Pattern Recognition**: Identifies common task types (authentication, API, testing)
- **Complexity Analysis**: Estimates token requirements and difficulty
- **Dependency Mapping**: Creates relationships between subtasks
- **Model Assignment**: Assigns optimal Claude model based on complexity

### 📊 Task Graph
Represents decomposed tasks as a Directed Acyclic Graph (DAG):
- **Nodes**: Individual subtasks with metadata
- **Edges**: Dependencies between tasks
- **Phases**: Groups of tasks that can execute in parallel
- **Critical Path**: Longest sequence of dependent tasks

### 🎯 Task Orchestrator
Coordinates task execution across workers:
- **Worker Assignment**: Matches tasks to available workers
- **Progress Tracking**: Monitors completion and triggers next phases
- **Load Balancing**: Distributes work optimally
- **Error Handling**: Manages failures and reassignments

## Task Decomposition Process

### 1. Task Analysis
```python
# Analyze the input task
task_analysis = {
    "description": "Add authentication system to the app",
    "task_type": "authentication_system",
    "complexity_level": "complex",
    "keywords": ["JWT", "password", "security"],
    "technologies": ["python", "database", "web"]
}
```

### 2. Subtask Generation
Based on analysis, generates subtasks using predefined patterns or generic decomposition:

**Authentication System Pattern:**
- User Model and Database Schema (Medium/Sonnet)
- JWT Token Service (Medium/Sonnet)
- Password Hashing Utilities (Simple/Haiku)
- Authentication Middleware (Medium/Sonnet)
- Component Integration (Complex/Opus)
- Testing Implementation (Medium/Sonnet)
- Documentation (Simple/Haiku)

### 3. Dependency Analysis
Creates dependency relationships:
```
Phase 1 (Parallel):
├── User Model and Database Schema
├── JWT Token Service
├── Password Hashing Utilities
└── Authentication Middleware

Phase 2 (After Phase 1):
├── Component Integration
├── Testing Implementation
└── Documentation

Phase 3 (After Phase 2):
└── Master Review and Integration
```

### 4. Worker Assignment
Assigns tasks based on:
- **Model Requirements**: Opus for complex, Sonnet for medium, Haiku for simple
- **Worker Availability**: Available workers with appropriate models
- **Load Balancing**: Distributes work evenly across workers
- **Specialization**: Considers worker expertise if available

## MCP Tools

### Primary Tool: `decompose_and_assign`

**Usage:**
```python
await decompose_and_assign({
    "task_description": "Add authentication system to the app",
    "context": {
        "app_type": "web_application",
        "framework": "fastapi",
        "requirements": ["JWT tokens", "role-based access"]
    },
    "priority": 7,
    "constraints": {"max_workers": 4}
})
```

**Response:**
```json
{
    "status": "success",
    "graph_id": "graph_a1b2c3d4",
    "decomposition_summary": {
        "total_tasks": 7,
        "phases": 3,
        "estimated_tokens": 12000,
        "estimated_duration_minutes": 180,
        "parallelization_factor": 2.33
    },
    "task_breakdown": [...],
    "execution_phases": [...]
}
```

### Monitoring and Control Tools

#### `get_task_graph_status`
Monitor execution progress:
```python
await get_task_graph_status("graph_a1b2c3d4")
```

Returns real-time status including:
- Tasks completed/in-progress/pending
- Progress percentage
- Phase-by-phase breakdown
- Worker assignments

#### `list_active_task_graphs`
View all active orchestrations:
```python
await list_active_task_graphs()
```

#### `manually_assign_task`
Override automatic assignment:
```python
await manually_assign_task({
    "task_id": "auth_001",
    "worker_id": "worker-opus-001",
    "priority": 8
})
```

#### `cancel_task_graph`
Cancel orchestration:
```python
await cancel_task_graph("graph_a1b2c3d4", "Requirements changed")
```

### Analysis Tools

#### `analyze_task_complexity`
Analyze without executing:
```python
await analyze_task_complexity("Build REST API for user management")
```

Returns complexity estimates, model requirements, and resource needs.

#### `get_task_execution_recommendations`
Get optimization suggestions:
```python
await get_task_execution_recommendations(
    "Implement microservices architecture",
    available_workers=["worker-001", "worker-002"],
    time_constraints=240  # minutes
)
```

## Task Types and Patterns

### Predefined Patterns

#### Authentication System
- **Subtasks**: 7 tasks across 3 phases
- **Models**: 1 Opus, 4 Sonnet, 2 Haiku
- **Duration**: ~3 hours with 4 workers
- **Files**: models/, services/, middleware/, tests/

#### REST API Development
- **Subtasks**: 4 tasks across 2 phases
- **Models**: 0 Opus, 3 Sonnet, 1 Haiku
- **Duration**: ~2 hours with 3 workers
- **Files**: routes/, schemas/, services/

#### Testing Suite
- **Subtasks**: 3 tasks across 2 phases
- **Models**: 0 Opus, 2 Sonnet, 1 Haiku
- **Duration**: ~1.5 hours with 2 workers
- **Files**: tests/, conftest.py

#### Deployment Pipeline
- **Subtasks**: 8 tasks across 4 phases
- **Models**: 2 Opus, 4 Sonnet, 2 Haiku
- **Duration**: ~5 hours with 6 workers
- **Files**: .github/, docker/, k8s/

### Generic Decomposition
For unrecognized tasks, uses generic pattern:
1. **Architecture and Design** (Complex/Opus)
2. **Core Implementation** (Variable/Assigned)
3. **Testing Implementation** (Medium/Sonnet)
4. **Documentation** (Simple/Haiku)

## Complexity and Model Assignment

### Task Complexity Levels

**Simple (Haiku)**
- Documentation writing
- Basic utility functions
- Simple bug fixes
- Code formatting
- 500-800 tokens, 15-30 minutes

**Medium (Sonnet)**
- CRUD operations
- API endpoint implementation
- Unit testing
- Component integration
- 1000-1500 tokens, 45-90 minutes

**Complex (Opus)**
- Architecture decisions
- System design
- Complex integrations
- Performance optimization
- 2500-3000 tokens, 120-180 minutes

**Critical (Opus)**
- Core system coordination
- Security implementations
- Critical path resolution
- Cross-system integration
- 3500-5000 tokens, 180-300 minutes

### Model Selection Strategy

```python
def determine_preferred_model(complexity):
    return {
        TaskComplexity.SIMPLE: "haiku",     # Fast, cost-effective
        TaskComplexity.MEDIUM: "sonnet",    # Balanced capability
        TaskComplexity.COMPLEX: "opus",     # High capability
        TaskComplexity.CRITICAL: "opus"     # Maximum capability
    }[complexity]
```

## Dependency Management

### Dependency Types

**Explicit Dependencies**
- Defined in task patterns
- Example: "Integration" depends on "Implementation"

**Implicit Dependencies**
- Inferred from task types and file patterns
- Architecture tasks typically come first
- Testing depends on implementation
- Integration depends on components

**File-based Dependencies**
- Tasks working on same files/modules
- Prevents conflicts and ensures proper ordering

### Cycle Detection and Resolution
- Validates DAG has no circular dependencies
- Automatically breaks problematic cycles
- Provides warnings for dependency issues

## Execution Phases

### Phase Organization
Tasks organized into phases where:
- **Within Phase**: Tasks execute in parallel
- **Between Phases**: Sequential execution (Phase N+1 starts after Phase N completes)
- **Phase Duration**: Maximum duration of any task in the phase

### Phase Transitions
1. **Phase Completion**: All tasks in phase marked complete
2. **Dependency Check**: Verify next phase dependencies satisfied
3. **Worker Assignment**: Assign next phase tasks to available workers
4. **Parallel Execution**: Start all tasks in next phase simultaneously

### Example Phase Execution
```
Authentication System:

Phase 1 (0-90 min): [4 parallel tasks]
├── User Model (Worker-1, Sonnet)
├── JWT Service (Worker-2, Sonnet)
├── Password Utils (Worker-3, Haiku)
└── Auth Middleware (Worker-4, Sonnet)

Phase 2 (90-150 min): [3 parallel tasks]
├── Integration (Worker-1, Opus)
├── Testing (Worker-2, Sonnet)
└── Documentation (Worker-3, Haiku)

Phase 3 (150-180 min): [1 task]
└── Master Review (Master, Opus)
```

## Performance Metrics

### Parallelization Factor
Measures parallelization effectiveness:
```
Parallelization Factor = Total Tasks / Number of Phases
```
- **1.0**: Completely sequential
- **2.0+**: Good parallelization
- **3.0+**: Excellent parallelization

### Resource Utilization
- **Token Efficiency**: Optimal model assignment reduces costs
- **Time Efficiency**: Parallel execution reduces total time
- **Worker Efficiency**: Balanced load distribution

### Example Performance
**Authentication System (Traditional vs Orchestrated):**
- **Sequential**: 7 tasks × 60 min avg = 420 minutes
- **Orchestrated**: 3 phases × 60 min max = 180 minutes
- **Speedup**: 2.33x faster
- **Cost**: 15% reduction through optimal model assignment

## Integration with Orchestrator

### Worker Lifecycle Integration
```python
# Orchestrator automatically:
# 1. Checks worker availability
# 2. Assigns tasks based on model requirements
# 3. Monitors task completion
# 4. Triggers next phase execution
# 5. Handles worker failures and reassignment
```

### Communication Integration
- Uses existing message queue for task assignment
- Integrates with worker status reporting
- Provides real-time progress updates

### Monitoring Integration
- Displays task graphs in web dashboard
- Shows real-time progress in GUI
- Provides execution metrics and analytics

## Error Handling and Recovery

### Task Failure Handling
1. **Immediate Response**: Mark task as failed
2. **Impact Analysis**: Check dependent tasks
3. **Recovery Options**:
   - Automatic retry (up to 2 attempts)
   - Reassign to different worker
   - Manual intervention required
   - Cancel dependent tasks

### Worker Failure Handling
1. **Detection**: Worker becomes unresponsive
2. **Task Recovery**: Reassign in-progress tasks
3. **Dependency Update**: Update task graph status
4. **Continuation**: Resume execution with remaining workers

### Graph-level Recovery
- Cancel entire graph if critical path fails
- Partial completion with manual intervention
- Rollback and restart options

## Usage Examples

### Example 1: Simple Task
```python
# Simple task - will create 4 generic subtasks
result = await decompose_and_assign({
    "task_description": "Fix login validation bug",
    "context": {"urgency": "high"},
    "priority": 8
})
```

### Example 2: Complex Project
```python
# Complex project - uses predefined patterns
result = await decompose_and_assign({
    "task_description": "Build complete e-commerce platform",
    "context": {
        "architecture": "microservices",
        "features": ["auth", "catalog", "cart", "payment"],
        "timeline": "2_weeks"
    },
    "priority": 7
})
```

### Example 3: Custom Constraints
```python
# With resource constraints
result = await decompose_and_assign({
    "task_description": "Implement GraphQL API",
    "context": {"framework": "graphene"},
    "constraints": {
        "max_workers": 3,
        "preferred_models": ["sonnet", "haiku"],
        "deadline": "2024-01-15"
    }
})
```

## Best Practices

### Task Description Guidelines
1. **Be Specific**: Include technical details and requirements
2. **Provide Context**: Add framework, architecture, constraints
3. **Define Scope**: Clear boundaries and acceptance criteria
4. **Include Examples**: Reference implementations or patterns

### Optimization Strategies
1. **Right-size Workers**: Match complexity to model capabilities
2. **Monitor Progress**: Track phases and adjust as needed
3. **Plan Resources**: Ensure adequate workers for parallel phases
4. **Review Dependencies**: Validate logical task ordering

### Common Patterns
- Start with architecture/design tasks
- Implement components in parallel when possible
- Integration and testing after implementation
- Documentation throughout development
- Master review at critical points

## Troubleshooting

### Common Issues

**No Tasks Generated**
- Check task description clarity
- Verify context information
- Review decomposition patterns

**Poor Parallelization**
- Analyze dependency structure
- Consider breaking large tasks further
- Review task type assignments

**Worker Assignment Failures**
- Check worker availability
- Verify model requirements
- Review worker capacity

**Dependency Conflicts**
- Examine task relationships
- Check for circular dependencies
- Review file overlap patterns

### Debug Tools
```python
# Analyze without executing
analysis = await analyze_task_complexity(description)

# Check execution recommendations
recs = await get_task_execution_recommendations(description)

# Monitor active graphs
graphs = await list_active_task_graphs()

# Get detailed status
status = await get_task_graph_status(graph_id)
```

The Task Orchestration System transforms complex development projects into efficiently coordinated multi-agent workflows, enabling teams to leverage the full power of parallel AI development while maintaining quality and coordination.