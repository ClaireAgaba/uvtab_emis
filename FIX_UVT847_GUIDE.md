# Fix Guide for Center UVT847 - Multi-Level Billing Issue

## Problem Summary

**Center**: UVT847 (Kibuli Core Primary Teachers College Department of Vocational Studies)  
**Location**: N/A, Kampala, Uganda  
**Assessment Series**: November 2025 Series  
**Total Candidates**: 50

### Expected Breakdown
- **4 Modular** candidates × 70,000 = **280,000 UGX**
- **27 Level 1** candidates × 80,000 = **2,160,000 UGX**
- **16 Level 2** candidates × 100,000 = **1,600,000 UGX**
- **3 Level 3** candidates × 150,000 = **450,000 UGX**
- **TOTAL EXPECTED: 4,490,000 UGX**

### Current Invoice Shows
- Modular: **0.00** (should be 280,000) ❌
- Formal: **1,040,000** (should be 4,210,000) ❌
- Total Bill: **5,450,000** (incorrect)
- Amount Paid: **4,410,000**
- Amount Due: **1,040,000**

### Issues Identified
1. ❌ Modular candidates showing 0.00 instead of 280,000
2. ❌ Formal total is wrong (1,040,000 vs expected 4,210,000)
3. ❌ Overall total doesn't match expected breakdown
4. ❌ Multi-level billing not calculating correctly

## Solution - New Management Commands

### Command 1: Diagnose Multi-Level Billing
**Purpose**: Get detailed breakdown by level with expected vs actual fees

```bash
# Diagnose UVT847
python manage.py diagnose_multilevel_billing UVT847

# With series filter
python manage.py diagnose_multilevel_billing UVT847 --series "November 2025"
```

**What it shows**:
- Modular candidates breakdown
- Formal candidates grouped by level (Level 1, Level 2, Level 3)
- Each level's fee structure and candidate count
- Current vs correct fees for each candidate
- Discrepancies highlighted
- Grand total summary

### Command 2: Fix Multi-Level Billing
**Purpose**: Fix billing for all candidates including multi-level scenarios

```bash
# Preview changes (dry run)
python manage.py fix_multilevel_billing UVT847 --dry-run

# Apply fixes
python manage.py fix_multilevel_billing UVT847

# With verbose output
python manage.py fix_multilevel_billing UVT847 --verbose

# With series filter
python manage.py fix_multilevel_billing UVT847 --series "November 2025"
```

**What it does**:
1. Identifies all enrolled candidates at the center
2. Calculates correct fees based on:
   - Modular: Number of modules × module fee
   - Formal: Level's formal_fee (80k, 100k, 150k, etc.)
   - Informal: Module count × workers_pas_module_fee
3. Updates `fees_balance` field with correct amount
4. Provides detailed reporting by category and level

## Step-by-Step Fix for UVT847

### Step 1: Diagnose the Issue
```bash
python manage.py diagnose_multilevel_billing UVT847
```

**Expected output**:
```
MODULAR CANDIDATES (4)
- Shows each modular candidate
- Current: 0.00, Correct: 70,000
- Discrepancy: 280,000 total

FORMAL CANDIDATES BY LEVEL

Level 1 (27 candidates)
- Level Fee: 80,000
- Expected: 2,160,000
- Current: varies
- Discrepancy: shown

Level 2 (16 candidates)
- Level Fee: 100,000
- Expected: 1,600,000
- Current: varies
- Discrepancy: shown

Level 3 (3 candidates)
- Level Fee: 150,000
- Expected: 450,000
- Current: varies
- Discrepancy: shown

GRAND TOTAL
- Current: varies
- Correct: 4,490,000
- Discrepancy: shown
```

### Step 2: Preview Fixes
```bash
python manage.py fix_multilevel_billing UVT847 --dry-run --verbose
```

Review the proposed changes carefully.

### Step 3: Apply Fixes
```bash
python manage.py fix_multilevel_billing UVT847
```

### Step 4: Verify Fixes
```bash
python manage.py diagnose_multilevel_billing UVT847
```

Should show "✅ No billing discrepancies found"

