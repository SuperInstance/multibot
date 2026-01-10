#!/usr/bin/env python3
"""
Merge Coordination Examples
Example workflows and test scenarios for the merge coordination system.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List

from merge_coordination import MergeCoordinator, WorkerBranch, MergeConflict, ConflictType

logger = logging.getLogger(__name__)


class MergeCoordinationExamples:
    """Example workflows demonstrating merge coordination functionality."""

    def __init__(self):
        self.coordinator = MergeCoordinator()
        self.examples = self._load_example_scenarios()

    def _load_example_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """Load predefined example merge scenarios."""
        return {
            "simple_parallel_merge": {
                "description": "Three workers with non-conflicting changes",
                "worker_branches": [
                    {
                        "worker_id": "worker-001",
                        "branch_name": "feature/auth-model",
                        "task_ids": ["auth_001"],
                        "files_modified": ["src/models/user.py", "src/schemas/auth.py"],
                        "test_status": "passed",
                        "dependencies": [],
                        "merge_priority": 1
                    },
                    {
                        "worker_id": "worker-002",
                        "branch_name": "feature/jwt-service",
                        "task_ids": ["auth_002"],
                        "files_modified": ["src/services/jwt.py", "src/utils/tokens.py"],
                        "test_status": "passed",
                        "dependencies": [],
                        "merge_priority": 2
                    },
                    {
                        "worker_id": "worker-003",
                        "branch_name": "feature/password-utils",
                        "task_ids": ["auth_003"],
                        "files_modified": ["src/utils/password.py", "tests/test_password.py"],
                        "test_status": "passed",
                        "dependencies": [],
                        "merge_priority": 3
                    }
                ],
                "expected_conflicts": 0,
                "expected_outcome": "success"
            },
            "file_conflict_scenario": {
                "description": "Two workers modifying the same configuration file",
                "worker_branches": [
                    {
                        "worker_id": "worker-001",
                        "branch_name": "feature/api-config",
                        "task_ids": ["config_001"],
                        "files_modified": ["config/settings.py", "src/api/routes.py"],
                        "test_status": "passed",
                        "dependencies": [],
                        "merge_priority": 1
                    },
                    {
                        "worker_id": "worker-002",
                        "branch_name": "feature/db-config",
                        "task_ids": ["config_002"],
                        "files_modified": ["config/settings.py", "src/database/connection.py"],
                        "test_status": "passed",
                        "dependencies": [],
                        "merge_priority": 2
                    }
                ],
                "expected_conflicts": 1,
                "expected_outcome": "conflict_resolution_needed"
            },
            "dependency_chain_merge": {
                "description": "Workers with dependencies between their changes",
                "worker_branches": [
                    {
                        "worker_id": "worker-001",
                        "branch_name": "feature/base-model",
                        "task_ids": ["base_001"],
                        "files_modified": ["src/models/base.py"],
                        "test_status": "passed",
                        "dependencies": [],
                        "merge_priority": 1
                    },
                    {
                        "worker_id": "worker-002",
                        "branch_name": "feature/user-model",
                        "task_ids": ["user_001"],
                        "files_modified": ["src/models/user.py"],
                        "test_status": "passed",
                        "dependencies": ["worker-001"],
                        "merge_priority": 2
                    },
                    {
                        "worker_id": "worker-003",
                        "branch_name": "feature/user-service",
                        "task_ids": ["user_service_001"],
                        "files_modified": ["src/services/user.py"],
                        "test_status": "passed",
                        "dependencies": ["worker-002"],
                        "merge_priority": 3
                    }
                ],
                "expected_conflicts": 0,
                "expected_outcome": "success"
            },
            "complex_conflict_scenario": {
                "description": "Multiple types of conflicts requiring different resolution strategies",
                "worker_branches": [
                    {
                        "worker_id": "worker-001",
                        "branch_name": "feature/auth-refactor",
                        "task_ids": ["refactor_001"],
                        "files_modified": ["src/auth/__init__.py", "src/auth/middleware.py", "src/models/user.py"],
                        "test_status": "passed",
                        "dependencies": [],
                        "merge_priority": 1
                    },
                    {
                        "worker_id": "worker-002",
                        "branch_name": "feature/auth-endpoints",
                        "task_ids": ["endpoints_001"],
                        "files_modified": ["src/api/auth.py", "src/auth/__init__.py"],
                        "test_status": "passed",
                        "dependencies": [],
                        "merge_priority": 2
                    },
                    {
                        "worker_id": "worker-003",
                        "branch_name": "feature/user-profile",
                        "task_ids": ["profile_001"],
                        "files_modified": ["src/models/user.py", "src/api/profile.py"],
                        "test_status": "failed",  # Test failure adds complexity
                        "dependencies": [],
                        "merge_priority": 3
                    }
                ],
                "expected_conflicts": 2,
                "expected_outcome": "complex_resolution_needed"
            }
        }

    async def run_example(self, example_name: str) -> Dict[str, Any]:
        """Run a specific merge coordination example."""
        if example_name not in self.examples:
            raise ValueError(f"Example '{example_name}' not found")

        example = self.examples[example_name]
        logger.info(f"Running merge coordination example: {example_name}")

        # Generate a graph ID for this example
        graph_id = f"example_{example_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Run merge coordination
        merge_report = await self.coordinator.coordinate_merge_phase(
            graph_id, example["worker_branches"]
        )

        # Analyze results
        analysis = {
            "example_name": example_name,
            "description": example["description"],
            "graph_id": graph_id,
            "merge_results": {
                "status": merge_report.status.value,
                "branches_merged": len(merge_report.branches_merged),
                "conflicts_detected": len(merge_report.conflicts_detected),
                "conflicts_resolved": len(merge_report.conflicts_resolved),
                "test_results": merge_report.test_results,
                "dependency_fixes": len(merge_report.dependency_fixes),
                "duration_seconds": (
                    merge_report.end_time - merge_report.start_time
                ).total_seconds() if merge_report.end_time else None
            },
            "validation": self._validate_example_results(merge_report, example),
            "conflict_analysis": self._analyze_example_conflicts(merge_report.conflicts_detected),
            "performance_metrics": self._calculate_performance_metrics(merge_report)
        }

        return analysis

    async def run_all_examples(self) -> Dict[str, Any]:
        """Run all merge coordination examples."""
        logger.info("Running all merge coordination examples")

        results = {}
        summary = {
            "total_examples": len(self.examples),
            "successful_merges": 0,
            "failed_merges": 0,
            "conflicts_resolved": 0,
            "total_conflicts": 0,
            "average_merge_time": 0.0
        }

        total_time = 0.0

        for example_name in self.examples:
            try:
                result = await self.run_example(example_name)
                results[example_name] = result

                # Update summary
                merge_results = result["merge_results"]
                if merge_results["status"] == "completed":
                    summary["successful_merges"] += 1
                else:
                    summary["failed_merges"] += 1

                summary["conflicts_resolved"] += merge_results["conflicts_resolved"]
                summary["total_conflicts"] += merge_results["conflicts_detected"]

                if merge_results["duration_seconds"]:
                    total_time += merge_results["duration_seconds"]

            except Exception as e:
                logger.error(f"Error running example {example_name}: {e}")
                results[example_name] = {"error": str(e)}
                summary["failed_merges"] += 1

        # Calculate averages
        if summary["total_examples"] > 0:
            summary["average_merge_time"] = total_time / summary["total_examples"]

        return {
            "summary": summary,
            "results": results,
            "generated_at": datetime.now().isoformat()
        }

    async def demonstrate_conflict_resolution(self) -> Dict[str, Any]:
        """Demonstrate different conflict resolution strategies."""
        logger.info("Demonstrating conflict resolution strategies")

        # Create a scenario with various conflict types
        complex_scenario = {
            "worker_branches": [
                {
                    "worker_id": "worker-alpha",
                    "branch_name": "feature/interface-changes",
                    "task_ids": ["interface_001"],
                    "files_modified": ["src/api/base.py", "src/models/interface.py"],
                    "test_status": "passed",
                    "dependencies": [],
                    "merge_priority": 1
                },
                {
                    "worker_id": "worker-beta",
                    "branch_name": "feature/api-updates",
                    "task_ids": ["api_001"],
                    "files_modified": ["src/api/base.py", "src/api/endpoints.py"],
                    "test_status": "passed",
                    "dependencies": [],
                    "merge_priority": 2
                },
                {
                    "worker_id": "worker-gamma",
                    "branch_name": "feature/model-refactor",
                    "task_ids": ["model_001"],
                    "files_modified": ["src/models/interface.py", "src/models/user.py"],
                    "test_status": "passed",
                    "dependencies": [],
                    "merge_priority": 3
                }
            ]
        }

        # Create WorkerBranch objects
        branches = [
            self.coordinator._create_worker_branch(branch_data)
            for branch_data in complex_scenario["worker_branches"]
        ]

        # Analyze conflicts
        conflicts = await self.coordinator.conflict_analyzer.analyze_conflicts(branches)

        # Demonstrate different resolution strategies
        resolution_strategies = {}

        for i, conflict in enumerate(conflicts):
            strategy_name = f"strategy_{i+1}"

            if conflict.auto_resolvable:
                strategy = "automatic_resolution"
                success = await self.coordinator.conflict_resolver.resolve_conflict(
                    conflict, self.coordinator.task_orchestrator
                )
                resolution_strategies[strategy_name] = {
                    "conflict_type": conflict.conflict_type.value,
                    "strategy": strategy,
                    "success": success,
                    "description": "Automatically resolved using built-in resolvers"
                }
            else:
                strategy = "worker_assignment"
                await self.coordinator.conflict_resolver._assign_conflict_to_worker(
                    conflict, self.coordinator.task_orchestrator
                )
                resolution_strategies[strategy_name] = {
                    "conflict_type": conflict.conflict_type.value,
                    "strategy": strategy,
                    "success": True,
                    "description": f"Assigned to worker for manual resolution"
                }

        return {
            "scenario": "complex_conflict_resolution",
            "total_conflicts": len(conflicts),
            "conflicts_by_type": self._group_conflicts_by_type(conflicts),
            "resolution_strategies": resolution_strategies,
            "recommendations": self._generate_resolution_recommendations(conflicts)
        }

    def _validate_example_results(self, merge_report, example) -> Dict[str, Any]:
        """Validate merge results against expected outcomes."""
        validation = {
            "passes": True,
            "checks": [],
            "warnings": [],
            "errors": []
        }

        expected_conflicts = example.get("expected_conflicts", 0)
        actual_conflicts = len(merge_report.conflicts_detected)

        if actual_conflicts == expected_conflicts:
            validation["checks"].append(f"✓ Conflict count matches expectation: {actual_conflicts}")
        else:
            validation["warnings"].append(f"⚠ Conflict count differs: expected {expected_conflicts}, got {actual_conflicts}")

        expected_outcome = example.get("expected_outcome", "success")
        actual_outcome = merge_report.status.value

        if expected_outcome == "success" and actual_outcome == "completed":
            validation["checks"].append("✓ Merge completed successfully as expected")
        elif expected_outcome == "conflict_resolution_needed" and merge_report.conflicts_detected:
            validation["checks"].append("✓ Conflicts detected as expected")
        else:
            validation["warnings"].append(f"⚠ Outcome differs: expected {expected_outcome}, got {actual_outcome}")

        # Check test results
        test_failures = sum(
            1 for result in merge_report.test_results.values()
            if not result.get("passed", True)
        )
        if test_failures == 0:
            validation["checks"].append("✓ All post-merge tests passed")
        else:
            validation["errors"].append(f"✗ {test_failures} test failures after merge")
            validation["passes"] = False

        return validation

    def _analyze_example_conflicts(self, conflicts) -> Dict[str, Any]:
        """Analyze conflicts found in example."""
        if not conflicts:
            return {"status": "no_conflicts"}

        return {
            "total_conflicts": len(conflicts),
            "by_type": self._group_conflicts_by_type(conflicts),
            "by_severity": self._group_conflicts_by_severity(conflicts),
            "auto_resolvable": len([c for c in conflicts if c.auto_resolvable]),
            "manual_resolution_needed": len([c for c in conflicts if not c.auto_resolvable]),
            "affected_files": list(set(
                file_path for conflict in conflicts for file_path in conflict.files_involved
            ))
        }

    def _calculate_performance_metrics(self, merge_report) -> Dict[str, Any]:
        """Calculate performance metrics for merge operation."""
        if not merge_report.end_time:
            return {"status": "incomplete"}

        duration = (merge_report.end_time - merge_report.start_time).total_seconds()

        return {
            "total_duration_seconds": duration,
            "branches_per_minute": len(merge_report.branches_merged) / (duration / 60) if duration > 0 else 0,
            "conflicts_per_branch": len(merge_report.conflicts_detected) / len(merge_report.branches_merged) if merge_report.branches_merged else 0,
            "resolution_rate": len(merge_report.conflicts_resolved) / len(merge_report.conflicts_detected) if merge_report.conflicts_detected else 1.0,
            "test_success_rate": sum(
                1 for result in merge_report.test_results.values() if result.get("passed", False)
            ) / len(merge_report.test_results) if merge_report.test_results else 1.0
        }

    def _group_conflicts_by_type(self, conflicts) -> Dict[str, int]:
        """Group conflicts by type."""
        conflict_types = {}
        for conflict in conflicts:
            conflict_type = conflict.conflict_type.value
            conflict_types[conflict_type] = conflict_types.get(conflict_type, 0) + 1
        return conflict_types

    def _group_conflicts_by_severity(self, conflicts) -> Dict[str, int]:
        """Group conflicts by severity."""
        severities = {}
        for conflict in conflicts:
            severity = conflict.severity
            severities[severity] = severities.get(severity, 0) + 1
        return severities

    def _generate_resolution_recommendations(self, conflicts) -> List[str]:
        """Generate recommendations for conflict resolution."""
        recommendations = []

        auto_resolvable = [c for c in conflicts if c.auto_resolvable]
        if auto_resolvable:
            recommendations.append(f"Automatically resolve {len(auto_resolvable)} simple conflicts first")

        high_severity = [c for c in conflicts if c.severity in ["high", "critical"]]
        if high_severity:
            recommendations.append(f"Prioritize {len(high_severity)} high-severity conflicts")

        file_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.FILE_CONFLICT]
        if len(file_conflicts) > 2:
            recommendations.append("Consider using 3-way merge tools for file conflicts")

        interface_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.INTERFACE_BREAKING]
        if interface_conflicts:
            recommendations.append("Review interface changes carefully before merging")

        return recommendations

    def generate_merge_coordination_report(self) -> str:
        """Generate a human-readable merge coordination report."""
        report = """
