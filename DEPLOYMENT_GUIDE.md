# Deployment Guide - Billing Fix for UBT154

## Quick Summary
Fix for modular candidates showing 0.00 in invoices instead of actual fees (70k-90k per candidate).

## Files to Push to Git

### New Management Commands (3 files):
1. `eims/management/commands/diagnose_center_billing.py` - Diagnostic tool
2. `eims/management/commands/fix_modular_billing.py` - Fix modular billing
3. `eims/management/commands/harmonize_billing_status.py` - Fix all categories

### Documentation:
- `BILLING_FIX_GUIDE.md` - Detailed guide
- `quick_fix_ubt154.sh` - Quick fix script (optional)

## Git Commands

```bash
cd /home/claire/Desktop/projects/emis

# Add the new management commands
git add eims/management/commands/diagnose_center_billing.py
git add eims/management/commands/fix_modular_billing.py
git add eims/management/commands/harmonize_billing_status.py

# Add documentation
git add BILLING_FIX_GUIDE.md

# Commit
git commit -m "Fix: Add management commands to fix modular billing issues (UBT154 and system-wide)

- Add diagnose_center_billing command for detailed diagnostics
- Add fix_modular_billing command to fix modular candidate billing
- Add harmonize_billing_status command to fix all enrollment billing
- Resolves issue where modular candidates show 0.00 in invoices
- Includes comprehensive documentation and dry-run support"

# Push to repository
git push origin main
```

## Server Deployment Steps

### 1. Pull Latest Code
```bash
cd /path/to/emis/on/server
git pull origin main
```

### 2. Verify Commands Are Available
```bash
python manage.py help diagnose_center_billing
python manage.py help fix_modular_billing
python manage.py help harmonize_billing_status
```

### 3. Run Diagnostic (Preview Only)
```bash
# Check UBT154 specifically
python manage.py diagnose_center_billing UBT154
```

This will show:
- All enrolled candidates by category
- Current vs correct fees
- Total discrepancy amount

### 4. Preview Fixes (Dry Run)
```bash
# Preview modular fixes for UBT154
python manage.py fix_modular_billing --center UBT154 --dry-run

# Preview all category fixes for UBT154
python manage.py harmonize_billing_status --center UBT154 --dry-run
```

### 5. Apply Fixes
```bash
# Fix modular candidates at UBT154
python manage.py fix_modular_billing --center UBT154

# Harmonize all billing status at UBT154
python manage.py harmonize_billing_status --center UBT154
```

### 6. Verify Fixes
```bash
# Re-run diagnostic - should show no discrepancies
python manage.py diagnose_center_billing UBT154
```

### 7. Test Invoice Generation
- Go to UVTAB Fees → Center Fees
- Search for UBT154
- Click "Invoice" button
- Verify modular candidates now show correct amounts (70k or 90k)

## System-Wide Fix (If Needed)

If other centers have the same issue:

```bash
# Preview system-wide
python manage.py fix_modular_billing --dry-run
python manage.py harmonize_billing_status --dry-run

# Apply system-wide
python manage.py fix_modular_billing
python manage.py harmonize_billing_status
```

## Expected Results for UBT154

**Before Fix**:
- Modular candidates: 0.00 (incorrect)
- Formal candidates: 560,000 (correct)
- Total: 560,000

**After Fix**:
- Modular candidates: ~3,780,000 - 4,860,000 (depending on module counts)
- Formal candidates: 560,000
- Total: ~4,340,000 - 5,420,000

## Rollback (If Needed)

These commands only update billing fields and don't delete data. If issues occur:

1. The old values are reported in the command output
2. You can manually revert specific candidates if needed
3. No enrollment data is modified - only billing amounts

## Support Commands

```bash
# Check specific center with series filter
python manage.py diagnose_center_billing UBT154 --series "August 2025"

# Fix with verbose output
python manage.py fix_modular_billing --center UBT154 --verbose

# Fix specific series only
python manage.py harmonize_billing_status --center UBT154 --series "August 2025"
```

## Safety Features

✅ All commands support `--dry-run` for preview  
✅ Detailed reporting of all changes  
✅ No data deletion - only updates billing fields  
✅ Can be run multiple times safely (idempotent)  
✅ Center-specific filtering available  
✅ Series-specific filtering available  

## Timeline

**Estimated Time**: 5-10 minutes total
- Git push: 1 min
- Server pull: 1 min
- Diagnostic: 1 min
- Preview fixes: 2 min
- Apply fixes: 2-3 min
- Verification: 2 min

## Contact

If issues arise during deployment, the commands provide detailed error messages and can be safely re-run.
