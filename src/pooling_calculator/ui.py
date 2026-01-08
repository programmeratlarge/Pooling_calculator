"""
Gradio UI for Pooling Calculator

This module provides a web-based user interface using Gradio for the NGS library pooling calculator.
"""

import io
from pathlib import Path

import gradio as gr
import pandas as pd

from pooling_calculator import __version__
from pooling_calculator.io import (
    load_spreadsheet,
    normalize_dataframe_columns,
    export_results_to_excel,
)
from pooling_calculator.validation import run_all_validations
from pooling_calculator.compute import (
    compute_effective_molarity,
    compute_pool_volumes,
    summarize_by_project,
)
from pooling_calculator.hierarchical import (
    determine_pooling_strategy,
    compute_hierarchical_pooling,
)
from pooling_calculator.config import (
    MIN_TOTAL_VOLUME_UL,
    WARN_LOW_TOTAL_VOLUME_UL,
)


def analyze_file(
    file_obj,
) -> tuple[str, pd.DataFrame | None, str, list[str], dict]:
    """
    Analyze uploaded file and recommend pooling strategy.

    Args:
        file_obj: Uploaded file object from Gradio

    Returns:
        Tuple of (status_message, validated_df, recommended_strategy, grouping_options, analysis)
    """
    if file_obj is None:
        return "Please upload a file first.", None, "single_stage", [], {}

    try:
        # Load spreadsheet
        df = load_spreadsheet(file_obj.name)
        df_normalized = normalize_dataframe_columns(df)

        # Validate
        validation_result = run_all_validations(df_normalized)

        if not validation_result.is_valid:
            error_msg = "❌ **VALIDATION FAILED**\n\n"
            error_msg += f"**Errors ({len(validation_result.errors)}):**\n"
            for err in validation_result.errors:
                error_msg += f"- {err}\n"
            if validation_result.warnings:
                error_msg += f"\n**Warnings ({len(validation_result.warnings)}):**\n"
                for warn in validation_result.warnings:
                    error_msg += f"- {warn}\n"
            return error_msg, None, "single_stage", [], {}

        # Build status message with warnings
        status_msg = f"✅ **VALIDATION PASSED**\n\n"
        status_msg += f"- Libraries loaded: {len(df_normalized)}\n"
        status_msg += f"- Projects: {df_normalized['Project ID'].nunique()}\n"

        if validation_result.warnings:
            status_msg += f"\n⚠️ **Warnings ({len(validation_result.warnings)}):**\n"
            for warn in validation_result.warnings:
                status_msg += f"- {warn}\n"

        # Analyze pooling strategy
        strategy, grouping_options, analysis = determine_pooling_strategy(df_normalized)

        status_msg += f"\n\n## 📊 Pooling Strategy Analysis\n\n"
        status_msg += f"**Total Libraries:** {analysis['total_libraries']}\n\n"

        if strategy == "hierarchical":
            status_msg += f"**Recommendation:** ✨ **Hierarchical Pooling** (Multi-stage)\n\n"
            status_msg += f"**Reason:** {analysis['reason']}\n\n"
            if grouping_options:
                status_msg += f"**Suggested Grouping:** {', '.join(grouping_options)}\n"
                for col in grouping_options:
                    num_groups = analysis.get(f"{col}_num_groups", 0)
                    status_msg += f"  - {col}: {num_groups} sub-pools\n"
            else:
                status_msg += f"⚠️ {analysis.get('warning', 'Consider adding grouping column')}\n"
        else:
            status_msg += f"**Recommendation:** ✅ **Single-Stage Pooling**\n\n"
            status_msg += f"**Reason:** {analysis['reason']}\n\n"

        status_msg += f"\n📋 Configure parameters below and click **Calculate** to proceed."

        return status_msg, df_normalized, strategy, grouping_options, analysis

    except Exception as e:
        error_msg = f"❌ **ERROR**: {str(e)}\n\n"
        error_msg += "Please check your input file format and try again."
        import traceback
        error_msg += f"\n\nDetails:\n{traceback.format_exc()}"
        return error_msg, None, "single_stage", [], {}


