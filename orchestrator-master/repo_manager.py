"""
Repository Manager Module
Handles Git operations for worker worktrees and branch management.
"""

import asyncio
import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import tempfile

logger = logging.getLogger(__name__)


@dataclass
class WorktreeInfo:
    """Information about a Git worktree."""
    worker_id: str
    branch_name: str
    worktree_path: Path
    created_at: datetime
    last_commit: Optional[str] = None
    has_uncommitted_changes: bool = False
    merge_conflicts: List[str] = None

    def __post_init__(self):
        if self.merge_conflicts is None:
            self.merge_conflicts = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "worker_id": self.worker_id,
            "branch_name": self.branch_name,
            "worktree_path": str(self.worktree_path),
            "created_at": self.created_at.isoformat(),
            "last_commit": self.last_commit,
            "has_uncommitted_changes": self.has_uncommitted_changes,
            "merge_conflicts": self.merge_conflicts
        }


class RepositoryManager:
    """Manages Git operations for the multi-agent system."""

    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.worktrees_dir = self.repo_path / "worktrees"
        self.worktrees: Dict[str, WorktreeInfo] = {}
        self.state_file = Path("/tmp/multibot/repo_state.json")

        # Ensure we're in a Git repository
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a Git repository: {self.repo_path}")

    async def initialize(self):
        """Initialize the repository manager."""
        logger.info(f"Initializing Repository Manager for {self.repo_path}")

        # Create worktrees directory
        self.worktrees_dir.mkdir(exist_ok=True)

        # Load existing state
        await self._load_state()

        # Verify existing worktrees
        await self._verify_existing_worktrees()

        logger.info(f"Repository Manager initialized with {len(self.worktrees)} worktrees")

    async def create_worktree(self, worker_id: str, branch_name: str) -> Dict[str, Any]:
        """Create a Git worktree for a worker."""
        if worker_id in self.worktrees:
            raise ValueError(f"Worktree for worker {worker_id} already exists")

        logger.info(f"Creating worktree for worker {worker_id} on branch {branch_name}")

        # Sanitize branch name
        safe_branch_name = self._sanitize_branch_name(branch_name)
        full_branch_name = f"worker-{worker_id}-{safe_branch_name}"

        # Worktree path
        worktree_path = self.worktrees_dir / worker_id

        try:
            # Check if branch exists
            branch_exists = await self._branch_exists(full_branch_name)

            if not branch_exists:
                # Create new branch from main/master
                main_branch = await self._get_main_branch()
                await self._run_git_command([
                    "checkout", "-b", full_branch_name, main_branch
                ])
                logger.info(f"Created new branch {full_branch_name}")
            else:
                logger.info(f"Using existing branch {full_branch_name}")

            # Create worktree
            await self._run_git_command([
                "worktree", "add", str(worktree_path), full_branch_name
            ])

            # Get initial commit hash
            last_commit = await self._get_last_commit(worktree_path)

            # Create worktree info
            worktree_info = WorktreeInfo(
                worker_id=worker_id,
                branch_name=full_branch_name,
                worktree_path=worktree_path,
                created_at=datetime.now(),
                last_commit=last_commit
            )

            self.worktrees[worker_id] = worktree_info

            # Save state
            await self._save_state()

            logger.info(f"Worktree created for worker {worker_id} at {worktree_path}")

            return {
                "worker_id": worker_id,
                "branch": full_branch_name,
                "path": str(worktree_path),
                "commit": last_commit
            }

        except Exception as e:
            # Cleanup on failure
            if worktree_path.exists():
                try:
                    await self._run_git_command(["worktree", "remove", str(worktree_path), "--force"])
                except:
                    shutil.rmtree(worktree_path, ignore_errors=True)

            raise Exception(f"Failed to create worktree for {worker_id}: {str(e)}")

    async def delete_worktree(self, worker_id: str) -> bool:
        """Delete a worker's Git worktree."""
        if worker_id not in self.worktrees:
            logger.warning(f"Worktree for worker {worker_id} not found")
            return False

        worktree_info = self.worktrees[worker_id]
        logger.info(f"Deleting worktree for worker {worker_id}")

        try:
            # Check for uncommitted changes
            if await self._has_uncommitted_changes(worktree_info.worktree_path):
                logger.warning(f"Worker {worker_id} has uncommitted changes, committing them")
                await self._auto_commit_changes(worker_id, "Auto-commit before worktree deletion")

            # Remove worktree
            await self._run_git_command([
                "worktree", "remove", str(worktree_info.worktree_path), "--force"
            ])

            # Remove from registry
            del self.worktrees[worker_id]

            # Save state
            await self._save_state()

            logger.info(f"Worktree for worker {worker_id} deleted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to delete worktree for {worker_id}: {str(e)}")
            # Force cleanup if Git command failed
            if worktree_info.worktree_path.exists():
                shutil.rmtree(worktree_info.worktree_path, ignore_errors=True)
            return False

    async def merge_worker_branch(
        self,
        worker_id: str,
        target_branch: str = "main"
    ) -> Dict[str, Any]:
        """Merge a worker's branch into target branch."""
        if worker_id not in self.worktrees:
            raise ValueError(f"Worker {worker_id} worktree not found")

        worktree_info = self.worktrees[worker_id]
        logger.info(f"Merging worker {worker_id} branch {worktree_info.branch_name} into {target_branch}")

        try:
            # Ensure worker has committed their changes
            if await self._has_uncommitted_changes(worktree_info.worktree_path):
                await self._auto_commit_changes(worker_id, "Auto-commit before merge")

            # Switch to target branch in main repo
            await self._run_git_command(["checkout", target_branch])

            # Pull latest changes
            try:
                await self._run_git_command(["pull", "origin", target_branch])
            except subprocess.CalledProcessError:
                logger.warning(f"Could not pull latest {target_branch}, continuing with local version")

            # Attempt merge
            try:
                result = await self._run_git_command([
                    "merge", "--no-ff", worktree_info.branch_name,
                    "-m", f"Merge worker {worker_id} changes from {worktree_info.branch_name}"
                ])

                # Get merge commit hash
                merge_commit = await self._get_last_commit(self.repo_path)

                logger.info(f"Successfully merged worker {worker_id} branch")

                return {
                    "status": "success",
                    "worker_id": worker_id,
                    "source_branch": worktree_info.branch_name,
                    "target_branch": target_branch,
                    "commit_hash": merge_commit,
                    "conflicts": []
                }

            except subprocess.CalledProcessError as e:
                # Merge conflict occurred
                conflicts = await self._get_merge_conflicts()
                logger.warning(f"Merge conflicts detected for worker {worker_id}: {conflicts}")

                # Abort the merge
                await self._run_git_command(["merge", "--abort"])

                return {
                    "status": "conflict",
                    "worker_id": worker_id,
                    "source_branch": worktree_info.branch_name,
                    "target_branch": target_branch,
                    "conflicts": conflicts,
                    "error": str(e)
                }

        except Exception as e:
            logger.error(f"Failed to merge worker {worker_id} branch: {str(e)}")
            raise

    async def resolve_conflicts(self, worker_branches: List[str]) -> Dict[str, Any]:
        """Resolve conflicts between multiple worker branches."""
        logger.info(f"Resolving conflicts between branches: {worker_branches}")

        try:
            # Create temporary merge branch
            temp_branch = f"temp-merge-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            main_branch = await self._get_main_branch()

            await self._run_git_command(["checkout", "-b", temp_branch, main_branch])

            resolved_conflicts = []
            remaining_conflicts = []
            resolution_strategy = "automatic"

            # Attempt to merge branches one by one
            for branch in worker_branches:
                try:
                    await self._run_git_command(["merge", "--no-ff", branch])
                    resolved_conflicts.append(branch)
                    logger.info(f"Successfully merged {branch} without conflicts")

                except subprocess.CalledProcessError:
                    # Conflict detected
                    conflicts = await self._get_merge_conflicts()
                    remaining_conflicts.extend(conflicts)

                    # Try automatic resolution strategies
                    if await self._auto_resolve_conflicts():
                        await self._run_git_command(["add", "."])
                        await self._run_git_command([
                            "commit", "-m", f"Auto-resolved conflicts for {branch}"
                        ])
                        resolved_conflicts.append(branch)
                        logger.info(f"Auto-resolved conflicts for {branch}")
                    else:
                        # Manual resolution required
                        await self._run_git_command(["merge", "--abort"])
                        remaining_conflicts.append(branch)
                        resolution_strategy = "manual"
                        logger.warning(f"Manual resolution required for {branch}")

            # If all conflicts resolved, this could be the final merge
            if not remaining_conflicts:
                logger.info("All conflicts resolved successfully")

            return {
                "resolved": resolved_conflicts,
                "remaining": remaining_conflicts,
                "strategy": resolution_strategy,
                "temp_branch": temp_branch if remaining_conflicts else None
            }

        except Exception as e:
            logger.error(f"Failed to resolve conflicts: {str(e)}")
            # Cleanup temp branch
            try:
                await self._run_git_command(["checkout", main_branch])
                await self._run_git_command(["branch", "-D", temp_branch])
            except:
                pass
            raise

    async def get_worktree_status(self, worker_id: str) -> Dict[str, Any]:
        """Get status of a worker's worktree."""
        if worker_id not in self.worktrees:
            raise ValueError(f"Worker {worker_id} worktree not found")

        worktree_info = self.worktrees[worker_id]

        try:
            # Update status
            worktree_info.has_uncommitted_changes = await self._has_uncommitted_changes(
                worktree_info.worktree_path
            )
            worktree_info.last_commit = await self._get_last_commit(worktree_info.worktree_path)

            # Get file status
            status_output = await self._run_git_command_in_worktree(
                worktree_info.worktree_path,
                ["status", "--porcelain"]
            )

            modified_files = []
            for line in status_output.split('\n'):
                if line.strip():
                    status_code = line[:2]
                    filename = line[3:]
                    modified_files.append({
                        "file": filename,
                        "status": self._parse_git_status_code(status_code)
                    })

            # Get commit count ahead/behind main
            main_branch = await self._get_main_branch()
            try:
                ahead_behind = await self._run_git_command_in_worktree(
                    worktree_info.worktree_path,
                    ["rev-list", "--left-right", "--count", f"{main_branch}...HEAD"]
                )
                behind, ahead = map(int, ahead_behind.split())
            except:
                ahead, behind = 0, 0

            return {
                "worker_id": worker_id,
                "branch": worktree_info.branch_name,
                "path": str(worktree_info.worktree_path),
                "last_commit": worktree_info.last_commit,
                "has_uncommitted_changes": worktree_info.has_uncommitted_changes,
                "modified_files": modified_files,
                "commits_ahead": ahead,
                "commits_behind": behind,
                "created_at": worktree_info.created_at.isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get worktree status for {worker_id}: {str(e)}")
            raise

    async def list_worktrees(self) -> List[Dict[str, Any]]:
        """List all worker worktrees."""
        worktree_list = []

        for worker_id in self.worktrees:
            try:
                status = await self.get_worktree_status(worker_id)
                worktree_list.append(status)
            except Exception as e:
                logger.error(f"Failed to get status for worktree {worker_id}: {str(e)}")

        return worktree_list

    async def commit_worker_changes(
        self,
        worker_id: str,
        commit_message: str,
        files: Optional[List[str]] = None
    ) -> str:
        """Commit changes in a worker's worktree."""
        if worker_id not in self.worktrees:
            raise ValueError(f"Worker {worker_id} worktree not found")

        worktree_info = self.worktrees[worker_id]

        try:
            # Add files
            if files:
                for file in files:
                    await self._run_git_command_in_worktree(
                        worktree_info.worktree_path,
                        ["add", file]
                    )
            else:
                # Add all changes
                await self._run_git_command_in_worktree(
                    worktree_info.worktree_path,
                    ["add", "."]
                )

            # Commit
            await self._run_git_command_in_worktree(
                worktree_info.worktree_path,
                ["commit", "-m", commit_message]
            )

            # Update last commit
            worktree_info.last_commit = await self._get_last_commit(worktree_info.worktree_path)
            worktree_info.has_uncommitted_changes = False

            await self._save_state()

            logger.info(f"Committed changes for worker {worker_id}: {commit_message}")
            return worktree_info.last_commit

        except subprocess.CalledProcessError as e:
            if "nothing to commit" in str(e):
                logger.info(f"No changes to commit for worker {worker_id}")
                return worktree_info.last_commit
            else:
                logger.error(f"Failed to commit changes for worker {worker_id}: {str(e)}")
                raise

    async def _auto_commit_changes(self, worker_id: str, message: str) -> str:
        """Auto-commit changes for a worker."""
        return await self.commit_worker_changes(
            worker_id,
            f"{message}\n\nAuto-committed by multibot orchestrator"
        )

    async def _run_git_command(self, args: List[str], cwd: Optional[Path] = None) -> str:
        """Run a Git command."""
        cmd = ["git"] + args
        work_dir = cwd or self.repo_path

        logger.debug(f"Running Git command: {' '.join(cmd)} in {work_dir}")

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                error_msg = stderr.decode().strip()
                raise subprocess.CalledProcessError(result.returncode, cmd, stderr=error_msg)

            return stdout.decode().strip()

        except Exception as e:
            logger.error(f"Git command failed: {' '.join(cmd)} - {str(e)}")
            raise

    async def _run_git_command_in_worktree(self, worktree_path: Path, args: List[str]) -> str:
        """Run a Git command in a specific worktree."""
        return await self._run_git_command(args, cwd=worktree_path)

    async def _branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists."""
        try:
            await self._run_git_command(["rev-parse", "--verify", f"refs/heads/{branch_name}"])
            return True
        except subprocess.CalledProcessError:
            return False

    async def _get_main_branch(self) -> str:
        """Get the main branch name (main or master)."""
        try:
            # Try to get default branch from remote
            result = await self._run_git_command(["symbolic-ref", "refs/remotes/origin/HEAD"])
            return result.split('/')[-1]
        except:
            # Fallback: check if main exists, otherwise use master
            if await self._branch_exists("main"):
                return "main"
            elif await self._branch_exists("master"):
                return "master"
            else:
                raise Exception("Could not determine main branch")

    async def _get_last_commit(self, path: Path) -> str:
        """Get the last commit hash."""
        try:
            return await self._run_git_command(["rev-parse", "HEAD"], cwd=path)
        except:
            return ""

    async def _has_uncommitted_changes(self, worktree_path: Path) -> bool:
        """Check if worktree has uncommitted changes."""
        try:
            result = await self._run_git_command_in_worktree(worktree_path, ["status", "--porcelain"])
            return bool(result.strip())
        except:
            return False

    async def _get_merge_conflicts(self) -> List[str]:
        """Get list of files with merge conflicts."""
        try:
            result = await self._run_git_command(["diff", "--name-only", "--diff-filter=U"])
            return [f.strip() for f in result.split('\n') if f.strip()]
        except:
            return []

    async def _auto_resolve_conflicts(self) -> bool:
        """Attempt automatic conflict resolution."""
        try:
            conflicts = await self._get_merge_conflicts()
            if not conflicts:
                return True

            # Simple strategy: for each conflict file, try to resolve automatically
            for conflict_file in conflicts:
                conflict_path = self.repo_path / conflict_file

                if not conflict_path.exists():
                    continue

                # Read file content
                with open(conflict_path, 'r') as f:
                    content = f.read()

                # Simple resolution: if conflict is just whitespace/formatting, take "ours"
                if self._is_simple_conflict(content):
                    resolved_content = self._resolve_simple_conflict(content)
                    with open(conflict_path, 'w') as f:
                        f.write(resolved_content)
                else:
                    return False  # Manual resolution needed

            return True

        except Exception as e:
            logger.error(f"Auto-resolution failed: {str(e)}")
            return False

    def _is_simple_conflict(self, content: str) -> bool:
        """Check if conflict is simple (whitespace, formatting, etc.)."""
        lines = content.split('\n')
        conflict_sections = []
        current_section = []
        in_conflict = False

        for line in lines:
            if line.startswith('<<<<<<< '):
                in_conflict = True
                current_section = []
            elif line.startswith('======='):
                if in_conflict:
                    conflict_sections.append(('ours', current_section))
                    current_section = []
            elif line.startswith('>>>>>>> '):
                if in_conflict:
                    conflict_sections.append(('theirs', current_section))
                    in_conflict = False
            elif in_conflict:
                current_section.append(line)

        # Simple heuristic: if conflicts are mostly whitespace differences
        for section_type, section_lines in conflict_sections:
            if len(section_lines) > 10:  # Too complex
                return False

        return True

    def _resolve_simple_conflict(self, content: str) -> str:
        """Resolve simple conflicts by taking 'ours' version."""
        lines = content.split('\n')
        resolved_lines = []
        in_conflict = False
        take_section = False

        for line in lines:
            if line.startswith('<<<<<<< '):
                in_conflict = True
                take_section = True
                continue
            elif line.startswith('======='):
                take_section = False
                continue
            elif line.startswith('>>>>>>> '):
                in_conflict = False
                continue
            elif in_conflict:
                if take_section:
                    resolved_lines.append(line)
            else:
                resolved_lines.append(line)

        return '\n'.join(resolved_lines)

    def _sanitize_branch_name(self, branch_name: str) -> str:
        """Sanitize branch name for Git."""
        # Replace invalid characters
        sanitized = branch_name.replace(' ', '-').replace('/', '-')
        # Remove any other invalid characters
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9\-_]', '', sanitized)
        return sanitized[:50]  # Limit length

    def _parse_git_status_code(self, status_code: str) -> str:
        """Parse Git status code to human readable format."""
        code_map = {
            'M ': 'modified',
            ' M': 'modified',
            'MM': 'modified',
            'A ': 'added',
            ' A': 'added',
            'D ': 'deleted',
            ' D': 'deleted',
            'R ': 'renamed',
            ' R': 'renamed',
            'C ': 'copied',
            ' C': 'copied',
            'U ': 'unmerged',
            ' U': 'unmerged',
            'UU': 'unmerged',
            '??': 'untracked'
        }
        return code_map.get(status_code, 'unknown')

    async def _verify_existing_worktrees(self):
        """Verify that existing worktrees are still valid."""
        invalid_worktrees = []

        for worker_id, worktree_info in self.worktrees.items():
            if not worktree_info.worktree_path.exists():
                logger.warning(f"Worktree path {worktree_info.worktree_path} no longer exists")
                invalid_worktrees.append(worker_id)

        # Remove invalid worktrees
        for worker_id in invalid_worktrees:
            del self.worktrees[worker_id]

        if invalid_worktrees:
            await self._save_state()
            logger.info(f"Cleaned up {len(invalid_worktrees)} invalid worktrees")

    async def _save_state(self):
        """Save repository state to disk."""
        state = {
            "worktrees": {
                worker_id: worktree_info.to_dict()
                for worker_id, worktree_info in self.worktrees.items()
            },
            "repo_path": str(self.repo_path),
            "saved_at": datetime.now().isoformat()
        }

        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save repository state: {str(e)}")

    async def _load_state(self):
        """Load repository state from disk."""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file) as f:
                state = json.load(f)

            for worker_id, worktree_data in state.get("worktrees", {}).items():
                worktree_info = WorktreeInfo(
                    worker_id=worktree_data["worker_id"],
                    branch_name=worktree_data["branch_name"],
                    worktree_path=Path(worktree_data["worktree_path"]),
                    created_at=datetime.fromisoformat(worktree_data["created_at"]),
                    last_commit=worktree_data.get("last_commit"),
                    has_uncommitted_changes=worktree_data.get("has_uncommitted_changes", False),
                    merge_conflicts=worktree_data.get("merge_conflicts", [])
                )

                self.worktrees[worker_id] = worktree_info

            logger.info(f"Loaded repository state with {len(self.worktrees)} worktrees")

        except Exception as e:
            logger.error(f"Failed to load repository state: {str(e)}")

    async def cleanup(self):
        """Cleanup repository resources."""
        logger.info("Cleaning up repository manager")

        # Save current state
        await self._save_state()

        # Optionally cleanup worktrees (commented out for safety)
        # for worker_id in list(self.worktrees.keys()):
        #     await self.delete_worktree(worker_id)

        logger.info("Repository Manager cleanup completed")