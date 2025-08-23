# Installation

## Prerequisites

- Python 3.10+
- PostgreSQL 15+
- Node.js 18+ (for web UI)

## Quick Install

### 1. Clone the repository
```bash
git clone https://github.com/chriswritescode-dev/codedox.git
cd codedox
```

### 2. Set up Python environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 4. Initialize database
```bash
python cli.py init
```

### 5. Install frontend dependencies
```bash
cd frontend
npm install
cd ..
```

## Docker Installation

```bash
docker-compose up
```

This will start all services including PostgreSQL, API server, and web UI.