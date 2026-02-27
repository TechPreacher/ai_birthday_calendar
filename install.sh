#!/bin/bash
# Birthday Tracker Installation Script

set -e

echo "🎂 Birthday Tracker - Installation Script"
echo "=========================================="
echo ""

# Check if running as root for systemd setup
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  This script needs sudo access to install the systemd service."
    echo "   It will prompt for your password."
    echo ""
fi

# Install systemd service
echo "📦 Installing systemd service..."
sudo cp /opt/birthdays/birthdays.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start service
echo "🚀 Enabling and starting service..."
sudo systemctl enable birthdays
sudo systemctl start birthdays

# Wait a moment for startup
sleep 3

# Check status
echo ""
echo "✅ Installation complete!"
echo ""
echo "Service status:"
sudo systemctl status birthdays --no-pager | head -10
echo ""
echo "📍 The app is running at: http://localhost:8081"
echo ""
echo "🔐 Default login credentials:"
echo "   Username: admin"
echo "   Password: changeme"
echo ""
echo "⚠️  IMPORTANT: Change the admin password after first login!"
echo ""
echo "📖 See README.md for full documentation."
echo ""
echo "To view logs: sudo journalctl -u birthdays -f"
echo "To restart: sudo systemctl restart birthdays"
echo "To stop: sudo systemctl stop birthdays"
