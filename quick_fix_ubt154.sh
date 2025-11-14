#!/bin/bash

# Quick Fix Script for Center UBT154 Billing Issues
# This script runs the diagnostic and fix commands in sequence

echo "=========================================="
echo "BILLING FIX FOR CENTER UBT154"
echo "=========================================="
echo ""

# Navigate to project directory
cd /home/claire/Desktop/projects/emis

echo "Step 1: Running diagnostic..."
echo "=========================================="
python manage.py diagnose_center_billing UBT154
echo ""

read -p "Do you want to proceed with the fix? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo ""
    echo "Step 2: Fixing modular billing..."
    echo "=========================================="
    python manage.py fix_modular_billing --center UBT154
    echo ""
    
    echo "Step 3: Harmonizing all billing status..."
    echo "=========================================="
    python manage.py harmonize_billing_status --center UBT154
    echo ""
    
    echo "Step 4: Verifying fixes..."
    echo "=========================================="
    python manage.py diagnose_center_billing UBT154
    echo ""
    
    echo "=========================================="
    echo "✅ FIX COMPLETE!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Go to UVTAB Fees → Center Fees"
    echo "2. Search for UBT154"
    echo "3. Click 'Invoice' button"
    echo "4. Verify modular candidates now show correct amounts"
    echo ""
else
    echo ""
    echo "Fix cancelled. No changes were made."
    echo ""
fi
