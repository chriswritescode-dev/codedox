# Contributing to CodeDox

Thank you for your interest in contributing to CodeDox!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a feature branch
4. Make your changes
5. Submit a pull request

## Development Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/codedox.git
cd codedox

# Set up Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set up frontend
cd frontend
npm install
cd ..

# Initialize database
python cli.py init

# Run tests
pytest tests/
```

## Code Style

- Python: Follow PEP 8, use Black formatter
- TypeScript: Use Prettier
- No unnecessary comments
- Follow DRY principles