def process_upload(
    file_obj,
    strategy_choice: str,
    grouping_column: str,
    scaling_factor: float,
    min_volume: float,
    max_volume: float | None,
    total_reads: float | None,
    validated_df: pd.DataFrame | None,
) -> tuple[str, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, bytes | None]:
    """
    Process uploaded file and compute pooling plan based on selected strategy.

    Args:
        file_obj: Uploaded file object from Gradio
        strategy_choice: "single_stage" or "hierarchical"
        grouping_column: Column to group by for hierarchical pooling
        scaling_factor: Volume calculation scaling factor (controls pool volume)
        min_volume: Minimum pipettable volume in µl
        max_volume: Maximum volume per library (optional)
        total_reads: Total sequencing reads in millions (optional)
        validated_df: Pre-validated DataFrame from analyze_file()

    Returns:
        Tuple of (status_message, library_df, project_df, stage1_df, stage2_df, excel_bytes)
    """
    if file_obj is None or validated_df is None:
        return "Please upload a file and analyze it first.", None, None, None, None, None

    try:
        df_normalized = validated_df.copy()

        # Compute molarity
        df_with_molarity = compute_effective_molarity(df_normalized)

        # Validate pool parameters
        if scaling_factor <= 0:
            return "❌ Error: Scaling factor must be > 0", None, None, None, None, None
        if min_volume < 0:
            return "❌ Error: Minimum volume must be >= 0", None, None, None, None, None
        if max_volume is not None and max_volume <= 0:
            return "❌ Error: Maximum volume must be > 0", None, None, None, None, None

        max_vol = max_volume if max_volume and max_volume > 0 else None
        total_r = total_reads if total_reads and total_reads > 0 else None

        # Branch: Single-stage or Hierarchical
        if strategy_choice == "hierarchical":
            # ========== HIERARCHICAL POOLING ==========
            try:
                plan = compute_hierarchical_pooling(
                    df_with_molarity,
                    grouping_column=grouping_column,
                    scaling_factor=scaling_factor,
                    final_pool_volume_ul=20.0,  # Could be a parameter
                    min_volume_ul=min_volume,
                    max_volume_ul=max_vol,
                    total_reads_m=total_r,
                )

                # Extract Stage 1 and Stage 2 DataFrames
                stage1_df = pd.DataFrame(plan.stages[0].volumes_df_json)
                stage2_df = pd.DataFrame(plan.stages[1].volumes_df_json)

                # Build status message
                status_msg = "✅ **HIERARCHICAL POOLING COMPLETE**\n\n"
                status_msg += f"**Strategy:** Multi-stage pooling\n"
                status_msg += f"**Grouping:** {plan.grouping_method}\n\n"

                status_msg += f"### Stage 1: {plan.stages[0].description}\n"
                status_msg += f"- Input: {plan.stages[0].input_count} libraries\n"
                status_msg += f"- Output: {plan.stages[0].output_count} sub-pools\n"
                status_msg += f"- Pipetting steps: {plan.stages[0].total_pipetting_steps}\n\n"

                status_msg += f"### Stage 2: {plan.stages[1].description}\n"
                status_msg += f"- Input: {plan.stages[1].input_count} sub-pools\n"
                status_msg += f"- Output: {plan.stages[1].output_count} master pool\n"
                status_msg += f"- Pipetting steps: {plan.stages[1].total_pipetting_steps}\n\n"

                status_msg += f"**Total pipetting steps:** {plan.total_pipetting_steps}\n"
                status_msg += f"**Final pool volume:** {plan.final_pool_volume_ul} µl\n\n"

                status_msg += "✅ Ready to download hierarchical pooling plan"

                # Format Stage 1 for display
                display_cols_stage1 = [
                    "Library Name",
                    "SubPool ID",
                    "Calculated nM",
                    "Effective nM (Use)",
                    "Stock Volume (µl)",
                    "Final Volume (µl)",
                    "Pool Fraction",
                ]
                stage1_display = stage1_df[
                    [col for col in display_cols_stage1 if col in stage1_df.columns]
                ].copy()

                # Round numeric columns
                for col in stage1_display.select_dtypes(include=['float64', 'float32']).columns:
                    stage1_display[col] = stage1_display[col].round(4)

                # Format Stage 2 for display
                display_cols_stage2 = [
                    "Library Name",  # This is subpool ID in stage 2
                    "Calculated nM",
                    "Effective nM (Use)",
                    "Final Volume (µl)",
                    "Pool Fraction",
                ]
                stage2_display = stage2_df[
                    [col for col in display_cols_stage2 if col in stage2_df.columns]
                ].copy()

                # Round numeric columns
                for col in stage2_display.select_dtypes(include=['float64', 'float32']).columns:
                    stage2_display[col] = stage2_display[col].round(4)

                # No project summary for hierarchical (sub-pools replace projects)
                # TODO: Export hierarchical results to Excel
                excel_bytes = None

                return status_msg, stage1_display, None, stage1_display, stage2_display, excel_bytes

            except Exception as e:
                error_msg = f"❌ **HIERARCHICAL POOLING ERROR**: {str(e)}\n\n"
                error_msg += "Falling back to single-stage pooling."
                import traceback
                error_msg += f"\n\nDetails:\n{traceback.format_exc()}"
                # Fall through to single-stage

        # ========== SINGLE-STAGE POOLING ==========
        status_msg = "✅ **SINGLE-STAGE POOLING COMPLETE**\n\n"

        df_with_volumes = compute_pool_volumes(
            df_with_molarity,
            scaling_factor=scaling_factor,
            min_volume_ul=min_volume,
            max_volume_ul=max_vol,
            total_reads_m=total_r,
        )

        # Check for flags
        flagged = df_with_volumes[df_with_volumes["Flags"] != ""]
        if len(flagged) > 0:
            status_msg += f"\n⚠️ **{len(flagged)} libraries have warnings:**\n"
            for _, row in flagged.head(5).iterrows():  # Show first 5
                status_msg += f"- {row['Library Name']}: {row['Flags']}\n"
            if len(flagged) > 5:
                status_msg += f"- ... and {len(flagged) - 5} more\n"

        # Compute project summary
        df_projects = summarize_by_project(df_with_volumes)

        # Format dataframes for display
        display_cols = [
            "Library Name",
            "Project ID",
            "Final ng/ul",
            "Adjusted peak size",
            "Target Reads (M)",
            "Calculated nM",
            "Effective nM (Use)",
            "Stock Volume (µl)",
            "Pre-Dilute Factor",
            "Final Volume (µl)",
            "Pool Fraction",
        ]

        if "Expected Reads (M)" in df_with_volumes.columns:
            display_cols.append("Expected Reads (M)")

        display_cols.append("Flags")

        df_display = df_with_volumes[display_cols].copy()

        # Round numeric columns for display
        df_display["Final ng/ul"] = df_display["Final ng/ul"].round(3)
        df_display["Calculated nM"] = df_display["Calculated nM"].round(3)
        df_display["Effective nM (Use)"] = df_display["Effective nM (Use)"].round(3)
        df_display["Stock Volume (µl)"] = df_display["Stock Volume (µl)"].round(4)
        df_display["Final Volume (µl)"] = df_display["Final Volume (µl)"].round(4)
        df_display["Pool Fraction"] = df_display["Pool Fraction"].round(4)

        if "Expected Reads (M)" in df_display.columns:
            df_display["Expected Reads (M)"] = df_display["Expected Reads (M)"].round(2)

        # Format project summary
        df_projects_display = df_projects.copy()
        df_projects_display["Total Volume (µl)"] = df_projects_display["Total Volume (µl)"].round(4)
        df_projects_display["Pool Fraction"] = df_projects_display["Pool Fraction"].round(4)

        if "Expected Reads (M)" in df_projects_display.columns:
            df_projects_display["Expected Reads (M)"] = df_projects_display["Expected Reads (M)"].round(2)

        # Export to Excel
        excel_bytes = export_results_to_excel(
            library_df=df_with_volumes,
            project_df=df_projects,
            pooling_params={
                "Version": __version__,
                "Input File": Path(file_obj.name).name,
                "Scaling Factor": scaling_factor,
                "Min Volume (µl)": min_volume,
                "Max Volume (µl)": max_vol if max_vol else "N/A",
                "Total Reads (M)": total_r if total_r else "N/A",
            },
        )

        status_msg += f"\n✅ **Pooling plan computed successfully!**\n"
        status_msg += f"- Total volume to pipette: {df_with_volumes['Final Volume (µl)'].sum():.3f} µl\n"

        # Count libraries requiring pre-dilution
        pre_dilute_count = len(df_with_volumes[df_with_volumes["Pre-Dilute Factor"] > 1])
        if pre_dilute_count > 0:
            status_msg += f"- {pre_dilute_count} libraries require pre-dilution\n"

        status_msg += f"- Ready to download Excel file\n"

        return status_msg, df_display, df_projects_display, None, None, excel_bytes

    except Exception as e:
        error_msg = f"❌ **ERROR**: {str(e)}\n\n"
        error_msg += "Please check your input file format and try again."
        import traceback
        error_msg += f"\n\nDetails:\n{traceback.format_exc()}"
        return error_msg, None, None, None, None, None


