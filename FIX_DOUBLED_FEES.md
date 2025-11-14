# Emergency Fix - Doubled Fees at UVT847

## Problem

After running the billing fix commands, UVT847 now shows:
- **Current Total**: 8,900,000 UGX (DOUBLED!)
- **Expected Total**: 4,490,000 UGX
- **Issue**: Fees were added instead of replaced

## Root Cause

The candidates already had some `fees_balance` set. When we ran the fix command, it likely:
1. Calculated the correct fee (4.49M)
2. But the system already had fees set
3. Result: Double counting

## Quick Fix - Reset and Recalculate

### Step 1: Push Emergency Command to Git

```bash
cd /home/claire/Desktop/projects/emis
git add emis/eims/management/commands/reset_center_billing.py
git add EMERGENCY_FIX_UVT847.sh
git add FIX_DOUBLED_FEES.md
git commit -m "Emergency: Add reset command to fix doubled fees at UVT847"
git push origin main
```

### Step 2: On Production Server

```bash
cd /path/to/emis
git pull origin main

# Preview the reset
python manage.py reset_center_billing UVT847 --dry-run

# Apply the reset
python manage.py reset_center_billing UVT847

# Verify
python manage.py diagnose_multilevel_billing UVT847
```

## What the Reset Command Does

1. **Resets** all `fees_balance` to correct amounts
2. **Recalculates** from scratch using `calculate_fees_balance()`
3. **Ensures** no double-counting
4. **Updates** modular billing fields properly

## Expected Result After Reset

```
Modular (4 candidates):      280,000
Level 1 (27 candidates):   2,160,000
Level 2 (16 candidates):   1,600,000
Level 3 (3 candidates):      450,000
--------------------------------
TOTAL:                     4,490,000 ✅
```

## Alternative Manual Fix (If Needed)

If the command doesn't work, you can manually divide by 2:

```python
# In Django shell
from eims.models import Candidate, AssessmentCenter

center = AssessmentCenter.objects.get(center_number='UVT847')
candidates = Candidate.objects.filter(assessment_center=center)

for c in candidates:
    if c.fees_balance and c.fees_balance > 0:
        c.fees_balance = c.fees_balance / 2
        if c.modular_billing_amount:
            c.modular_billing_amount = c.modular_billing_amount / 2
        c.save()
```

## Prevention for Future

Before running billing fix commands:
1. Always use `--dry-run` first
2. Check if candidates already have fees set
3. Use `reset_center_billing` if fees are already set
4. Verify totals match expected breakdown

## Quick Commands

```bash
# Reset UVT847
python manage.py reset_center_billing UVT847 --dry-run
python manage.py reset_center_billing UVT847

# Verify
python manage.py diagnose_multilevel_billing UVT847

# Check invoice in UI
# UVTAB Fees → Center Fees → Search UVT847 → Invoice
```

## Timeline

- **Estimated Time**: 2-3 minutes
- **Impact**: Will correct 8.9M down to 4.49M
- **Safety**: Dry-run available for preview

## Support

If the reset command doesn't work:
1. Check that candidates have proper enrollments
2. Verify level fees are configured correctly
3. Try the manual fix in Django shell
4. Contact for additional support
