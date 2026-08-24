# Calibre MCP Server

Calibre MCP server for Claude Code, designed around family reading workflows.

## Background

- Existing third-party [THeK3nger/calibre-mcp](https://github.com/THeK3nger/calibre-mcp) depends on Calibre Content Server or `calibredb` CLI
- This project is built from scratch for tighter workflow integration

## Technical Decisions

- **Python + FastMCP** — MCP ecosystem standard
- **Local mode only** — reads directly from Calibre Library directory, no Content Server needed
- **`calibredb` CLI** — stable, full-featured, doesn't require Calibre GUI running
## Workflow Integration

### Reading Quiz Generation (`/reading-quiz`)
`search_books("title:pirates past noon")` → `get_epub_path(book_id)` → unzip EPUB → read chapters

## Project Plan

### Phase 1: Basic Search & Retrieval (DONE)

**Goal: Replace manual Glob + unzip workflow**

- [x] `search_books(query)` — Calibre search syntax, returns book list
- [x] `get_book_info(book_id)` — metadata (title, author, series, formats, file paths)
- [x] `get_epub_path(book_id)` — returns EPUB absolute file path
- [x] `list_series(series_name)` — list all books in a series, sorted by series_index

### Phase 2: Library Management (DONE)

**Goal: Custom column and metadata operations**

- [x] `get_custom_columns(details)` — list custom columns
- [x] `set_custom_column(book_id, column, value, append)` — write custom column values
- [x] `set_metadata(book_id, fields)` — edit standard metadata fields

## Installation

### Prerequisites

- [Calibre](https://calibre-ebook.com/) installed with `calibredb` in PATH
- [uv](https://docs.astral.sh/uv/) or [uvx](https://docs.astral.sh/uv/guides/tools/)

### Claude Code

Add to `~/.claude.json` under `mcpServers`:

```json
{
  "calibre": {
    "command": "uvx",
    "args": ["--from", "git+https://github.com/xmkevinchen/calibre-mcp.git", "calibre-mcp"],
    "env": {
      "CALIBRE_LIBRARY_PATH": "/path/to/Calibre Library"
    }
  }
}
```

Or for local development:

```json
{
  "calibre": {
    "command": "uvx",
    "args": ["--from", "/path/to/calibre-mcp", "calibre-mcp"],
    "env": {
      "CALIBRE_LIBRARY_PATH": "/path/to/Calibre Library"
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CALIBRE_LIBRARY_PATH` | Path to Calibre library directory | `~/Calibre Library` |
| `CALIBREDB_PATH` | Path to `calibredb` binary (if not in PATH) | auto-detected |

## References

- `calibredb` docs: `calibredb --help`, subcommands `calibredb list --help` etc.
- [FastMCP](https://github.com/jlowin/fastmcp): `pip install mcp[cli]`, use `@mcp.tool()` decorator
