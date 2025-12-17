![checkMyIndex](./header_image.png)

# Pooling calculator

Next-Generation Sequencing (NGS) library pooling utility that calculates precise pipetting volumes to achieve equimolar (or weighted) pooling across samples. The calculator takes per-library concentration and fragment length data and computes volumes needed so each library contributes the desired number of molecules to the final sequencing pool.

The project focuses on advanced sub-pool management, allowing users to combine pre-pooled sample groups while preserving equal representation across all underlying samples. This is critical for high-plex experiments where dozens or hundreds of libraries need balanced read depth.

## Live App

You can run the pooling calculator here:

👉 **[pooling_calculator.com](https://pooling_calculator.com)**

---

## What This App Does

This repository contains the code and configuration for the pooling calculator, which:

Features (Coming Soon)
✅ Molarity conversion (ng/µl → nM)
🔄 Weighted pooling calculations
🔄 Sub-pool management by project
🔄 Excel input/output
🔄 Comprehensive validation

Technology Stack:
🎯 Python 3.11+
🎯 Gradio for UI
🎯 Pandas for data processing
🎯 Pydantic for validation

---

## Update History

| Version | Date       | Description                                                       |
|--------:|------------|-------------------------------------------------------------------|
| v0.1.0  | 2025-12-12 | Initial commit.                                                   |
