#!/bin/bash

# vast.ai On-Start Script
# Paste this content into the "On-start script" field in vast.ai configuration.

# 1. Define your Google Drive File ID for the dataset
# REPLACE THIS WITH YOUR ACTUAL FILE ID
DATASET_GDRIVE_ID="YOUR_FILE_ID_HERE"

echo "Starting On-Start Script..."

# 2. Download Dataset if it doesn't exist
if [ ! -d "/workspace/data" ]; then
    echo "Downloading dataset from Google Drive..."
    mkdir -p /workspace/data
    
    # Download using gdown (installed in Docker image)
    # If the file is large, this might take a while.
    gdown $DATASET_GDRIVE_ID -O /workspace/dataset.tar.gz
    
    echo "Extracting dataset..."
    tar -xzvf /workspace/dataset.tar.gz -C /workspace/data
    
    # Cleanup
    rm /workspace/dataset.tar.gz
    echo "Dataset ready."
else
    echo "Data directory already exists. Skipping download."
fi

# 3. (Optional) Update code from git if you want the latest changes without rebuilding Docker
# git pull origin main

echo "On-Start Script Complete."
