# Formula Analysis: 7050I_miRNA_pool_copy.xlsx

## Problem Statement
The current volume calculation in the pooling calculator is incorrect. We need to implement the formula from the reference spreadsheet, which includes:
1. A user-configurable scaling factor
2. Pre-dilution logic for volumes that are too small to pipette accurately
3. Volume availability checking

## Reference Spreadsheet Structure

### Key Columns (Final Pool sheet)

| Column | Name | Formula | Description |
|--------|------|---------|-------------|
| P | nM | `=IF(ISNUMBER(O),O,K)` | Library molarity (empirical if available, else calculated) |
| Q | Reads (M) | From INPUTS | Target reads in millions |
| R | Adj lib nM | `=P - (J*R$4)` | Adjusted library nM (after subtracting contaminants) |
| S | tot nM | `=SUM(J,R)` | **Total nM (CORRECT - currently working)** |
| Z | pre-dilute | See below | Dilution factor (5x or 10x) if volume too small |
| AA | vol | `=AF*IF(Z="",1,Z)` | **Final volume (INCORRECT - needs fixing)** |
| AF | stock vol | `=$AA$4/R*Q` | **Intermediate volume calculation** |

### Cell AA4: Scaling Factor
- **Default value:** 0.1
- **User-configurable:** Yes
- **Purpose:** Controls the overall pool volume scaling

## Formulas Breakdown

### Formula 1: Stock Volume (AF column)
```
AF = (scaling_factor) / (Adj_lib_nM) * (Target_Reads_M)
```

**In Excel:** `=\$AA$4/R6*Q6`

Where:
- `$AA$4` = scaling factor (default 0.1, user-adjustable)
- `R6` = Adj lib nM (adjusted library molarity)
- `Q6` = Target Reads (M) (target reads in millions)

**Physical meaning:** This calculates the base volume needed before considering pipetting limits.

### Formula 2: Pre-dilute Factor (Z column)
```
IF AF < 0.2:    pre-dilute = 10x
ELIF AF < 0.795: pre-dilute = 5x
ELSE:            pre-dilute = (blank, meaning 1x)
```

**In Excel:** `=IF($AK>0,"",IF($R="","",IF(AF<0.2,10,IF(AF<0.795,5,""))))`

**Physical meaning:** If the calculated volume is too small to pipette accurately (<0.2 µL), the sample should be diluted 10-fold. If it's still small (<0.795 µL), dilute 5-fold.

**Threshold:** 0.2 µL appears to be below pipetting accuracy (user mentioned 0.08 µL minimum)

### Formula 3: Final Volume (AA column) - **THE FIX**
```
vol = stock_vol * pre_dilute_factor
```

**In Excel:** `=IF($AK>0,"in Prepool",IF($R="","",AF*IF($Z="",1,$Z)))`

Where:
- `AF` = stock vol (from Formula 1)
- `Z` = pre-dilute factor (from Formula 2, defaults to 1 if blank)

**Note:** The formula also checks if the library is already in a prepool (`$AK>0`) and marks it as "in Prepool" instead of calculating a volume.

## Current Implementation Issues

### Issue 1: Incorrect Volume Formula
**Current code (compute.py:compute_pool_volumes):**
```python
# Current (WRONG):
v_raw = target_reads_m / effective_nm

# Should be (CORRECT):
stock_vol = scaling_factor / effective_nm * target_reads_m
final_vol = stock_vol * pre_dilute_factor
```

### Issue 2: Missing Scaling Factor
- The scaling factor (AA4 = 0.1) is not exposed in the UI
- No way for users to adjust it
- This is critical for controlling final pool volume

### Issue 3: No Pre-dilution Logic
- No check for volumes below pipetting minimum (< 0.2 µL)
- No automatic dilution recommendation
- Missing the "pre-dilute" column in output

### Issue 4: No Volume Availability Check
- Need to verify: `final_vol <= Total_Volume`
- Should flag libraries where we don't have enough material

## Required Changes

### 1. Update `compute_pool_volumes()` Function

**New parameters:**
```python
def compute_pool_volumes(
    df: pd.DataFrame,
    scaling_factor: float = 0.1,          # NEW: AA4 equivalent
    min_pipettable_volume_ul: float = 0.2, # NEW: threshold for pre-dilution
    total_reads_m: float | None = None    # Existing
) -> pd.DataFrame:
```

**New calculation logic:**
```python
# Step 1: Calculate stock volume
stock_vol = scaling_factor / effective_nm * target_reads_m

# Step 2: Determine pre-dilution factor
pre_dilute_factor = []
for vol in stock_vol:
    if vol < 0.2:
        pre_dilute_factor.append(10)
    elif vol < 0.795:
        pre_dilute_factor.append(5)
    else:
        pre_dilute_factor.append(1)

# Step 3: Calculate final volume
final_vol = stock_vol * pre_dilute_factor

# Step 4: Check volume availability
volume_available_flag = final_vol <= total_volume
```

