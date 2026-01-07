# Multi-Step Pooling Workflow (Hierarchical Pooling) - Implementation Plan

## Executive Summary

Hierarchical pooling enables users to combine hundreds or thousands of libraries in a multi-tiered approach: libraries → sub-pools → master pool. This is critical for ultra-high-plex experiments where pipetting hundreds of individual libraries into a single pool is impractical.

**Use Case Example:**
- 400 libraries across 8 projects
- Step 1: Pool libraries within each project (8 sub-pools of ~50 libraries each)
- Step 2: Pool the 8 sub-pools into a master pool
- Result: Only 58 total pipetting steps instead of 400

## 1. Core Concepts

### 1.1 Pooling Hierarchy Levels

```
Level 0 (Libraries):     Individual libraries with measured concentrations
                         ↓
Level 1 (Sub-pools):     Project-based pools (e.g., ProjectA_pool, ProjectB_pool)
                         ↓
Level 2 (Master Pool):   Final sequencing pool combining all sub-pools
```

**Future extensibility:** Support arbitrary depth (e.g., Level 1 → Level 2 → Level 3 for mega-studies)

### 1.2 Key Requirements

1. **Preserve Read Balance:** If Library001 should get 2x reads of Library002, this ratio must be maintained through all pooling steps
2. **Volume Tracking:** Track both pipetting volumes and intermediate pool concentrations
3. **Practical Constraints:**
   - Min pipettable volume (e.g., 0.5 µl)
   - Max libraries per sub-pool (e.g., 96 for plate layout)
   - Available volumes at each stage
4. **Validation:** Ensure sub-pools are balanced before final pooling
5. **Export:** Generate step-by-step protocols for each pooling stage

### 1.3 Mathematical Approach

For hierarchical pooling to preserve read balance:

**Step 1 - Sub-pool creation:**
- Within each sub-pool, use weighted pooling algorithm (already implemented)
- Result: Each sub-pool has known total molarity and volume

**Step 2 - Master pool creation:**
- Treat sub-pools as "super-libraries"
- Weight each sub-pool by: (sum of target reads for all libraries in that sub-pool)
- Use same weighted pooling algorithm

**Key insight:** The existing `compute_pool_volumes()` function is already composable - it can be reused at each hierarchical level!

## 2. Data Model Extensions

### 2.1 New Data Models

#### PoolingStage (Enum)
```python
class PoolingStage(Enum):
    LIBRARY_TO_SUBPOOL = "library_to_subpool"
    SUBPOOL_TO_MASTER = "subpool_to_master"
    # Future: MASTER_TO_SUPERPOOL = "master_to_superpool"
```

#### SubPoolRecord (Pydantic Model)
```python
class SubPoolRecord(BaseModel):
    """Represents an intermediate pool created from multiple libraries."""

    subpool_id: str                    # e.g., "ProjectA_pool"
    member_libraries: list[str]        # Library names in this sub-pool
    calculated_nm: float               # Effective molarity after pooling
    total_volume_ul: float             # Total volume of this sub-pool
    target_reads_m: float              # Sum of target reads from member libraries
    creation_date: datetime

    # Optional metadata
    parent_project_id: str | None = None
    custom_grouping: dict | None = None
```

#### HierarchicalPoolingPlan (Pydantic Model)
```python
class HierarchicalPoolingPlan(BaseModel):
    """Complete multi-step pooling workflow."""

    stages: list[PoolingStageData]     # Ordered list of pooling steps
    final_pool_volume_ul: float
    total_libraries: int
    total_subpools: int

    # Metadata
    created_at: datetime
    parameters: dict                   # Global pooling parameters
```

#### PoolingStageData (Pydantic Model)
```python
class PoolingStageData(BaseModel):
    """Data for a single stage in the hierarchical workflow."""

    stage_type: PoolingStage
    stage_number: int                  # 1, 2, 3, etc.

    # Inputs to this stage
    input_entities: pd.DataFrame       # Libraries or sub-pools being pooled

    # Outputs from this stage
    output_volumes: pd.DataFrame       # Pipetting volumes for this stage
    output_pools: list[SubPoolRecord]  # Pools created by this stage

    # Parameters
    target_volume_per_pool: float
    min_volume_ul: float
    max_volume_ul: float | None
```

