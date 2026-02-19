#!/bin/bash

# Configuration
DEST_DIR="vps_inference"
EXCLUDES=(
    "--exclude=node_modules"
    "--exclude=__pycache__"
    "--exclude=.git"
    "--exclude=.next"
    "--exclude=.vscode"
    "--exclude=*.pyc"
    "--exclude=output"
    "--exclude=logs"
    "--exclude=tmp"
    "--exclude=.DS_Store"
    "--exclude=vps_inference" # Don't copy self into self
)

echo "📦 Packaging output to $DEST_DIR..."

# Ensure destination exists
mkdir -p "$DEST_DIR"

# Copy Directories (Source Code)
echo "  -> Copying Backend..."
rsync -av "${EXCLUDES[@]}" backend "$DEST_DIR/"

echo "  -> Copying Frontend..."
rsync -av "${EXCLUDES[@]}" frontend "$DEST_DIR/"

echo "  -> Copying Tools..."
rsync -av "${EXCLUDES[@]}" tools "$DEST_DIR/"

echo "  -> Copying Scripts..."
rsync -av "${EXCLUDES[@]}" scripts "$DEST_DIR/"

# Move/Copy Specific Configuration Files
echo "  -> Setup Docker Configuration..."
if [ -f "Dockerfile.cpu" ]; then
    cp Dockerfile.cpu "$DEST_DIR/Dockerfile"
    echo "     Copied Dockerfile.cpu -> Dockerfile"
fi

if [ -f "docker-compose.cpu.yml" ]; then
    cp docker-compose.cpu.yml "$DEST_DIR/docker-compose.yml"
    echo "     Copied docker-compose.cpu.yml -> docker-compose.yml"
fi

if [ -f "lrose-core-20250105.ubuntu_22.04.amd64.deb" ]; then
    cp lrose-core-20250105.ubuntu_22.04.amd64.deb "$DEST_DIR/"
    echo "     Copied LROSE installer"
fi

# Create Data/Logs/Model directories
mkdir -p "$DEST_DIR/data"
mkdir -p "$DEST_DIR/logs"
mkdir -p "$DEST_DIR/model"
mkdir -p "$DEST_DIR/backend/output"

echo "✅ Package complete in $DEST_DIR"
echo "   You can now zip this folder and upload to VPS:"
echo "   zip -r vps_inference.zip vps_inference"
