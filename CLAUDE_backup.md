# Pooling calculator - Calculate liquid volumes for pool, so that we have an equal number of molecules for each library in the pool

## Project Overview

**Pooling calculator** is a utility that helps design Next-Generation Sequencing (NGS) library pools so that each library contributes the desired number of molecules to a shared sequencing run. In practice, it takes per-library concentration and size information and converts that into precise pipetting volumes, ensuring that the final pool is equimolar (or otherwise “weighted” according to user-defined targets) across all samples. Tools of this type are widely used when preparing Illumina libraries, where the goal is to build a mixed pool that has the correct overall molarity and volume for instrument loading and that yields balanced read depth per sample.

Conceptually, the calculator automates a set of routine but error-prone dilution and mixing calculations. For each input library, a user typically provides: (1) a measured concentration (for example in ng/µl from Qubit or similar), (2) an average fragment length (from a Bioanalyzer or Fragment Analyzer trace), and sometimes (3) a directly measured molarity from qPCR or another assay. The calculator converts mass concentration into molar concentration using the fragment length, then determines how much volume of each library must be taken so that all libraries contribute the same number of molecules (equimolar pooling) or a specified proportion of the total reads. Vendor tools such as Illumina’s Pooling Calculator and similar NGS equimolar pooling calculators follow this pattern to standardize library normalization and pooling.

In a typical workflow, libraries first undergo quantification and quality control, then are normalized—either physically in the lab or virtually by the calculator—to a common target concentration (for example, 2–4 nM per library for many Illumina platforms). The pooling calculator then works out how to combine equal or unequal volumes of these normalized libraries to reach a user-specified final pool molarity and total volume, taking into account whether all libraries start at the same concentration or at different concentrations. This avoids hand-calculating serial dilutions and back-of-the-envelope volume splits, while enforcing good practices such as minimum pipet volumes and intermediate dilutions when stocks are very concentrated.

We need to build a more advanced pooling calculator that can operate on higher-level structures such as sub-pools. For example, we need an equimolar pooling tool that can   pre-pooled multiple groups of samples (“sub-pools”), each with its own concentration, volume, and sample count, and then compute: (1) the volume to draw from each sub-pool, (2) the fraction of each sub-pool that will be consumed, and (3) the resulting per-sample molar contribution in the final combined pool. This is especially useful in high-plex experiments where dozens or hundreds of libraries have already been normalized and pre-combined, and the user now needs to merge them into a single pool for sequencing while preserving equal representation across all underlying samples.

Finally, pooling calculators often provide guardrails and convenience features that make the process reproducible and auditable. These can include: unit conversions (ng/µl ↔ nM), checks for over- or under-dilution relative to instrument loading guidelines, calculation of optional spike-ins such as PhiX, and exportable tables that can feed directly into liquid-handling robots or lab protocols. By centralizing the logic of library normalization and pooling, a pooling calculator reduces manual arithmetic, minimizes variability between runs and operators, and helps ensure that sequencing reads are distributed across samples in a way that matches the experimental design.

### What the User Will Build

The user is a programmer in a biology lab. You are working with the user to help them build the pooling calculator successfully. The user is working in Cursor (the VS Code fork), on a Windows PC. All python code is run with uv and there are uv projects in every directory that needs it. The user is familiar with uv, and docker.

The user will deploy a complete app featuring:
- **Input spreadsheet**: Contains columns for "Project ID", "Library Name", 
xxx

---

## Directory Structure

```
Pooling_calculator/
├── images/            
└── data/             
    └── example_pool.xlsx       
```

---

## IMPORTANT: Working with users - approach

Users are on Windows PC. Always use uv for ALL python code. It is not a problem to have a uv project in a subdirectory of another uv project, although uv may show a warning.

Always do `uv add package` and `uv run module.py`, but NEVER `pip install xxx` and NEVER `python -c "code"` or `python -m module.py` or `python script.py`.
It is VERY IMPORTANT that you do not use the python command outside a uv project.
Try to lean away from shell scripts or Powershell scripts as they are platform dependent. Heavily favor writing python scripts (via uv) and managing files in the Cursor File Explorer, as this will be clear for all users.

## Working with Users: Core Principles

### Before starting, always read project plan for the full background

### 1. **Always Establish Context First**

When a user asks for help:
1. **Ask what they're trying to accomplish** - Understand the goal before diving into code
2. **Ask what error or behavior they're seeing** - Get the actual error message, not their interpretation

### 2. **Diagnose Before Fixing** ⚠️ MOST IMPORTANT

**DO NOT jump to conclusions and write lots of code before the problem is truly understood.**

Common mistakes to avoid:
- Writing defensive code with `isinstance()` checks before understanding the root cause
- Adding try/except blocks that hide the real error
- Creating workarounds that mask the actual problem
- Making multiple changes at once (makes debugging impossible)

**Instead, follow this process:**
1. **Reproduce the issue** - Ask for exact error messages, logs, commands
2. **Identify root cause** - Use error traces
3. **Verify understanding** - Explain what you think is happening and confirm with user
4. **Propose minimal fix** - Change one thing at a time
5. **Test and verify** - Confirm the fix works before moving on

### 3. **Common Root Causes (Check These First)**

Before writing any code, check these common issues:

**Docker Desktop Not Running** (Most common with `package_docker.py`)
- The script will fail with a generic uv warning about nested projects
- The real issue is Docker isn't running
- Users often get distracted by the uv warning (this was recently fixed in the script)
- **Always ask**: "Is Docker Desktop running?"

### 4. **Help Users Help Themselves**

Encourage users to:
- Read error messages carefully (especially logs)
- Test incrementally (don't deploy everything at once)

---

## Common Issues and Troubleshooting

### Issue 1: `package_docker.py` Fails

**Symptoms**: Script fails with uv warning about nested projects and perhaps an error message

**Root Cause (common)**: Docker Desktop is not running or a Docker mounts denied issue

**Diagnosis**:
1. Ask: "Is Docker Desktop running?"
2. Check: Can they run `docker ps` successfully?
3. Recent fix: The script now gives better error messages, but older versions were misleading

**Solution**: Start Docker Desktop, wait for it to fully initialize, then retry

**If the issue is a Mounts Denied error**: It fails to mount the /tmp directory into Docker as it doesn't have access to it. Going to Docker Desktop app, and adding the directory mentioned in the error to the shared paths (Settings -> Resources -> File Sharing) solved the problem for a user.

**Not the solution**: Changing uv project configurations (this is a red herring)

---

### For Claude Code (AI Assistant)

When helping users:

0. **Prepare** - Read code base and project plan to be fully briefed.
1. **Establish context** - What's the goal?
2. **Get error details** - Actual messages, logs, console output
3. **Diagnose first** - Don't write code before understanding the problem
4. **Think incrementally** - One change at a time
5. **Verify understanding** - Explain what you think is wrong before fixing
6. **Keep it simple** - Avoid over-engineering solutions

**Remember**: Users are learning. The goal is to help them understand what went wrong and how to fix it, not just to make the error go away.

---

*This guide was created to help AI assistants (like Claude Code) effectively support users through the pooling calculator project. Last updated: December 2025*
