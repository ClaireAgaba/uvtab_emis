# Billing Issue Fix Guide - Center UBT154 and Similar Issues

## Problem Summary

**Center**: UBT154 (Hakitengeya Community Polytechnic)  
**Issue**: Modular candidates showing 0.00 in invoice instead of actual fees  
**Impact**: Misleading financial reports - 560k from 7 formal candidates shown correctly, but 54 modular candidates showing 0.00

## Root Causes

### 1. **Modular Billing Calculation Issue**
- Modular candidates enrolled in modules but `modular_billing_amount` field not set
- `fees_balance` showing 0.00 even though candidates are enrolled
- Missing or incorrect `modular_module_count` field

### 2. **Historical Billing Status Not Stored**
- Some candidates were enrolled and billed before billing status tracking was implemented
- These candidates have enrollments (CandidateLevel/CandidateModule records) but `fees_balance = 0`
- System needs to recalculate and store correct billing amounts

### 3. **Invoice Generation Logic**
The invoice generation in `views_fees.py` (lines 1004-1016) tries to calculate modular fees but:
- Falls back to hardcoded values (70k/90k) when `modular_billing_amount` is not set
- Doesn't update the candidate record with calculated amount
- Shows 0.00 when calculation fails

## Solution - Three Management Commands

### Command 1: Diagnose Center Billing
**Purpose**: Get detailed diagnostic information about billing issues

```bash
# Diagnose specific center
python manage.py diagnose_center_billing UBT154

# Diagnose with series filter
python manage.py diagnose_center_billing UBT154 --series "August 2025"
```

**Output**:
- Lists all enrolled candidates by category (Modular, Formal, Informal)
- Shows current vs calculated fees for each candidate
- Displays module/level enrollments and fee structures
- Highlights discrepancies
- Provides category-wise and overall summaries

### Command 2: Fix Modular Billing
**Purpose**: Specifically fix modular candidate billing issues

```bash
# Preview changes (dry run)
python manage.py fix_modular_billing --dry-run

# Fix all modular candidates
python manage.py fix_modular_billing

# Fix specific center
python manage.py fix_modular_billing --center UBT154

# Verbose output
python manage.py fix_modular_billing --center UBT154 --verbose
```

**What it does**:
1. Finds all modular candidates with module enrollments
2. Calculates correct fees based on:
   - Number of enrolled modules (1 or 2)
   - Level fee structure (modular_fee_single/modular_fee_double)
3. Updates three fields:
   - `modular_module_count`: Number of enrolled modules
   - `modular_billing_amount`: Calculated fee amount
   - `fees_balance`: Current outstanding balance
4. Provides detailed reporting of changes

### Command 3: Harmonize Billing Status
**Purpose**: Fix all enrolled candidates (all categories) with billing status issues

```bash
# Preview changes (dry run)
python manage.py harmonize_billing_status --dry-run

# Fix all enrolled candidates
python manage.py harmonize_billing_status

# Fix specific center
python manage.py harmonize_billing_status --center UBT154

# Fix specific series
python manage.py harmonize_billing_status --series "August 2025"

# Combine filters
python manage.py harmonize_billing_status --center UBT154 --series "August 2025"
```

**What it does**:
1. Finds all candidates with enrollments (CandidateLevel or CandidateModule)
2. Recalculates fees using `calculate_fees_balance()` method
3. Updates billing fields appropriately for each category:
   - **Modular**: Updates module count, billing amount, and balance
   - **Formal**: Updates fees balance based on level fees
   - **Informal**: Updates fees balance based on module fees
4. Provides category-wise reporting

## Recommended Fix Workflow for UBT154

### Step 1: Diagnose the Issue
```bash
python manage.py diagnose_center_billing UBT154
```

Review the output to understand:
- How many candidates are affected
- Which categories have issues
- Total discrepancy amount

### Step 2: Preview Fixes (Dry Run)
```bash
# Preview modular fixes
python manage.py fix_modular_billing --center UBT154 --dry-run

# Preview all category fixes
python manage.py harmonize_billing_status --center UBT154 --dry-run
```

