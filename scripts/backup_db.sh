#!/bin/bash

# Configuration
LOCAL_DB_PATH="./backend/app.db"
REMOTE_NAME="gdrive"
REMOTE_FOLDER="convlstm_backups"

echo "=== Backup Database to Google Drive ==="
echo "Local: $LOCAL_DB_PATH"
echo "Remote: $REMOTE_NAME:$REMOTE_FOLDER"

if [ ! -f "$LOCAL_DB_PATH" ]; then
    echo "❌ Error: Local database not found at $LOCAL_DB_PATH"
    exit 1
fi

# Check if rclone is configured
if ! rclone listremotes | grep -q "$REMOTE_NAME:"; then
    echo "❌ Error: Remote '$REMOTE_NAME' not configured. Run 'rclone config' first."
    exit 1
fi

echo "🚀 Uploading..."
rclone copy "$LOCAL_DB_PATH" "$REMOTE_NAME:$REMOTE_FOLDER" --verbose

if [ $? -eq 0 ]; then
    echo "✅ Backup Successful!"
    date
else
    echo "❌ Backup Failed!"
fi
