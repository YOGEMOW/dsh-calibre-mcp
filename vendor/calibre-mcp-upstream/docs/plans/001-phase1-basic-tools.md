---
id: "001"
title: "Phase 1: Basic Calibre MCP Tools"
type: plan
created: 2026-03-24
status: completed
discussion: ""
---

# Feature: Phase 1 Basic Calibre MCP Tools

## Goal
Replace the manual Glob + unzip workflow with MCP tools that search books, retrieve metadata, get EPUB paths, and list series — so reading-quiz can be done in one Claude Code call.

## Steps

### Step 1: Validate existing tools against real Calibre library (AC1, AC2)
- [x] Verify `calibredb` is reachable in the MCP server process PATH — `/opt/homebrew/bin/calibredb`
- [x] Run `search_books` with "Pirates Past Noon" — found 1 book, ID=247, correct metadata
- [x] Run `get_book_info` with book ID 247 — full metadata returned correctly
- [x] Run `get_epub_path` with book ID 247 — absolute path exists on disk, ends with `.epub`
- [x] Verify `--for-machine` output returns absolute paths in the `formats` field — confirmed
- [x] Run `list_series` with "Magic Tree House" — sorted by series_index (1.0, 2.0, 3.0, 4.0...)

### Step 2: Configure MCP server in Claude Code settings (AC3)
Step 2a and 2b can run in parallel with Step 1. Step 2c requires Step 1 + Step 3 to be complete.

- [x] (2a) Add calibre MCP config to project `.claude/settings.json` — `calibredb` in PATH, no need for `CALIBREDB_PATH`
- [x] (2b) Verify server starts — 4 tools registered (search_books, get_book_info, get_epub_path, list_series)
- [x] (2c) End-to-end MCP call confirmed — `search_books("title:pirates past noon")` returns correct results via stdio transport

### Step 3: Fix issues found during validation (AC1, AC2)
After Step 1, produce a specific bug list and fix only those items. Known candidates:
- [x] No `calibredb` CLI compatibility issues found — all commands work correctly
- [x] Edge cases already handled in code (RuntimeError catch, empty results, format fallback)
- [x] `--for-machine` JSON parsing confirmed robust — returns absolute paths

## Acceptance Criteria

### AC1: Reference Case — Search and retrieve a known book
Search for "Pirates Past Noon" by title → returns exactly 1 result with correct author (Mary Pope Osborne), series (Magic Tree House), and series_index (4).

### AC2: Reference Case — EPUB path resolution
`get_epub_path` for a known book with EPUB format → returns an absolute path that exists on disk and ends with `.epub`. For a book without EPUB → returns available formats list.

### AC3: MCP Integration — End-to-end tool call
From a Claude Code session with the calibre MCP server configured, `search_books("title:pirates past noon")` returns structured results without errors. Server starts and stays running via stdio transport.