Review the proposed changes to ensure they're correct.

### Step 3: Apply Fixes
```bash
# Fix modular candidates first (most common issue)
python manage.py fix_modular_billing --center UBT154

# Then harmonize all categories
python manage.py harmonize_billing_status --center UBT154
```

### Step 4: Verify Fixes
```bash
# Re-run diagnostic to confirm
python manage.py diagnose_center_billing UBT154
```

Should show "✅ No billing discrepancies found"

### Step 5: Regenerate Invoice
- Go to UVTAB Fees → Center Fees
- Search for UBT154
- Click "Invoice" button
- Verify that modular candidates now show correct amounts

## Understanding the Fee Structure

### Modular Registration
- **Enrollment**: Candidates enroll in MODULES ONLY (no level enrollment)
- **Fee Calculation**: Based on number of modules selected
  - 1 module: `level.modular_fee_single` (typically 70,000 UGX)
  - 2 modules: `level.modular_fee_double` (typically 90,000 UGX)
- **Billing**: Stored in `modular_billing_amount` and `fees_balance`

### Formal Registration
- **Enrollment**: Candidates enroll in a LEVEL
- **Fee Calculation**: Based on level's `formal_fee` (typically 80,000 UGX)
- **Billing**: Stored in `fees_balance`

### Worker's PAS/Informal Registration
- **Enrollment**: Enroll in level → select modules → select papers
- **Fee Calculation**: Charged PER MODULE
  - Formula: `level.workers_pas_module_fee × number_of_modules`
- **Billing**: Stored in `fees_balance`

## System-Wide Fix (All Centers)

If this issue affects multiple centers, run commands without center filter:

```bash
# Diagnose all centers (generates large output)
# Better to check specific centers

# Fix all modular candidates system-wide
python manage.py fix_modular_billing --dry-run  # Preview first
python manage.py fix_modular_billing            # Apply

# Harmonize all enrolled candidates system-wide
python manage.py harmonize_billing_status --dry-run  # Preview first
python manage.py harmonize_billing_status            # Apply
```

## Prevention - Ensuring Future Enrollments Work Correctly

The `calculate_fees_balance()` method in the Candidate model (models.py, line 855) should automatically calculate fees. The issue occurs when:

1. **Modular candidates**: `modular_module_count` not set during enrollment
2. **All candidates**: `fees_balance` not updated after enrollment

**Solution**: Ensure enrollment views call `candidate.update_fees_balance()` after enrollment.

## Technical Details

### Files Involved
- `models.py`: Candidate model with `calculate_fees_balance()` method
- `views_fees.py`: Invoice generation logic
- Management commands:
  - `diagnose_center_billing.py`: Diagnostic tool
  - `fix_modular_billing.py`: Modular-specific fix
  - `harmonize_billing_status.py`: All-category fix

### Database Fields Updated
- `Candidate.modular_module_count`: Number of enrolled modules (modular only)
- `Candidate.modular_billing_amount`: Cached billing amount (modular only)
- `Candidate.fees_balance`: Current outstanding balance (all categories)

### Calculation Logic
The `calculate_fees_balance()` method uses:
1. **Modular**: Checks `modular_billing_amount` first, then calculates from level fees
2. **Formal**: Sums fees from all enrolled levels
3. **Informal**: Calculates based on module count × module fee

## Support

If issues persist after running these commands:
1. Check that level fees are properly configured (modular_fee_single, modular_fee_double, formal_fee, workers_pas_module_fee)
2. Verify that candidates have proper enrollments (CandidateModule or CandidateLevel records)
3. Check for any database constraints or validation errors in logs

## Summary

**Quick Fix for UBT154**:
```bash
python manage.py diagnose_center_billing UBT154
python manage.py fix_modular_billing --center UBT154
python manage.py harmonize_billing_status --center UBT154
python manage.py diagnose_center_billing UBT154  # Verify
```

This should resolve the issue where modular candidates show 0.00 instead of their actual fees.