def build_app() -> gr.Blocks:
    """
    Build and return the Gradio interface.

    Returns:
        Configured Gradio Blocks interface
    """
    # Custom CSS with Tailwind CDN
    custom_css = """
    <style>
        /* Import Tailwind CSS */
        @import url('https://cdn.jsdelivr.net/npm/tailwindcss@3.4.1/base.min.css');

        /* Custom styling for the app */
        .gradio-container {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
        }

        /* Header styling */
        .gradio-container h1 {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        /* Section headers */
        .gradio-container h2 {
            color: #4a5568;
            font-weight: 600;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 0.5rem;
            margin-bottom: 1rem;
        }

        /* Card-like containers */
        .gradio-container .block {
            background: white;
            border-radius: 0.75rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }

        /* Input fields */
        .gradio-container input[type="number"],
        .gradio-container input[type="text"] {
            border: 1px solid #cbd5e0;
            border-radius: 0.5rem;
            transition: all 0.2s;
        }

        .gradio-container input[type="number"]:focus,
        .gradio-container input[type="text"]:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        /* Buttons */
        .gradio-container button {
            border-radius: 0.5rem;
            font-weight: 500;
            transition: all 0.2s;
        }

        .gradio-container button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        /* Primary button */
        .gradio-container .primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }

        /* Status section */
        .status-section {
            background: linear-gradient(135deg, #f6f8fc 0%, #eef2f7 100%);
            border-radius: 0.75rem;
            padding: 1.5rem;
            border-left: 4px solid #667eea;
        }

        /* Tables */
        .gradio-container .dataframe {
            border-radius: 0.5rem;
            overflow: hidden;
        }

        .gradio-container .dataframe thead {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .gradio-container .dataframe tbody tr:hover {
            background-color: #f7fafc;
        }

        /* Tabs */
        .gradio-container .tab-nav button {
            border-radius: 0.5rem 0.5rem 0 0;
            font-weight: 500;
        }

        .gradio-container .tab-nav button.selected {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        /* File upload area */
        .gradio-container .upload-container {
            border: 2px dashed #cbd5e0;
            border-radius: 0.75rem;
            transition: all 0.2s;
        }

        .gradio-container .upload-container:hover {
            border-color: #667eea;
            background-color: #f7fafc;
        }

        /* Info/warning badges */
        .info-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
            background: #e6f7ff;
            color: #0366d6;
            margin-right: 0.5rem;
        }

        .warning-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
            background: #fff3cd;
            color: #856404;
            margin-right: 0.5rem;
        }

        .success-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
            background: #d4edda;
            color: #155724;
            margin-right: 0.5rem;
        }
    </style>
    """

    with gr.Blocks(title="Pooling Calculator", css=custom_css) as app:
        # Inject custom CSS as HTML
        gr.HTML(custom_css)

        gr.Markdown(
            f"""
            # 🧬 NGS Library Pooling Calculator
            **Version {__version__}**

            Calculate precise pipetting volumes for equimolar or weighted NGS library pooling.
            """
        )

        # Top Row: Input Section (File Upload + Strategy Analysis)
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 📁 Input")

                file_upload = gr.File(
                    label="Upload Excel/CSV File",
                    file_types=[".xlsx", ".csv"],
                    type="filepath",
                )

                analyze_btn = gr.Button(
                    "🔍 Analyze File & Recommend Strategy",
                    variant="primary",
                    size="lg",
                )

            with gr.Column(scale=1):
                gr.Markdown("## 🎯 Pooling Strategy")

                strategy_radio = gr.Radio(
                    choices=["single_stage", "hierarchical"],
                    value="single_stage",
                    label="Select Pooling Strategy",
                    info="Choose single-stage (all libraries at once) or hierarchical (libraries → sub-pools → master)",
                )

                grouping_dropdown = gr.Dropdown(
                    choices=["Project ID"],
                    value="Project ID",
                    label="Grouping Column (for Hierarchical)",
                    visible=False,
                    info="Column to group libraries into sub-pools",
                )

        # Second Row: Global Parameters
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## ⚙️ Global Parameters")

                scaling_factor = gr.Number(
                    label="Scaling Factor",
                    value=0.1,
                    minimum=0.001,
                    maximum=10.0,
                    step=0.01,
                    info="Controls volume calculation (lower = smaller volumes, higher = larger volumes)",
                )

                gr.Markdown(
                    """
                    <details>
                    <summary><small>ℹ️ About Scaling Factor & Pre-dilution</small></summary>

                    **Scaling Factor** adjusts the volume calculation formula to achieve your desired pool characteristics.

                    **Pre-dilution** is automatically calculated when volumes are too small to pipette accurately:
                    - If calculated volume < **0.2 µL**: Recommends **10x dilution**
                    - If calculated volume < **0.795 µL**: Recommends **5x dilution**
                    - Otherwise: No dilution needed

                    *Pre-dilution values are informational - samples can be diluted before pooling if needed.*
                    </details>
                    """
                )

                desired_volume = gr.Number(
                    label="Desired Total Pool Volume (µl)",
                    value=20.0,
                    minimum=0.001,
                    step=0.1,
                    info="Target volume for the final pooled library",
                )

                min_volume = gr.Number(
                    label="Minimum Pipettable Volume (µl)",
                    value=0.5,
                    minimum=0,
                    step=0.01,
                    info="Smallest volume your pipette can accurately dispense",
                )

                max_volume = gr.Number(
                    label="Maximum Volume per Library (µl) [Optional]",
                    value=None,
                    minimum=0,
                    step=0.1,
                    info="Leave empty for no maximum constraint",
                )

                total_reads = gr.Number(
                    label="Total Sequencing Reads (M) [Optional]",
                    value=None,
                    minimum=0,
                    step=1,
                    info="Expected total reads for the sequencing run (for reporting)",
                )

            with gr.Column(scale=1):
                gr.Markdown("## 🔧 Actions")

                calculate_btn = gr.Button(
                    "🧮 Calculate Pooling Plan",
                    variant="primary",
                    size="lg",
                    interactive=False,
                )

        # Middle Row: Status and Results
        with gr.Row():
            with gr.Column():
                gr.Markdown("## 📊 Status & Validation Results")

                status_output = gr.Markdown(
                    value="Upload a file and click 'Calculate Pooling Plan' to begin.",
                    label="Status",
                )

                download_btn = gr.DownloadButton(
                    label="📥 Download Pooling Plan (Excel)",
                    variant="secondary",
                    size="lg",
                    visible=False,
                )

        # Bottom Row: Data Tables (Full Width)
        with gr.Row():
            with gr.Column():
                with gr.Tabs():
                    with gr.Tab("📋 Library-Level Results"):
                        library_table = gr.DataFrame(
                            label="Pooling Plan per Library (Single-Stage) or Stage 1 (Hierarchical)",
                            wrap=True,
                        )

                    with gr.Tab("📦 Project Summary"):
                        project_table = gr.DataFrame(
                            label="Aggregated by Project (Single-Stage Only)",
                            wrap=True,
                        )

                    with gr.Tab("🔸 Stage 1: Libraries → Sub-Pools"):
                        stage1_table = gr.DataFrame(
                            label="Stage 1 Pooling Volumes (Hierarchical)",
                            wrap=True,
                            visible=False,
                        )

                    with gr.Tab("🔹 Stage 2: Sub-Pools → Master"):
                        stage2_table = gr.DataFrame(
                            label="Stage 2 Pooling Volumes (Hierarchical)",
                            wrap=True,
                            visible=False,
                        )

        # Hidden states
        excel_state = gr.State(value=None)
        validated_df_state = gr.State(value=None)
        recommended_strategy_state = gr.State(value="single_stage")
        grouping_options_state = gr.State(value=[])
        analysis_state = gr.State(value={})

        # Wire up the analyze button
        def analyze_wrapper(file_obj):
            status, df, strategy, grouping_opts, analysis = analyze_file(file_obj)

            # Enable calculate button and update strategy selection
            show_grouping = strategy == "hierarchical" and len(grouping_opts) > 0

            return (
                status,
                df,
                strategy,
                grouping_opts,
                analysis,
                gr.update(interactive=True),  # Enable calculate button
                gr.update(value=strategy),  # Update strategy radio
                gr.update(choices=grouping_opts if grouping_opts else ["Project ID"], visible=show_grouping),  # Update grouping dropdown
            )

        analyze_btn.click(
            fn=analyze_wrapper,
            inputs=[file_upload],
            outputs=[
                status_output,
                validated_df_state,
                recommended_strategy_state,
                grouping_options_state,
                analysis_state,
                calculate_btn,
                strategy_radio,
                grouping_dropdown,
            ],
        )

        # Show/hide grouping dropdown based on strategy selection
        def update_grouping_visibility(strategy):
            return gr.update(visible=(strategy == "hierarchical"))

        strategy_radio.change(
            fn=update_grouping_visibility,
            inputs=[strategy_radio],
            outputs=[grouping_dropdown],
        )

        # Wire up the calculate button
        def calculate_wrapper(
            file_obj,
            strategy,
            grouping,
            scaling,
            min_vol,
            max_vol,
            total_r,
            validated_df,
        ):
            status, lib_df, proj_df, stage1_df, stage2_df, excel_bytes = process_upload(
                file_obj,
                strategy,
                grouping,
                scaling,
                min_vol,
                max_vol,
                total_r,
                validated_df,
            )

            # Show download button if successful
            show_download = excel_bytes is not None

            # Show hierarchical tabs if hierarchical strategy
            show_hierarchical = strategy == "hierarchical" and stage1_df is not None

            return (
                status,
                lib_df if lib_df is not None else gr.update(),
                proj_df if proj_df is not None else gr.update(),
                stage1_df if stage1_df is not None else gr.update(),
                stage2_df if stage2_df is not None else gr.update(),
                excel_bytes,
                gr.update(visible=show_download),
            )

        calculate_btn.click(
            fn=calculate_wrapper,
            inputs=[
                file_upload,
                strategy_radio,
                grouping_dropdown,
                scaling_factor,
                min_volume,
                max_volume,
                total_reads,
                validated_df_state,
            ],
            outputs=[
                status_output,
                library_table,
                project_table,
                stage1_table,
                stage2_table,
                excel_state,
                download_btn,
            ],
        )

        # Wire up download button
        def prepare_download(excel_bytes):
            if excel_bytes is None:
                return None

            # Write bytes to a temporary file
            import tempfile
            from datetime import datetime

            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pooling_plan_{timestamp}.xlsx"

            # Create temp file
            temp_dir = Path(tempfile.gettempdir())
            temp_path = temp_dir / filename

            # Write bytes to file
            with open(temp_path, "wb") as f:
                f.write(excel_bytes)

            return str(temp_path)

        download_btn.click(
            fn=prepare_download,
            inputs=[excel_state],
            outputs=download_btn,
        )

        # Footer
        gr.Markdown(
            """
            ---
            ### 📖 Quick Start Guide

            1. **Prepare your input file** (Excel or CSV) with these required columns:
               - `Project ID`, `Library Name`, `Final ng/ul`, `Total Volume`, `Barcodes`,
               - `Adjusted peak size`, `Target Reads (M)`
               - Optional: `Empirical Library nM`

            2. **Upload your file** using the file picker above

            3. **Set parameters**:
               - Desired pool volume: Total volume you want to create
               - Min volume: Minimum your pipette can dispense accurately
               - Max volume: Optional constraint on individual library volumes
               - Total reads: Optional, for calculating expected read distribution

            4. **Click "Calculate Pooling Plan"** and review the results

            5. **Download the Excel file** containing your complete pooling protocol

            ---
            **Need help?** Check the [documentation](https://github.com/your-repo/pooling-calculator) or [report an issue](https://github.com/your-repo/pooling-calculator/issues).
            """
        )

    return app


def main():
    """Main entry point to launch the Gradio app."""
    import os

    app = build_app()

    # Use environment variables for Docker compatibility
    # When running in Docker, set GRADIO_SERVER_NAME=0.0.0.0
    server_name = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
    server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))

    # Apply custom CSS and theme in launch (Gradio 6.0+)
    app.launch(
        server_name=server_name,
        server_port=server_port,
        share=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
