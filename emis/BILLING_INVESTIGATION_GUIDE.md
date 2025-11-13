# Billing Investigation Guide for UVT634

## Problem Summary
- **Center**: Don Bosco Vocational Training Center-palabek (UVT634)
- **Expected Bill**: UGX 12,140,000
  - 82 Modular candidates × 70,000 = 5,740,000
  - 80 Formal candidates × 80,000 = 6,400,000
- **Actual Bill**: UGX 12,910,000
- **Discrepancy**: UGX 770,000 (excess)

## Investigation Steps

### Step 1: Investigate the Billing
Run the diagnostic command to see detailed breakdown:

```bash
cd /home/claire/Desktop/projects/emis/emis
python manage.py investigate_center_billing UVT634
```

This will show:
- Total candidates by registration category
- Modular candidates: how many enrolled in 1 vs 2 modules
- Formal candidates: which levels they're enrolled in
- Individual candidate fees breakdown
- Identify where the 770,000 excess is coming from

### Step 2: Dry Run Recalculation
Preview what changes would be made without actually changing anything:

```bash
python manage.py recalculate_center_fees UVT634 --dry-run
```

This will show:
- Which candidates have fee mismatches
- Old fees vs new (correct) fees
- Total difference

### Step 3: Fix the Billing (if needed)
If the dry run shows the correct fees, apply the fix:

```bash
python manage.py recalculate_center_fees UVT634 --fix
```

This will:
- Recalculate all candidate fees based on actual enrollment
- Update the fees_balance for each candidate
- Show summary of changes made

## Possible Root Causes

### 1. **Modular Fee Confusion**
- Some modular candidates might be charged for 2 modules when they only enrolled in 1
- Or vice versa
- Check: modular_fee_single vs modular_fee_double

### 2. **Wrong Fee Amounts Set**
- The level fees might not match expected amounts:
  - Modular single module fee should be 70,000
  - Formal base fee should be 80,000
- Check the Level model fees for this occupation

### 3. **Duplicate Enrollments**
- Some candidates might be enrolled multiple times
- Or enrolled in multiple levels when they should only be in one

### 4. **Manual Fee Adjustments**
- Someone might have manually adjusted fees_balance without proper calculation

### 5. **Old Enrollment Data**
- Candidates might have old enrollment records that weren't cleared
- Previous enrollment fees might still be counted

## Verification Queries

After running the investigation, you can verify specific things:

### Check Level Fees
```python
from eims.models import Level, Occupation
# Find the occupation for this center's candidates
occupation = Occupation.objects.get(code='XXX')  # Replace with actual code
levels = Level.objects.filter(occupation=occupation)
for level in levels:
    print(f"{level.name}: base_fee={level.base_fee}, modular_single={level.modular_fee_single}, modular_double={level.modular_fee_double}")
```

### Check Specific Candidate
```python
from eims.models import Candidate, CandidateModule, CandidateLevel
candidate = Candidate.objects.get(reg_number='XXX')  # Replace with actual reg number
print(f"Category: {candidate.registration_category}")
print(f"Fees Balance: {candidate.fees_balance}")
print(f"Modules: {CandidateModule.objects.filter(candidate=candidate).count()}")
print(f"Levels: {CandidateLevel.objects.filter(candidate=candidate).count()}")
```

## Expected Output Analysis

The investigation command will help identify:

1. **If 770,000 = 11 candidates × 70,000**
   - Suggests 11 extra modular candidates or wrong module count

2. **If 770,000 = 9.625 candidates × 80,000**
   - Suggests some formal candidates charged incorrectly

3. **Mixed scenario**
   - Some combination of modular and formal fee errors

## Next Steps After Investigation

1. **Review the detailed output** from investigate_center_billing
2. **Identify the pattern** of incorrect fees
3. **Run dry-run** to see proposed fixes
4. **Apply fix** if the recalculation looks correct
5. **Regenerate invoice** for the center with correct amounts

## Important Notes

- ⚠️ Always run --dry-run first before --fix
- ⚠️ The investigation command is read-only and safe to run
- ⚠️ The fix command will update the database
- ✓ All changes are logged and can be verified
- ✓ The center's total will automatically update after fixing individual candidates

## Contact

If you need help interpreting the results, share the output of the investigation command.
