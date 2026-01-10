#!/usr/bin/env python3
"""
Task Decomposition System
Implements intelligent task breakdown, dependency analysis, and worker assignment.
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels for model assignment."""
    SIMPLE = "simple"          # Haiku - straightforward implementations
    MEDIUM = "medium"          # Sonnet - balanced complexity
    COMPLEX = "complex"        # Opus - architectural decisions, coordination
    CRITICAL = "critical"      # Opus - critical path, difficult problems


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    READY = "ready"           # Dependencies satisfied
    ASSIGNED = "assigned"     # Assigned to worker
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"       # Waiting for dependencies


class TaskType(Enum):
    """Types of development tasks."""
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    INTEGRATION = "integration"
    REVIEW = "review"
    DEPLOYMENT = "deployment"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"


@dataclass
class SubTask:
    """Represents a decomposed subtask."""
    task_id: str
    title: str
    description: str
    task_type: TaskType
    complexity: TaskComplexity
    estimated_tokens: int
    estimated_duration: int  # minutes
    dependencies: List[str]  # task_ids this task depends on
    files_involved: List[str]
    acceptance_criteria: List[str]
    preferred_model: str  # opus, sonnet, haiku
    phase: int  # execution phase
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            **asdict(self),
            'task_type': self.task_type.value,
            'complexity': self.complexity.value,
            'status': TaskStatus.PENDING.value
        }


@dataclass
class TaskGraph:
    """Represents the task dependency graph."""
    tasks: Dict[str, SubTask]
    phases: List[List[str]]  # Lists of task_ids by phase
    total_estimated_tokens: int
    total_estimated_duration: int
    critical_path: List[str]
    parallelization_factor: float

    def get_ready_tasks(self, completed_tasks: Set[str]) -> List[str]:
        """Get tasks that are ready to execute (dependencies satisfied)."""
        ready_tasks = []
        for task_id, task in self.tasks.items():
            if task_id not in completed_tasks:
                deps_satisfied = all(dep in completed_tasks for dep in task.dependencies)
                if deps_satisfied:
                    ready_tasks.append(task_id)
        return ready_tasks

    def get_phase_tasks(self, phase: int) -> List[str]:
        """Get tasks for a specific phase."""
        if 0 <= phase < len(self.phases):
            return self.phases[phase]
        return []

    def calculate_critical_path(self) -> List[str]:
        """Calculate the critical path through the task graph."""
        # Simple critical path calculation based on duration
        path = []
        remaining_tasks = set(self.tasks.keys())

        while remaining_tasks:
            # Find task with longest duration that has dependencies satisfied
            best_task = None
            best_duration = 0

            for task_id in remaining_tasks:
                task = self.tasks[task_id]
                deps_satisfied = all(dep not in remaining_tasks for dep in task.dependencies)

                if deps_satisfied and task.estimated_duration > best_duration:
                    best_task = task_id
                    best_duration = task.estimated_duration

            if best_task:
                path.append(best_task)
                remaining_tasks.remove(best_task)
            else:
                # Break cycles or handle remaining tasks
                if remaining_tasks:
                    path.append(next(iter(remaining_tasks)))
                    remaining_tasks.remove(path[-1])

        return path