### 2.2 Configuration Extensions

Add to `config.py`:

```python
# Hierarchical pooling defaults
DEFAULT_SUBPOOL_VOLUME_UL = 50.0          # Target volume for intermediate pools
MAX_LIBRARIES_PER_SUBPOOL = 96            # Practical limit (e.g., 96-well plate)
MIN_SUBPOOLS_FOR_HIERARCHICAL = 5         # Below this, single-stage is fine
SUBPOOL_NAMING_PATTERN = "{project_id}_pool_{index}"

# Sub-pool concentration measurement approach
SUBPOOL_CONCENTRATION_METHOD = "calculated"  # or "measured" if user provides qPCR
```

## 3. Computation Engine Extensions

### 3.1 New Functions in `compute.py`

#### Function 1: `determine_pooling_strategy()`

```python
def determine_pooling_strategy(
    df: pd.DataFrame,
    max_libraries_per_pool: int = 96,
    min_subpools_for_hierarchical: int = 5
) -> tuple[str, list[str]]:
    """
    Decide if hierarchical pooling is needed.

    Args:
        df: DataFrame with library data
        max_libraries_per_pool: Maximum libraries per single pool
        min_subpools_for_hierarchical: Threshold for using hierarchical approach

    Returns:
        Tuple of (strategy, grouping_column_options)
        - strategy: "single_stage" or "hierarchical"
        - grouping_column_options: Suggested columns for sub-pool grouping

    Logic:
        - If total libraries <= max_libraries_per_pool → single_stage
        - If grouping by Project ID creates >= min_subpools → hierarchical with Project ID
        - Otherwise → recommend hierarchical with custom grouping
    """
```

#### Function 2: `create_subpool_definitions()`

```python
def create_subpool_definitions(
    df: pd.DataFrame,
    grouping_column: str = "Project ID",
    max_libraries_per_subpool: int = 96
) -> pd.DataFrame:
    """
    Define sub-pools based on grouping criteria.

    Args:
        df: DataFrame with library data
        grouping_column: Column to group by (e.g., "Project ID")
        max_libraries_per_subpool: Split large groups if needed

    Returns:
        DataFrame with additional "SubPool ID" column

    Example:
        Input: 150 libraries with Project ID = "ProjectA"
        Output: Same libraries but split into "ProjectA_pool_1" and "ProjectA_pool_2"
    """
```

#### Function 3: `compute_subpool_properties()`

```python
def compute_subpool_properties(
    df_libraries: pd.DataFrame,
    df_volumes: pd.DataFrame,
    subpool_id: str
) -> SubPoolRecord:
    """
    Calculate properties of a sub-pool after pooling its member libraries.

    Args:
        df_libraries: Original library data
        df_volumes: Pooling volumes for libraries in this sub-pool
        subpool_id: Identifier for this sub-pool

    Returns:
        SubPoolRecord with calculated molarity and total volume

    Logic:
        1. Sum volumes: V_total = Σ V_i
        2. Calculate total moles: n_total = Σ (C_i × V_i)
        3. Calculate sub-pool molarity: C_subpool = n_total / V_total
        4. Sum target reads: TR_subpool = Σ TR_i
    """
```

#### Function 4: `compute_hierarchical_pooling()`

```python
def compute_hierarchical_pooling(
    df: pd.DataFrame,
    grouping_column: str = "Project ID",
    subpool_volume_ul: float = 50.0,
    final_pool_volume_ul: float = 20.0,
    min_volume_ul: float = 0.5,
    max_volume_ul: float | None = None
) -> HierarchicalPoolingPlan:
    """
    Complete hierarchical pooling workflow.

    Args:
        df: Library data with all required columns
        grouping_column: How to group libraries into sub-pools
        subpool_volume_ul: Target volume for each sub-pool
        final_pool_volume_ul: Target volume for master pool
        min_volume_ul: Minimum pipettable volume
        max_volume_ul: Maximum volume per pipetting step

    Returns:
        HierarchicalPoolingPlan with complete multi-stage workflow

    Workflow:
        Stage 1: Libraries → Sub-pools
            - Group libraries by grouping_column
            - For each group, compute pooling volumes (target: subpool_volume_ul)
            - Create SubPoolRecord for each result

        Stage 2: Sub-pools → Master Pool
            - Treat SubPoolRecords as "super-libraries"
            - Use weighted pooling with target reads = sum of member library targets
            - Compute final pooling volumes (target: final_pool_volume_ul)
    """
```

