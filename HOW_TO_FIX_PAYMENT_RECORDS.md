# How to Fix UVTAB Fees Payment Records

## 🚨 The Problem

When candidates are deleted after payment clearance, the payment records (`CenterSeriesPayment.amount_paid`) still show the old amounts including the deleted candidates. This causes:

- **Test Center3 (UVT003)**: Shows UGX 210,000 paid, but only 1 candidate exists (should be UGX 70,000)
- **Test Branch Center**: Shows UGX 315,000 paid, but ALL candidates were deleted (should be UGX 0)

## ✅ The Solution

We've created a management command to clean up the payment records:

### Step 1: Preview Changes (Dry Run)

```bash
source /home/claire/Desktop/projects/emis/venv/bin/activate
cd /home/claire/Desktop/projects/emis/emis
python manage.py fix_payment_records --dry-run --mark-historical
```

This shows what will be changed WITHOUT making actual changes.

### Step 2: Apply the Fixes

```bash
python manage.py fix_payment_records --mark-historical
```

**What This Does:**

1. **Recalculates Payment Amounts**
   - Removes amounts from deleted candidates
   - Only counts EXISTING paid candidates
   - Example: Test Center3: UGX 210,000 → UGX 70,000 ✓

2. **Marks Historical Cleared Candidates**
   - Finds candidates with `fees_balance = 0` and enrollments
   - These were cleared BEFORE our payment tracking system
   - Marks them with `payment_cleared = True` for audit trail

3. **Generates Audit Report**
   - Shows total paid candidates
   - Shows total unpaid candidates
   - Verifies payment integrity

## 📊 Expected Results

### Before Fix:
```
Test Center3:
- 1 candidate (UGX 70,000)
- Payment record: UGX 210,000 ❌ WRONG
- Due: UGX 0
```

### After Fix:
```
Test Center3:
- 1 candidate (UGX 70,000)
- Payment record: UGX 70,000 ✓ CORRECT
- Due: UGX 0
```

## 🔄 When to Run This Command

Run this command:
- ✅ **NOW** - To fix existing data
- ✅ **After accidental candidate deletion** (shouldn't happen with new protection)
- ✅ **During monthly financial audit**
- ✅ **Before generating financial reports**

## ⚠️ Important Notes

1. **Backup First** (Production Only)
   ```bash
   pg_dump emis_db > backup_before_payment_fix_$(date +%Y%m%d).sql
   ```

2. **Safe to Run Multiple Times**
   - The command is idempotent
   - Running it multiple times produces the same result
   - No data is lost

3. **Historical Candidates**
   - Candidates with `fees_balance = 0` are marked as historically cleared
   - They get `payment_cleared = True` with historical timestamp
   - This maintains audit trail for old payments

## 📋 Command Options

```bash
# Preview without making changes
python manage.py fix_payment_records --dry-run

# Preview and include historical candidates
python manage.py fix_payment_records --dry-run --mark-historical

# Apply fixes (recalculate only)
python manage.py fix_payment_records

# Apply fixes + mark historical candidates
python manage.py fix_payment_records --mark-historical
```

## 🧪 Verification

After running the command:

1. **Check Center Fees View**
   - Go to: UVTAB Fees → Center Fees
   - Verify: Test Center3 shows UGX 70,000 paid (not UGX 210,000)

2. **Check Admin Panel**
   - Filter candidates by: `payment_cleared = True`
   - Verify: All paid candidates are listed
   - Verify: Historical candidates now have payment flag

3. **Run Audit Report**
   ```bash
   python manage.py fix_payment_records --dry-run
   ```
   - Look for: "✓ PAYMENT INTEGRITY CHECK: PASSED"
   - This confirms payment records match candidate amounts

## 🎯 What Gets Fixed

| Issue | Before | After |
|-------|--------|-------|
| Test Center3 payment | UGX 210,000 | UGX 70,000 ✓ |
| Test Branch Center payment | UGX 315,000 | UGX 0 ✓ |
| Historical candidates | Not tracked | Marked as cleared ✓ |
| Payment integrity | FAILED | PASSED ✓ |

## 🔒 Future Protection

With our new payment tracking system:
- **Paid candidates CANNOT be deleted** (model-level protection)
- **Payment amounts are recalculated** automatically
- **Complete audit trail** for every payment
- **This fix should only be needed ONCE** to clean up old data

## 📞 Support

If you encounter issues:
- Check command output for error messages
- Verify database connection
- Contact IT Admin if integrity check fails after fix
