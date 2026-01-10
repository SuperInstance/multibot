# Multi-Agent Orchestrator Installation Guide

Complete setup guide for the Multi-Agent Orchestrator system.

## Prerequisites

### Required Software
- **Python 3.8+** - Core runtime environment
- **Git** - Version control and repository management
- **Claude Code CLI** - Available from https://claude.ai/code
- **Node.js 16+** (optional) - For web dashboard enhancements

### Platform-Specific Requirements

#### Windows
- **WSL (Windows Subsystem for Linux)** - Required for proper Unix-like environment
- **WSL2** recommended for better performance

#### Linux/macOS
- Standard development tools (gcc, make) for some Python packages

### API Keys
- **ANTHROPIC_API_KEY** - Required for Claude model access
- **GITHUB_TOKEN** (optional) - For GitHub integration

## Quick Installation

### 1. Download and Run Setup
```bash
# Clone or download the orchestrator files
git clone <repository-url> multi-agent-orchestrator
cd multi-agent-orchestrator

# Run the automated setup
chmod +x setup.sh
./setup.sh
```

### 2. Set API Keys
```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
export GITHUB_TOKEN="your-github-token"  # Optional
```

### 3. Start the System
```bash
cd orchestrator
./scripts/start_master.sh
```

### 4. Access Dashboard
Open http://localhost:8080 in your browser

## Manual Installation

If the automated setup fails, follow these manual steps:

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install Optional Node.js Packages
```bash
npm install -g ws express socket.io
```

### 3. Create Directory Structure
```bash
mkdir -p orchestrator/{master/{config,logs},workers/worker_template,shared_knowledge,monitoring/web,scripts,docs,tests}
```

### 4. Copy Files
Copy all Python files to the `orchestrator/master/` directory:
- orchestrator_master.py
- All supporting modules (*.py files)

### 5. Configure MCP Servers
Create configuration files:

**orchestrator/master/config/claude_desktop_config.json:**
```json
{
  "mcpServers": {
    "orchestrator-master": {
      "command": "python",
      "args": ["orchestrator/master/orchestrator_master.py"],
      "env": {
        "ORCHESTRATOR_HOST": "localhost",
        "ORCHESTRATOR_PORT": "8765"
      }
    }
  }
}
```

### 6. Initialize Git Repository
```bash
cd orchestrator
git init
git add .
git commit -m "Initial orchestrator setup"
```

## Directory Structure

After installation, your directory structure will look like:

```
orchestrator/
├── master/                     # Master orchestrator
│   ├── orchestrator_master.py  # Main orchestrator server
│   ├── config/                 # Configuration files
│   ├── logs/                   # Log files
│   └── *.py                    # All orchestrator modules
├── workers/                    # Worker instances
│   └── worker_template/        # Template for new workers
├── shared_knowledge/           # Cross-worker knowledge base
│   ├── architecture_decisions.md
│   ├── api_contracts.json
│   ├── coding_standards.md
│   └── module_ownership.json
├── monitoring/                 # Web dashboard
│   └── web/                    # Web assets
├── scripts/                    # Start/stop scripts
│   ├── start_master.sh
│   ├── start_worker.sh
│   ├── stop_all.sh
│   └── monitor.sh
├── docs/                       # Documentation
├── tests/                      # Test files
├── requirements.txt            # Python dependencies
├── .gitignore                 # Git ignore rules
└── README.md                  # Project overview
```

## Configuration

### Master Configuration
Edit `orchestrator/master/config/orchestrator_config.json`:

```json
{
  "server": {
    "host": "localhost",
    "port": 8765,
    "max_workers": 10,
    "log_level": "INFO"
  },
  "workers": {
    "default_model": "sonnet",
    "max_concurrent_tasks": 5,
    "timeout_minutes": 30,
    "auto_scale": true
  },
  "monitoring": {
    "web_port": 8080,
    "metrics_enabled": true,
    "log_retention_days": 30
  }
}
```

### Worker Configuration
Worker configurations are generated automatically from the template when workers are spawned.

### Environment Variables
Set these environment variables for optimal operation:

```bash
# Required
export ANTHROPIC_API_KEY="your-anthropic-api-key"

# Optional
export GITHUB_TOKEN="your-github-token"
export ORCHESTRATOR_HOST="localhost"
export ORCHESTRATOR_PORT="8765"
export LOG_LEVEL="INFO"
```

## Starting the System

### Start Master Orchestrator
```bash
cd orchestrator
./scripts/start_master.sh
```

### Start a Worker
```bash
./scripts/start_worker.sh worker-001 sonnet "authentication-task"
```

### Monitor Status
```bash
./scripts/monitor.sh
```

### Stop Everything
```bash
./scripts/stop_all.sh
```

## Verification

### Check Installation
1. **Master running**: `pgrep -f orchestrator_master.py`
2. **Web dashboard**: Visit http://localhost:8080
3. **MCP server**: Test connection on localhost:8765
4. **Logs**: Check `orchestrator/master/logs/orchestrator.log`

### Test Basic Functionality
1. Start the master
2. Access the web dashboard
3. Deploy a test worker through the interface
4. Verify worker appears in the dashboard
5. Assign a simple task to test communication

## Troubleshooting

### Common Issues

#### "Claude Code CLI not found"
- Install Claude Code CLI from https://claude.ai/code
- Ensure it's in your PATH: `which claude-code`

#### "Permission denied" on scripts
```bash
chmod +x orchestrator/scripts/*.sh
```

#### "Port already in use"
- Change ports in `orchestrator/master/config/orchestrator_config.json`
- Default ports: 8765 (MCP), 8080 (web dashboard)

#### "Python package installation failed"
- Use virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

#### "Worker fails to connect"
- Check master is running: `./scripts/monitor.sh`
- Verify network connectivity between master and worker
- Check firewall settings for ports 8765 and 8080

### Log Files
- **Master logs**: `orchestrator/master/logs/orchestrator.log`
- **Worker logs**: Generated in individual worker directories
- **Setup logs**: Console output during installation

### Getting Help
1. Check the logs for specific error messages
2. Verify all prerequisites are installed
3. Test each component individually
4. Check GitHub issues for known problems

## Next Steps

After successful installation:

1. **Read the documentation**: `orchestrator/docs/`
2. **Run examples**: Test with sample tasks
3. **Configure your project**: Set up repository integration
4. **Deploy workers**: Start with simple tasks
5. **Monitor performance**: Use the web dashboard

## Security Considerations

- Store API keys securely (environment variables, not in code)
- Restrict network access to orchestrator ports
- Regularly update dependencies
- Review worker access permissions
- Monitor logs for unusual activity

## Updating

To update the orchestrator:

1. **Backup current installation**:
```bash
cp -r orchestrator orchestrator.backup
```

2. **Run setup again**:
```bash
./setup.sh
```

3. **Migrate configuration** if needed

4. **Test functionality** before removing backup

The setup script is idempotent and safe to run multiple times.