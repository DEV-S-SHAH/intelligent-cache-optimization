#!/bin/bash
set -e

echo "=========================================="
echo "Intelligent Cache Middleware - Quick Start"
echo "=========================================="

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Install dependencies
echo ""
echo "[1/5] Installing dependencies..."
pip install -r requirements.txt

# Copy env if not exists
if [ ! -f .env ]; then
    echo ""
    echo "[2/5] Creating .env from .env.example..."
    cp .env.example .env
fi

# Start Docker services
echo ""
echo "[3/5] Starting Docker services (Redis + PostgreSQL/pgvector)..."
docker compose up -d

# Wait for services
echo "Waiting for services to be ready..."
sleep 5

# Initialize database
echo ""
echo "[4/5] Initializing database..."
python3 -c "from app.database.session import init_db; init_db(); print('Database initialized')"

# Create directories
mkdir -p data results/charts

echo ""
echo "[5/5] Starting services..."
echo ""
echo "=========================================="
echo "Starting FastAPI server on port ${API_PORT:-8000}..."
echo "Starting Streamlit dashboard on port ${DASHBOARD_PORT:-8501}..."
echo "=========================================="
echo ""
echo "API docs: http://localhost:8000/docs"
echo "Dashboard: http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Start services in background
uvicorn app.main:app --host 0.0.0.0 --port ${API_PORT:-8000} &
API_PID=$!

streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port ${DASHBOARD_PORT:-8501} &
STREAMLIT_PID=$!

# Wait for interrupt
trap "echo 'Stopping services...'; kill $API_PID $STREAMLIT_PID 2>/dev/null; exit 0" INT TERM
wait