### Step 5: Regenerate Invoice
1. Go to UVTAB Fees → Center Fees
2. Search for UVT847
3. Click "Invoice" button
4. Verify the breakdown:
   - Modular: 280,000 (4 candidates)
   - Formal: 4,210,000 (46 candidates across 3 levels)
   - Total: 4,490,000

## Alternative: Use General Commands

You can also use the general billing fix commands:

```bash
# Fix modular billing
python manage.py fix_modular_billing --center UVT847

# Harmonize all billing
python manage.py harmonize_billing_status --center UVT847
```

## Understanding Multi-Level Fee Structure

### Level Fees Configuration
Each level has its own `formal_fee` field:
- **Level 1**: 80,000 UGX
- **Level 2**: 100,000 UGX
- **Level 3**: 150,000 UGX

### How Billing Works
1. **Formal candidates**: Billed based on their enrolled level's `formal_fee`
2. **Modular candidates**: Billed based on module count (70k for 1, 90k for 2)
3. **Informal candidates**: Billed per module (workers_pas_module_fee × module_count)

### Calculation Method
The `calculate_fees_balance()` method in the Candidate model:
- For Formal: Sums fees from all enrolled levels
- For Modular: Uses level's modular_fee_single or modular_fee_double
- For Informal: Multiplies module count by workers_pas_module_fee

## Git Deployment

### Files to Push
```bash
cd /home/claire/Desktop/projects/emis

# Add new commands
git add eims/management/commands/diagnose_multilevel_billing.py
git add eims/management/commands/fix_multilevel_billing.py

# Add documentation
git add FIX_UVT847_GUIDE.md

# Commit
git commit -m "Fix: Add multi-level billing diagnostic and fix commands for UVT847

- Add diagnose_multilevel_billing for detailed level-by-level analysis
- Add fix_multilevel_billing to fix multi-level billing issues
- Handles Level 1, Level 2, Level 3 fee structures correctly
- Resolves UVT847 issue where formal candidates show wrong totals
- Includes comprehensive reporting and dry-run support"

# Push
git push origin main
```

### Server Deployment
```bash
# On production server
cd /path/to/emis
git pull origin main

# Run diagnostic
python manage.py diagnose_multilevel_billing UVT847

# Preview fix
python manage.py fix_multilevel_billing UVT847 --dry-run

# Apply fix
python manage.py fix_multilevel_billing UVT847

# Verify
python manage.py diagnose_multilevel_billing UVT847
```

## Expected Results After Fix

### Invoice Breakdown
```
Number of Candidates: 50

Modular — 4 candidate(s):     280,000.00
Formal — 46 candidate(s):   4,210,000.00
  - Level 1 (27): 2,160,000
  - Level 2 (16): 1,600,000
  - Level 3 (3):    450,000

Total Bill:                 4,490,000.00
Amount Paid:                4,410,000.00
Amount Due:                    80,000.00
```

## Troubleshooting

### If totals still don't match:
1. Check that level fees are configured correctly:
   ```bash
   python manage.py shell
   >>> from eims.models import Level
   >>> Level.objects.filter(name__icontains='level').values('name', 'formal_fee')
   ```

2. Verify candidate enrollments:
   ```bash
   python manage.py diagnose_multilevel_billing UVT847 --verbose
   ```

3. Check for duplicate enrollments or missing level assignments

### If specific candidates have issues:
- The diagnostic command shows each candidate individually
- Look for candidates with "⚠️" status
- Check their enrolled levels and fee calculations

## Summary

**Quick Fix Commands**:
```bash
# Local machine
cd /home/claire/Desktop/projects/emis
git add eims/management/commands/diagnose_multilevel_billing.py eims/management/commands/fix_multilevel_billing.py FIX_UVT847_GUIDE.md
git commit -m "Fix: Add multi-level billing commands for UVT847"
git push origin main

# Production server
cd /path/to/emis
git pull origin main
python manage.py diagnose_multilevel_billing UVT847
python manage.py fix_multilevel_billing UVT847 --dry-run
python manage.py fix_multilevel_billing UVT847
python manage.py diagnose_multilevel_billing UVT847
```

This should resolve all billing issues for UVT847 and any other centers with multi-level enrollment scenarios.
