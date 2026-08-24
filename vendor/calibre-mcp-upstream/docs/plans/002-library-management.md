---
id: "002"
title: "Phase 2: Library Management"
type: plan
created: 2026-03-24
status: approved
discussion: ""
---

# Feature: Library Management

## Goal
Add custom column and metadata operations to the Calibre MCP server — the building blocks for reading tracking and library curation.

## Steps

### Step 1: Custom column tools (AC1, AC2)
- [x] `get_custom_columns(details)` — implemented, returns "No custom columns" when none exist
- [x] `set_custom_column(book_id, column, value, append)` — implemented with append support
- [x] Library has no custom columns; tools handle gracefully with clear message

### Step 2: Metadata editing (AC3)
- [x] `set_metadata(book_id, fields)` — implemented with replace semantics, dict-based field input

### Step 3: Validation against real library (AC1, AC2, AC3)
- [x] All tools tested against real Calibre library
- [x] AC2: No custom columns in library — tools return clear message
- [x] AC3: set_metadata round-trip verified (set tag → search → found → restore → clean)
- [ ] End-to-end MCP test from Claude Code session (requires restart)

## Acceptance Criteria

### AC1: Custom Column Read — list columns
`get_custom_columns()` returns all custom columns defined in the library. `get_custom_columns(details=True)` includes column types and metadata.

### AC2: Custom Column Write — round-trip verification
`set_custom_column(book_id, "#column", "value")` succeeds, then `get_book_info(book_id)` shows the updated value in output. If no custom columns exist, tool returns a clear message.

### AC3: Metadata Edit — modify and verify
`set_metadata(book_id, {"tags": "test-tag"})` succeeds, then `search_books("tag:test-tag")` returns the book. Clean up after test.
