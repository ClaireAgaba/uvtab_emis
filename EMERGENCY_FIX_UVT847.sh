#!/bin/bash

echo "=========================================="
echo "EMERGENCY FIX FOR UVT847 - DOUBLED FEES"
echo "=========================================="
echo ""
echo "Current situation: Fees are doubled (8.9M instead of 4.49M)"
echo "This will reset and recalculate from scratch"
echo ""

cd /home/claire/Desktop/projects/emis

read -p "Run on LOCAL or SERVER? (local/server): " env

if [[ $env == "local" ]]; then
    echo ""
    echo "Step 1: Adding emergency reset command..."
    git add emis/eims/management/commands/reset_center_billing.py
    git commit -m "Emergency: Add reset_center_billing command to fix doubled fees"
    git push origin main
    echo ""
    echo "✅ Pushed to git. Now run on server:"
    echo ""
    echo "cd /path/to/emis"
    echo "git pull origin main"
    echo "python manage.py reset_center_billing UVT847 --dry-run"
    echo "python manage.py reset_center_billing UVT847"
    echo ""
elif [[ $env == "server" ]]; then
    echo ""
    echo "Step 1: Preview reset..."
    python manage.py reset_center_billing UVT847 --dry-run
    echo ""
    read -p "Proceed with reset? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Step 2: Resetting billing..."
        python manage.py reset_center_billing UVT847
        echo ""
        echo "Step 3: Verifying..."
        python manage.py diagnose_multilevel_billing UVT847
        echo ""
        echo "✅ Done! Check invoice in UI"
    fi
else
    echo "Invalid option. Exiting."
fi