### 3.2 Reusable Architecture

**Key Design Principle:** The existing `compute_pool_volumes()` function should work at any hierarchy level without modification.

Current signature:
```python
def compute_pool_volumes(
    df: pd.DataFrame,
    desired_pool_volume_ul: float = 20.0,
    min_volume_ul: float = 0.5,
    max_volume_ul: float | None = None,
    total_reads_m: float | None = None
) -> pd.DataFrame:
```

This function expects:
- `Effective nM (Use)`: Molarity column
- `Target Reads (M)`: Weight column
- `Total Volume`: Availability column

For hierarchical pooling:
- **Stage 1 (Libraries → Sub-pools):** Use library data directly (already works)
- **Stage 2 (Sub-pools → Master):** Create DataFrame from SubPoolRecords where:
  - `Effective nM (Use)` = SubPoolRecord.calculated_nm
  - `Target Reads (M)` = SubPoolRecord.target_reads_m
  - `Total Volume` = SubPoolRecord.total_volume_ul

**No changes needed to core algorithm!** Just data transformation.

## 4. UI Extensions

### 4.1 New UI Section: "Pooling Strategy"

Add a collapsible section before "Pooling Parameters":

```python
with gr.Accordion("Pooling Strategy", open=True):
    strategy_radio = gr.Radio(
        choices=[
            "Automatic (Recommended)",
            "Single-Stage Pooling",
            "Hierarchical Pooling (Multi-Step)"
        ],
        value="Automatic (Recommended)",
        label="Pooling Approach"
    )

    # Shown only if Hierarchical selected
    grouping_column_dropdown = gr.Dropdown(
        choices=["Project ID", "Custom Column"],
        value="Project ID",
        label="Group Libraries By",
        visible=False
    )

    subpool_volume = gr.Number(
        value=50.0,
        label="Sub-Pool Target Volume (µl)",
        visible=False
    )

    strategy_info = gr.Textbox(
        label="Strategy Recommendation",
        interactive=False,
        visible=True
    )
```

### 4.2 UI Workflow Changes

**Current:** Upload → Validate → Calculate → Download

**New (Hierarchical):**
1. Upload file
2. Validate data
3. **Analyze pooling strategy** (new step)
   - Display: "Your file has 400 libraries across 8 projects"
   - Recommendation: "Hierarchical pooling recommended: Create 8 sub-pools, then combine"
4. User configures strategy
5. Calculate pooling plan
6. **Display multi-stage results** (new)
   - Tab 1: "Stage 1 - Library Pooling" (8 tables, one per sub-pool)
   - Tab 2: "Stage 2 - Sub-Pool Pooling" (1 table with 8 rows)
   - Tab 3: "Master Pool Summary"
7. Download

### 4.3 Output Visualization

Add new result tabs:

```python
with gr.Tabs():
    with gr.Tab("Workflow Summary"):
        workflow_diagram = gr.Markdown()  # ASCII art or mermaid diagram

    with gr.Tab("Stage 1: Create Sub-Pools"):
        for subpool in subpools:
            with gr.Accordion(f"{subpool.name} ({len(subpool.libraries)} libraries)"):
                stage1_table = gr.Dataframe()

    with gr.Tab("Stage 2: Combine Sub-Pools"):
        stage2_table = gr.Dataframe()

    with gr.Tab("Final Pool Composition"):
        composition_table = gr.Dataframe()
        expected_reads_chart = gr.Plot()  # Bar chart of expected reads per library
```

## 5. Export Extensions

### 5.1 Multi-Sheet Excel Output

Current sheets:
- PoolingPlan_Libraries
- PoolingPlan_Projects
- Metadata

New sheets for hierarchical pooling:

**Sheet: "Workflow_Overview"**
| Stage | Input | Output | Target Volume | Libraries/Pools | Notes |
|-------|-------|--------|---------------|-----------------|-------|
| 1 | 400 libraries | 8 sub-pools | 50 µl each | 50 per sub-pool | Group by Project ID |
| 2 | 8 sub-pools | 1 master pool | 20 µl | 8 pools | Final sequencing pool |

