# Web-Based Monitoring Dashboard

## Overview

The Web-Based Monitoring Dashboard provides remote access to the Multi-Agent Orchestrator system through any modern web browser. Built with FastAPI, WebSockets, and modern web technologies, it offers the same comprehensive monitoring capabilities as the desktop GUI but accessible from any device with internet connectivity.

## Features

### 🌐 Web-Based Access
- **Universal Compatibility**: Access from any device with a web browser
- **Responsive Design**: Optimized for desktop, tablet, and mobile devices
- **Real-time Updates**: WebSocket-powered live data streaming
- **No Installation Required**: Zero client-side installation needed

### 🎯 Core Functionality
- **Worker Monitoring**: Real-time status, progress, and terminal output
- **Master Control Panel**: System overview and worker management
- **Communication Log**: Live Master ↔ Worker message monitoring
- **Interactive Controls**: Pause, resume, terminate, and message workers
- **Terminal Emulation**: Full-featured terminal using xterm.js
- **Data Visualization**: Charts and graphs powered by Chart.js

### 🔧 Technical Stack
- **Backend**: FastAPI with async/await support
- **WebSockets**: Real-time bidirectional communication
- **Frontend**: Bootstrap 5 with responsive design
- **Terminal**: xterm.js for authentic terminal experience
- **Charts**: Chart.js for data visualization
- **Icons**: Font Awesome for professional UI

## Installation

### Prerequisites
- Python 3.8 or higher
- FastAPI and dependencies
- Access to the orchestrator system

### Quick Setup

1. **Run the setup script:**
   ```bash
   python3 setup_web_dashboard.py
   ```

2. **Start the web dashboard:**
   ```bash
   python3 run_web_dashboard.py
   ```

3. **Open your browser:**
   ```
   http://localhost:8000
   ```

### Manual Installation

1. **Install dependencies:**
   ```bash
   pip install -r web_requirements.txt
   ```

2. **Start the server:**
   ```bash
   python3 web_dashboard_server.py
   ```

## Usage

### Starting the Web Dashboard

#### Basic Mode
```bash
python3 run_web_dashboard.py
```
- Default: http://localhost:8000
- Connects to real orchestrator system
- Full interactive functionality

#### Custom Configuration
```bash
python3 run_web_dashboard.py --host 0.0.0.0 --port 8080
```
- Accessible from other devices on network
- Custom port configuration
- Production-ready setup

#### Advanced Features
```bash
python3 advanced_web_dashboard.py
```
- Enhanced UI with better styling
- Advanced terminal emulation
- Improved charts and visualizations
- Professional dashboard layout

### Command Line Options

```bash
python3 run_web_dashboard.py [OPTIONS]

Options:
  --host HOST        Host to bind server (default: 127.0.0.1)
  --port PORT        Port to bind server (default: 8000)
  --config FILE      Configuration file path
  --log-level LEVEL  Logging level (DEBUG, INFO, WARNING, ERROR)
  --reload          Enable auto-reload for development
  --workers N       Number of worker processes
  --version         Show version information
```

## REST API Endpoints

### Worker Management

#### `GET /workers`
List all active workers.

**Response:**
```json
[
  {
    "worker_id": "worker-001",
    "model": "sonnet",
    "status": "working",
    "branch": "feature/auth",
    "task_title": "Implement authentication",
    "progress": 75,
    "last_activity": "Writing unit tests",
    "uptime": 3600.5
  }
]
```

#### `POST /workers/{worker_id}/pause`
Pause a specific worker.

**Response:**
```json
{
  "status": "success",
  "message": "Worker worker-001 paused"
}
```

#### `POST /workers/{worker_id}/resume`
Resume a paused worker.

#### `POST /workers/{worker_id}/terminate`
Terminate a worker with graceful shutdown.

#### `POST /workers/{worker_id}/message`
Send a message to a worker.

**Request Body:**
```json
{
  "message": "Please implement rate limiting",
  "priority": 5
}
```

#### `GET /workers/{worker_id}/logs`
Get worker's log output.

**Query Parameters:**
- `lines`: Number of lines to return (default: 100)

**Response:**
```json
{
  "worker_id": "worker-001",
  "logs": [
    "[12:34:56] Starting task implementation",
    "[12:35:10] Created new module auth.py",
    "[12:35:25] Running unit tests"
  ]
}
```

#### `GET /workers/{worker_id}/memory`
Get worker's memory files.

