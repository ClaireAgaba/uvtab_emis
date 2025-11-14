#!/bin/bash
# Git commands to push billing fix to repository

cd /home/claire/Desktop/projects/emis

echo "Adding management commands..."
git add eims/management/commands/diagnose_center_billing.py
git add eims/management/commands/fix_modular_billing.py
git add eims/management/commands/harmonize_billing_status.py

echo "Adding documentation..."
git add BILLING_FIX_GUIDE.md
git add DEPLOYMENT_GUIDE.md
git add QUICK_FIX_REFERENCE.txt

echo "Committing changes..."
git commit -m "Fix: Add management commands to fix modular billing issues (UBT154)

- Add diagnose_center_billing: Detailed diagnostic tool for center billing
- Add fix_modular_billing: Fix modular candidates showing 0.00 in invoices
- Add harmonize_billing_status: Fix all enrollment billing status issues
- Resolves issue where 54 modular candidates at UBT154 show 0.00 instead of 70k-90k
- Includes dry-run support, center filtering, and comprehensive reporting
- Safe to run multiple times (idempotent)
- Includes detailed documentation and deployment guide"

echo "Pushing to repository..."
git push origin main

echo ""
echo "✅ Done! Files pushed to repository."
echo ""
echo "Next steps on server:"
echo "1. git pull origin main"
echo "2. python manage.py diagnose_center_billing UBT154"
echo "3. python manage.py fix_modular_billing --center UBT154"
echo "4. python manage.py harmonize_billing_status --center UBT154"
echo ""
