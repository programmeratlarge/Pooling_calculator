# Analysis of Example Spreadsheet vs SPEC.md

## Date
2025-12-16

## Summary
The example spreadsheet `7050I_miRNA_pool_copy.xlsx` aligns well with the SPEC.md, with some minor differences and clarifications needed.

---

## Spreadsheet Structure

### INPUTS Sheet
Primary input data with the following columns:

| Column | Letter | Name | Description | Required in SPEC? |
|--------|--------|------|-------------|-------------------|
| A | 1 | Project# | Project identifier | ✓ Yes (Project ID) |
| B | 2 | Lib Name | Library name | ✓ Yes (Library Name) |
| C | 3 | RNA | RNA sample ID | ⚠️ Not in spec (could be metadata) |
| D | 4 | Final ng/ul | Concentration | ✓ Yes (Final ng/ul) |
| E | 5 | Total vol | Available volume | ✓ Yes (Total Volume) |
| F | 6 | UDI: Plate_Well | Barcode/index | ✓ Yes (Barcodes) |
| G | 7 | notes | Notes | ⚠️ Optional metadata |
| H | 8 | Adj peak size | Fragment length (bp) | ✓ Yes (Adjusted peak size) |
| I | 9 | lowMW=primer %ofLib | Low MW % | ⚠️ Not in spec |
| J | 10 | AdDimer nM | Adapter dimer conc | ⚠️ Not in spec (used for adjustment) |
| K | 11 | Library nM (Calculated) | Calculated molarity | Computed |
| L | 12 | Total nM | Total molarity | ⚠️ Not in spec |
| M | 13 | final# | Final number | ⚠️ Not in spec |
| N | 14 | library storage | Storage location | ⚠️ Optional metadata |
| O | 15 | Library nM (Empirical) | qPCR molarity | ✓ Yes (Empirical Library nM) |
| P | 16 | Library nM (Use) | Selected molarity | Computed (effective nM) |
| Q | 17 | Target Reads (M) | Target read count | ✓ Yes (Target Reads M) |

### Final Pool Sheet
Calculations and pooling plan with key columns:

| Column | Letter | Name | Description |
|--------|--------|------|-------------|
| R | 18 | Adj lib nM | Adjusted library molarity (after adapter dimer correction) |
| AA | 27 | vol | Volume to add to pool (µl) |
| AF | 32 | stock vol | Base volume calculation before dilution |
| AC | 29 | adj lib pmol | Picomoles of library in pool |
| AH | 34 | adj lib pmol | Total picomoles (for % calculation) |
| AI | 35 | % of pool | Percentage of total pool |
| AJ | 36 | est M reads | Estimated reads (if total reads specified) |

---

## Key Formulas

### 1. Molarity Calculation (Column K - INPUTS)
```
=D6/(H6*660)*1000000
```

**Interpretation:**
- C_nM = (ng/µl × 10⁶) / (bp × 660)
- Where 660 g/mol is the average molecular weight per base pair for dsDNA

**Verification:**
- Example: EF19
- ng/µl = 1.7766
- bp = 198
- Calculated: 1.7766 × 1000000 / (198 × 660) = 13.5950 nM ✓

**SPEC Alignment:** ✓ Matches SPEC.md Section 3.2

### 2. Effective Molarity Selection (Column P - INPUTS)
```
=IF(ISNUMBER(O6),O6,K6)
```

**Interpretation:**
- If empirical nM is provided (numeric), use it
- Otherwise, use calculated nM

**SPEC Alignment:** ✓ Matches SPEC.md Section 3.2

### 3. Adapter Dimer Adjustment (Column R - Final Pool)
```
=IF($C6=0,"",$P6-($J6*R$4))
```

**Interpretation:**
- Adj lib nM = Use nM - (AdDimer nM × adjustment_factor)
- Where R$4 appears to be an adjustment coefficient (0.05)

**SPEC Alignment:** ⚠️ **Not in current SPEC**
- This is an additional refinement to account for adapter dimers
- Should be considered for inclusion in SPEC

### 4. Volume Calculation (Column AF - Final Pool)
```
=IF(R6="","",$AA$4/R6*Q6)
```

**Interpretation:**
- V_i = (pool_volume / C_i) × w_i
- Where:
  - $AA$4 = Desired pool volume parameter (0.1 µl in this example)
  - R6 = Adjusted library molarity (nM)
  - Q6 = Target reads (weight factor)

**SPEC Alignment:** ⚠️ **Different from SPEC formula**

**SPEC.md formula (Section 4.3.2):**
1. v_i^raw = w_i / C_i
2. V_raw,total = Σ v_i^raw
3. s = V_pool / V_raw,total
4. V_i = v_i^raw × s

**Spreadsheet approach:**
- V_i = (pool_volume / C_i) × w_i
- This simplifies to: V_i = pool_volume × (w_i / C_i)

