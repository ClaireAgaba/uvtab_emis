#!/bin/bash
# Git commands to push all billing fixes to repository

cd /home/claire/Desktop/projects/emis

echo "=========================================="
echo "PUSHING BILLING FIX COMMANDS TO GIT"
echo "=========================================="
echo ""

echo "Adding management commands..."
git add eims/management/commands/diagnose_center_billing.py
git add eims/management/commands/fix_modular_billing.py
git add eims/management/commands/harmonize_billing_status.py
git add eims/management/commands/diagnose_multilevel_billing.py
git add eims/management/commands/fix_multilevel_billing.py

echo "Adding documentation..."
git add BILLING_FIX_GUIDE.md
git add DEPLOYMENT_GUIDE.md
git add QUICK_FIX_REFERENCE.txt
git add FIX_UVT847_GUIDE.md

echo ""
echo "Files to be committed:"
git status --short

echo ""
read -p "Proceed with commit? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo ""
    echo "Committing changes..."
    git commit -m "Fix: Add comprehensive billing fix commands for UBT154 and UVT847

ISSUE 1 - UBT154: Modular candidates showing 0.00 instead of 70k-90k
ISSUE 2 - UVT847: Multi-level billing incorrect (Level 1/2/3 fees not calculating)

NEW COMMANDS:
- diagnose_center_billing: Detailed diagnostic for single centers
- fix_modular_billing: Fix modular candidate billing issues
- harmonize_billing_status: Fix all enrollment billing status
- diagnose_multilevel_billing: Multi-level breakdown and analysis
- fix_multilevel_billing: Fix multi-level billing scenarios

FEATURES:
- Dry-run support for safe previewing
- Center-specific and series-specific filtering
- Comprehensive reporting by category and level
- Safe to run multiple times (idempotent)
- Detailed documentation and deployment guides

FIXES:
- Modular candidates with 0.00 balance
- Missing modular_billing_amount field
- Incorrect fees_balance for enrolled candidates
- Multi-level fee calculation issues
- Level 1, 2, 3 fee structure handling

DOCUMENTATION:
- BILLING_FIX_GUIDE.md: Comprehensive guide for UBT154
- FIX_UVT847_GUIDE.md: Multi-level billing guide
- DEPLOYMENT_GUIDE.md: Step-by-step deployment
- QUICK_FIX_REFERENCE.txt: Quick command reference"

    echo ""
    echo "Pushing to repository..."
    git push origin main

    echo ""
    echo "=========================================="
    echo "✅ DONE! Files pushed to repository."
    echo "=========================================="
    echo ""
    echo "NEXT STEPS ON SERVER:"
    echo "1. git pull origin main"
    echo ""
    echo "FOR UBT154 (Modular billing issue):"
    echo "   python manage.py diagnose_center_billing UBT154"
    echo "   python manage.py fix_modular_billing --center UBT154"
    echo "   python manage.py harmonize_billing_status --center UBT154"
    echo ""
    echo "FOR UVT847 (Multi-level billing issue):"
    echo "   python manage.py diagnose_multilevel_billing UVT847"
    echo "   python manage.py fix_multilevel_billing UVT847"
    echo ""
    echo "FOR SYSTEM-WIDE FIX:"
    echo "   python manage.py fix_modular_billing --dry-run"
    echo "   python manage.py harmonize_billing_status --dry-run"
    echo "   # Review output, then run without --dry-run"
    echo ""
else
    echo ""
    echo "Commit cancelled. No changes were made."
    echo ""
fi
