#!/bin/bash

# ==================================================================================
# INFERENCE STARTUP SCRIPT FOR VAST.AI
# ==================================================================================
# USAGE: Paste this entire content into the "On-start script" field in Vast.ai.
# ==================================================================================

# 1. Rclone Configuration
# ----------------------------------------------------------------------------------
# IMPORTANT: Replace the token below with your own from 'rclone config' (cat ~/.config/rclone/rclone.conf)
echo "Configuring Rclone..."
mkdir -p /root/.config/rclone
cat <<EOF > /root/.config/rclone/rclone.conf
[mydrive]
type = drive
scope = drive
token = {"access_token":"YOUR_ACCESS_TOKEN","token_type":"Bearer","refresh_token":"YOUR_REFRESH_TOKEN","expiry":"2026-01-01T00:00:00.000000000-00:00"}
EOF

# 2. Download Trained Model
# ----------------------------------------------------------------------------------
# REPLACE THIS ID WITH YOUR REAL FILE ID FROM DRIVE
MODEL_DRIVE_ID="PON_AQUI_EL_ID_DEL_MODELO" 

MODEL_DEST_DIR="/app/model"
MODEL_DEST_PATH="$MODEL_DEST_DIR/best_convlstm_model.pth"

echo "⬇️ Downloading Model from Drive (ID: $MODEL_DRIVE_ID)..."
mkdir -p $MODEL_DEST_DIR

# Use `backend copyid` to download by ID regardless of folder structure
if rclone backend copyid mydrive: $MODEL_DRIVE_ID $MODEL_DEST_PATH; then
    echo "✅ Model downloaded successfully to $MODEL_DEST_PATH"
else
    echo "❌ ERROR: Model download failed! Check your Token and File ID."
    # We don't exit, maybe there's a baked-in model fallback?
fi

# 3. (Optional) Real-Time Data Sync
# ----------------------------------------------------------------------------------
# Uncomment the following lines if you want to automatically download new files from a Drive folder.
# REPLACE 'mydrive:RadarData/2026' with your actual folder path.
# echo "📡 Starting Drive Watcher..."
# nohup python3 /app/tools/drive_watcher.py --remote-base "mydrive:RadarData/2026" --interval 60 > /app/logs/watcher.log 2>&1 &


# 4. Start Services
# ----------------------------------------------------------------------------------
echo "🚀 Starting Application Services..."
cd /app
# Ensure start_all.sh is executable
chmod +x start_all.sh
./start_all.sh