# Merge Coordination System Report

## Overview
The merge coordination system successfully manages parallel worker branches with intelligent conflict detection and resolution strategies.

## Key Features
- **Conflict Analysis**: Detects file, dependency, and interface conflicts
- **Merge Strategies**: Sequential, dependency-ordered, and parallel-safe merging
- **Automatic Resolution**: Resolves simple conflicts automatically
- **Worker Assignment**: Assigns complex conflicts to appropriate workers
- **Validation**: Comprehensive pre/post-merge testing and validation

## Merge Strategies Supported
- **Sequential Merge**: Merge branches one by one in priority order
- **Dependency-Ordered Merge**: Merge based on dependency relationships
- **Parallel-Safe Merge**: Group non-conflicting branches for parallel processing

## Conflict Resolution Capabilities
- **File Conflicts**: Intelligent 3-way merging and manual assignment
- **Dependency Conflicts**: Import and module dependency resolution
- **Interface Conflicts**: Breaking change detection and resolution
- **Type Conflicts**: Type system consistency checking

## Example Scenarios Handled
- **Simple Parallel Merge**: Multiple workers, no conflicts
- **File Conflict Resolution**: Same file modified by multiple workers
- **Dependency Chain Merge**: Sequential dependencies between workers
- **Complex Multi-Conflict**: Multiple conflict types requiring different strategies

