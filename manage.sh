#!/bin/bash
# Adventure MUD - Management Script
# Usage: ./manage.sh [command]

set -e

VENV_DIR=".venv"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/adventure.pid"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Ensure venv exists
ensure_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        log_info "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
        log_info "Virtual environment created successfully"
    fi
}

# Activate venv
activate_venv() {
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        log_error "Virtual environment not found. Run './manage.sh setup' first."
        exit 1
    fi
    source "$VENV_DIR/bin/activate"
}

# Setup command
cmd_setup() {
    log_info "Setting up Adventure MUD..."

    # Create venv
    ensure_venv
    activate_venv

    # Create logs directory
    mkdir -p "$LOG_DIR"

    # Create instance directory
    mkdir -p instance

    # Initialize database
    log_info "Initializing database..."
    flask db upgrade

    # Seed initial data
    log_info "Seeding initial data..."
    python3 -c "from app.seed_items import seed_all; seed_all()"

    log_info "Setup complete! Run './manage.sh start' to start the server."
}

# Start command
cmd_start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log_warn "Server is already running (PID: $PID)"
            exit 0
        else
            rm -f "$PID_FILE"
        fi
    fi

    activate_venv
    mkdir -p "$LOG_DIR"

    log_info "Starting Adventure MUD server..."
    nohup python3 run.py > "$LOG_DIR/server.log" 2>&1 &
    echo $! > "$PID_FILE"

    sleep 2
    if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        log_info "Server started successfully (PID: $(cat "$PID_FILE"))"
        log_info "Access at: http://localhost:5000"
    else
        log_error "Server failed to start. Check logs: tail -f $LOG_DIR/server.log"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Stop command
cmd_stop() {
    if [ ! -f "$PID_FILE" ]; then
        log_warn "Server is not running"
        return 0
    fi

    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        log_info "Stopping server (PID: $PID)..."
        kill "$PID"
        sleep 2

        if ps -p "$PID" > /dev/null 2>&1; then
            log_warn "Process didn't stop gracefully, forcing..."
            kill -9 "$PID"
        fi

        rm -f "$PID_FILE"
        log_info "Server stopped"
    else
        log_warn "Server process not found, cleaning up PID file"
        rm -f "$PID_FILE"
    fi
}

# Restart command
cmd_restart() {
    log_info "Restarting server..."
    cmd_stop
    sleep 1
    cmd_start
}

# Status command
cmd_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log_info "Server is running (PID: $PID)"
            ps -p "$PID" -o pid,vsz,rss,etime,cmd
        else
            log_warn "PID file exists but process is not running"
            rm -f "$PID_FILE"
        fi
    else
        log_info "Server is not running"
    fi
}

# Logs command
cmd_logs() {
    if [ ! -f "$LOG_DIR/server.log" ]; then
        log_warn "No log file found"
        exit 0
    fi

    if [ "$1" == "-f" ] || [ "$1" == "--follow" ]; then
        tail -f "$LOG_DIR/server.log"
    else
        tail -n 50 "$LOG_DIR/server.log"
    fi
}

# Test command
cmd_test() {
    activate_venv
    log_info "Running tests..."
    pytest "${@:2}"
}

# Lint command
cmd_lint() {
    activate_venv
    log_info "Running linters..."
    ruff check app/ tests/
    log_info "Linting complete"
}

# Check exception handling
cmd_check_exceptions() {
    activate_venv
    log_info "Checking for silent exception handlers..."
    python scripts/fix_exception_handling.py --check
}

# Fix exception handling
cmd_fix_exceptions() {
    activate_venv
    log_warn "This will modify source files. Commit changes first!"
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python scripts/fix_exception_handling.py --fix
        log_info "Fixes applied. Review changes and run tests!"
    else
        log_info "Cancelled."
    fi
}

# Format command
cmd_format() {
    activate_venv
    log_info "Formatting code..."
    black app/ tests/ scripts/
    ruff check --fix app/ tests/
    log_info "Formatting complete"
}

# DB commands
cmd_db() {
    activate_venv
    case "$2" in
        migrate)
            # NOTE: this project uses Alembic directly (Flask-Migrate is not registered).
            # Autogenerate can misfire against a create_all DB; review the generated file
            # and prefer hand-authoring for simple column/table adds (see migrations/versions).
            log_info "Creating migration (alembic autogenerate)..."
            alembic revision --autogenerate -m "${3:-Auto migration}"
            ;;
        upgrade)
            log_info "Upgrading database (alembic upgrade head)..."
            alembic upgrade head
            ;;
        downgrade)
            log_info "Downgrading database (alembic downgrade -1)..."
            alembic downgrade -1
            ;;
        seed)
            log_info "Seeding database (items, merchants, skills)..."
            python run.py reseed-items
            python run.py seed-merchants
            python run.py seed-skills
            ;;
        *)
            echo "Usage: ./manage.sh db [migrate|upgrade|downgrade|seed]"
            exit 1
            ;;
    esac
}

# Shell command
cmd_shell() {
    activate_venv
    log_info "Starting Flask shell..."
    flask shell
}

# Main command dispatcher
case "${1:-help}" in
    setup)
        cmd_setup
        ;;
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs "$2"
        ;;
    test)
        cmd_test "$@"
        ;;
    lint)
        cmd_lint
        ;;
    check-exceptions)
        cmd_check_exceptions
        ;;
    fix-exceptions)
        cmd_fix_exceptions
        ;;
    format)
        cmd_format
        ;;
    db)
        cmd_db "$@"
        ;;
    shell)
        cmd_shell
        ;;
    help|--help|-h)
        cat << EOF
Adventure MUD Management Script

Usage: ./manage.sh [command] [options]

Commands:
    setup                Initial setup (create venv, install deps, init db)
    start                Start the server in background
    stop                 Stop the server
    restart              Restart the server
    status               Check server status
    logs [-f]            Show server logs (-f to follow)
    test [args]          Run tests (pass pytest args)
    lint                 Run code linters
    check-exceptions     Check for silent exception handlers
    fix-exceptions       Fix silent exception handlers (prompts for confirmation)
    format               Format code with black and ruff
    db <cmd>             Database commands:
                           migrate [msg]  - Create migration
                      upgrade        - Apply migrations
                      downgrade      - Rollback migration
                      seed           - Seed initial data
    shell           Open Flask shell
    help            Show this help message

Examples:
    ./manage.sh setup              # First time setup
    ./manage.sh start              # Start server
    ./manage.sh logs -f            # Follow logs
    ./manage.sh test -v            # Run tests verbosely
    ./manage.sh db migrate "Add users table"
EOF
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Run './manage.sh help' for usage information"
        exit 1
        ;;
esac
