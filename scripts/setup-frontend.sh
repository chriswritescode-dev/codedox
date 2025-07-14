#!/bin/bash

# Simple script to set up frontend dependencies

echo "Setting up frontend dependencies..."

cd frontend

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
else
    echo "Frontend dependencies already installed."
fi

echo "Frontend setup complete!"
echo "To start the web UI, run: python cli.py ui"