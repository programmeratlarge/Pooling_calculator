# Test Data Directory

This directory contains test datasets for the NGS Library Pooling Calculator.

## Files

### Original Example Spreadsheet
- **`7050I_miRNA_pool_copy.xlsx`** - Original example spreadsheet with formulas and calculations
  - Contains INPUTS sheet with raw data
  - Contains Final Pool, Prepool 1, Prepool 2 sheets with calculations
  - Source of truth for validation

### Test Input Files
- **`7050I_test_input.xlsx`** - Clean input-only spreadsheet for testing
- **`7050I_test_input.csv`** - CSV version of test inputs
  - Contains only the required input columns from SPEC.md
  - 12 libraries from project 7050I
  - Ready to use with pooling calculator app

**Required Columns:**
1. Project ID
2. Library Name
3. Final ng/ul
4. Total Volume
5. Barcodes
6. Adjusted peak size
7. Empirical Library nM (optional - all empty in this dataset)
8. Target Reads (M)

### Expected Output Files
- **`7050I_expected_outputs.xlsx`** - Expected calculation results
- **`7050I_expected_outputs.csv`** - CSV version of expected outputs
  - Extracted from original spreadsheet
  - Use for validation testing
  - Contains calculated nM, effective nM, and stock volumes

**Output Columns:**
1. Library Name
2. Project ID
3. Final ng/ul (input)
4. Adjusted peak size (input)
5. Empirical Library nM (input)
6. Target Reads (M) (input)
7. **Calculated nM** - Computed from ng/ul and fragment size
8. **Effective nM (Use)** - Either empirical or calculated
9. **Adjusted lib nM** - After adapter dimer adjustment
10. **Stock Volume (µl)** - Volume to add to pool

### Analysis Documents
- **`ANALYSIS.md`** - Detailed analysis comparing original spreadsheet with SPEC.md
  - Formula breakdowns
  - Differences identified
  - Recommendations for SPEC updates

## Test Dataset: 7050I miRNA Libraries

### Overview
- **Project:** 7050I
- **Library type:** miRNA (small RNA)
- **Number of libraries:** 12
- **Fragment sizes:** 196-199 bp (very uniform)
- **Concentrations:** 0.1 - 3.3 ng/µl (wide range)

### Target Read Distribution
The dataset demonstrates **weighted pooling**:
- **6 libraries** with 100M target reads (high priority)
- **6 libraries** with 10M target reads (low priority)

This 10-fold difference in target reads should result in ~10x volume difference for libraries at the same concentration.

### Libraries

| # | Library | Final ng/µl | Peak Size (bp) | Target Reads (M) | Calculated nM | Stock Vol (µl) |
|---|---------|-------------|----------------|------------------|---------------|----------------|
| 1 | EF19 | 1.777 | 198 | 100 | 13.595 | 0.736 |
| 2 | EF20 | 1.704 | 198 | 10 | 13.037 | 0.077 |
| 3 | EF21 | 1.612 | 198 | 100 | 12.334 | 0.811 |
| 4 | EF22 | 2.272 | 196 | 10 | 17.566 | 0.057 |
| 5 | EF23 | 2.456 | 198 | 100 | 18.792 | 0.532 |
| 6 | EF24 | 2.396 | 198 | 10 | 18.337 | 0.055 |
| 7 | EF25 | 2.530 | 199 | 100 | 19.263 | 0.519 |
| 8 | EF26 | 3.300 | 198 | 10 | 25.253 | 0.040 |
| 9 | EF27 | 3.121 | 197 | 100 | 24.006 | 0.417 |
| 10 | EF28 | 0.100 | 198 | 10 | 0.765 | 1.307 |
| 11 | EF29 | 0.100 | 196 | 100 | 0.773 | **12.936** ⚠️ |
| 12 | EF30 | 0.100 | 197 | 10 | 0.769 | 1.300 |

### Key Test Cases

#### 1. Standard Libraries (EF19-EF27)
- Normal concentrations (1.6 - 3.3 ng/µl)
- Small volume requirements (0.04 - 0.81 µl)
- Good for testing basic pooling calculations

#### 2. Low Concentration Libraries (EF28-EF30)
- Very low concentration (0.1 ng/µl)
- Larger volume requirements (1.3 - 12.9 µl)
- Tests edge cases and volume warnings

#### 3. Extreme Case: EF29 ⚠️
- Lowest concentration (0.1 ng/µl)
- Highest target reads (100M)
- Requires **12.936 µl** - potential concern
- Good test for validation warnings

#### 4. Paired Comparison
- **EF19 vs EF20**: Same concentration, 10x target difference
  - EF19: 100M target → 0.736 µl
  - EF20: 10M target → 0.077 µl
  - Ratio: ~10x ✓

- **EF28 vs EF29**: Same concentration, 10x target difference
  - EF29: 100M target → 12.936 µl
  - EF28: 10M target → 1.307 µl
  - Ratio: ~10x ✓

### Expected Calculation Formula

**Molarity (nM):**
```
C_nM = (ng/µl × 10^6) / (bp × 660)
```

**Stock Volume (µl):**
```
V = (pool_param / C_nM) × target_reads
```
Where `pool_param = 0.1` in the original spreadsheet.

**Total Stock Volume Sum:** 18.785 µl

## Validation Checklist

When testing the pooling calculator, verify:

- [ ] Molarity calculations match expected values (within 0.0001 nM)
- [ ] Volume calculations match expected values (within 0.0001 µl)
- [ ] Total volume sum is correct (18.785 µl)
- [ ] Libraries with 10x target reads get ~10x volume (at same concentration)
- [ ] Low concentration libraries are flagged if volume > threshold
- [ ] All 12 libraries are processed
- [ ] No duplicates in Library Name or Barcodes
- [ ] Project-level summary shows correct aggregation

## Usage

### For Testing Input Validation
Use: `7050I_test_input.xlsx` or `7050I_test_input.csv`

### For Testing Calculations
1. Load `7050I_test_input.xlsx`
2. Run pooling calculator with pool_volume = 0.1
3. Compare results with `7050I_expected_outputs.csv`

### For Understanding the Original Workflow
1. Open `7050I_miRNA_pool_copy.xlsx`
2. Review INPUTS sheet for input structure
3. Review Final Pool sheet for calculation formulas
4. See ANALYSIS.md for detailed formula breakdown

## Notes

- No empirical nM values in this dataset (all libraries use calculated nM)
- No adapter dimer adjustment in test inputs (would require additional columns)
- Fragment sizes are very uniform (196-199 bp) - typical for miRNA libraries
- Wide concentration range (0.1 - 3.3 ng/µl) tests the calculator's robustness

## Future Test Datasets

Consider adding:
- Dataset with empirical nM values
- Multi-project dataset (test sub-pool aggregation)
- Dataset with validation errors (duplicates, missing values, etc.)
- Dataset with extreme fragment size variation (150 - 600 bp)
- Dataset requiring dilution/volume warnings