**New output columns:**
- `Stock Volume (µl)` - intermediate calculation
- `Pre-Dilute Factor` - 1x, 5x, or 10x
- `Stock Volume (µl)` - final volume to pipette
- `Volume Available` - boolean flag
- Existing `Flags` column should include volume availability issues

### 2. Update UI (ui.py)

**Add new input:**
```python
scaling_factor = gr.Number(
    value=0.1,
    minimum=0.001,
    maximum=10.0,
    step=0.01,
    label="Scaling Factor",
    info="Controls overall pool volume (default: 0.1)"
)
```

**Add info text:**
```python
gr.Markdown("""
### Volume Calculation Parameters

**Scaling Factor:** Adjusts the volume calculation to achieve desired final pool volume.
- Lower values = smaller volumes
- Higher values = larger volumes
- Typical range: 0.05 - 0.5

**Pre-dilution:** Automatically applied when calculated volumes are too small to pipette accurately (<0.2 µL).
- 10x dilution if volume < 0.2 µL
- 5x dilution if volume < 0.795 µL
""")
```

### 3. Update Config (config.py)

```python
# Volume calculation
DEFAULT_SCALING_FACTOR = 0.1
MIN_PIPETTABLE_VOLUME_UL = 0.2
PRE_DILUTE_THRESHOLD_10X = 0.2   # Below this: 10x dilution
PRE_DILUTE_THRESHOLD_5X = 0.795  # Below this: 5x dilution
```

### 4. Update Output Columns (io.py)

**Add to OUTPUT_LIBRARY_COLUMNS:**
```python
OUTPUT_LIBRARY_COLUMNS = [
    # ... existing columns ...
    "Stock Volume (µl)",           # NEW
    "Pre-Dilute Factor",           # NEW
    "Stock Volume (µl)",       # Updated name from "Volume (µl)"
    "Volume Available",            # NEW
    # ... rest of columns ...
]
```

## Testing Requirements

### Test Case 1: High Concentration Library
```
Library: High_Conc
Adj lib nM: 50
Target Reads (M): 100
Scaling Factor: 0.1

Expected:
- Stock vol = 0.1 / 50 * 100 = 0.2 µL
- Pre-dilute = 10x (because 0.2 < 0.2 threshold, edge case)
- Final vol = 0.2 * 10 = 2.0 µL
```

### Test Case 2: Medium Concentration Library
```
Library: Med_Conc
Adj lib nM: 15
Target Reads (M): 100
Scaling Factor: 0.1

Expected:
- Stock vol = 0.1 / 15 * 100 = 0.667 µL
- Pre-dilute = 5x (because 0.667 < 0.795)
- Final vol = 0.667 * 5 = 3.335 µL
```

### Test Case 3: Low Concentration Library
```
Library: Low_Conc
Adj lib nM: 5
Target Reads (M): 100
Scaling Factor: 0.1

Expected:
- Stock vol = 0.1 / 5 * 100 = 2.0 µL
- Pre-dilute = 1x (because 2.0 >= 0.795)
- Final vol = 2.0 * 1 = 2.0 µL
```

### Test Case 4: Insufficient Volume
```
Library: Insuff_Vol
Adj lib nM: 10
Target Reads (M): 100
Total Volume: 1.0 µL
Scaling Factor: 0.1

Expected:
- Stock vol = 0.1 / 10 * 100 = 1.0 µL
- Pre-dilute = 5x (because 1.0 >= 0.795, wait... this needs review)
- Final vol = 1.0 * 5 = 5.0 µL
- Flag: "Insufficient volume" because 5.0 > 1.0 available
```

## Implementation Priority

1. **High Priority (Blocking):**
   - Fix volume calculation formula in `compute_pool_volumes()`
   - Add scaling factor parameter
   - Add pre-dilution logic
   - Add volume availability check

2. **Medium Priority:**
   - Update UI with scaling factor input
   - Add informational text about pre-dilution
   - Update output columns

3. **Low Priority:**
   - Add visual indicators for pre-dilution in UI
   - Add helper to suggest optimal scaling factor
   - Add batch testing with real data

## Questions for User

1. **Pre-dilution thresholds:** Confirm 0.2 µL and 0.795 µL are correct for your pipettes?
2. **Scaling factor range:** What's the typical range users adjust this to?
3. **Volume availability:** Should we block calculation or just warn when insufficient volume?
4. **Pre-dilution workflow:** Do users physically dilute samples, or is this just a flag for awareness?
5. **Edge case:** What if pre-diluted volume STILL exceeds available volume? Cascade to higher dilution?

## References

- Original spreadsheet: `data/7050I_miRNA_pool_copy.xlsx`
- Sheet: "Final Pool"
- Key cells: AA4 (scaling), AF column (stock vol), Z column (pre-dilute), AA column (final vol)