## Performance Benefits
1. **Automated Conflict Detection**: Identifies issues before merge attempts
2. **Intelligent Resolution**: Resolves simple conflicts without human intervention
3. **Parallel Processing**: Merges non-conflicting branches simultaneously
4. **Comprehensive Validation**: Ensures merge quality through testing
5. **Error Recovery**: Handles merge failures and provides recovery options

## Integration Points
- Works with existing task orchestration system
- Integrates with worker lifecycle management
- Provides monitoring hooks for dashboards
- Supports manual intervention and override capabilities
        """
        return report.strip()


async def run_merge_coordination_demo():
    """Run a complete demonstration of the merge coordination system."""
    examples = MergeCoordinationExamples()

    print("🔀 Merge Coordination System Demo")
    print("=" * 50)

    # Run all examples
    print("\n📋 Running all merge coordination examples...")
    all_results = await examples.run_all_examples()

    print(f"\n📊 Summary:")
    print(f"  • Total examples: {all_results['summary']['total_examples']}")
    print(f"  • Successful merges: {all_results['summary']['successful_merges']}")
    print(f"  • Failed merges: {all_results['summary']['failed_merges']}")
    print(f"  • Total conflicts: {all_results['summary']['total_conflicts']}")
    print(f"  • Conflicts resolved: {all_results['summary']['conflicts_resolved']}")
    print(f"  • Average merge time: {all_results['summary']['average_merge_time']:.1f} seconds")

    # Demonstrate conflict resolution
    print("\n🛠️ Conflict Resolution Demonstration...")
    conflict_demo = await examples.demonstrate_conflict_resolution()

    print(f"\n🔧 Conflict Resolution Results:")
    print(f"  • Total conflicts: {conflict_demo['total_conflicts']}")
    print(f"  • Conflict types: {list(conflict_demo['conflicts_by_type'].keys())}")
    print(f"  • Resolution strategies: {len(conflict_demo['resolution_strategies'])}")

    for strategy_name, strategy_info in conflict_demo['resolution_strategies'].items():
        print(f"    - {strategy_name}: {strategy_info['strategy']} ({'✓' if strategy_info['success'] else '✗'})")

    print("\n✅ Merge coordination demo completed successfully!")
    return all_results, conflict_demo


if __name__ == "__main__":
    # Run the demo
    asyncio.run(run_merge_coordination_demo())