**Mathematical equivalence check:**
- SPEC: V_i = (w_i / C_i) × (V_pool / Σ(w_j / C_j))
- Spreadsheet: V_i = V_pool × (w_i / C_i)

**These are NOT equivalent!**

The spreadsheet formula is missing the normalization step. Let me verify:

**Spreadsheet sum check:**
- Sum of all volumes (AA20) = 19.696 µl
- Pool volume parameter (AA4) = 0.1 µl

This doesn't match! The sum should equal the pool volume.

**Wait - checking the actual implementation...**
The spreadsheet uses pool_volume = 0.1 but the sum is ~20 µl, which means:
- The spreadsheet is NOT using this as the final pool volume
- It appears to be using it as a normalization constant or concentration target

Let me re-examine the actual workflow...

### Re-analysis of Volume Calculation

Looking at the actual values:
- AF6 (stock vol for EF19) = 0.7356 µl (this is what's shown as "stock vol")
- AA6 (vol for EF19) = "in Prepool" (text, not a number)

The libraries go into pre-pools first, then those pre-pools are combined.

**Column AA (vol) formula:**
```
=IF($AK6>0,"in Prepool",IF($R6="","",AF6*IF($Z6="",1,$Z6)))
```

This shows:
- If in a prepool (AK6>0), display "in Prepool"
- Otherwise, volume = stock_vol × dilution_factor

**So the workflow is:**
1. Calculate stock_vol (AF) = (pool_param / C_i) × w_i
2. This gives relative volumes
3. Sum these to get total volume needed
4. Apply dilution if needed (column Z)

**Key insight:** The pool parameter (0.1) is NOT the final pool volume, but rather a concentration or normalization parameter!

---

## Comparison with SPEC.md

### ✓ **Matches SPEC:**
1. Molarity calculation formula (660 g/mol/bp)
2. Empirical nM override logic
3. Target reads as weighting factor
4. Project-level grouping
5. Volume constraints checking

### ⚠️ **Differs from SPEC:**

#### 1. Volume Calculation Method
**SPEC:** Normalize to desired total pool volume
**Spreadsheet:** Use pool parameter as concentration/normalization constant

**Recommendation:** Clarify in SPEC what the "pool volume" parameter means. Options:
- A) Keep SPEC approach: User specifies final pool volume (e.g., 50 µl)
- B) Use spreadsheet approach: User specifies molarity or concentration target

#### 2. Adapter Dimer Adjustment
**SPEC:** Not mentioned
**Spreadsheet:** Adjusts effective molarity by subtracting adapter dimer contribution

**Recommendation:** Add to SPEC as optional advanced feature

#### 3. Pre-pool/Sub-pool Workflow
**SPEC:** Mentions sub-pools conceptually
**Spreadsheet:** Has dedicated Prepool 1 and Prepool 2 sheets with detailed tracking

**Recommendation:** Expand SPEC Section 4.3.3 with concrete pre-pool implementation

#### 4. Additional Columns Not in SPEC
- RNA sample ID (Column C)
- Low MW / primer % (Column I)
- Total nM (Column L)
- Storage location (Column N)

**Recommendation:** Add to SPEC as optional metadata columns

---

## Test Data Summary

### Example Dataset: 7050I_miRNA_pool
- Project: 7050I
- Number of libraries: 13
- Fragment sizes: 196-199 bp (very uniform - miRNA libraries)
- Concentrations: 0.11 - 3.3 ng/µl
- Target reads: Mix of 10M and 100M (10x difference for weighted pooling)

### Libraries with 100M target:
EF19, EF21, EF23, EF25, EF27, EF29 (6 libraries)

### Libraries with 10M target:
EF20, EF22, EF24, EF26, EF28, EF30, EF31 (7 libraries)

### Calculated volumes (stock vol, column AF):
Range: 0.04 - 12.94 µl

### Key observations:
1. Libraries with lower concentration require more volume
2. Libraries with higher target reads require more volume
3. The 100M target libraries get ~10x more volume than 10M libraries (at same concentration)
4. One library (EF29) has very low molarity (0.77 nM) and requires 12.94 µl - potentially flagged

---

## Recommendations for SPEC Updates

### High Priority:
1. **Clarify pool volume parameter meaning** - is it final volume or normalization constant?
2. **Add adapter dimer adjustment** as optional feature
3. **Expand pre-pool/sub-pool section** with concrete implementation

### Medium Priority:
4. Add optional metadata columns (RNA ID, storage, etc.)
5. Add validation for extreme volume requirements
6. Specify rounding/precision for volumes

### Low Priority:
7. Document dilution factor logic (column Z)
8. Add pre-dilution calculations
9. Add post-pool QC calculations (% of pool, expected reads)

---

## Next Steps

1. Create clean input-only spreadsheet for testing
2. Extract expected outputs for validation
3. Update SPEC.md based on findings
4. Implement calculator with aligned logic