**Response:**
```json
{
  "worker_id": "worker-001",
  "memory_files": [
    {
      "name": "context_auth.json",
      "size": 2048,
      "modified": "2024-01-01T12:34:56"
    }
  ]
}
```

#### `GET /workers/{worker_id}/diff`
Get worker's Git diff.

**Response:**
```json
{
  "worker_id": "worker-001",
  "diff": "+def authenticate_user(username, password):\n+    return verify_credentials(username, password)"
}
```

### System Management

#### `GET /master/status`
Get master orchestrator status.

**Response:**
```json
{
  "active_workers": 3,
  "tasks_completed": 15,
  "tasks_in_progress": 2,
  "tasks_queued": 1,
  "current_activity": "Coordinating worker tasks",
  "repository_status": "3 active branches",
  "uptime": 7200.0
}
```

#### `GET /tasks`
List all tasks in the system.

#### `POST /workers/spawn`
Spawn a new worker.

**Form Data:**
- `model`: Worker model (opus/sonnet/haiku)
- `task_name`: Task name
- `base_branch`: Base Git branch

#### `GET /communication/log`
Get recent communication messages.

**Query Parameters:**
- `limit`: Number of messages to return (default: 50)

## WebSocket Endpoints

### Dashboard WebSocket: `/ws/dashboard`
Real-time dashboard updates including:
- Worker status changes
- Master status updates
- Communication log messages
- System notifications

**Message Format:**
```json
{
  "type": "worker_update",
  "worker_id": "worker-001",
  "data": {
    "status": "working",
    "progress": 80,
    "log_lines": ["..."]
  }
}
```

### Worker Terminal WebSocket: `/ws/worker/{worker_id}`
Real-time terminal output for specific workers.

**Message Format:**
```json
{
  "type": "log_update",
  "logs": [
    "[12:34:56] Task completed successfully",
    "[12:35:00] Starting cleanup process"
  ]
}
```

## Frontend Features

### Dashboard Layout

**Master Control Panel**
- Active workers count
- Task statistics (completed/in progress/queued)
- Current master activity
- Repository status
- System uptime

**Worker Grid**
- Responsive card layout
- Status indicators with color coding
- Progress bars for task completion
- Live terminal output
- Action buttons (pause/resume/terminate)

**Communication Log**
- Real-time message stream
- Message filtering capabilities
- Export functionality
- Auto-scroll with history

### Interactive Elements

**Worker Cards**
- Click to select worker
- Double-click to expand terminal
- Right-click context menu
- Drag-and-drop (future enhancement)

**Terminal Emulation**
- Full xterm.js integration
- Authentic terminal experience
- Copy/paste support
- Search functionality
- Theme customization

**Charts and Visualizations**
- Task distribution pie chart
- Worker performance line chart
- Real-time data updates
- Interactive tooltips

### Keyboard Shortcuts
- **Ctrl+R**: Refresh dashboard
- **Ctrl+N**: Spawn new worker
- **Space**: Pause/resume selected worker
- **ESC**: Close modals
- **F11**: Fullscreen mode

### Context Menus
Right-click on worker cards for:
- View detailed logs
- Send direct message
- View memory files
- View Git diff
- Copy worker ID
- Download logs

## Configuration

### Web Dashboard Configuration (`web_dashboard_config.json`)

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 8000,
    "reload": false,
    "workers": 1
  },
  "dashboard": {
    "title": "Multi-Agent Orchestrator Dashboard",
    "update_interval": 2.0,
    "max_log_lines": 100,
    "terminal_theme": "dark"
  },
  "security": {
    "enable_auth": false,
    "cors_origins": ["*"],
    "rate_limiting": {
      "enabled": false,
      "requests_per_minute": 60
    }
  },
  "features": {
    "xterm_js": true,
    "chart_js": true,
    "bootstrap": true,
    "font_awesome": true
  }
}
```

### Environment Variables

```bash
# Server configuration
export WEB_DASHBOARD_HOST="0.0.0.0"
export WEB_DASHBOARD_PORT="8080"

# Orchestrator integration
export MULTIBOT_BASE_DIR="/tmp/multibot"
export MESSAGE_QUEUE_DB="/tmp/multibot/message_queue.db"

