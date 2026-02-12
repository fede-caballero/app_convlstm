#!/bin/bash
set -e

echo "=== STARTING VAST ENTRYPOINT ==="

# 1. Install Tools (Rclone & Cloudflared)
if ! command -v rclone &> /dev/null; then
    echo "Installing Rclone..."
    curl https://rclone.org/install.sh | bash
fi

if [ ! -f /usr/local/bin/cloudflared ]; then
    echo "Installing Cloudflared..."
    curl -L --output /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
    chmod +x /usr/local/bin/cloudflared
fi

# 2. Configure Rclone (Fail gracefully if config missing)
# functionality moved to env var check if desired, but for now assuming manual config or existing
if [ ! -f /root/.config/rclone/rclone.conf ]; then
    echo "⚠️ Rclone config missing. Skipping Rclone setup."
else
    echo "Rclone config found. Setting up model..."
    mkdir -p /app/model
    # Attempt download (non-blocking if it fails, or allow check)
    # Use || true to prevent exit on network error
    rclone backend copyid mydrive: 1Rodv1nQPnNCH545-4PoXo7S7rIZDntPG /app/model/best_convlstm_model.pth || echo "Rclone download failed"
    
    # Start Watcher
    nohup python3 /app/tools/drive_watcher.py --remote-base "mydrive:cart_no_clutter" --interval 60 > /app/logs/watcher.log 2>&1 &
fi

# 3. Check/Create .env (Sanity Check)
if [ ! -f /app/.env ] && [ -z "$VAPID_PRIVATE_KEY" ]; then
    echo "❌ CRITICAL: No .env file and no VAPID_PRIVATE_KEY env var found."
    echo "   Please create /app/.env manually."
fi

# 4. Start Cloudflare Tunnel
echo "Starting Cloudflare Tunnel..."
mkdir -p /app/logs
nohup cloudflared tunnel --url http://localhost:8000 > /app/logs/tunnel.log 2>&1 &

# 5. Start Application Services
echo "Starting API and Worker..."
cd /app
# Kill existing pythons if any (cleanup)
pkill -f api.py || true
pkill -f pipeline_worker.py || true

nohup python3 api.py > /app/logs/api.log 2>&1 &
nohup python3 pipeline_worker.py > /app/logs/worker.log 2>&1 &

echo "=== VAST ENTRYPOINT COMPLETE ==="
echo "Monitor logs with: tail -f /app/logs/*.log"