**Sheet: "Stage1_ProjectA_Pool"** (one sheet per sub-pool)
| Library Name | Concentration (nM) | Volume to Add (µl) | ... |

**Sheet: "Stage2_MasterPool"**
| Sub-Pool ID | Concentration (nM) | Volume to Add (µl) | Expected Reads (M) | ... |

**Sheet: "SubPool_Properties"**
| Sub-Pool ID | Total Volume (µl) | Calculated nM | Member Libraries | Target Reads (M) | Creation Method |

### 5.2 Lab Protocol Export

Generate human-readable protocol:

```markdown
# Hierarchical Pooling Protocol - [Timestamp]

## Stage 1: Create Sub-Pools (8 pools)

### Sub-Pool 1: ProjectA_pool
**Target Volume:** 50 µl
**Libraries:** 52

| Step | Library | Source | Volume (µl) | Add to |
|------|---------|--------|-------------|--------|
| 1 | Lib001 | Plate1 A1 | 2.5 | ProjectA_pool tube |
| 2 | Lib002 | Plate1 A2 | 3.1 | ProjectA_pool tube |
...

**After Stage 1:**
- Label tube "ProjectA_pool"
- Measure concentration with Qubit (expected: ~15 nM)
- Store at 4°C until Stage 2

### Sub-Pool 2: ProjectB_pool
...

## Stage 2: Combine Sub-Pools into Master Pool

**Target Volume:** 20 µl
**Inputs:** 8 sub-pools from Stage 1

| Step | Sub-Pool | Volume (µl) | Add to |
|------|----------|-------------|--------|
| 1 | ProjectA_pool | 2.8 | MasterPool tube |
| 2 | ProjectB_pool | 2.5 | MasterPool tube |
...

**Final Pool:**
- Total volume: 20 µl
- Expected concentration: ~18 nM
- Ready for sequencing
```

## 6. Validation Extensions

### 6.1 New Validation Checks

Add to `validation.py`:

```python
def validate_hierarchical_pooling_feasibility(
    df: pd.DataFrame,
    grouping_column: str,
    max_libraries_per_subpool: int
) -> ValidationResult:
    """
    Check if hierarchical pooling configuration is valid.

    Checks:
    1. Grouping column exists and has values
    2. Each group has >= 1 library
    3. No group exceeds max_libraries_per_subpool after auto-splitting
    4. All libraries in a group have compatible target reads (warn if variance too high)
    5. Sub-pool volumes are achievable given library concentrations
    """
```

```python
def validate_subpool_balance(
    subpool_records: list[SubPoolRecord],
    balance_tolerance: float = 0.1
) -> ValidationResult:
    """
    Check that sub-pools are balanced for final pooling.

    Checks:
    1. All sub-pools have calculated_nm > 0
    2. Sub-pool concentrations are within reasonable range (warn if 10x difference)
    3. Expected read distribution matches user intent (within balance_tolerance)

    Returns warnings if imbalance detected, errors if catastrophic.
    """
```

### 6.2 Interactive Validation

When user enables hierarchical pooling:
- **Before calculation:** Show preview of sub-pool groupings
- **After Stage 1 calculation:** Show sub-pool summary and ask for confirmation
- **After Stage 2 calculation:** Show final balance and flag any issues

## 7. Testing Strategy

### 7.1 Unit Tests

**test_compute_hierarchical.py** (new file):

```python
def test_compute_subpool_properties():
    """Test sub-pool property calculation from member libraries."""
    # Given: 3 libraries pooled with known volumes and concentrations
    # When: compute_subpool_properties() is called
    # Then: Sub-pool molarity = weighted average, volume = sum

def test_hierarchical_preserves_balance():
    """Test that hierarchical pooling maintains read ratios."""
    # Given: 100 libraries with 2:1 target read ratio
    # When: Hierarchical pooling creates 5 sub-pools then master pool
    # Then: Final expected reads maintain 2:1 ratio

def test_hierarchical_vs_single_stage():
    """Test that hierarchical and single-stage give same final balance."""
    # Given: Same input libraries
    # When: Computed with hierarchical vs. single-stage
    # Then: Final read distribution is identical (within rounding)

def test_subpool_creation_respects_max_size():
    """Test auto-splitting of large groups."""
    # Given: 150 libraries in ProjectA, max_per_subpool = 96
    # When: create_subpool_definitions()
    # Then: Creates ProjectA_pool_1 (96) and ProjectA_pool_2 (54)
```