# Security
export WEB_DASHBOARD_SECRET_KEY="your-secret-key"
export ENABLE_CORS="true"
```

### Nginx Reverse Proxy Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

## Architecture

### Backend Architecture

```
FastAPI Application
├── WebSocket Manager      # Real-time communication
├── REST API Endpoints     # HTTP API for actions
├── Static File Serving    # CSS, JS, assets
├── Template Rendering     # HTML dashboard
└── Orchestrator Integration
    ├── Message Queue      # Communication monitoring
    ├── Worker Lifecycle   # Worker management
    └── Data Provider      # Real-time data collection
```

### Frontend Architecture

```
HTML Dashboard
├── Bootstrap CSS Framework    # Responsive design
├── JavaScript Application    # Dashboard logic
├── WebSocket Client         # Real-time updates
├── xterm.js Terminal        # Terminal emulation
├── Chart.js Visualizations # Data charts
└── Font Awesome Icons       # UI icons
```

### Data Flow

```
Orchestrator System → FastAPI Backend → WebSocket → Browser Dashboard
                   ↓                   ↓           ↑
             Message Queue         Data Updates    User Actions
                   ↓                   ↓           ↓
             Communication Log    Terminal Output  API Calls
```

## Security Considerations

### Development Mode
- Default configuration suitable for local development
- No authentication required
- CORS enabled for all origins
- Debug mode available

### Production Deployment
- Enable authentication and authorization
- Configure CORS for specific origins
- Use HTTPS with SSL certificates
- Enable rate limiting
- Set up proper logging and monitoring

### Authentication Options
```python
# Basic authentication example
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

@app.get("/protected")
async def protected_route(credentials: HTTPBasicCredentials = Depends(security)):
    # Verify credentials
    pass
```

### Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/workers")
@limiter.limit("10/minute")
async def get_workers(request: Request):
    # Limited endpoint
    pass
```

## Troubleshooting

### Common Issues

**Dashboard won't start**
```bash
# Check Python version
python3 --version  # Should be 3.8+

# Check dependencies
pip install -r web_requirements.txt

# Check port availability
netstat -an | grep :8000
```

**WebSocket connection fails**
```bash
# Check firewall settings
sudo ufw allow 8000

# Check server logs
python3 run_web_dashboard.py --log-level DEBUG

# Test WebSocket manually
wscat -c ws://localhost:8000/ws/dashboard
```

**No workers showing**
```bash
# Check orchestrator is running
ls /tmp/multibot/workers/

# Check message queue
sqlite3 /tmp/multibot/message_queue.db "SELECT COUNT(*) FROM messages;"

# Verify API endpoints
curl http://localhost:8000/workers
```

**Performance issues**
```bash
# Reduce update frequency
# Edit web_dashboard_config.json
"update_interval": 5.0

# Limit worker count
"max_workers_display": 8

# Check system resources
htop
```

### Debug Mode

```bash
# Run with debug logging
python3 run_web_dashboard.py --log-level DEBUG --reload

# Check browser console
# Open developer tools (F12)
# Look for JavaScript errors

# Monitor network requests
# Check WebSocket connections
# Verify API responses
```

### Log Analysis

```bash
# Check server logs
tail -f /tmp/multibot/logs/web_dashboard.log

# Check orchestrator logs
tail -f /tmp/multibot/logs/orchestrator.log

# Check individual worker logs
tail -f /tmp/multibot/workers/worker-001/logs/worker.log
```

## Development

### Local Development Setup

```bash
# Clone and setup
git clone <repository>
cd orchestrator-master

# Install dependencies
pip install -r web_requirements.txt

# Run in development mode
python3 run_web_dashboard.py --reload --log-level DEBUG
```

### Adding Custom Features

**Custom API Endpoint:**
```python
@app.get("/custom/endpoint")
async def custom_endpoint():
    return {"custom": "data"}
```

**WebSocket Message Type:**
```javascript
// Frontend
case 'custom_update':
    handleCustomUpdate(message.data);
    break;
```

**Dashboard Widget:**
```html
<div class="custom-widget">
    <h5>Custom Widget</h5>
    <div id="customContent"></div>
</div>
```

### Testing

```bash
# Unit tests
python3 -m pytest tests/test_web_dashboard.py

# Integration tests
python3 -m pytest tests/test_api_endpoints.py

# Load testing
ab -n 1000 -c 10 http://localhost:8000/workers
```

The web dashboard provides a powerful, accessible interface for monitoring and controlling the Multi-Agent Orchestrator system from anywhere with internet access, making it ideal for remote teams and distributed development environments.