class TaskDecomposer:
    """Decomposes complex tasks into manageable subtasks."""

    def __init__(self):
        self.decomposition_patterns = self._load_decomposition_patterns()
        self.complexity_analyzer = ComplexityAnalyzer()
        self.dependency_analyzer = DependencyAnalyzer()

    def _load_decomposition_patterns(self) -> Dict[str, Any]:
        """Load predefined decomposition patterns for common task types."""
        return {
            "authentication_system": {
                "pattern": [
                    {
                        "title": "User Model and Database Schema",
                        "type": "implementation",
                        "complexity": "medium",
                        "files": ["models/user.py", "migrations/"],
                        "acceptance_criteria": [
                            "User model with required fields",
                            "Database migration scripts",
                            "Model validation and constraints"
                        ]
                    },
                    {
                        "title": "JWT Token Service",
                        "type": "implementation",
                        "complexity": "medium",
                        "files": ["services/auth.py", "utils/jwt.py"],
                        "acceptance_criteria": [
                            "JWT token generation and validation",
                            "Token refresh mechanism",
                            "Secure token storage"
                        ]
                    },
                    {
                        "title": "Password Hashing Utilities",
                        "type": "implementation",
                        "complexity": "simple",
                        "files": ["utils/password.py"],
                        "acceptance_criteria": [
                            "Secure password hashing with salt",
                            "Password verification function",
                            "Password strength validation"
                        ]
                    },
                    {
                        "title": "Authentication Middleware",
                        "type": "implementation",
                        "complexity": "medium",
                        "files": ["middleware/auth.py"],
                        "dependencies": ["JWT Token Service"],
                        "acceptance_criteria": [
                            "Request authentication middleware",
                            "Role-based access control",
                            "Error handling for auth failures"
                        ]
                    },
                    {
                        "title": "Component Integration",
                        "type": "integration",
                        "complexity": "complex",
                        "files": ["main.py", "config.py"],
                        "dependencies": ["User Model and Database Schema", "JWT Token Service", "Password Hashing Utilities", "Authentication Middleware"],
                        "acceptance_criteria": [
                            "All components working together",
                            "Configuration management",
                            "Error handling and logging"
                        ]
                    },
                    {
                        "title": "Authentication Tests",
                        "type": "testing",
                        "complexity": "medium",
                        "files": ["tests/test_auth.py"],
                        "dependencies": ["Component Integration"],
                        "acceptance_criteria": [
                            "Unit tests for all components",
                            "Integration tests",
                            "Security testing"
                        ]
                    },
                    {
                        "title": "API Documentation",
                        "type": "documentation",
                        "complexity": "simple",
                        "files": ["docs/authentication.md"],
                        "dependencies": ["Component Integration"],
                        "acceptance_criteria": [
                            "API endpoint documentation",
                            "Authentication flow diagrams",
                            "Usage examples"
                        ]
                    }
                ]
            },
            "api_endpoints": {
                "pattern": [
                    {
                        "title": "API Route Structure",
                        "type": "architecture",
                        "complexity": "medium",
                        "files": ["routes/", "main.py"],
                        "acceptance_criteria": [
                            "REST API route structure",
                            "Request/response models",
                            "Error handling framework"
                        ]
                    },
                    {
                        "title": "Data Models and Validation",
                        "type": "implementation",
                        "complexity": "medium",
                        "files": ["models/", "schemas/"],
                        "acceptance_criteria": [
                            "Pydantic models for validation",
                            "Database model definitions",
                            "Serialization methods"
                        ]
                    },
                    {
                        "title": "CRUD Operations",
                        "type": "implementation",
                        "complexity": "simple",
                        "files": ["services/crud.py"],
                        "dependencies": ["Data Models and Validation"],
                        "acceptance_criteria": [
                            "Create, read, update, delete operations",
                            "Database query optimization",
                            "Error handling"
                        ]
                    },
                    {
                        "title": "API Endpoints Implementation",
                        "type": "implementation",
                        "complexity": "medium",
                        "files": ["routes/api.py"],
                        "dependencies": ["API Route Structure", "CRUD Operations"],
                        "acceptance_criteria": [
                            "All API endpoints implemented",
                            "Request validation",
                            "Response formatting"
                        ]
                    }
                ]
            },
            "testing_suite": {
                "pattern": [
                    {
                        "title": "Test Framework Setup",
                        "type": "architecture",
                        "complexity": "simple",
                        "files": ["conftest.py", "pytest.ini"],
                        "acceptance_criteria": [
                            "Test configuration",
                            "Fixtures and utilities",
                            "Test database setup"
                        ]
                    },
                    {
                        "title": "Unit Tests",
                        "type": "testing",
                        "complexity": "medium",
                        "files": ["tests/unit/"],
                        "dependencies": ["Test Framework Setup"],
                        "acceptance_criteria": [
                            "Individual component tests",
                            "Mocking external dependencies",
                            "Edge case coverage"
                        ]
                    },
                    {
                        "title": "Integration Tests",
                        "type": "testing",
                        "complexity": "medium",
                        "files": ["tests/integration/"],
                        "dependencies": ["Test Framework Setup"],
                        "acceptance_criteria": [
                            "Component interaction tests",
                            "Database integration tests",
                            "API endpoint tests"
                        ]
                    }
                ]
            }
        }

    async def decompose_task(self, task_description: str, context: Dict[str, Any] = None) -> TaskGraph:
        """Decompose a complex task into subtasks with dependencies."""
        logger.info(f"Decomposing task: {task_description}")

        # Analyze task to identify patterns and type
        task_analysis = await self._analyze_task_description(task_description, context or {})

        # Generate subtasks
        subtasks = await self._generate_subtasks(task_analysis)

        # Analyze dependencies
        dependency_graph = await self.dependency_analyzer.analyze_dependencies(subtasks)

        # Organize into phases
        phases = self._organize_into_phases(subtasks, dependency_graph)

        # Calculate estimates
        total_tokens = sum(task.estimated_tokens for task in subtasks.values())
        total_duration = self._calculate_total_duration(subtasks, dependency_graph)

        # Create task graph
        task_graph = TaskGraph(
            tasks=subtasks,
            phases=phases,
            total_estimated_tokens=total_tokens,
            total_estimated_duration=total_duration,
            critical_path=[],
            parallelization_factor=self._calculate_parallelization_factor(phases)
        )

        # Calculate critical path
        task_graph.critical_path = task_graph.calculate_critical_path()

        logger.info(f"Task decomposed into {len(subtasks)} subtasks across {len(phases)} phases")
        logger.info(f"Estimated {total_tokens} tokens, {total_duration} minutes")

        return task_graph

    async def _analyze_task_description(self, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze task description to extract key information."""
        analysis = {
            "description": description,
            "context": context,
            "task_type": self._identify_task_type(description),
            "complexity_level": self._estimate_overall_complexity(description),
            "keywords": self._extract_keywords(description),
            "file_patterns": self._identify_file_patterns(description),
            "technologies": self._identify_technologies(description)
        }

        return analysis

    def _identify_task_type(self, description: str) -> str:
        """Identify the primary type of task from description."""
        description_lower = description.lower()

        # Pattern matching for task types
        if any(word in description_lower for word in ["authentication", "auth", "login", "user"]):
            return "authentication_system"
        elif any(word in description_lower for word in ["api", "endpoint", "rest", "route"]):
            return "api_endpoints"
        elif any(word in description_lower for word in ["test", "testing", "spec", "unit test"]):
            return "testing_suite"
        elif any(word in description_lower for word in ["database", "model", "schema", "migration"]):
            return "database_system"
        elif any(word in description_lower for word in ["frontend", "ui", "interface", "component"]):
            return "frontend_system"
        else:
            return "generic_implementation"

    def _estimate_overall_complexity(self, description: str) -> TaskComplexity:
        """Estimate the overall complexity of the task."""
        description_lower = description.lower()

        # Simple heuristics for complexity estimation
        complex_indicators = ["architecture", "system", "framework", "integration", "security"]
        medium_indicators = ["implement", "create", "build", "develop"]
        simple_indicators = ["fix", "update", "modify", "add"]

        if any(indicator in description_lower for indicator in complex_indicators):
            return TaskComplexity.COMPLEX
        elif any(indicator in description_lower for indicator in medium_indicators):
            return TaskComplexity.MEDIUM
        else:
            return TaskComplexity.SIMPLE

    def _extract_keywords(self, description: str) -> List[str]:
        """Extract key technical terms from description."""
        # Simple keyword extraction
        technical_terms = re.findall(r'\b(?:API|JWT|OAuth|REST|SQL|NoSQL|React|Vue|Angular|Flask|Django|FastAPI|pytest|unittest)\b', description, re.IGNORECASE)
        return list(set(technical_terms))

    def _identify_file_patterns(self, description: str) -> List[str]:
        """Identify likely file patterns from description."""
        patterns = []
        description_lower = description.lower()

        if "test" in description_lower:
            patterns.extend(["tests/", "test_*.py", "*_test.py"])
        if "model" in description_lower:
            patterns.extend(["models/", "models.py"])
        if "api" in description_lower:
            patterns.extend(["routes/", "api/", "endpoints/"])
        if "config" in description_lower:
            patterns.extend(["config/", "settings.py"])

        return patterns

    def _identify_technologies(self, description: str) -> List[str]:
        """Identify technologies mentioned in description."""
        tech_patterns = {
            "python": ["python", "py", "flask", "django", "fastapi"],
            "javascript": ["javascript", "js", "node", "react", "vue", "angular"],
            "database": ["sql", "mysql", "postgresql", "mongodb", "redis"],
            "testing": ["pytest", "unittest", "jest", "mocha"],
            "web": ["html", "css", "bootstrap", "tailwind"]
        }

        identified_techs = []
        description_lower = description.lower()

        for tech_category, keywords in tech_patterns.items():
            if any(keyword in description_lower for keyword in keywords):
                identified_techs.append(tech_category)

        return identified_techs

    async def _generate_subtasks(self, task_analysis: Dict[str, Any]) -> Dict[str, SubTask]:
        """Generate subtasks based on task analysis."""
        task_type = task_analysis["task_type"]

        # Use predefined pattern if available
        if task_type in self.decomposition_patterns:
            return await self._generate_from_pattern(task_analysis)
        else:
            return await self._generate_generic_subtasks(task_analysis)

    async def _generate_from_pattern(self, task_analysis: Dict[str, Any]) -> Dict[str, SubTask]:
        """Generate subtasks using predefined patterns."""
        task_type = task_analysis["task_type"]
        pattern = self.decomposition_patterns[task_type]["pattern"]

        subtasks = {}

        for i, task_template in enumerate(pattern):
            task_id = f"{task_type}_{i+1:03d}"

            # Create subtask from template
            subtask = SubTask(
                task_id=task_id,
                title=task_template["title"],
                description=f"Implement {task_template['title'].lower()} for {task_analysis['description']}",
                task_type=TaskType(task_template["type"]),
                complexity=TaskComplexity(task_template["complexity"]),
                estimated_tokens=self.complexity_analyzer.estimate_tokens(
                    TaskComplexity(task_template["complexity"]),
                    TaskType(task_template["type"])
                ),
                estimated_duration=self.complexity_analyzer.estimate_duration(
                    TaskComplexity(task_template["complexity"]),
                    TaskType(task_template["type"])
                ),
                dependencies=[],  # Will be resolved later
                files_involved=task_template.get("files", []),
                acceptance_criteria=task_template.get("acceptance_criteria", []),
                preferred_model=self._determine_preferred_model(TaskComplexity(task_template["complexity"])),
                phase=0,  # Will be calculated later
                metadata={"template": task_template}
            )

            subtasks[task_id] = subtask

        # Resolve dependencies
        self._resolve_template_dependencies(subtasks, pattern)

        return subtasks

    async def _generate_generic_subtasks(self, task_analysis: Dict[str, Any]) -> Dict[str, SubTask]:
        """Generate subtasks for generic tasks without predefined patterns."""
        description = task_analysis["description"]
        complexity = task_analysis["complexity_level"]

        # Generic decomposition based on common development phases
        generic_tasks = [
            {
                "title": "Architecture and Design",
                "type": TaskType.ARCHITECTURE,
                "complexity": TaskComplexity.COMPLEX,
                "description": f"Design architecture and components for: {description}"
            },
            {
                "title": "Core Implementation",
                "type": TaskType.IMPLEMENTATION,
                "complexity": complexity,
                "description": f"Implement core functionality for: {description}",
                "dependencies": ["Architecture and Design"]
            },
            {
                "title": "Testing Implementation",
                "type": TaskType.TESTING,
                "complexity": TaskComplexity.MEDIUM,
                "description": f"Create tests for: {description}",
                "dependencies": ["Core Implementation"]
            },
            {
                "title": "Documentation",
                "type": TaskType.DOCUMENTATION,
                "complexity": TaskComplexity.SIMPLE,
                "description": f"Document implementation: {description}",
                "dependencies": ["Core Implementation"]
            }
        ]

        subtasks = {}

        for i, task_def in enumerate(generic_tasks):
            task_id = f"generic_{i+1:03d}"

            subtask = SubTask(
                task_id=task_id,
                title=task_def["title"],
                description=task_def["description"],
                task_type=task_def["type"],
                complexity=task_def["complexity"],
                estimated_tokens=self.complexity_analyzer.estimate_tokens(
                    task_def["complexity"], task_def["type"]
                ),
                estimated_duration=self.complexity_analyzer.estimate_duration(
                    task_def["complexity"], task_def["type"]
                ),
                dependencies=task_def.get("dependencies", []),
                files_involved=task_analysis.get("file_patterns", []),
                acceptance_criteria=[f"Complete {task_def['title'].lower()}"],
                preferred_model=self._determine_preferred_model(task_def["complexity"]),
                phase=0,
                metadata={"generic": True}
            )

            subtasks[task_id] = subtask

        return subtasks

    def _resolve_template_dependencies(self, subtasks: Dict[str, SubTask], pattern: List[Dict]):
        """Resolve string dependencies to task IDs."""
        # Create title to task_id mapping
        title_to_id = {task.title: task_id for task_id, task in subtasks.items()}

        # Resolve dependencies
        for i, task_template in enumerate(pattern):
            task_id = list(subtasks.keys())[i]
            template_deps = task_template.get("dependencies", [])

            resolved_deps = []
            for dep_title in template_deps:
                if dep_title in title_to_id:
                    resolved_deps.append(title_to_id[dep_title])

            subtasks[task_id].dependencies = resolved_deps

    def _determine_preferred_model(self, complexity: TaskComplexity) -> str:
        """Determine the preferred model based on task complexity."""
        model_assignment = {
            TaskComplexity.SIMPLE: "haiku",
            TaskComplexity.MEDIUM: "sonnet",
            TaskComplexity.COMPLEX: "opus",
            TaskComplexity.CRITICAL: "opus"
        }
        return model_assignment.get(complexity, "sonnet")

    def _organize_into_phases(self, subtasks: Dict[str, SubTask], dependency_graph: Dict[str, Set[str]]) -> List[List[str]]:
        """Organize tasks into execution phases based on dependencies."""
        phases = []
        remaining_tasks = set(subtasks.keys())
        completed_tasks = set()

        phase_num = 0
        while remaining_tasks:
            current_phase = []

            # Find tasks with no unfulfilled dependencies
            for task_id in list(remaining_tasks):
                task = subtasks[task_id]
                if all(dep in completed_tasks for dep in task.dependencies):
                    current_phase.append(task_id)
                    task.phase = phase_num

            if not current_phase:
                # Handle circular dependencies by picking one task
                logger.warning("Potential circular dependency detected, breaking cycle")
                current_phase.append(next(iter(remaining_tasks)))
                subtasks[current_phase[0]].phase = phase_num

            phases.append(current_phase)
            completed_tasks.update(current_phase)
            remaining_tasks -= set(current_phase)
            phase_num += 1

        return phases

    def _calculate_total_duration(self, subtasks: Dict[str, SubTask], dependency_graph: Dict[str, Set[str]]) -> int:
        """Calculate total estimated duration considering parallelization."""
        phases = self._organize_into_phases(subtasks, dependency_graph)

        total_duration = 0
        for phase_tasks in phases:
            # Phase duration is the maximum duration of tasks in the phase (parallel execution)
            phase_duration = max(subtasks[task_id].estimated_duration for task_id in phase_tasks)
            total_duration += phase_duration

        return total_duration

    def _calculate_parallelization_factor(self, phases: List[List[str]]) -> float:
        """Calculate how much parallelization is possible."""
        total_tasks = sum(len(phase) for phase in phases)
        sequential_tasks = len(phases)

        if sequential_tasks == 0:
            return 1.0

        return total_tasks / sequential_tasks


class ComplexityAnalyzer:
    """Analyzes and estimates task complexity."""

    def __init__(self):
        self.token_estimates = {
            TaskComplexity.SIMPLE: {
                TaskType.IMPLEMENTATION: 500,
                TaskType.TESTING: 300,
                TaskType.DOCUMENTATION: 200,
                TaskType.DEBUGGING: 400,
                TaskType.REFACTORING: 350
            },
            TaskComplexity.MEDIUM: {
                TaskType.IMPLEMENTATION: 1500,
                TaskType.TESTING: 800,
                TaskType.DOCUMENTATION: 500,
                TaskType.INTEGRATION: 1200,
                TaskType.REVIEW: 600
            },
            TaskComplexity.COMPLEX: {
                TaskType.ARCHITECTURE: 3000,
                TaskType.IMPLEMENTATION: 2500,
                TaskType.INTEGRATION: 2000,
                TaskType.TESTING: 1500,
                TaskType.REVIEW: 1000
            },
            TaskComplexity.CRITICAL: {
                TaskType.ARCHITECTURE: 5000,
                TaskType.IMPLEMENTATION: 4000,
                TaskType.INTEGRATION: 3500,
                TaskType.DEBUGGING: 3000,
                TaskType.REVIEW: 2000
            }
        }

        self.duration_estimates = {
            TaskComplexity.SIMPLE: {
                TaskType.IMPLEMENTATION: 30,
                TaskType.TESTING: 20,
                TaskType.DOCUMENTATION: 15,
                TaskType.DEBUGGING: 25,
                TaskType.REFACTORING: 20
            },
            TaskComplexity.MEDIUM: {
                TaskType.IMPLEMENTATION: 90,
                TaskType.TESTING: 60,
                TaskType.DOCUMENTATION: 30,
                TaskType.INTEGRATION: 75,
                TaskType.REVIEW: 45
            },
            TaskComplexity.COMPLEX: {
                TaskType.ARCHITECTURE: 180,
                TaskType.IMPLEMENTATION: 150,
                TaskType.INTEGRATION: 120,
                TaskType.TESTING: 90,
                TaskType.REVIEW: 60
            },
            TaskComplexity.CRITICAL: {
                TaskType.ARCHITECTURE: 300,
                TaskType.IMPLEMENTATION: 240,
                TaskType.INTEGRATION: 200,
                TaskType.DEBUGGING: 180,
                TaskType.REVIEW: 120
            }
        }

    def estimate_tokens(self, complexity: TaskComplexity, task_type: TaskType) -> int:
        """Estimate token requirements for a task."""
        return self.token_estimates.get(complexity, {}).get(task_type, 1000)

    def estimate_duration(self, complexity: TaskComplexity, task_type: TaskType) -> int:
        """Estimate duration in minutes for a task."""
        return self.duration_estimates.get(complexity, {}).get(task_type, 60)


class DependencyAnalyzer:
    """Analyzes task dependencies and creates dependency graphs."""

    async def analyze_dependencies(self, subtasks: Dict[str, SubTask]) -> Dict[str, Set[str]]:
        """Analyze dependencies between subtasks."""
        dependency_graph = {}

        for task_id, task in subtasks.items():
            dependencies = set()

            # Add explicit dependencies
            dependencies.update(task.dependencies)

            # Analyze implicit dependencies based on file patterns
            implicit_deps = await self._find_implicit_dependencies(task, subtasks)
            dependencies.update(implicit_deps)

            dependency_graph[task_id] = dependencies

        # Validate dependency graph (no cycles)
        self._validate_dependency_graph(dependency_graph)

        return dependency_graph

    async def _find_implicit_dependencies(self, task: SubTask, all_tasks: Dict[str, SubTask]) -> Set[str]:
        """Find implicit dependencies based on file patterns and task types."""
        implicit_deps = set()

        # Architecture tasks should generally come first
        if task.task_type != TaskType.ARCHITECTURE:
            for other_id, other_task in all_tasks.items():
                if other_task.task_type == TaskType.ARCHITECTURE and other_id != task.task_id:
                    implicit_deps.add(other_id)

        # Testing depends on implementation
        if task.task_type == TaskType.TESTING:
            for other_id, other_task in all_tasks.items():
                if other_task.task_type == TaskType.IMPLEMENTATION and other_id != task.task_id:
                    # Check if they work on related files
                    if self._files_overlap(task.files_involved, other_task.files_involved):
                        implicit_deps.add(other_id)

        # Integration depends on individual components
        if task.task_type == TaskType.INTEGRATION:
            for other_id, other_task in all_tasks.items():
                if other_task.task_type == TaskType.IMPLEMENTATION and other_id != task.task_id:
                    implicit_deps.add(other_id)

        return implicit_deps

    def _files_overlap(self, files1: List[str], files2: List[str]) -> bool:
        """Check if two file lists have overlapping patterns."""
        for f1 in files1:
            for f2 in files2:
                if f1 in f2 or f2 in f1 or f1.split('/')[0] == f2.split('/')[0]:
                    return True
        return False

    def _validate_dependency_graph(self, dependency_graph: Dict[str, Set[str]]):
        """Validate that the dependency graph has no cycles."""
        def has_cycle(graph, node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    if has_cycle(graph, neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        visited = set()
        for node in dependency_graph:
            if node not in visited:
                if has_cycle(dependency_graph, node, visited, set()):
                    logger.warning(f"Cycle detected in dependency graph involving {node}")
                    # Remove problematic dependencies to break cycles
                    self._break_cycles(dependency_graph)
                    break

    def _break_cycles(self, dependency_graph: Dict[str, Set[str]]):
        """Break cycles in dependency graph by removing some edges."""
        # Simple cycle breaking: remove dependencies that create cycles
        for node in dependency_graph:
            deps_to_remove = []
            for dep in dependency_graph[node]:
                # Check if removing this dependency would break a cycle
                temp_graph = {k: v.copy() for k, v in dependency_graph.items()}
                temp_graph[node].remove(dep)

                # If no cycle after removal, keep it removed
                if not self._has_any_cycle(temp_graph):
                    deps_to_remove.append(dep)

            for dep in deps_to_remove:
                dependency_graph[node].discard(dep)

    def _has_any_cycle(self, graph: Dict[str, Set[str]]) -> bool:
        """Check if graph has any cycles."""
        def has_cycle(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        visited = set()
        for node in graph:
            if node not in visited:
                if has_cycle(node, visited, set()):
                    return True
        return False


class TaskOrchestrator:
    """Orchestrates task execution across workers."""

    def __init__(self, message_queue, worker_lifecycle):
        self.message_queue = message_queue
        self.worker_lifecycle = worker_lifecycle
        self.active_task_graphs: Dict[str, TaskGraph] = {}
        self.task_assignments: Dict[str, str] = {}  # task_id -> worker_id
        self.completed_tasks: Dict[str, Set[str]] = {}  # graph_id -> completed_task_ids

    async def execute_task_graph(self, graph_id: str, task_graph: TaskGraph) -> str:
        """Execute a task graph across available workers."""
        logger.info(f"Starting execution of task graph {graph_id}")

        self.active_task_graphs[graph_id] = task_graph
        self.completed_tasks[graph_id] = set()

        # Start with first phase
        await self._execute_next_phase(graph_id)

        return graph_id

    async def _execute_next_phase(self, graph_id: str):
        """Execute the next phase of tasks."""
        task_graph = self.active_task_graphs[graph_id]
        completed = self.completed_tasks[graph_id]

        ready_tasks = task_graph.get_ready_tasks(completed)

        if not ready_tasks:
            if len(completed) == len(task_graph.tasks):
                logger.info(f"Task graph {graph_id} completed successfully")
                await self._finalize_task_graph(graph_id)
            else:
                logger.warning(f"No ready tasks found for graph {graph_id}, may be blocked")
            return

        # Assign tasks to workers
        assignments = await self._assign_tasks_to_workers(ready_tasks, task_graph)

        for task_id, worker_id in assignments.items():
            await self._assign_task_to_worker(task_id, worker_id, task_graph)
            self.task_assignments[task_id] = worker_id

    async def _assign_tasks_to_workers(self, task_ids: List[str], task_graph: TaskGraph) -> Dict[str, str]:
        """Assign tasks to optimal workers based on model preferences and availability."""
        assignments = {}

        # Get available workers
        available_workers = await self._get_available_workers()

        # Sort tasks by complexity (critical/complex first)
        sorted_tasks = sorted(task_ids, key=lambda tid: (
            task_graph.tasks[tid].complexity.value,
            task_graph.tasks[tid].estimated_tokens
        ), reverse=True)

        for task_id in sorted_tasks:
            task = task_graph.tasks[task_id]

            # Find best worker for this task
            best_worker = await self._find_best_worker(task, available_workers)

            if best_worker:
                assignments[task_id] = best_worker
                available_workers.remove(best_worker)  # Worker is now busy
            else:
                logger.warning(f"No available worker for task {task_id}")

        return assignments

    async def _get_available_workers(self) -> List[str]:
        """Get list of available workers."""
        if self.worker_lifecycle:
            worker_states = await self.worker_lifecycle.get_all_worker_states()
            available = []

            for worker_id, state in worker_states.items():
                if state.get("status") in ["active", "idle"] and not state.get("current_task"):
                    available.append(worker_id)

            return available
        return []

    async def _find_best_worker(self, task: SubTask, available_workers: List[str]) -> Optional[str]:
        """Find the best worker for a given task."""
        if not available_workers:
            return None

        # Get worker capabilities
        worker_models = {}
        if self.worker_lifecycle:
            worker_states = await self.worker_lifecycle.get_all_worker_states()
            for worker_id in available_workers:
                if worker_id in worker_states:
                    worker_models[worker_id] = worker_states[worker_id].get("model", "sonnet")

        # Prefer workers with matching model
        preferred_workers = [w for w in available_workers
                           if worker_models.get(w) == task.preferred_model]

        if preferred_workers:
            return preferred_workers[0]

        # Fall back to any available worker
        return available_workers[0]

    async def _assign_task_to_worker(self, task_id: str, worker_id: str, task_graph: TaskGraph):
        """Assign a specific task to a worker."""
        task = task_graph.tasks[task_id]

        logger.info(f"Assigning task {task_id} ({task.title}) to worker {worker_id}")

        # Send task assignment message
        await self.message_queue.send_task_assignment(
            worker_id=worker_id,
            task_id=task_id,
            description=task.description,
            context={
                "title": task.title,
                "type": task.task_type.value,
                "complexity": task.complexity.value,
                "files_involved": task.files_involved,
                "acceptance_criteria": task.acceptance_criteria,
                "estimated_tokens": task.estimated_tokens,
                "estimated_duration": task.estimated_duration
            },
            priority=7 if task.complexity in [TaskComplexity.COMPLEX, TaskComplexity.CRITICAL] else 5
        )

    async def _finalize_task_graph(self, graph_id: str):
        """Finalize a completed task graph."""
        task_graph = self.active_task_graphs[graph_id]

        logger.info(f"Task graph {graph_id} completed with {len(task_graph.tasks)} tasks")

        # Clean up
        del self.active_task_graphs[graph_id]
        del self.completed_tasks[graph_id]

        # Remove task assignments
        tasks_to_remove = [tid for tid, _ in self.task_assignments.items()
                          if tid.startswith(graph_id)]
        for task_id in tasks_to_remove:
            del self.task_assignments[task_id]

    async def mark_task_completed(self, task_id: str):
        """Mark a task as completed and trigger next phase execution."""
        # Find which graph this task belongs to
        graph_id = None
        for gid, task_graph in self.active_task_graphs.items():
            if task_id in task_graph.tasks:
                graph_id = gid
                break

        if graph_id:
            self.completed_tasks[graph_id].add(task_id)
            logger.info(f"Task {task_id} completed in graph {graph_id}")

            # Check if we can start more tasks
            await self._execute_next_phase(graph_id)

    async def mark_task_failed(self, task_id: str, error: str):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {error}")

        # For now, just log the failure
        # In a more sophisticated system, we might retry or reassign
        # Find which graph this task belongs to
        graph_id = None
        for gid, task_graph in self.active_task_graphs.items():
            if task_id in task_graph.tasks:
                graph_id = gid
                break

        if graph_id:
            logger.error(f"Task {task_id} failed in graph {graph_id}: {error}")
            # Could implement retry logic here