### 7.2 Integration Tests

**test_integration_hierarchical.py** (new file):

```python
def test_full_hierarchical_workflow():
    """Test complete multi-stage pooling from file to export."""
    # Given: 400-library test fixture
    # When: Run hierarchical pooling pipeline
    # Then:
    #   - Stage 1 creates 8 sub-pools
    #   - Stage 2 combines into master pool
    #   - Export has all required sheets
    #   - Read balance is maintained

def test_measured_vs_calculated_subpool_concentration():
    """Test using measured concentrations for sub-pools."""
    # Given: Stage 1 complete, user provides qPCR measurements for sub-pools
    # When: Use measured concentrations in Stage 2
    # Then: Stage 2 calculations use measured values, not calculated
```

### 7.3 Performance Tests

```python
def test_hierarchical_performance_1000_libraries():
    """Test that hierarchical pooling scales to large datasets."""
    # Given: 1000 libraries across 20 projects
    # When: Compute hierarchical pooling plan
    # Then: Completes in < 5 seconds
```

## 8. Implementation Phases

### Phase 1: Core Algorithm (Week 1)
- [ ] Implement `SubPoolRecord` and `HierarchicalPoolingPlan` models
- [ ] Implement `compute_subpool_properties()`
- [ ] Implement `create_subpool_definitions()`
- [ ] Implement `compute_hierarchical_pooling()`
- [ ] Write comprehensive unit tests
- [ ] Verify mathematical correctness

### Phase 2: Validation & Strategy (Week 1-2)
- [ ] Implement `determine_pooling_strategy()`
- [ ] Implement hierarchical validation functions
- [ ] Add configuration options to `config.py`
- [ ] Test edge cases (empty groups, single-library groups, etc.)

### Phase 3: UI Integration (Week 2)
- [ ] Add pooling strategy selection UI
- [ ] Add multi-stage results display
- [ ] Add workflow visualization
- [ ] Update file upload to analyze strategy automatically
- [ ] Add interactive sub-pool preview

### Phase 4: Export & Documentation (Week 2-3)
- [ ] Implement multi-sheet Excel export
- [ ] Generate human-readable lab protocols
- [ ] Add workflow diagram generation (mermaid or ASCII)
- [ ] Update user documentation
- [ ] Create example hierarchical pooling dataset

### Phase 5: Testing & Refinement (Week 3)
- [ ] Integration tests with real-world data
- [ ] Performance testing with large datasets
- [ ] User acceptance testing
- [ ] Bug fixes and polish

## 9. Future Enhancements (Beyond Initial Implementation)

### 9.1 Advanced Features
- **3+ Level Hierarchies:** Support libraries → sub-pools → super-pools → master pool
- **Plate Layout Optimization:** Auto-arrange libraries on 96-well plates for convenience
- **Dilution Recommendations:** If sub-pool concentration too high, suggest dilution
- **Barcode Conflict Detection:** Ensure no barcode collisions across sub-pools
- **Custom Grouping UI:** Allow users to manually assign libraries to sub-pools

### 9.2 Quality Control
- **Expected vs. Measured:** Compare calculated sub-pool concentrations to qPCR measurements
- **Variance Analysis:** Flag sub-pools with high variance in member library properties
- **Simulation Mode:** Preview expected results before executing

### 9.3 Automation

#### Liquid Handler Export
Generate worklist/script files for automated liquid handling platforms:

**Hamilton STAR/STARlet/Vantage:**
- `.gwl` (Generic Worklist) format
- Plate definitions with source/destination mappings
- Aspirate/dispense commands with volumes
- Tip handling and wash stations

**Tecan Freedom EVO/Fluent:**
- `.gwl` (Gemini Worklist) format
- Source and destination labware definitions
- Multi-channel pipetting optimization
- Liquid class specifications

