#!/bin/bash

# Configuration
LOCAL_DB_PATH="./backend/app.db"
REMOTE_NAME="gdrive"
REMOTE_FOLDER="convlstm_backups"

echo "=== Restore Database from Google Drive ==="
echo "Remote: $REMOTE_NAME:$REMOTE_FOLDER/app.db"
echo "Local Target: $LOCAL_DB_PATH"

# Check if rclone is configured
if ! rclone listremotes | grep -q "$REMOTE_NAME:"; then
    echo "❌ Error: Remote '$REMOTE_NAME' not configured. Run 'rclone config' first."
    exit 1
fi

echo "⚠️  WARNING: This will OVERWRITE the local database."
read -p "Are you sure? (y/N): " confirm
if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Operation cancelled."
    exit 0
fi

echo "🚀 Downloading..."
rclone copy "$REMOTE_NAME:$REMOTE_FOLDER/app.db" "./backend/" --verbose

if [ $? -eq 0 ]; then
    echo "✅ Restore Successful!"
    # Set permissions just in case
    chmod 666 "$LOCAL_DB_PATH"
    date
else
    echo "❌ Restore Failed!"
fi
