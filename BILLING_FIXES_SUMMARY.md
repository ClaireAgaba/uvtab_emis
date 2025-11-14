# Billing Fixes Summary - Complete Solution

## Overview

Created comprehensive solution to fix billing issues affecting multiple assessment centers in the EMIS system.

## Problems Identified

### Problem 1: UBT154 - Modular Billing Issue
- **Center**: UBT154 (Hakitengeya Community Polytechnic)
- **Issue**: 54 modular candidates showing 0.00 instead of 70k-90k
- **Impact**: Missing ~3.8M-4.8M UGX in billing
- **Root Cause**: `modular_billing_amount` and `fees_balance` not set during enrollment

### Problem 2: UVT847 - Multi-Level Billing Issue
- **Center**: UVT847 (Kibuli Core Primary Teachers College)
- **Issue**: Multi-level formal candidates not calculating correctly
- **Breakdown**:
  - 4 Modular × 70k = 280k (showing 0.00) ❌
  - 27 Level 1 × 80k = 2,160k
  - 16 Level 2 × 100k = 1,600k
  - 3 Level 3 × 150k = 450k
  - **Expected Total**: 4,490,000 UGX
  - **Actual Invoice**: Incorrect breakdown
- **Root Cause**: Multi-level fee calculation not working properly

## Solution - 5 Management Commands Created

### 1. diagnose_center_billing.py
**Purpose**: Detailed diagnostic for single center billing issues

**Usage**:
```bash
python manage.py diagnose_center_billing UBT154
python manage.py diagnose_center_billing UVT847 --series "November 2025"
```

**Features**:
- Shows all enrolled candidates by category
- Displays current vs correct fees
- Highlights discrepancies
- Provides category-wise summaries
- Shows enrollment details (modules/levels)

### 2. fix_modular_billing.py
**Purpose**: Fix modular candidate billing specifically

**Usage**:
```bash
python manage.py fix_modular_billing --dry-run  # Preview
python manage.py fix_modular_billing --center UBT154
python manage.py fix_modular_billing --verbose
```

**What it fixes**:
- Sets `modular_module_count` based on enrolled modules
- Calculates and sets `modular_billing_amount`
- Updates `fees_balance` with correct amount
- Uses level fee structure (70k for 1 module, 90k for 2)

### 3. harmonize_billing_status.py
**Purpose**: Fix all enrollment billing status issues (all categories)

**Usage**:
```bash
python manage.py harmonize_billing_status --dry-run
python manage.py harmonize_billing_status --center UBT154
python manage.py harmonize_billing_status --series "August 2025"
```

**What it fixes**:
- All enrolled candidates with missing `fees_balance`
- Modular, Formal, and Informal categories
- Recalculates using `calculate_fees_balance()` method
- Updates billing fields appropriately per category

### 4. diagnose_multilevel_billing.py
**Purpose**: Detailed multi-level billing diagnostic

**Usage**:
```bash
python manage.py diagnose_multilevel_billing UVT847
```

**Features**:
- Groups formal candidates by level (Level 1, 2, 3, etc.)
- Shows each level's fee structure
- Displays expected vs actual fees per level
- Provides level-by-level breakdown
- Calculates grand totals

### 5. fix_multilevel_billing.py
**Purpose**: Fix multi-level billing scenarios

**Usage**:
```bash
python manage.py fix_multilevel_billing UVT847 --dry-run
python manage.py fix_multilevel_billing UVT847
python manage.py fix_multilevel_billing UVT847 --verbose
```

**What it fixes**:
- Formal candidates across multiple levels
- Ensures each candidate billed at their level's fee
- Handles Level 1 (80k), Level 2 (100k), Level 3 (150k), etc.
- Also fixes modular and informal in same center

## Files Created

### Management Commands (5 files)
1. ✅ `eims/management/commands/diagnose_center_billing.py`
2. ✅ `eims/management/commands/fix_modular_billing.py`
3. ✅ `eims/management/commands/harmonize_billing_status.py`
4. ✅ `eims/management/commands/diagnose_multilevel_billing.py`
5. ✅ `eims/management/commands/fix_multilevel_billing.py`

### Documentation (5 files)
6. ✅ `BILLING_FIX_GUIDE.md` - Comprehensive guide for UBT154
7. ✅ `FIX_UVT847_GUIDE.md` - Multi-level billing guide for UVT847
8. ✅ `DEPLOYMENT_GUIDE.md` - Step-by-step deployment instructions
9. ✅ `QUICK_FIX_REFERENCE.txt` - Quick command reference
10. ✅ `BILLING_FIXES_SUMMARY.md` - This file

### Scripts (2 files)
11. ✅ `GIT_PUSH_ALL_FIXES.sh` - Automated git push script
12. ✅ `quick_fix_ubt154.sh` - Quick fix script for UBT154

## Deployment Instructions

### Quick Deployment (Recommended)

**On Local Machine**:
```bash
cd /home/claire/Desktop/projects/emis
bash GIT_PUSH_ALL_FIXES.sh
```

This script will:
- Add all management commands
- Add all documentation
- Show files to be committed
- Ask for confirmation
- Commit with detailed message
- Push to repository
- Display next steps

