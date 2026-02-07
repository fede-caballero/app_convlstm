#!/bin/bash

# Configuration
LOCAL_DB_PATH="/app/data/radar_history.db"
REMOTE_NAME="mydrive"
REMOTE_FOLDER="convlstm_backups"

echo "=== Restore Database from Google Drive ==="
echo "Remote: $REMOTE_NAME:$REMOTE_FOLDER/app.db"
echo "Local Target: $LOCAL_DB_PATH"

# Force mode (skip confirmation)
if [[ "$1" == "--force" ]]; then
    FORCE=true
else
    FORCE=false
fi

# Check if rclone is configured
if ! rclone listremotes | grep -q "$REMOTE_NAME:"; then
    echo "❌ Error: Remote '$REMOTE_NAME' not configured."
    exit 1
fi

if [ "$FORCE" = false ]; then
    echo "⚠️  WARNING: This will OVERWRITE the local database."
    read -p "Are you sure? (y/N): " confirm
    if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
        echo "Operation cancelled."
        exit 0
    fi
fi

# Ensure parent directory exists
mkdir -p "$(dirname "$LOCAL_DB_PATH")"

echo "🚀 Downloading..."
# Note: Rclone destination is the file path directly if source is file
# But remote structure is "convlstm_backups/radar_history.db" (from backup script)
# Wait, backup script uses `rclone copy source dest_folder`. So file name is preserved.
# Original file was `app.db`? No, we changed backup script to backup `radar_history.db`.
# But checking backup_db.sh change: `rclone copy "$LOCAL_DB_PATH" "$REMOTE_NAME:$REMOTE_FOLDER"`.
# So the remote file name will be `radar_history.db`.

rclone copy "$REMOTE_NAME:$REMOTE_FOLDER/radar_history.db" "$(dirname "$LOCAL_DB_PATH")" --verbose

if [ $? -eq 0 ]; then
    echo "✅ Restore Successful!"
    # Set permissions
    if [ -f "$LOCAL_DB_PATH" ]; then
        chmod 666 "$LOCAL_DB_PATH"
    fi
    date
else
    echo "❌ Restore Failed! File might not exist in backup."
fi
