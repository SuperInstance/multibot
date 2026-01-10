#!/usr/bin/env python3
"""
Web-Based Monitoring Dashboard Server
FastAPI + WebSockets server for remote monitoring of the multi-agent orchestration system.
"""

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

# Import our existing components
from message_queue import MessageQueueManager, MessageType, MessagePriority
from worker_lifecycle import WorkerLifecycleManager
from dashboard_integration import DashboardDataProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for API
class WorkerInfo(BaseModel):
    worker_id: str
    model: str
    status: str
    branch: str
    task_title: str
    progress: int
    last_activity: str
    uptime: float

class TaskInfo(BaseModel):
    task_id: str
    worker_id: str
    description: str
    status: str
    priority: int
    created_at: str
    progress: int

class MasterStatus(BaseModel):
    active_workers: int
    tasks_completed: int
    tasks_in_progress: int
    tasks_queued: int
    current_activity: str
    repository_status: str
    uptime: float

class MessageRequest(BaseModel):
    message: str
    priority: int = 5

class WorkerAction(BaseModel):
    action: str
    parameters: Optional[Dict[str, Any]] = None


class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.worker_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, connection_type: str, worker_id: str = None):
        """Accept WebSocket connection."""
        await websocket.accept()

        if connection_type == "dashboard":
            if "dashboard" not in self.active_connections:
                self.active_connections["dashboard"] = []
            self.active_connections["dashboard"].append(websocket)
        elif connection_type == "worker" and worker_id:
            if worker_id not in self.worker_connections:
                self.worker_connections[worker_id] = []
            self.worker_connections[worker_id].append(websocket)

        logger.info(f"WebSocket connected: {connection_type} {worker_id or ''}")

    def disconnect(self, websocket: WebSocket, connection_type: str, worker_id: str = None):
        """Remove WebSocket connection."""
        try:
            if connection_type == "dashboard" and "dashboard" in self.active_connections:
                self.active_connections["dashboard"].remove(websocket)
            elif connection_type == "worker" and worker_id and worker_id in self.worker_connections:
                self.worker_connections[worker_id].remove(websocket)
        except ValueError:
            pass  # Connection already removed

        logger.info(f"WebSocket disconnected: {connection_type} {worker_id or ''}")

    async def send_to_dashboard(self, message: Dict[str, Any]):
        """Send message to all dashboard connections."""
        if "dashboard" not in self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections["dashboard"]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.append(connection)

        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn, "dashboard")

    async def send_to_worker_terminals(self, worker_id: str, message: Dict[str, Any]):
        """Send message to all connections for a specific worker terminal."""
        if worker_id not in self.worker_connections:
            return

        disconnected = []
        for connection in self.worker_connections[worker_id]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.append(connection)

        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn, "worker", worker_id)

    async def broadcast_worker_update(self, worker_id: str, data: Dict[str, Any]):
        """Broadcast worker update to both dashboard and worker terminals."""
        message = {
            "type": "worker_update",
            "worker_id": worker_id,
            "data": data
        }

        await self.send_to_dashboard(message)
        await self.send_to_worker_terminals(worker_id, {
            "type": "log_update",
            "logs": data.get("log_lines", [])
        })


