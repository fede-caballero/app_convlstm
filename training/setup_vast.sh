#!/bin/bash

# Setup script for vast.ai instance (Ubuntu/Debian based)

echo "Starting setup..."

# 1. Update system and install basics
apt-get update
apt-get install -y git wget python3-pip liblibnetcdf-dev libnetcdf-dev

# 2. Install Python dependencies
pip install -r requirements.txt
pip install gdown

# 3. Create directories
mkdir -p checkpoints
mkdir -p logs

echo "Setup complete! You can now run the training scripts."
