#!/bin/bash

# ==================================================================================
# AUTOMATED SETUP SCRIPT FOR VAST.AI
# ==================================================================================
# This script is meant to be downloaded and run by the on-start script.
# It handles: Rclone config injection, Dataset download errors, and Extraction.
# ==================================================================================

# 0. Rclone Configuration
# ----------------------------------------------------------------------------------
echo "Configuring Rclone..."
mkdir -p /root/.config/rclone
cat <<EOF > /root/.config/rclone/rclone.conf
[mydrive]
type = drive
scope = drive
token = {"access_token":"YOUR_ACCESS_TOKEN","token_type":"Bearer","refresh_token":"YOUR_REFRESH_TOKEN","expiry":"2026-01-01T00:00:00.000000000-00:00"}
EOF


# 1. Configuration
# ----------------------------------------------------------------------------------
DATASET_GDRIVE_ID="1m0ElnC8RA9hvkOwElnwtiLCVX-9wZKkm"

#Dataset para prueba:
#https://drive.google.com/file/d/1TF8U5e_XAeLhwYT9vBcqu_3hIJhNxvYe/view?usp=sharing

#Dataset 200 secuencias:
#https://drive.google.com/file/d/1wtkjOAJ-2w3WZnM2Qb9l9oFddiHPPaL8/view?usp=sharing
#DATASET_GDRIVE_ID="1wtkjOAJ-2w3WZnM2Qb9l9oFddiHPPaL8"

LOCAL_FILENAME="sample.tar.gz"

echo "Starting Setup..."

# 2. Download Dataset
# ----------------------------------------------------------------------------------
if [ ! -d "/workspace/data" ] || [ -z "$(ls -A /workspace/data)" ]; then
    echo "Downloading dataset..."
    mkdir -p /workspace/data
    
    # Try Rclone first (Robust)
    if grep -q "access_token" /root/.config/rclone/rclone.conf; then
        echo "Rclone config found. Trying rclone via ID..."
        # Magic command: Download directly by ID (ignores paths/folders)
        if rclone backend copyid mydrive: $DATASET_GDRIVE_ID /workspace/$LOCAL_FILENAME; then
            echo "Rclone download successful."
        else
            echo "Rclone failed. Falling back to gdown..."
            gdown $DATASET_GDRIVE_ID -O /workspace/$LOCAL_FILENAME
        fi
    else
        echo "No rclone config found. Falling back to gdown..."
        gdown $DATASET_GDRIVE_ID -O /workspace/$LOCAL_FILENAME
    fi
    
    echo "Extracting dataset..."
    tar -xzvf /workspace/$LOCAL_FILENAME -C /workspace/data
    
    # Cleanup
    rm /workspace/$LOCAL_FILENAME
    echo "Dataset ready."
else
    echo "Data directory already exists. Skipping download."
fi

# 3. Pull latest code
# ----------------------------------------------------------------------------------
cd /workspace/app_convlstm
git pull origin main

echo "Setup Complete."
