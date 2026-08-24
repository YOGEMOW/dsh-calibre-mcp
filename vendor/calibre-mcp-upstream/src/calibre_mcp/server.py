"""
Calibre MCP Server

MCP server for Calibre book library management.
Local mode: reads directly from Calibre Library via calibredb CLI.
"""

import json
import os
import shutil
import subprocess

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Calibre")

CALIBRE_LIBRARY_PATH = os.environ.get("CALIBRE_LIBRARY_PATH", os.path.expanduser("~/Calibre Library"))

CALIBREDB = os.environ.get("CALIBREDB_PATH") or shutil.which("calibredb")
if not CALIBREDB:
    raise RuntimeError("calibredb not found. Add Calibre to PATH or set CALIBREDB_PATH env var.")


def _run_calibredb(*args: str, timeout: int = 30) -> str:
    """Run a calibredb command and return stdout."""
    cmd = [CALIBREDB, "--with-library", CALIBRE_LIBRARY_PATH, *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"calibredb timed out after {timeout}s")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"calibredb exited with code {result.returncode}")
    return result.stdout.strip()


@mcp.tool()
def search_books(
    query: str,
    fields: list[str] | None = None,
    limit: int | None = None,
    sort_by: str = "title",
) -> str:
    """
    Search books in the Calibre library using Calibre's search syntax.

    Search syntax examples:
    - Simple text: "robot" (searches all fields)
    - Field-specific: author:asimov, title:"magic tree house", tag:fiction
    - Boolean: author:asimov AND title:foundation
    - Series: series:"magic tree house"

    Args:
        query: Search expression using Calibre's query language
        fields: Fields to include in results
        limit: Max number of results (omit for all)
        sort_by: Field to sort by
    """
    if fields is None:
        fields = ["title", "authors", "series", "series_index", "formats"]

    cmd = [
        "list", "--for-machine",
        "--fields", ",".join(fields),
        "--sort-by", sort_by,
        "--search", query,
    ]
    if limit is not None:
        cmd.extend(["--limit", str(limit)])

    try:
        result = _run_calibredb(*cmd)
    except RuntimeError as e:
        return f"Search error: {e}"

    if not result:
        return "No books found."

    books = json.loads(result)
    if not books:
        return "No books found."

    count = len(books)
    # Format as human-readable table too
    table = _run_calibredb(
        "list", "--fields", ",".join(fields),
        "--sort-by", sort_by, "--search", query,
        *(["--limit", str(limit)] if limit is not None else []),
    )
    return f"Found {count} book(s):\n\n{table}"


@mcp.tool()
def get_book_info(book_id: int) -> str:
    """
    Get detailed metadata for a book by its Calibre ID.

    Returns title, authors, series, tags, formats, file paths, and all other metadata.

    Args:
        book_id: The Calibre book ID
    """
    try:
        return _run_calibredb("show_metadata", str(book_id))
    except RuntimeError as e:
        return f"Error retrieving book {book_id}: {e}"


@mcp.tool()
def get_epub_path(book_id: int) -> str:
    """
    Get the absolute file path of a book's EPUB file.

    This is the core tool for the reading-quiz workflow — returns the EPUB path
    so it can be unzipped and chapters read directly.

    Args:
        book_id: The Calibre book ID
    """
    try:
        result = _run_calibredb(
            "list", "--fields", "formats", "--search", f"id:{book_id}", "--for-machine"
        )
    except RuntimeError as e:
        return f"Error retrieving book {book_id}: {e}"

    try:
        books = json.loads(result)
    except json.JSONDecodeError:
        return f"Error parsing calibredb output for book {book_id}."

    if not books:
        return f"Book {book_id} not found."

    formats = books[0].get("formats", [])
    for fmt in formats:
        if fmt.lower().endswith(".epub"):
            return fmt

    available = [os.path.splitext(f)[1] for f in formats] if formats else []
    return f"No EPUB found for book {book_id}. Available formats: {', '.join(available) or 'none'}"


@mcp.tool()
def list_series(
    series_name: str,
    fields: list[str] | None = None,
) -> str:
    """
    List all books in a series, sorted by series_index.

    Great for seeing the full reading order of a series like "Magic Tree House".

    Args:
        series_name: Name of the series to look up
        fields: Fields to include in results
    """
    if fields is None:
        fields = ["title", "series_index", "authors", "formats"]
    elif "series_index" not in fields:
        fields = [*fields, "series_index"]

    cmd = [
        "list",
        "--fields", ",".join(fields),
        "--sort-by", "series_index",
        "--ascending",
        "--search", f'series:"{series_name}"',
    ]

    try:
        result = _run_calibredb(*cmd)
    except RuntimeError as e:
        return f'Error searching series "{series_name}": {e}'

    if not result:
        return f'No books found in series "{series_name}".'

    return result


@mcp.tool()
def get_custom_columns(details: bool = False) -> str:
    """
    List all custom columns defined in the Calibre library.

    Custom columns are user-defined metadata fields beyond the standard
    fields (title, author, tags, etc.).

    Args:
        details: Include column types, default values, and other metadata
    """
    cmd = ["custom_columns"]
    if details:
        cmd.append("--details")

    try:
        result = _run_calibredb(*cmd)
    except RuntimeError as e:
        return f"Error retrieving custom columns: {e}"

    return result if result else "No custom columns defined in this library."


@mcp.tool()
def set_custom_column(
    book_id: int,
    column: str,
    value: str,
    append: bool = False,
) -> str:
    """
    Set the value of a custom column for a book.

    Custom columns are referenced by their lookup name (e.g. "#status", "#rating").
    Use get_custom_columns() to see available columns.

    Args:
        book_id: The Calibre book ID
        column: Custom column lookup name (e.g. "#status")
        value: Value to set
        append: If True, append to existing values instead of replacing
    """
    cmd = ["set_custom"]
    if append:
        cmd.append("--append")
    cmd.extend([column, str(book_id), value])

    try:
        _run_calibredb(*cmd)
    except RuntimeError as e:
        return f"Error setting custom column '{column}' for book {book_id}: {e}"

    action = "appended to" if append else "set"
    return f"Custom column '{column}' {action} '{value}' for book {book_id}."


@mcp.tool()
def set_metadata(
    book_id: int,
    fields: dict[str, str],
) -> str:
    """
    Set standard metadata fields for a book.

    Supported fields: title, authors, author_sort, comments, cover, isbn,
    languages, pubdate, publisher, rating, series, series_index, sort, tags,
    title_sort, identifiers.

    Note: this REPLACES field values. For tags, pass all desired tags comma-separated.
    For identifiers: "isbn:123456,goodreads:789".

    Args:
        book_id: The Calibre book ID
        fields: Dict of field_name → value, e.g. {"tags": "sci-fi,classics", "series": "Foundation"}
    """
    if not fields:
        return "No fields specified."

    cmd = ["set_metadata", str(book_id)]
    for name, value in fields.items():
        cmd.extend(["--field", f"{name}:{value}"])

    try:
        result = _run_calibredb(*cmd)
    except RuntimeError as e:
        return f"Error setting metadata for book {book_id}: {e}"

    summary = ", ".join(f"{k}={v}" for k, v in fields.items())
    return f"Updated book {book_id}: {summary}\n{result}" if result else f"Updated book {book_id}: {summary}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