### Manual Deployment

**On Local Machine**:
```bash
cd /home/claire/Desktop/projects/emis

# Add files
git add eims/management/commands/diagnose_center_billing.py
git add eims/management/commands/fix_modular_billing.py
git add eims/management/commands/harmonize_billing_status.py
git add eims/management/commands/diagnose_multilevel_billing.py
git add eims/management/commands/fix_multilevel_billing.py
git add BILLING_FIX_GUIDE.md FIX_UVT847_GUIDE.md DEPLOYMENT_GUIDE.md

# Commit
git commit -m "Fix: Add comprehensive billing fix commands"

# Push
git push origin main
```

**On Production Server**:
```bash
cd /path/to/emis
git pull origin main
```

## Fixing UBT154 (Modular Billing Issue)

```bash
# Step 1: Diagnose
python manage.py diagnose_center_billing UBT154

# Step 2: Preview fix
python manage.py fix_modular_billing --center UBT154 --dry-run

# Step 3: Apply fix
python manage.py fix_modular_billing --center UBT154

# Step 4: Harmonize all billing
python manage.py harmonize_billing_status --center UBT154

# Step 5: Verify
python manage.py diagnose_center_billing UBT154
```

**Expected Result**:
- Before: Modular = 0.00, Total = 560,000
- After: Modular = ~3.8M-4.8M, Total = ~4.3M-5.4M

## Fixing UVT847 (Multi-Level Billing Issue)

```bash
# Step 1: Diagnose with level breakdown
python manage.py diagnose_multilevel_billing UVT847

# Step 2: Preview fix
python manage.py fix_multilevel_billing UVT847 --dry-run

# Step 3: Apply fix
python manage.py fix_multilevel_billing UVT847

# Step 4: Verify
python manage.py diagnose_multilevel_billing UVT847
```

**Expected Result**:
- Modular: 280,000 (4 candidates)
- Formal: 4,210,000 (46 candidates)
  - Level 1: 2,160,000 (27 candidates)
  - Level 2: 1,600,000 (16 candidates)
  - Level 3: 450,000 (3 candidates)
- Total: 4,490,000

## System-Wide Fix (All Centers)

If multiple centers have similar issues:

```bash
# Preview system-wide
python manage.py fix_modular_billing --dry-run
python manage.py harmonize_billing_status --dry-run

# Review output carefully, then apply
python manage.py fix_modular_billing
python manage.py harmonize_billing_status
```

## Key Features

### Safety Features
- ✅ **Dry-run mode**: Preview all changes before applying
- ✅ **Detailed reporting**: See exactly what will change
- ✅ **Idempotent**: Safe to run multiple times
- ✅ **No data deletion**: Only updates billing fields
- ✅ **Rollback info**: Old values shown in output

### Filtering Options
- ✅ **By center**: `--center UBT154`
- ✅ **By series**: `--series "November 2025"`
- ✅ **Verbose output**: `--verbose`
- ✅ **Combined filters**: `--center UBT154 --series "August 2025"`

### Comprehensive Reporting
- ✅ Category breakdown (Modular, Formal, Informal)
- ✅ Level-by-level analysis for multi-level scenarios
- ✅ Current vs correct fees comparison
- ✅ Discrepancy highlighting
- ✅ Grand totals and summaries

## Technical Details

### Fields Updated
- `Candidate.modular_module_count`: Number of enrolled modules (modular only)
- `Candidate.modular_billing_amount`: Cached billing amount (modular only)
- `Candidate.fees_balance`: Current outstanding balance (all categories)

### Calculation Logic
Uses `Candidate.calculate_fees_balance()` method:
- **Modular**: `level.modular_fee_single` (1 module) or `level.modular_fee_double` (2 modules)
- **Formal**: `level.formal_fee` (varies by level: 80k, 100k, 150k, etc.)
- **Informal**: `level.workers_pas_module_fee × module_count`

### Database Queries
- Optimized with `select_related` and `prefetch_related`
- Efficient batch processing
- Minimal database hits

## Testing & Verification

After running fixes:

1. **Run diagnostic command** to verify no discrepancies
2. **Check invoice in UI**:
   - Go to UVTAB Fees → Center Fees
   - Search for center
   - Click "Invoice" button
   - Verify amounts match expected breakdown
3. **Spot-check individual candidates** in candidate view

## Support & Troubleshooting

### If issues persist:
1. Check level fees are configured correctly
2. Verify candidates have proper enrollments
3. Run diagnostic with `--verbose` flag
4. Check command output for specific error messages

### Common Issues:
- **Level fees not set**: Configure in Level model
- **No enrollments**: Candidates must have CandidateLevel or CandidateModule records
- **Wrong registration category**: Check candidate.registration_category field

## Summary

**Total Solution**:
- 5 management commands
- 5 documentation files
- 2 automation scripts
- Comprehensive fix for 2 major billing issues
- System-wide applicability
- Production-ready with safety features

**Ready to deploy**: All files syntax-checked and tested ✅

**Estimated fix time**: 5-10 minutes per center

**Impact**: Fixes potentially millions of UGX in missing billing across affected centers
