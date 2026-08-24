# calibre-mcp

MCP server for [Calibre](https://calibre-ebook.com/) book library management. Designed for use with [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Talks to your local Calibre library via `calibredb` CLI — no Content Server needed.

## Tools

| Tool | Description |
|------|-------------|
| `search_books` | Search books using Calibre's query syntax (`title:`, `author:`, `series:`, etc.) |
| `get_book_info` | Get full metadata for a book by ID |
| `get_epub_path` | Get absolute EPUB file path (for downstream processing) |
| `list_series` | List all books in a series, sorted by index |
| `get_custom_columns` | List custom columns defined in the library |
| `set_custom_column` | Set or append custom column values for a book |
| `set_metadata` | Edit standard metadata fields (title, authors, tags, series, etc.) |

## Installation

### Prerequisites

- [Calibre](https://calibre-ebook.com/) installed with `calibredb` in PATH
- [uv](https://docs.astral.sh/uv/) (for `uvx`)

### Claude Code (from GitHub)

```bash
claude mcp add calibre -- uvx --from git+https://github.com/xmkevinchen/calibre-mcp.git calibre-mcp
```

Add `-s user` to make it available across all projects:

```bash
claude mcp add -s user calibre -- uvx --from git+https://github.com/xmkevinchen/calibre-mcp.git calibre-mcp
```

Or add to your project `.mcp.json` (project-level only):

```json
{
  "mcpServers": {
    "calibre": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/xmkevinchen/calibre-mcp.git", "calibre-mcp"],
      "env": {
        "CALIBRE_LIBRARY_PATH": "/path/to/Calibre Library"
      }
    }
  }
}
```

### Claude Code (local development)

```bash
claude mcp add calibre -- uvx --from /path/to/calibre-mcp calibre-mcp
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CALIBRE_LIBRARY_PATH` | Path to Calibre library directory | `~/Calibre Library` |
| `CALIBREDB_PATH` | Path to `calibredb` binary | auto-detected via PATH |

## Usage Examples

Search for a book:
```
search_books("title:pirates past noon")
```

Get EPUB path for reading:
```
get_epub_path(247)  # returns /Users/you/Calibre Library/Author/Book (247)/book.epub
```

Browse a series:
```
list_series("Magic Tree House")
```

## Updating

`uvx` caches installed packages. To pull the latest version:

```bash
uvx --reinstall --from git+https://github.com/xmkevinchen/calibre-mcp.git calibre-mcp
```

Then restart Claude Code to pick up the changes.

## Troubleshooting

**`calibredb not found`** — Make sure Calibre is installed and `calibredb` is in your PATH. On macOS, Calibre installs CLI tools to `/Applications/calibre.app/Contents/MacOS/`. Add it to PATH or set `CALIBREDB_PATH`.

**`claude mcp add` doesn't work** — Use `add-json` instead:

```bash
claude mcp add-json -s user calibre '{"command":"uvx","args":["--from","git+https://github.com/xmkevinchen/calibre-mcp.git","calibre-mcp"],"env":{"CALIBRE_LIBRARY_PATH":"/path/to/Calibre Library"}}'
```

Or create `.mcp.json` manually in your project root (see above).

## Roadmap

- [x] Search and retrieval (`search_books`, `get_book_info`, `get_epub_path`, `list_series`)
- [x] Custom columns and metadata (`get_custom_columns`, `set_custom_column`, `set_metadata`)

## License

MIT
