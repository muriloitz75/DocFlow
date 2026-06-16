# Gazette Hierarchical Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create extraction links on detailed index rows by inheriting category context and locating both registered and unregistered document types in the Gazette body.

**Architecture:** Parse the source index into hierarchical rows before matching. Build document candidates from category and detail rows, then enrich the existing detected-norm collection by matching normalized title tokens against body pages near the indexed page. Reuse the existing `norm_id` frontend contract and extraction endpoint.

**Tech Stack:** Python, Flask, `pdfplumber`, `unittest`, existing Gazette parser and cache.

---

### Task 1: Contextual index parsing

**Files:**
- Modify: `app.py`
- Test: `test_app.py`

- [x] Add a failing unit test where `INSTRUÇÃO NORMATIVA` is the category and `Nº 001...` is the detailed row; assert that only the detailed row links to the matching norm.
- [x] Run the focused test and confirm it fails because the detail lacks the explicit type.
- [x] Update `parse_gazette_index_rows` to retain category context and match norms against the combined category and detail text.
- [x] Run the focused test and existing Gazette parser tests.

### Task 2: Documents outside the fixed type list

**Files:**
- Modify: `app.py`
- Test: `test_app.py`

- [x] Add scanner tests for `CONCORRÊNCIA PÚBLICA Nº 003/2021` and a numbered resolution whose titles appear in the body but are not both recognized by the current regex format.
- [x] Add a failing scanner test for a non-numbered `ERRATA` detail and assert that its index row receives a `norm_id`.
- [x] Implement normalized title matching from detailed index rows to non-index body pages, using the indexed page as the primary location hint.
- [x] Add matched candidates to `norms` with stable IDs and page ranges, while deduplicating candidates already detected by type and number.
- [x] Run all Gazette tests.

### Task 3: Regression verification

**Files:**
- Verify: `app.py`
- Verify: `test_app.py`

- [x] Run the full test suite.
- [x] Scan the saved real Gazette PDF and confirm the existing 30 linked Portarias remain linked.
- [x] Run `git diff --check` and review the final diff without reverting unrelated workspace changes.