**INTEGRA ASSIST PLUS:**
- `.csv` worklist format compatible with VIALINK software
- Support for both single-channel and 8/12/16-channel modes
- Column/row-wise pipetting patterns for plate-to-plate transfers
- Volume-optimized tip selection (10-125 µL, 125-300 µL, or 300-1250 µL ranges)
- Multi-step workflows with intermediate mixing steps
- Customizable aspiration/dispense speeds and delays
- Plate barcode tracking integration

**Example INTEGRA ASSIST PLUS Worklist Format:**
```csv
Step,Source_Plate,Source_Well,Dest_Plate,Dest_Well,Volume_uL,Tip_Type,Mix_Cycles,Comments
1,LibraryPlate1,A1,SubPoolPlate,A1,2.5,GreenTip,3,Lib001 to ProjectA_pool
2,LibraryPlate1,A2,SubPoolPlate,A1,3.1,GreenTip,3,Lib002 to ProjectA_pool
3,LibraryPlate1,A3,SubPoolPlate,A2,1.8,GreenTip,3,Lib003 to ProjectB_pool
```

**INTEGRA-Specific Features:**
- **Intelligent Tip Selection:** Auto-select tip size based on volume ranges
- **Multi-dispense Optimization:** Group transfers to same destination well
- **Plate Format Support:** 96-well, 384-well, tubes, reservoirs
- **VIALINK Integration:** Direct import into INTEGRA's control software
- **Run Summary Export:** Expected volumes, completion time estimates

**Implementation Priority:**
1. INTEGRA ASSIST PLUS (most commonly requested for NGS workflows)
2. Hamilton STAR (high-throughput labs)
3. Tecan Freedom EVO (alternative high-throughput platform)

#### LIMS Integration
- **Import library data:** Bi-directional sync with LIMS databases
- **Export pooling plans:** Push completed plans back to LIMS
- **Barcode tracking:** Link physical samples to digital records

#### Batch Processing
- **Multiple hierarchical pooling projects:** Run several experiments in parallel
- **Queue management:** Schedule and prioritize automation runs
- **Result aggregation:** Combine outputs from multiple pooling batches

## 10. Technical Considerations

### 10.1 Backward Compatibility
- Existing single-stage pooling must continue to work unchanged
- Default behavior: Auto-detect and recommend strategy, but allow manual override
- Existing tests must all pass without modification

### 10.2 Error Handling
- Graceful degradation: If hierarchical pooling fails validation, suggest single-stage
- Clear error messages: "Sub-pool ProjectA has only 1 library - consider merging with ProjectB"
- Recovery suggestions: "Reduce subpool_volume_ul to 30 µl to meet minimum volume constraints"

### 10.3 Performance Optimization
- Cache sub-pool calculations to avoid recomputation
- Parallel processing for independent sub-pool calculations
- Incremental validation (don't re-validate unchanged data)

## 11. Success Metrics

- [ ] Successfully pools 500+ library dataset in < 10 seconds
- [ ] Read balance error < 1% compared to single-stage pooling
- [ ] UI workflow intuitive for users (< 3 clicks to configure)
- [ ] Export format accepted by 95% of users (survey)
- [ ] Zero mathematical errors in production use

## 12. Open Questions for User Feedback

1. **Sub-pool measurement:** Should we assume calculated concentrations or require users to measure?
2. **Automatic vs. Manual:** How much control do users want over sub-pool groupings?
3. **Plate layout:** Do users want visual plate layout tools, or is CSV export sufficient?
4. **Dilution handling:** Should the tool suggest dilutions or just flag issues?
5. **Export format:** What liquid handler formats are most common in your lab?

---

## Summary

Hierarchical pooling extends the existing pooling calculator architecture with minimal changes to core algorithms. The key insight is that `compute_pool_volumes()` is already composable - we just need to:

1. Add data models for sub-pools
2. Add a function to calculate sub-pool properties
3. Apply the existing algorithm twice (libraries → sub-pools, sub-pools → master)
4. Extend UI to show multi-stage results
5. Export multi-stage protocols

**Estimated Effort:** 3 weeks for full implementation
**Risk Level:** Low (reuses proven algorithms)
**User Impact:** High (enables ultra-high-plex experiments)