class WebDashboardServer:
    """Web dashboard server with FastAPI and WebSockets."""

    def __init__(self, orchestrator=None):
        self.app = FastAPI(title="Multi-Agent Orchestrator Web Dashboard")
        self.orchestrator = orchestrator
        self.websocket_manager = WebSocketManager()

        # Initialize components
        self.message_queue = MessageQueueManager()
        self.worker_lifecycle = WorkerLifecycleManager() if not orchestrator else orchestrator.worker_lifecycle

        # Paths
        self.base_dir = Path("/tmp/multibot")
        self.workers_dir = self.base_dir / "workers"
        self.static_dir = Path(__file__).parent / "web_static"
        self.templates_dir = Path(__file__).parent / "web_templates"

        # Create directories
        self.static_dir.mkdir(exist_ok=True)
        self.templates_dir.mkdir(exist_ok=True)

        # Setup FastAPI app
        self.setup_routes()
        self.setup_static_files()
        self.setup_websockets()

        # Background tasks
        self.running = True
        self.update_task = None

    def setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Serve main dashboard page."""
            return self.render_dashboard()

        @self.app.get("/workers", response_model=List[WorkerInfo])
        async def get_workers():
            """Get list of all workers."""
            try:
                workers = []
                if self.worker_lifecycle:
                    worker_states = await self.worker_lifecycle.get_all_worker_states()

                    for worker_id, state in worker_states.items():
                        worker_info = await self.get_worker_info(worker_id, state)
                        workers.append(WorkerInfo(**worker_info))

                return workers
            except Exception as e:
                logger.error(f"Error getting workers: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/workers/{worker_id}/pause")
        async def pause_worker(worker_id: str):
            """Pause a specific worker."""
            try:
                if self.worker_lifecycle:
                    await self.worker_lifecycle.pause_worker(worker_id)
                    return {"status": "success", "message": f"Worker {worker_id} paused"}
                else:
                    raise HTTPException(status_code=503, detail="Worker lifecycle not available")
            except Exception as e:
                logger.error(f"Error pausing worker {worker_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/workers/{worker_id}/resume")
        async def resume_worker(worker_id: str):
            """Resume a specific worker."""
            try:
                if self.worker_lifecycle:
                    await self.worker_lifecycle.resume_worker(worker_id)
                    return {"status": "success", "message": f"Worker {worker_id} resumed"}
                else:
                    raise HTTPException(status_code=503, detail="Worker lifecycle not available")
            except Exception as e:
                logger.error(f"Error resuming worker {worker_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/workers/{worker_id}/terminate")
        async def terminate_worker(worker_id: str):
            """Terminate a specific worker."""
            try:
                if self.worker_lifecycle:
                    await self.worker_lifecycle.terminate_worker(
                        worker_id, save_state=True, commit_changes=True
                    )
                    return {"status": "success", "message": f"Worker {worker_id} terminated"}
                else:
                    raise HTTPException(status_code=503, detail="Worker lifecycle not available")
            except Exception as e:
                logger.error(f"Error terminating worker {worker_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/workers/{worker_id}/message")
        async def send_message_to_worker(worker_id: str, message_req: MessageRequest):
            """Send message to a specific worker."""
            try:
                message_id = await self.message_queue.send_message(
                    from_id="web_dashboard",
                    to_id=worker_id,
                    message_type=MessageType.GUIDANCE,
                    content={"message": message_req.message},
                    priority=MessagePriority(message_req.priority)
                )
                return {"status": "success", "message_id": message_id}
            except Exception as e:
                logger.error(f"Error sending message to worker {worker_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/workers/{worker_id}/logs")
        async def get_worker_logs(worker_id: str, lines: int = 100):
            """Get worker logs."""
            try:
                log_lines = await self.get_worker_log_lines(worker_id, lines)
                return {"worker_id": worker_id, "logs": log_lines}
            except Exception as e:
                logger.error(f"Error getting logs for worker {worker_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/workers/{worker_id}/memory")
        async def get_worker_memory(worker_id: str):
            """Get worker memory files."""
            try:
                memory_files = await self.get_worker_memory_files(worker_id)
                return {"worker_id": worker_id, "memory_files": memory_files}
            except Exception as e:
                logger.error(f"Error getting memory for worker {worker_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/workers/{worker_id}/diff")
        async def get_worker_diff(worker_id: str):
            """Get worker git diff."""
            try:
                diff_content = await self.get_worker_git_diff(worker_id)
                return {"worker_id": worker_id, "diff": diff_content}
            except Exception as e:
                logger.error(f"Error getting diff for worker {worker_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/master/status", response_model=MasterStatus)
        async def get_master_status():
            """Get master orchestrator status."""
            try:
                return await self.get_master_status_data()
            except Exception as e:
                logger.error(f"Error getting master status: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/tasks", response_model=List[TaskInfo])
        async def get_tasks():
            """Get list of all tasks."""
            try:
                return await self.get_all_tasks()
            except Exception as e:
                logger.error(f"Error getting tasks: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/workers/spawn")
        async def spawn_worker(model: str = "sonnet", task_name: str = "general", base_branch: str = "main"):
            """Spawn a new worker."""
            try:
                if self.worker_lifecycle:
                    worker_id = await self.worker_lifecycle.spawn_worker(
                        model=model, task_name=task_name, base_branch=base_branch
                    )
                    return {"status": "success", "worker_id": worker_id}
                else:
                    raise HTTPException(status_code=503, detail="Worker lifecycle not available")
            except Exception as e:
                logger.error(f"Error spawning worker: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/communication/log")
        async def get_communication_log(limit: int = 50):
            """Get recent communication messages."""
            try:
                messages = await self.message_queue.get_recent_messages(limit=limit)
                return {"messages": messages}
            except Exception as e:
                logger.error(f"Error getting communication log: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def setup_static_files(self):
        """Setup static file serving."""
        self.app.mount("/static", StaticFiles(directory=self.static_dir), name="static")

    def setup_websockets(self):
        """Setup WebSocket endpoints."""

        @self.app.websocket("/ws/dashboard")
        async def dashboard_websocket(websocket: WebSocket):
            """WebSocket for dashboard updates."""
            await self.websocket_manager.connect(websocket, "dashboard")
            try:
                while True:
                    # Keep connection alive and handle any incoming messages
                    data = await websocket.receive_text()
                    # Handle any dashboard commands if needed
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(websocket, "dashboard")

        @self.app.websocket("/ws/worker/{worker_id}")
        async def worker_terminal_websocket(websocket: WebSocket, worker_id: str):
            """WebSocket for individual worker terminal output."""
            await self.websocket_manager.connect(websocket, "worker", worker_id)
            try:
                while True:
                    # Send initial logs
                    log_lines = await self.get_worker_log_lines(worker_id)
                    await websocket.send_text(json.dumps({
                        "type": "log_update",
                        "logs": log_lines
                    }))

                    # Wait before next update
                    await asyncio.sleep(1)
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(websocket, "worker", worker_id)

    def render_dashboard(self) -> str:
        """Render the main dashboard HTML."""
        html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Agent Orchestrator Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/xterm@4.19.0/lib/xterm.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@4.19.0/css/xterm.css" />
    <style>
        .worker-card {
            margin-bottom: 20px;
            border: 2px solid #dee2e6;
            transition: border-color 0.3s;
        }
        .worker-card.active { border-color: #28a745; }
        .worker-card.waiting { border-color: #ffc107; }
        .worker-card.paused { border-color: #fd7e14; }
        .worker-card.error { border-color: #dc3545; }
        .worker-card.terminated { border-color: #6c757d; }

        .terminal-container {
            background: #1e1e1e;
            color: #fff;
            font-family: 'Courier New', monospace;
            height: 200px;
            overflow-y: auto;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }

        .status-indicator {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 10px;
        }
        .status-active { background-color: #28a745; }
        .status-waiting { background-color: #ffc107; }
        .status-paused { background-color: #fd7e14; }
        .status-error { background-color: #dc3545; }
        .status-terminated { background-color: #6c757d; }
        .status-initializing { background-color: #007bff; }

        .communication-log {
            height: 300px;
            overflow-y: auto;
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 10px;
            font-family: monospace;
            font-size: 12px;
        }

        .master-panel {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }

        .chart-container {
            height: 200px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container-fluid">
        <!-- Header -->
        <nav class="navbar navbar-dark bg-dark">
            <div class="container-fluid">
                <span class="navbar-brand mb-0 h1">
                    <i class="fas fa-desktop"></i> Multi-Agent Orchestrator Dashboard
                </span>
                <div class="d-flex">
                    <button class="btn btn-outline-light me-2" onclick="refreshAll()">
                        <i class="fas fa-sync-alt"></i> Refresh
                    </button>
                    <button class="btn btn-success me-2" onclick="spawnWorker()">
                        <i class="fas fa-plus"></i> Spawn Worker
                    </button>
                    <button class="btn btn-warning me-2" onclick="pauseAll()">
                        <i class="fas fa-pause"></i> Pause All
                    </button>
                    <button class="btn btn-info" onclick="resumeAll()">
                        <i class="fas fa-play"></i> Resume All
                    </button>
                </div>
            </div>
        </nav>

        <!-- Master Control Panel -->
        <div class="master-panel" id="masterPanel">
            <div class="row">
                <div class="col-md-3">
                    <h5><i class="fas fa-users"></i> Workers</h5>
                    <h3 id="activeWorkers">0</h3>
                    <small>Active Workers</small>
                </div>
                <div class="col-md-3">
                    <h5><i class="fas fa-check-circle"></i> Completed</h5>
                    <h3 id="tasksCompleted">0</h3>
                    <small>Tasks Completed</small>
                </div>
                <div class="col-md-3">
                    <h5><i class="fas fa-cog"></i> In Progress</h5>
                    <h3 id="tasksInProgress">0</h3>
                    <small>Tasks In Progress</small>
                </div>
                <div class="col-md-3">
                    <h5><i class="fas fa-clock"></i> Queued</h5>
                    <h3 id="tasksQueued">0</h3>
                    <small>Tasks Queued</small>
                </div>
            </div>
            <hr>
            <div class="row">
                <div class="col-md-6">
                    <strong>Current Activity:</strong>
                    <span id="currentActivity">Initializing...</span>
                </div>
                <div class="col-md-6">
                    <strong>Repository:</strong>
                    <span id="repositoryStatus">Unknown</span>
                </div>
            </div>
        </div>

        <!-- Workers Grid -->
        <div class="row" id="workersGrid">
            <!-- Worker cards will be dynamically added here -->
        </div>

        <!-- Communication Log -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-comments"></i> Master ↔ Worker Communication Log</h5>
                        <button class="btn btn-sm btn-outline-secondary float-end" onclick="clearCommunicationLog()">
                            Clear Log
                        </button>
                    </div>
                    <div class="card-body">
                        <div class="communication-log" id="communicationLog">
                            <!-- Communication messages will appear here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modals -->
    <!-- Worker Details Modal -->
    <div class="modal fade" id="workerDetailsModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Worker Details</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="workerDetailsContent">
                        <!-- Worker details will be loaded here -->
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Send Message Modal -->
    <div class="modal fade" id="sendMessageModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Send Message</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="messageForm">
                        <div class="mb-3">
                            <label for="messageRecipient" class="form-label">To:</label>
                            <input type="text" class="form-control" id="messageRecipient" readonly>
                        </div>
                        <div class="mb-3">
                            <label for="messageContent" class="form-label">Message:</label>
                            <textarea class="form-control" id="messageContent" rows="3" required></textarea>
                        </div>
                        <div class="mb-3">
                            <label for="messagePriority" class="form-label">Priority:</label>
                            <select class="form-select" id="messagePriority">
                                <option value="1">Low</option>
                                <option value="3" selected>Normal</option>
                                <option value="5">High</option>
                                <option value="7">Urgent</option>
                                <option value="9">Critical</option>
                            </select>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" onclick="sendMessage()">Send Message</button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="/static/dashboard.js"></script>
</body>
</html>
        '''
        return html_content

    async def get_worker_info(self, worker_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive worker information."""
        try:
            worker_dir = self.workers_dir / worker_id

            # Basic info from state
            worker_info = {
                "worker_id": worker_id,
                "model": state.get("model", "unknown"),
                "status": state.get("status", "unknown"),
                "branch": "unknown",
                "task_title": "No task assigned",
                "progress": 0,
                "last_activity": "Unknown",
                "uptime": 0.0
            }

            # Get current task
            current_task = state.get("current_task")
            if current_task:
                worker_info["task_title"] = current_task.get("description", "Unknown task")
                worker_info["progress"] = current_task.get("progress", 0)

            # Get branch info
            if worker_dir.exists():
                try:
                    result = subprocess.run(
                        ["git", "branch", "--show-current"],
                        cwd=worker_dir,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        worker_info["branch"] = result.stdout.strip()
                except Exception:
                    pass

            # Calculate uptime
            start_time = state.get("start_time")
            if start_time:
                try:
                    start_dt = datetime.fromisoformat(start_time)
                    worker_info["uptime"] = (datetime.now() - start_dt).total_seconds()
                except Exception:
                    pass

            return worker_info

        except Exception as e:
            logger.error(f"Error getting worker info for {worker_id}: {e}")
            return {
                "worker_id": worker_id,
                "model": "unknown",
                "status": "error",
                "branch": "unknown",
                "task_title": "Error loading data",
                "progress": 0,
                "last_activity": f"Error: {str(e)}",
                "uptime": 0.0
            }

    async def get_worker_log_lines(self, worker_id: str, lines: int = 100) -> List[str]:
        """Get log lines for a worker."""
        try:
            worker_dir = self.workers_dir / worker_id
            log_file = worker_dir / "logs" / "worker.log"

            if not log_file.exists():
                return ["Log file not found"]

            # Read last N lines
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                return [line.rstrip() for line in all_lines[-lines:]]

        except Exception as e:
            logger.error(f"Error reading logs for {worker_id}: {e}")
            return [f"Error reading logs: {str(e)}"]

    async def get_worker_memory_files(self, worker_id: str) -> List[Dict[str, Any]]:
        """Get worker's memory files."""
        try:
            worker_dir = self.workers_dir / worker_id
            memory_dir = worker_dir / "memory"

            if not memory_dir.exists():
                return []

            files = []
            for file_path in memory_dir.glob("*.json"):
                try:
                    stat = file_path.stat()
                    files.append({
                        "name": file_path.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "path": str(file_path)
                    })
                except Exception:
                    pass

            return sorted(files, key=lambda x: x["modified"], reverse=True)

        except Exception as e:
            logger.error(f"Error getting memory files for {worker_id}: {e}")
            return []

    async def get_worker_git_diff(self, worker_id: str) -> str:
        """Get worker's git diff."""
        try:
            worker_dir = self.workers_dir / worker_id

            if not worker_dir.exists():
                return "Worker directory not found"

            result = subprocess.run(
                ["git", "diff"],
                cwd=worker_dir,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout if result.stdout else "No changes"
            else:
                return f"Error getting diff: {result.stderr}"

        except Exception as e:
            logger.error(f"Error getting git diff for {worker_id}: {e}")
            return f"Error: {str(e)}"

    async def get_master_status_data(self) -> MasterStatus:
        """Get master status information."""
        try:
            # Get worker statistics
            worker_states = {}
            if self.worker_lifecycle:
                worker_states = await self.worker_lifecycle.get_all_worker_states()

            active_workers = len([s for s in worker_states.values()
                                if s.get("status") in ["active", "working"]])

            # Get task statistics
            task_stats = await self.message_queue.get_task_stats()

            # Get repository status
            repo_status = await self.get_repository_status()

            return MasterStatus(
                active_workers=active_workers,
                tasks_completed=task_stats.get("completed", 0),
                tasks_in_progress=task_stats.get("in_progress", 0),
                tasks_queued=task_stats.get("queued", 0),
                current_activity="Coordinating workers and monitoring tasks",
                repository_status=repo_status,
                uptime=0.0  # Would calculate actual uptime
            )

        except Exception as e:
            logger.error(f"Error getting master status: {e}")
            return MasterStatus(
                active_workers=0,
                tasks_completed=0,
                tasks_in_progress=0,
                tasks_queued=0,
                current_activity=f"Error: {str(e)}",
                repository_status="Unknown",
                uptime=0.0
            )

    async def get_repository_status(self) -> str:
        """Get repository status."""
        try:
            result = subprocess.run(
                ["git", "branch", "-a"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                branches = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                local_branches = [b for b in branches if not b.startswith('remotes/')]
                return f"{len(local_branches)} active branches"
            else:
                return "Repository status unknown"

        except Exception as e:
            logger.error(f"Error getting repository status: {e}")
            return "Error getting repository status"

    async def get_all_tasks(self) -> List[TaskInfo]:
        """Get all tasks from the system."""
        try:
            # This would integrate with the task management system
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return []

    async def start_update_loop(self):
        """Start the background update loop."""
        while self.running:
            try:
                # Get all workers and broadcast updates
                if self.worker_lifecycle:
                    worker_states = await self.worker_lifecycle.get_all_worker_states()

                    for worker_id, state in worker_states.items():
                        worker_data = await self.get_worker_info(worker_id, state)
                        log_lines = await self.get_worker_log_lines(worker_id, 20)
                        worker_data["log_lines"] = log_lines

                        await self.websocket_manager.broadcast_worker_update(worker_id, worker_data)

                # Broadcast master status
                master_status = await self.get_master_status_data()
                await self.websocket_manager.send_to_dashboard({
                    "type": "master_update",
                    "data": master_status.dict()
                })

                # Wait before next update
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Update loop error: {e}")
                await asyncio.sleep(5)

    async def start(self):
        """Start the web dashboard server."""
        logger.info("Starting web dashboard server")

        # Create static files
        await self.create_static_files()

        # Start update loop
        self.update_task = asyncio.create_task(self.start_update_loop())

    async def stop(self):
        """Stop the web dashboard server."""
        logger.info("Stopping web dashboard server")
        self.running = False

        if self.update_task:
            self.update_task.cancel()

    async def create_static_files(self):
        """Create static JavaScript and CSS files."""
        await self.create_dashboard_js()

    async def create_dashboard_js(self):
        """Create the main dashboard JavaScript file."""
        js_content = '''
// Dashboard JavaScript for Multi-Agent Orchestrator
let dashboardWS = null;
let workerTerminals = {};
let currentWorkerId = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
    connectWebSocket();
    loadInitialData();
});

function initializeDashboard() {
    console.log('Initializing Multi-Agent Orchestrator Dashboard');
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;

    dashboardWS = new WebSocket(wsUrl);

    dashboardWS.onopen = function(event) {
        console.log('Dashboard WebSocket connected');
        showNotification('Connected to dashboard', 'success');
    };

    dashboardWS.onmessage = function(event) {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };

    dashboardWS.onclose = function(event) {
        console.log('Dashboard WebSocket disconnected');
        showNotification('Disconnected from dashboard', 'warning');
        // Reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
    };

    dashboardWS.onerror = function(error) {
        console.error('Dashboard WebSocket error:', error);
        showNotification('WebSocket error', 'danger');
    };
}

function handleWebSocketMessage(message) {
    switch(message.type) {
        case 'worker_update':
            updateWorkerCard(message.worker_id, message.data);
            break;
        case 'master_update':
            updateMasterPanel(message.data);
            break;
        case 'communication_log':
            addCommunicationMessage(message.data);
            break;
        default:
            console.log('Unknown message type:', message.type);
    }
}

async function loadInitialData() {
    try {
        // Load workers
        const workersResponse = await fetch('/workers');
        const workers = await workersResponse.json();

        for (const worker of workers) {
            createWorkerCard(worker);
        }

        // Load master status
        const masterResponse = await fetch('/master/status');
        const masterStatus = await masterResponse.json();
        updateMasterPanel(masterStatus);

        // Load communication log
        const commResponse = await fetch('/communication/log');
        const commData = await commResponse.json();

        for (const message of commData.messages) {
            addCommunicationMessage(message);
        }

    } catch (error) {
        console.error('Error loading initial data:', error);
        showNotification('Error loading dashboard data', 'danger');
    }
}

function createWorkerCard(worker) {
    const workersGrid = document.getElementById('workersGrid');

    const cardHtml = `
        <div class="col-lg-4 col-md-6">
            <div class="card worker-card ${worker.status}" id="worker-${worker.worker_id}">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div>
                        <span class="status-indicator status-${worker.status}"></span>
                        <strong>${worker.worker_id}</strong>
                        <span class="badge bg-secondary">${worker.model}</span>
                    </div>
                    <div class="dropdown">
                        <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button"
                                data-bs-toggle="dropdown">
                            <i class="fas fa-ellipsis-v"></i>
                        </button>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="#" onclick="showWorkerDetails('${worker.worker_id}')">
                                <i class="fas fa-info-circle"></i> Details</a></li>
                            <li><a class="dropdown-item" href="#" onclick="showWorkerLogs('${worker.worker_id}')">
                                <i class="fas fa-file-alt"></i> View Logs</a></li>
                            <li><a class="dropdown-item" href="#" onclick="showSendMessage('${worker.worker_id}')">
                                <i class="fas fa-envelope"></i> Send Message</a></li>
                            <li><a class="dropdown-item" href="#" onclick="showWorkerMemory('${worker.worker_id}')">
                                <i class="fas fa-memory"></i> Memory Files</a></li>
                            <li><a class="dropdown-item" href="#" onclick="showWorkerDiff('${worker.worker_id}')">
                                <i class="fas fa-code-branch"></i> Git Diff</a></li>
                        </ul>
                    </div>
                </div>
                <div class="card-body">
                    <div class="mb-2">
                        <small class="text-muted">Branch:</small>
                        <code id="worker-${worker.worker_id}-branch">${worker.branch}</code>
                    </div>
                    <div class="mb-2">
                        <small class="text-muted">Task:</small>
                        <span id="worker-${worker.worker_id}-task">${worker.task_title}</span>
                    </div>
                    <div class="mb-3">
                        <div class="progress">
                            <div class="progress-bar" role="progressbar"
                                 style="width: ${worker.progress}%"
                                 id="worker-${worker.worker_id}-progress">
                                ${worker.progress}%
                            </div>
                        </div>
                    </div>
                    <div class="terminal-container" id="terminal-${worker.worker_id}">
                        <!-- Terminal output will be loaded here -->
                    </div>
                </div>
                <div class="card-footer">
                    <div class="btn-group" role="group">
                        <button type="button" class="btn btn-sm btn-warning"
                                onclick="toggleWorkerPause('${worker.worker_id}', '${worker.status}')"
                                id="pause-btn-${worker.worker_id}">
                            ${worker.status === 'paused' ? 'Resume' : 'Pause'}
                        </button>
                        <button type="button" class="btn btn-sm btn-danger"
                                onclick="terminateWorker('${worker.worker_id}')">
                            Terminate
                        </button>
                        <button type="button" class="btn btn-sm btn-info"
                                onclick="expandWorker('${worker.worker_id}')">
                            Expand
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    workersGrid.insertAdjacentHTML('beforeend', cardHtml);

    // Initialize terminal for this worker
    initializeWorkerTerminal(worker.worker_id);
}

function updateWorkerCard(workerId, data) {
    // Update existing worker card or create if it doesn't exist
    const card = document.getElementById(`worker-${workerId}`);

    if (!card) {
        createWorkerCard(data);
        return;
    }

    // Update status
    card.className = `card worker-card ${data.status}`;

    // Update status indicator
    const statusIndicator = card.querySelector('.status-indicator');
    if (statusIndicator) {
        statusIndicator.className = `status-indicator status-${data.status}`;
    }

    // Update branch
    const branchElement = document.getElementById(`worker-${workerId}-branch`);
    if (branchElement) {
        branchElement.textContent = data.branch;
    }

    // Update task
    const taskElement = document.getElementById(`worker-${workerId}-task`);
    if (taskElement) {
        taskElement.textContent = data.task_title;
    }

    // Update progress
    const progressElement = document.getElementById(`worker-${workerId}-progress`);
    if (progressElement) {
        progressElement.style.width = `${data.progress}%`;
        progressElement.textContent = `${data.progress}%`;
    }

    // Update pause button
    const pauseBtn = document.getElementById(`pause-btn-${workerId}`);
    if (pauseBtn) {
        pauseBtn.textContent = data.status === 'paused' ? 'Resume' : 'Pause';
    }

    // Update terminal output
    if (data.log_lines) {
        updateWorkerTerminal(workerId, data.log_lines);
    }
}

function updateMasterPanel(data) {
    document.getElementById('activeWorkers').textContent = data.active_workers;
    document.getElementById('tasksCompleted').textContent = data.tasks_completed;
    document.getElementById('tasksInProgress').textContent = data.tasks_in_progress;
    document.getElementById('tasksQueued').textContent = data.tasks_queued;
    document.getElementById('currentActivity').textContent = data.current_activity;
    document.getElementById('repositoryStatus').textContent = data.repository_status;
}

function initializeWorkerTerminal(workerId) {
    const terminalContainer = document.getElementById(`terminal-${workerId}`);

    // For now, just use a simple div. Could integrate xterm.js later
    terminalContainer.innerHTML = '<div class="terminal-output" id="terminal-output-' + workerId + '"></div>';

    // Connect to worker terminal WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/worker/${workerId}`;

    const workerWS = new WebSocket(wsUrl);
    workerTerminals[workerId] = workerWS;

    workerWS.onmessage = function(event) {
        const message = JSON.parse(event.data);
        if (message.type === 'log_update') {
            updateWorkerTerminal(workerId, message.logs);
        }
    };
}

function updateWorkerTerminal(workerId, logLines) {
    const terminalOutput = document.getElementById(`terminal-output-${workerId}`);
    if (terminalOutput) {
        // Show last 10 lines
        const recentLines = logLines.slice(-10);
        terminalOutput.innerHTML = recentLines.map(line =>
            `<div class="terminal-line">${escapeHtml(line)}</div>`
        ).join('');

        // Auto-scroll to bottom
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
    }
}

function addCommunicationMessage(message) {
    const communicationLog = document.getElementById('communicationLog');

    const timestamp = new Date(message.created_at).toLocaleTimeString();
    const messageHtml = `
        <div class="communication-message">
            [${timestamp}] ${message.from_id} → ${message.to_id} (${message.message_type}):
            ${escapeHtml(JSON.stringify(message.content).substring(0, 100))}...
        </div>
    `;

    communicationLog.insertAdjacentHTML('beforeend', messageHtml);
    communicationLog.scrollTop = communicationLog.scrollHeight;
}

// Worker actions
async function toggleWorkerPause(workerId, currentStatus) {
    const action = currentStatus === 'paused' ? 'resume' : 'pause';

    try {
        const response = await fetch(`/workers/${workerId}/${action}`, {
            method: 'POST'
        });

        if (response.ok) {
            showNotification(`Worker ${workerId} ${action}d successfully`, 'success');
        } else {
            throw new Error(`Failed to ${action} worker`);
        }
    } catch (error) {
        console.error(`Error ${action}ing worker:`, error);
        showNotification(`Error ${action}ing worker: ${error.message}`, 'danger');
    }
}

async function terminateWorker(workerId) {
    if (!confirm(`Are you sure you want to terminate worker ${workerId}?`)) {
        return;
    }

    try {
        const response = await fetch(`/workers/${workerId}/terminate`, {
            method: 'POST'
        });

        if (response.ok) {
            showNotification(`Worker ${workerId} terminated successfully`, 'success');
        } else {
            throw new Error('Failed to terminate worker');
        }
    } catch (error) {
        console.error('Error terminating worker:', error);
        showNotification(`Error terminating worker: ${error.message}`, 'danger');
    }
}

function expandWorker(workerId) {
    // This would show an expanded view of the worker
    showWorkerDetails(workerId);
}

function showWorkerDetails(workerId) {
    // Load and show worker details in modal
    currentWorkerId = workerId;

    fetch(`/workers/${workerId}/logs?lines=200`)
        .then(response => response.json())
        .then(data => {
            const modalContent = `
                <h6>Full Logs for ${workerId}</h6>
                <div class="terminal-container" style="height: 400px;">
                    ${data.logs.map(line => `<div>${escapeHtml(line)}</div>`).join('')}
                </div>
            `;
            document.getElementById('workerDetailsContent').innerHTML = modalContent;

            const modal = new bootstrap.Modal(document.getElementById('workerDetailsModal'));
            modal.show();
        })
        .catch(error => {
            console.error('Error loading worker details:', error);
            showNotification('Error loading worker details', 'danger');
        });
}

function showWorkerLogs(workerId) {
    showWorkerDetails(workerId);
}

function showSendMessage(workerId) {
    currentWorkerId = workerId;
    document.getElementById('messageRecipient').value = workerId;
    document.getElementById('messageContent').value = '';

    const modal = new bootstrap.Modal(document.getElementById('sendMessageModal'));
    modal.show();
}

async function sendMessage() {
    const recipient = document.getElementById('messageRecipient').value;
    const content = document.getElementById('messageContent').value;
    const priority = parseInt(document.getElementById('messagePriority').value);

    if (!content.trim()) {
        showNotification('Please enter a message', 'warning');
        return;
    }

    try {
        const response = await fetch(`/workers/${recipient}/message`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: content,
                priority: priority
            })
        });

        if (response.ok) {
            showNotification('Message sent successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('sendMessageModal')).hide();
        } else {
            throw new Error('Failed to send message');
        }
    } catch (error) {
        console.error('Error sending message:', error);
        showNotification(`Error sending message: ${error.message}`, 'danger');
    }
}

function showWorkerMemory(workerId) {
    fetch(`/workers/${workerId}/memory`)
        .then(response => response.json())
        .then(data => {
            const modalContent = `
                <h6>Memory Files for ${workerId}</h6>
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>File</th>
                                <th>Size</th>
                                <th>Modified</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.memory_files.map(file => `
                                <tr>
                                    <td>${file.name}</td>
                                    <td>${file.size} bytes</td>
                                    <td>${new Date(file.modified).toLocaleString()}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            document.getElementById('workerDetailsContent').innerHTML = modalContent;

            const modal = new bootstrap.Modal(document.getElementById('workerDetailsModal'));
            modal.show();
        })
        .catch(error => {
            console.error('Error loading worker memory:', error);
            showNotification('Error loading worker memory', 'danger');
        });
}

function showWorkerDiff(workerId) {
    fetch(`/workers/${workerId}/diff`)
        .then(response => response.json())
        .then(data => {
            const modalContent = `
                <h6>Git Diff for ${workerId}</h6>
                <pre class="bg-light p-3" style="max-height: 400px; overflow-y: auto;">${escapeHtml(data.diff)}</pre>
            `;
            document.getElementById('workerDetailsContent').innerHTML = modalContent;

            const modal = new bootstrap.Modal(document.getElementById('workerDetailsModal'));
            modal.show();
        })
        .catch(error => {
            console.error('Error loading worker diff:', error);
            showNotification('Error loading worker diff', 'danger');
        });
}

// Global actions
async function spawnWorker() {
    const model = prompt('Enter worker model (opus/sonnet/haiku):', 'sonnet');
    if (!model) return;

    const taskName = prompt('Enter task name:', 'general');
    if (!taskName) return;

    try {
        const response = await fetch('/workers/spawn', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `model=${model}&task_name=${taskName}&base_branch=main`
        });

        if (response.ok) {
            const result = await response.json();
            showNotification(`Worker ${result.worker_id} spawned successfully`, 'success');
        } else {
            throw new Error('Failed to spawn worker');
        }
    } catch (error) {
        console.error('Error spawning worker:', error);
        showNotification(`Error spawning worker: ${error.message}`, 'danger');
    }
}

async function pauseAll() {
    if (!confirm('Are you sure you want to pause all workers?')) {
        return;
    }

    // This would implement pause all functionality
    showNotification('Pause all workers functionality would be implemented here', 'info');
}

async function resumeAll() {
    if (!confirm('Are you sure you want to resume all workers?')) {
        return;
    }

    // This would implement resume all functionality
    showNotification('Resume all workers functionality would be implemented here', 'info');
}

function refreshAll() {
    location.reload();
}

function clearCommunicationLog() {
    document.getElementById('communicationLog').innerHTML = '';
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showNotification(message, type = 'info') {
    // Create and show a toast notification
    const toastHtml = `
        <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    // Add toast container if it doesn't exist
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }

    toastContainer.insertAdjacentHTML('beforeend', toastHtml);

    // Show the toast
    const toastElement = toastContainer.lastElementChild;
    const toast = new bootstrap.Toast(toastElement);
    toast.show();

    // Remove toast after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}
        '''

        js_file = self.static_dir / "dashboard.js"
        with open(js_file, 'w') as f:
            f.write(js_content)

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the web dashboard server."""
        logger.info(f"Starting web dashboard server on {host}:{port}")

        # Start the server
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )


async def main():
    """Main entry point for the web dashboard server."""
    server = WebDashboardServer()
    await server.start()

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Web dashboard server interrupted")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())