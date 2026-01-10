#!/usr/bin/env python3
"""
Advanced Web Dashboard with Enhanced Features
Enhanced version of the web dashboard with xterm.js, Chart.js, and advanced styling.
"""

import json
from pathlib import Path
from web_dashboard_server import WebDashboardServer


class AdvancedWebDashboard(WebDashboardServer):
    """Enhanced web dashboard with advanced features."""

    def render_dashboard(self) -> str:
        """Render the advanced dashboard HTML with enhanced features."""
        html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Agent Orchestrator Dashboard</title>

    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

    <!-- Font Awesome -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">

    <!-- xterm.js -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
    <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-web-links@0.9.0/lib/xterm-addon-web-links.min.js"></script>

    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.min.js"></script>

    <!-- Custom Styles -->
    <style>
        :root {
            --primary-color: #2563eb;
            --success-color: #16a34a;
            --warning-color: #d97706;
            --danger-color: #dc2626;
            --info-color: #0891b2;
            --dark-color: #1f2937;
            --light-color: #f8fafc;
        }

        body {
            background-color: #f1f5f9;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        }

        .dashboard-header {
            background: linear-gradient(135deg, var(--primary-color) 0%, #1e40af 100%);
            color: white;
            padding: 1rem 0;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        .worker-card {
            border: none;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
            margin-bottom: 1.5rem;
            overflow: hidden;
        }

        .worker-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px -3px rgba(0, 0, 0, 0.1);
        }

        .worker-card.active {
            border-left: 4px solid var(--success-color);
        }

        .worker-card.waiting {
            border-left: 4px solid var(--warning-color);
        }

        .worker-card.paused {
            border-left: 4px solid var(--danger-color);
        }

        .worker-card.error {
            border-left: 4px solid var(--danger-color);
        }

        .worker-card.terminated {
            border-left: 4px solid #6b7280;
            opacity: 0.7;
        }

        .terminal-container {
            background: #0f172a;
            border-radius: 8px;
            padding: 0;
            height: 200px;
            overflow: hidden;
            font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        }

        .terminal-container .xterm {
            padding: 10px;
        }

        .status-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .status-active {
            background-color: #dcfce7;
            color: #15803d;
        }

        .status-waiting {
            background-color: #fef3c7;
            color: #d97706;
        }

        .status-paused {
            background-color: #fee2e2;
            color: #dc2626;
        }

        .status-error {
            background-color: #fee2e2;
            color: #dc2626;
        }

        .status-terminated {
            background-color: #f3f4f6;
            color: #6b7280;
        }

        .status-initializing {
            background-color: #dbeafe;
            color: #2563eb;
        }

        .master-panel {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 10px 25px -3px rgba(0, 0, 0, 0.1);
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            backdrop-filter: blur(10px);
        }

        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        .stat-label {
            font-size: 0.875rem;
            opacity: 0.9;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .communication-log {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            height: 350px;
            overflow-y: auto;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
            font-size: 0.875rem;
        }

        .communication-message {
            padding: 0.5rem;
            border-bottom: 1px solid #e5e7eb;
            transition: background-color 0.2s;
        }

        .communication-message:hover {
            background-color: #f9fafb;
        }

        .progress-ring {
            transform: rotate(-90deg);
        }

        .progress-ring-circle {
            stroke-dasharray: 251.2;
            stroke-dashoffset: 251.2;
            transition: stroke-dashoffset 0.3s;
        }

        .btn-gradient {
            background: linear-gradient(45deg, var(--primary-color), #3b82f6);
            border: none;
            color: white;
            transition: all 0.3s ease;
        }

        .btn-gradient:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
            color: white;
        }

        .chart-container {
            position: relative;
            height: 300px;
            margin: 1rem 0;
        }

        .modal-content {
            border-radius: 16px;
            border: none;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        }

        .modal-header {
            border-bottom: 1px solid #e5e7eb;
            border-radius: 16px 16px 0 0;
        }

        .navbar-brand {
            font-weight: 700;
            font-size: 1.25rem;
        }

        .worker-header {
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            padding: 1rem;
            border-radius: 12px 12px 0 0;
        }

        .worker-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin: 0;
        }

        .worker-subtitle {
            font-size: 0.875rem;
            color: #64748b;
            margin: 0.25rem 0 0 0;
        }

        .action-buttons {
            gap: 0.5rem;
        }

        .btn-action {
            border-radius: 8px;
            font-size: 0.875rem;
            padding: 0.5rem 1rem;
            transition: all 0.2s ease;
        }

        .btn-action:hover {
            transform: translateY(-1px);
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .loading {
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }

        .toast-container {
            z-index: 9999;
        }

        /* Dark mode support */
        @media (prefers-color-scheme: dark) {
            body {
                background-color: #111827;
                color: #f9fafb;
            }

            .worker-card {
                background-color: #1f2937;
                color: #f9fafb;
            }

            .communication-log {
                background-color: #1f2937;
                color: #f9fafb;
            }

            .communication-message:hover {
                background-color: #374151;
            }
        }

        /* Responsive design */
        @media (max-width: 768px) {
            .master-panel {
                padding: 1rem;
            }

            .stat-card {
                padding: 1rem;
                margin-bottom: 1rem;
            }

            .stat-number {
                font-size: 2rem;
            }

            .terminal-container {
                height: 150px;
            }

            .communication-log {
                height: 250px;
            }
        }
    </style>
</head>
<body>
    <!-- Header -->
    <div class="dashboard-header">
        <div class="container-fluid">
            <div class="d-flex justify-content-between align-items-center">
                <div class="navbar-brand">
                    <i class="fas fa-desktop me-2"></i>
                    Multi-Agent Orchestrator Dashboard
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-outline-light btn-sm" onclick="refreshAll()">
                        <i class="fas fa-sync-alt me-1"></i> Refresh
                    </button>
                    <button class="btn btn-success btn-sm" onclick="spawnWorker()">
                        <i class="fas fa-plus me-1"></i> Spawn Worker
                    </button>
                    <button class="btn btn-warning btn-sm" onclick="pauseAll()">
                        <i class="fas fa-pause me-1"></i> Pause All
                    </button>
                    <button class="btn btn-info btn-sm" onclick="resumeAll()">
                        <i class="fas fa-play me-1"></i> Resume All
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="container-fluid p-4">
        <!-- Master Control Panel -->
        <div class="master-panel" id="masterPanel">
            <div class="row g-4">
                <div class="col-md-3">
                    <div class="stat-card">
                        <div class="stat-number" id="activeWorkers">0</div>
                        <div class="stat-label">Active Workers</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card">
                        <div class="stat-number" id="tasksCompleted">0</div>
                        <div class="stat-label">Completed</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card">
                        <div class="stat-number" id="tasksInProgress">0</div>
                        <div class="stat-label">In Progress</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card">
                        <div class="stat-number" id="tasksQueued">0</div>
                        <div class="stat-label">Queued</div>
                    </div>
                </div>
            </div>

            <div class="row mt-4">
                <div class="col-md-6">
                    <h6><i class="fas fa-activity me-2"></i>Current Activity</h6>
                    <p id="currentActivity" class="mb-0">Initializing...</p>
                </div>
                <div class="col-md-6">
                    <h6><i class="fas fa-code-branch me-2"></i>Repository Status</h6>
                    <p id="repositoryStatus" class="mb-0">Unknown</p>
                </div>
            </div>
        </div>

        <!-- Workers Grid -->
        <div class="row" id="workersGrid">
            <!-- Worker cards will be dynamically added here -->
        </div>

        <!-- Charts Section -->
        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-chart-pie me-2"></i>Task Distribution</h5>
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="taskChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-chart-line me-2"></i>Worker Performance</h5>
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="performanceChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Communication Log -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">
                            <i class="fas fa-comments me-2"></i>
                            Master ↔ Worker Communication Log
                        </h5>
                        <div>
                            <button class="btn btn-sm btn-outline-secondary" onclick="filterCommunicationLog()">
                                <i class="fas fa-filter me-1"></i> Filter
                            </button>
                            <button class="btn btn-sm btn-outline-secondary" onclick="clearCommunicationLog()">
                                <i class="fas fa-trash me-1"></i> Clear
                            </button>
                        </div>
                    </div>
                    <div class="card-body p-0">
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
        <div class="modal-dialog modal-xl">
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
                            <textarea class="form-control" id="messageContent" rows="4" required
                                      placeholder="Enter your message here..."></textarea>
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
                    <button type="button" class="btn btn-gradient" onclick="sendMessage()">
                        <i class="fas fa-paper-plane me-1"></i> Send Message
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- Spawn Worker Modal -->
    <div class="modal fade" id="spawnWorkerModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Spawn New Worker</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="spawnWorkerForm">
                        <div class="mb-3">
                            <label for="workerModel" class="form-label">Model:</label>
                            <select class="form-select" id="workerModel">
                                <option value="opus">Claude Opus (Highest capability)</option>
                                <option value="sonnet" selected>Claude Sonnet (Balanced)</option>
                                <option value="haiku">Claude Haiku (Fastest)</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label for="taskName" class="form-label">Task Name:</label>
                            <input type="text" class="form-control" id="taskName" value="general" required>
                        </div>
                        <div class="mb-3">
                            <label for="baseBranch" class="form-label">Base Branch:</label>
                            <input type="text" class="form-control" id="baseBranch" value="main" required>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-gradient" onclick="submitSpawnWorker()">
                        <i class="fas fa-rocket me-1"></i> Spawn Worker
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

    <!-- Enhanced Dashboard JS -->
    <script src="/static/advanced_dashboard.js"></script>
</body>
</html>
        '''
        return html_content

    async def create_static_files(self):
        """Create enhanced static files."""
        await super().create_static_files()
        await self.create_advanced_dashboard_js()

    async def create_advanced_dashboard_js(self):
        """Create the advanced dashboard JavaScript with enhanced features."""
        js_content = '''
// Advanced Dashboard JavaScript for Multi-Agent Orchestrator
class AdvancedDashboard {
    constructor() {
        this.dashboardWS = null;
        this.workerTerminals = {};
        this.workerCharts = {};
        this.currentWorkerId = null;
        this.taskChart = null;
        this.performanceChart = null;
        this.communicationFilter = '';
    }

    async initialize() {
        console.log('Initializing Advanced Multi-Agent Orchestrator Dashboard');

        this.connectWebSocket();
        await this.loadInitialData();
        this.initializeCharts();
        this.setupEventListeners();
        this.startPeriodicUpdates();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;

        this.dashboardWS = new WebSocket(wsUrl);

        this.dashboardWS.onopen = (event) => {
            console.log('Dashboard WebSocket connected');
            this.showNotification('Connected to dashboard', 'success');
        };

        this.dashboardWS.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleWebSocketMessage(message);
        };

        this.dashboardWS.onclose = (event) => {
            console.log('Dashboard WebSocket disconnected');
            this.showNotification('Disconnected from dashboard', 'warning');
            // Reconnect after 5 seconds
            setTimeout(() => this.connectWebSocket(), 5000);
        };

        this.dashboardWS.onerror = (error) => {
            console.error('Dashboard WebSocket error:', error);
            this.showNotification('WebSocket error', 'danger');
        };
    }

    handleWebSocketMessage(message) {
        switch(message.type) {
            case 'worker_update':
                this.updateWorkerCard(message.worker_id, message.data);
                break;
            case 'master_update':
                this.updateMasterPanel(message.data);
                break;
            case 'communication_log':
                this.addCommunicationMessage(message.data);
                break;
            default:
                console.log('Unknown message type:', message.type);
        }
    }

    async loadInitialData() {
        try {
            // Load workers
            const workersResponse = await fetch('/workers');
            const workers = await workersResponse.json();

            for (const worker of workers) {
                this.createWorkerCard(worker);
            }

            // Load master status
            const masterResponse = await fetch('/master/status');
            const masterStatus = await masterResponse.json();
            this.updateMasterPanel(masterStatus);

            // Load communication log
            const commResponse = await fetch('/communication/log');
            const commData = await commResponse.json();

            for (const message of commData.messages) {
                this.addCommunicationMessage(message);
            }

        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showNotification('Error loading dashboard data', 'danger');
        }
    }

    createWorkerCard(worker) {
        const workersGrid = document.getElementById('workersGrid');

        const cardHtml = `
            <div class="col-lg-4 col-md-6">
                <div class="card worker-card ${worker.status}" id="worker-${worker.worker_id}">
                    <div class="worker-header">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h5 class="worker-title">
                                    <span class="status-badge status-${worker.status}">${worker.status}</span>
                                    ${worker.worker_id}
                                </h5>
                                <p class="worker-subtitle">
                                    <i class="fas fa-microchip me-1"></i>${worker.model}
                                    <i class="fas fa-code-branch ms-2 me-1"></i><span id="worker-${worker.worker_id}-branch">${worker.branch}</span>
                                </p>
                            </div>
                            <div class="dropdown">
                                <button class="btn btn-sm btn-outline-secondary dropdown-toggle"
                                        type="button" data-bs-toggle="dropdown">
                                    <i class="fas fa-ellipsis-v"></i>
                                </button>
                                <ul class="dropdown-menu">
                                    <li><a class="dropdown-item" href="#" onclick="dashboard.showWorkerDetails('${worker.worker_id}')">
                                        <i class="fas fa-info-circle me-2"></i>Details</a></li>
                                    <li><a class="dropdown-item" href="#" onclick="dashboard.showWorkerLogs('${worker.worker_id}')">
                                        <i class="fas fa-file-alt me-2"></i>View Logs</a></li>
                                    <li><a class="dropdown-item" href="#" onclick="dashboard.showSendMessage('${worker.worker_id}')">
                                        <i class="fas fa-envelope me-2"></i>Send Message</a></li>
                                    <li><a class="dropdown-item" href="#" onclick="dashboard.showWorkerMemory('${worker.worker_id}')">
                                        <i class="fas fa-memory me-2"></i>Memory Files</a></li>
                                    <li><a class="dropdown-item" href="#" onclick="dashboard.showWorkerDiff('${worker.worker_id}')">
                                        <i class="fas fa-code-branch me-2"></i>Git Diff</a></li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <div class="card-body">
                        <div class="mb-3">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="text-muted">Task Progress</span>
                                <span class="fw-bold" id="worker-${worker.worker_id}-progress-text">${worker.progress}%</span>
                            </div>
                            <div class="progress" style="height: 8px;">
                                <div class="progress-bar bg-primary" role="progressbar"
                                     style="width: ${worker.progress}%"
                                     id="worker-${worker.worker_id}-progress"></div>
                            </div>
                        </div>

                        <div class="mb-3">
                            <small class="text-muted">Current Task:</small>
                            <div id="worker-${worker.worker_id}-task" class="small">${worker.task_title}</div>
                        </div>

                        <div class="terminal-container" id="terminal-${worker.worker_id}">
                            <!-- xterm.js terminal will be initialized here -->
                        </div>
                    </div>

                    <div class="card-footer bg-transparent">
                        <div class="d-flex action-buttons">
                            <button type="button" class="btn btn-sm btn-warning btn-action"
                                    onclick="dashboard.toggleWorkerPause('${worker.worker_id}', '${worker.status}')"
                                    id="pause-btn-${worker.worker_id}">
                                <i class="fas fa-${worker.status === 'paused' ? 'play' : 'pause'} me-1"></i>
                                ${worker.status === 'paused' ? 'Resume' : 'Pause'}
                            </button>
                            <button type="button" class="btn btn-sm btn-danger btn-action"
                                    onclick="dashboard.terminateWorker('${worker.worker_id}')">
                                <i class="fas fa-stop me-1"></i>Terminate
                            </button>
                            <button type="button" class="btn btn-sm btn-info btn-action"
                                    onclick="dashboard.expandWorker('${worker.worker_id}')">
                                <i class="fas fa-expand me-1"></i>Expand
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        workersGrid.insertAdjacentHTML('beforeend', cardHtml);
        this.initializeWorkerTerminal(worker.worker_id);
    }

    updateWorkerCard(workerId, data) {
        const card = document.getElementById(`worker-${workerId}`);

        if (!card) {
            this.createWorkerCard(data);
            return;
        }

        // Update status
        card.className = `card worker-card ${data.status}`;

        // Update status badge
        const statusBadge = card.querySelector('.status-badge');
        if (statusBadge) {
            statusBadge.className = `status-badge status-${data.status}`;
            statusBadge.textContent = data.status;
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
        const progressTextElement = document.getElementById(`worker-${workerId}-progress-text`);
        if (progressElement && progressTextElement) {
            progressElement.style.width = `${data.progress}%`;
            progressTextElement.textContent = `${data.progress}%`;
        }

        // Update pause button
        const pauseBtn = document.getElementById(`pause-btn-${workerId}`);
        if (pauseBtn) {
            const isResumeButton = data.status === 'paused';
            pauseBtn.innerHTML = `<i class="fas fa-${isResumeButton ? 'play' : 'pause'} me-1"></i>${isResumeButton ? 'Resume' : 'Pause'}`;
        }

        // Update terminal output
        if (data.log_lines && this.workerTerminals[workerId]) {
            this.updateWorkerTerminal(workerId, data.log_lines);
        }
    }

    updateMasterPanel(data) {
        document.getElementById('activeWorkers').textContent = data.active_workers;
        document.getElementById('tasksCompleted').textContent = data.tasks_completed;
        document.getElementById('tasksInProgress').textContent = data.tasks_in_progress;
        document.getElementById('tasksQueued').textContent = data.tasks_queued;
        document.getElementById('currentActivity').textContent = data.current_activity;
        document.getElementById('repositoryStatus').textContent = data.repository_status;

        // Update charts
        this.updateCharts(data);
    }

    initializeWorkerTerminal(workerId) {
        const terminalContainer = document.getElementById(`terminal-${workerId}`);

        // Initialize xterm.js terminal
        const terminal = new Terminal({
            cursorBlink: true,
            fontSize: 12,
            fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
            theme: {
                background: '#0f172a',
                foreground: '#f1f5f9',
                cursor: '#f1f5f9',
                black: '#1e293b',
                red: '#ef4444',
                green: '#22c55e',
                yellow: '#eab308',
                blue: '#3b82f6',
                magenta: '#a855f7',
                cyan: '#06b6d4',
                white: '#f1f5f9'
            }
        });

        const fitAddon = new FitAddon.FitAddon();
        terminal.loadAddon(fitAddon);
        terminal.loadAddon(new WebLinksAddon.WebLinksAddon());

        terminal.open(terminalContainer);
        fitAddon.fit();

        // Store terminal reference
        this.workerTerminals[workerId] = terminal;

        // Connect to worker terminal WebSocket
        this.connectWorkerTerminal(workerId, terminal);

        // Handle resize
        window.addEventListener('resize', () => {
            fitAddon.fit();
        });
    }

    connectWorkerTerminal(workerId, terminal) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/worker/${workerId}`;

        const workerWS = new WebSocket(wsUrl);

        workerWS.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.type === 'log_update') {
                this.updateWorkerTerminal(workerId, message.logs);
            }
        };

        workerWS.onclose = () => {
            // Reconnect after 5 seconds
            setTimeout(() => this.connectWorkerTerminal(workerId, terminal), 5000);
        };
    }

    updateWorkerTerminal(workerId, logLines) {
        const terminal = this.workerTerminals[workerId];
        if (terminal) {
            // Clear terminal and write new lines
            terminal.clear();

            // Show last 15 lines
            const recentLines = logLines.slice(-15);
            for (const line of recentLines) {
                terminal.writeln(line);
            }
        }
    }

    initializeCharts() {
        // Task Distribution Chart
        const taskCtx = document.getElementById('taskChart').getContext('2d');
        this.taskChart = new Chart(taskCtx, {
            type: 'doughnut',
            data: {
                labels: ['Completed', 'In Progress', 'Queued'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#22c55e', '#3b82f6', '#eab308'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });

        // Performance Chart
        const perfCtx = document.getElementById('performanceChart').getContext('2d');
        this.performanceChart = new Chart(perfCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Active Workers',
                    data: [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    updateCharts(data) {
        // Update task distribution chart
        if (this.taskChart) {
            this.taskChart.data.datasets[0].data = [
                data.tasks_completed,
                data.tasks_in_progress,
                data.tasks_queued
            ];
            this.taskChart.update();
        }

        // Update performance chart
        if (this.performanceChart) {
            const now = new Date().toLocaleTimeString();
            this.performanceChart.data.labels.push(now);
            this.performanceChart.data.datasets[0].data.push(data.active_workers);

            // Keep only last 10 data points
            if (this.performanceChart.data.labels.length > 10) {
                this.performanceChart.data.labels.shift();
                this.performanceChart.data.datasets[0].data.shift();
            }

            this.performanceChart.update();
        }
    }

    addCommunicationMessage(message) {
        const communicationLog = document.getElementById('communicationLog');

        // Apply filter if set
        if (this.communicationFilter &&
            !JSON.stringify(message).toLowerCase().includes(this.communicationFilter.toLowerCase())) {
            return;
        }

        const timestamp = new Date(message.created_at).toLocaleTimeString();
        const messageHtml = `
            <div class="communication-message">
                <span class="text-muted">[${timestamp}]</span>
                <span class="fw-bold text-primary">${message.from_id}</span>
                <i class="fas fa-arrow-right mx-2 text-muted"></i>
                <span class="fw-bold text-success">${message.to_id}</span>
                <span class="badge bg-secondary ms-2">${message.message_type}</span>
                <div class="mt-1 text-muted small">
                    ${this.escapeHtml(JSON.stringify(message.content).substring(0, 150))}${JSON.stringify(message.content).length > 150 ? '...' : ''}
                </div>
            </div>
        `;

        communicationLog.insertAdjacentHTML('beforeend', messageHtml);
        communicationLog.scrollTop = communicationLog.scrollHeight;

        // Keep only last 100 messages
        const messages = communicationLog.querySelectorAll('.communication-message');
        if (messages.length > 100) {
            messages[0].remove();
        }
    }

    setupEventListeners() {
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case 'r':
                        e.preventDefault();
                        this.refreshAll();
                        break;
                    case 'n':
                        e.preventDefault();
                        this.showSpawnWorkerModal();
                        break;
                }
            }
        });
    }

    startPeriodicUpdates() {
        // Refresh charts every 30 seconds
        setInterval(() => {
            this.loadInitialData();
        }, 30000);
    }

    // Worker Actions
    async toggleWorkerPause(workerId, currentStatus) {
        const action = currentStatus === 'paused' ? 'resume' : 'pause';
        await this.workerAction(workerId, action);
    }

    async terminateWorker(workerId) {
        if (!confirm(`Are you sure you want to terminate worker ${workerId}?`)) {
            return;
        }
        await this.workerAction(workerId, 'terminate');
    }

    async workerAction(workerId, action) {
        try {
            const response = await fetch(`/workers/${workerId}/${action}`, {
                method: 'POST'
            });

            if (response.ok) {
                this.showNotification(`Worker ${workerId} ${action}d successfully`, 'success');
            } else {
                throw new Error(`Failed to ${action} worker`);
            }
        } catch (error) {
            console.error(`Error ${action}ing worker:`, error);
            this.showNotification(`Error ${action}ing worker: ${error.message}`, 'danger');
        }
    }

    expandWorker(workerId) {
        this.showWorkerDetails(workerId);
    }

    // Modal Functions
    showWorkerDetails(workerId) {
        this.currentWorkerId = workerId;

        fetch(`/workers/${workerId}/logs?lines=500`)
            .then(response => response.json())
            .then(data => {
                const modalContent = `
                    <div class="row">
                        <div class="col-12">
                            <h6 class="text-primary"><i class="fas fa-terminal me-2"></i>Full Terminal Output for ${workerId}</h6>
                            <div class="terminal-container" style="height: 500px; font-size: 14px;">
                                <div style="padding: 15px; color: #f1f5f9; font-family: 'JetBrains Mono', monospace;">
                                    ${data.logs.map(line => `<div>${this.escapeHtml(line)}</div>`).join('')}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                document.getElementById('workerDetailsContent').innerHTML = modalContent;

                const modal = new bootstrap.Modal(document.getElementById('workerDetailsModal'));
                modal.show();
            })
            .catch(error => {
                console.error('Error loading worker details:', error);
                this.showNotification('Error loading worker details', 'danger');
            });
    }

    showWorkerLogs(workerId) {
        this.showWorkerDetails(workerId);
    }

    showSendMessage(workerId) {
        this.currentWorkerId = workerId;
        document.getElementById('messageRecipient').value = workerId;
        document.getElementById('messageContent').value = '';

        const modal = new bootstrap.Modal(document.getElementById('sendMessageModal'));
        modal.show();
    }

    async sendMessage() {
        const recipient = document.getElementById('messageRecipient').value;
        const content = document.getElementById('messageContent').value;
        const priority = parseInt(document.getElementById('messagePriority').value);

        if (!content.trim()) {
            this.showNotification('Please enter a message', 'warning');
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
                this.showNotification('Message sent successfully', 'success');
                bootstrap.Modal.getInstance(document.getElementById('sendMessageModal')).hide();
            } else {
                throw new Error('Failed to send message');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.showNotification(`Error sending message: ${error.message}`, 'danger');
        }
    }

    showWorkerMemory(workerId) {
        fetch(`/workers/${workerId}/memory`)
            .then(response => response.json())
            .then(data => {
                const modalContent = `
                    <h6 class="text-primary"><i class="fas fa-memory me-2"></i>Memory Files for ${workerId}</h6>
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead class="table-light">
                                <tr>
                                    <th><i class="fas fa-file me-2"></i>File</th>
                                    <th><i class="fas fa-weight me-2"></i>Size</th>
                                    <th><i class="fas fa-clock me-2"></i>Modified</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${data.memory_files.map(file => `
                                    <tr>
                                        <td><code>${file.name}</code></td>
                                        <td>${this.formatFileSize(file.size)}</td>
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
                this.showNotification('Error loading worker memory', 'danger');
            });
    }

    showWorkerDiff(workerId) {
        fetch(`/workers/${workerId}/diff`)
            .then(response => response.json())
            .then(data => {
                const modalContent = `
                    <h6 class="text-primary"><i class="fas fa-code-branch me-2"></i>Git Diff for ${workerId}</h6>
                    <pre class="bg-dark text-light p-3 rounded" style="max-height: 500px; overflow-y: auto; font-size: 13px;">${this.escapeHtml(data.diff)}</pre>
                `;
                document.getElementById('workerDetailsContent').innerHTML = modalContent;

                const modal = new bootstrap.Modal(document.getElementById('workerDetailsModal'));
                modal.show();
            })
            .catch(error => {
                console.error('Error loading worker diff:', error);
                this.showNotification('Error loading worker diff', 'danger');
            });
    }

    showSpawnWorkerModal() {
        const modal = new bootstrap.Modal(document.getElementById('spawnWorkerModal'));
        modal.show();
    }

    async submitSpawnWorker() {
        const model = document.getElementById('workerModel').value;
        const taskName = document.getElementById('taskName').value;
        const baseBranch = document.getElementById('baseBranch').value;

        if (!taskName.trim()) {
            this.showNotification('Please enter a task name', 'warning');
            return;
        }

        try {
            const response = await fetch('/workers/spawn', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: `model=${model}&task_name=${taskName}&base_branch=${baseBranch}`
            });

            if (response.ok) {
                const result = await response.json();
                this.showNotification(`Worker ${result.worker_id} spawned successfully`, 'success');
                bootstrap.Modal.getInstance(document.getElementById('spawnWorkerModal')).hide();
            } else {
                throw new Error('Failed to spawn worker');
            }
        } catch (error) {
            console.error('Error spawning worker:', error);
            this.showNotification(`Error spawning worker: ${error.message}`, 'danger');
        }
    }

    // Global Actions
    async pauseAll() {
        if (!confirm('Are you sure you want to pause all workers?')) {
            return;
        }
        this.showNotification('Pause all workers functionality would be implemented here', 'info');
    }

    async resumeAll() {
        if (!confirm('Are you sure you want to resume all workers?')) {
            return;
        }
        this.showNotification('Resume all workers functionality would be implemented here', 'info');
    }

    refreshAll() {
        location.reload();
    }

    clearCommunicationLog() {
        document.getElementById('communicationLog').innerHTML = '';
    }

    filterCommunicationLog() {
        const filter = prompt('Enter filter text (leave empty to clear filter):', this.communicationFilter);
        if (filter !== null) {
            this.communicationFilter = filter;
            this.showNotification(filter ? `Filter applied: ${filter}` : 'Filter cleared', 'info');
        }
    }

    // Utility Functions
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';

        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    showNotification(message, type = 'info') {
        const toastHtml = `
            <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="fas fa-${this.getIconForType(type)} me-2"></i>
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '9999';
            document.body.appendChild(toastContainer);
        }

        toastContainer.insertAdjacentHTML('beforeend', toastHtml);

        const toastElement = toastContainer.lastElementChild;
        const toast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: type === 'danger' ? 7000 : 3000
        });
        toast.show();

        toastElement.addEventListener('hidden.bs.toast', function() {
            toastElement.remove();
        });
    }

    getIconForType(type) {
        const icons = {
            success: 'check-circle',
            danger: 'exclamation-triangle',
            warning: 'exclamation-circle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }
}

// Global functions for compatibility
const dashboard = new AdvancedDashboard();

// Global function aliases
window.spawnWorker = () => dashboard.showSpawnWorkerModal();
window.submitSpawnWorker = () => dashboard.submitSpawnWorker();
window.sendMessage = () => dashboard.sendMessage();
window.pauseAll = () => dashboard.pauseAll();
window.resumeAll = () => dashboard.resumeAll();
window.refreshAll = () => dashboard.refreshAll();
window.clearCommunicationLog = () => dashboard.clearCommunicationLog();
window.filterCommunicationLog = () => dashboard.filterCommunicationLog();

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    dashboard.initialize();
});
        '''

        js_file = self.static_dir / "advanced_dashboard.js"
        with open(js_file, 'w') as f:
            f.write(js_content)


# Override the default server to use the advanced version
def create_advanced_web_dashboard(orchestrator=None):
    """Create advanced web dashboard server."""
    return AdvancedWebDashboard(orchestrator)


if __name__ == "__main__":
    import asyncio
    import uvicorn

    async def main():
        server = AdvancedWebDashboard()
        await server.start()

        try:
            server.run(host="0.0.0.0", port=8000)
        except KeyboardInterrupt:
            print("Server stopped")
        finally:
            await server.stop()

    asyncio.run(main())