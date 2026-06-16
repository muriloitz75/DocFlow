# Gazette PDF Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproduce the source PDF's editorial index while keeping each detected norm directly extractable.

**Architecture:** Parse captured index text into backend-owned structured rows and return them with the existing norm list. Render those rows in the single-page frontend with semantic levels, dotted leaders, page numbers, and clickable norm rows; fall back to generated rows when source parsing yields no usable entries.

**Tech Stack:** Python, Flask, unittest, vanilla JavaScript, CSS.

---

### Task 1: Parse source index rows

**Files:**
- Modify: `app.py`
- Test: `test_app.py`

- [ ] Add a failing unit test using representative blue/red/green hierarchy lines and assert text, page, level, role, and linked norm ID.
- [ ] Run `.venv\Scripts\python.exe -m unittest test_app.WebInterfaceTestCase.test_parse_gazette_index_rows -v` and confirm the parser is missing.
- [ ] Implement `parse_gazette_index_rows(index_text, norms)` with normalization, dotted leader/page extraction, hierarchy inference, and norm matching.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Expose structured rows through the API

**Files:**
- Modify: `app.py`
- Test: `test_app.py`

- [ ] Extend the endpoint test to assert `index_entries` and the source index text contract.
- [ ] Run the focused endpoint test and confirm it fails on the missing field.
- [ ] Store structured entries in the gazette cache and return them from `/api/gazette/index`.
- [ ] Re-run the focused endpoint test and confirm it passes.

### Task 3: Render the PDF-style index

**Files:**
- Modify: `interface.html`

- [ ] Replace card markup with semantic index rows generated from `index_entries`, including a fallback generated from norms.
- [ ] Add CSS for centered title, Times typography, hierarchy colors/recesses, dotted leaders, right-aligned pages, hover/focus states, and responsive sizing.
- [ ] Pass `data.index_entries` into `renderGazetteIndex` and preserve click rebinding when returning from a norm.

### Task 4: Verify the complete behavior

**Files:**
- Test: `test_app.py`

- [ ] Run `.venv\Scripts\python.exe test_app.py` and confirm zero failures.
- [ ] Start the local application and inspect the Diário Oficial index in the browser using representative structured data.
- [ ] Confirm the visual hierarchy matches the reference and clicking a document row invokes the existing extraction flow.
