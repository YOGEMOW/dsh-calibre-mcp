# -*- coding: utf-8 -*-
"""Calibre MCP 服务器（零依赖 stdio 实现）。

通过 MCP 协议（JSON-RPC 2.0 over stdio）把 Calibre 书库操作暴露为工具，
内部全部调用 calibredb / ebook-convert 官方命令行工具，不直接修改
metadata.db，由 Calibre 自身的锁与原子写保证安全。

本机部署常量在下方 DEFAULT_* 与 CALIBREDB_PATH 探测逻辑中；环境变量
CALIBRE_LIBRARY_PATH / CALIBREDB_PATH 始终优先。

stdout 只输出协议消息；诊断与日志一律走 stderr。
"""

import json
import os
import re
import subprocess
import sys
import tempfile

DEFAULT_LIBRARY = r"G:\Calibre 书库"
CALIBREDB_EXE = r"C:\Program Files\Calibre2\calibredb.exe"
EBOOK_CONVERT_EXE = r"C:\Program Files\Calibre2\ebook-convert.exe"

LIBRARY_PATH = os.environ.get("CALIBRE_LIBRARY_PATH") or DEFAULT_LIBRARY
CALIBREDB = os.environ.get("CALIBREDB_PATH") or (CALIBREDB_EXE if os.path.exists(CALIBREDB_EXE) else "calibredb")
EBOOK_CONVERT = os.environ.get("EBOOK_CONVERT_PATH") or EBOOK_CONVERT_EXE

SERVER_NAME = "calibre-mcp"
SERVER_VERSION = "1.0.0"

# 搜索/列表返回的默认字段（id 恒在首位）
SEARCH_FIELDS = "id,title,authors,series,series_index,rating,tags,publisher,formats,pubdate"


def log(msg: str) -> None:
    print(f"[calibre-mcp] {msg}", file=sys.stderr, flush=True)


def decode(raw: bytes) -> str:
    """优先按 UTF-8 解码；出现替换符（非 UTF-8 输出，如 Windows GBK 控制台）时回退 GBK。"""
    text = raw.decode("utf-8", errors="replace")
    if "\ufffd" in text:
        try:
            text = raw.decode("gbk", errors="replace")
        except Exception:
            pass
    return text


def run(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """执行外部命令，返回 (returncode, stdout, stderr)。"""
    try:
        proc = subprocess.run(args, capture_output=True, timeout=timeout)
        return proc.returncode, decode(proc.stdout), decode(proc.stderr)
    except subprocess.TimeoutExpired:
        return -1, "", f"命令超时（>{timeout}s）：{' '.join(args[:2])} ..."
    except OSError as e:
        return -1, "", f"无法启动命令：{e}"


def calibredb(subcommand: str, *args: str, timeout: int = 120) -> tuple[int, str, str]:
    rc, out, err = run([CALIBREDB, "--with-library", LIBRARY_PATH, subcommand, *args], timeout=timeout)
    if rc != 0 and re.search(r"另一个.?calibre|another calibre", f"{out}\n{err}", re.I):
        err = ("Calibre 主程序（GUI/服务器）正在使用该书库，calibredb 已拒绝并行访问。"
               "请先关闭 Calibre 再重试；如需 GUI 常驻，可改用 Calibre 内容服务器（calibredb "
               "支持 --with-library http://host:port/#library_id，届时在本文件的 "
               "CALIBREDB 命令后追加该 URL 即可）。")
        out = ""
    return rc, out, err


def json_ok(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- 工具实现

def tool_search_books(query: str, limit: int | None = 20, sort_by: str = "title", fields: str | None = None) -> str:
    """按 Calibre 搜索语法检索书籍。支持 title:xx、author:xx、series:"xx"、tag:xx、id:12、布尔组合。"""
    cmd = ["list", "--for-machine", "--fields", fields or SEARCH_FIELDS, "--sort-by", sort_by, "--search", query]
    if limit:
        cmd += ["--limit", str(limit)]
    rc, out, err = calibredb(*cmd)
    if rc != 0:
        return f"搜索失败：{err or out or rc}"
    try:
        books = json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        return out or "无结果"
    if not books:
        return "未找到匹配书籍。"
    lines = [f"共 {len(books)} 本："] + [
        f"- id={b.get('id')} 《{b.get('title')}》 {b.get('authors', '')}"
        f"{'（' + str(b.get('series', '') or '') + (str(b.get('series_index', '')) or '') + '）' if b.get('series') else ''}"
        f" [{'/'.join(b.get('formats', []))}]"
        for b in books
    ]
    return "\n".join(lines) + "\n\n" + json_ok(books)


def tool_get_book_info(book_id: int) -> str:
    """获取某本书的完整元数据（题名、作者、系列、标签、格式、标识符等）。"""
    rc, out, err = calibredb("show_metadata", str(book_id))
    if rc != 0:
        return f"获取书本 {book_id} 信息失败：{err or out or rc}"
    return out


def tool_get_epub_path(book_id: int) -> str:
    """获取某本书的 EPUB 文件绝对路径（无 EPUB 时提示可用格式）。"""
    rc, out, err = calibredb("list", "--for-machine", "--fields", "formats", "--search", f"id:{book_id}")
    if rc != 0:
        return f"查询书本 {book_id} 失败：{err or out or rc}"
    try:
        books = json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        return f"解析失败：{out}"
    if not books:
        return f"未找到 id={book_id} 的书籍。"
    formats = books[0].get("formats") or []
    for f in formats:
        if f.lower().endswith(".epub"):
            return f
    return f"该书无 EPUB 格式。可用格式：{', '.join(f or '' for f in formats) or '无'}"


def tool_list_series(series_name: str, limit: int | None = 50) -> str:
    """列出某系列全部书籍，按系列序号排序。"""
    fields = "id,title,authors,series,series_index,formats"
    cmd = ["list", "--for-machine", "--fields", fields, "--sort-by", "series_index", "--ascending",
           "--search", f'series:"{series_name}"']
    if limit:
        cmd += ["--limit", str(limit)]
    rc, out, err = calibredb(*cmd)
    if rc != 0:
        return f"查询系列失败：{err or out or rc}"
    try:
        books = json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        return out
    if not books:
        return f'系列 "{series_name}" 中没有书籍。'
    lines = [f'系列 "{series_name}" 共 {len(books)} 本：'] + [
        f"- {b.get('series_index', '')}期 id={b.get('id')} 《{b.get('title')}》 {b.get('authors', '')}"
        for b in books
    ]
    return "\n".join(lines) + "\n\n" + json_ok(books)


def tool_get_custom_columns(details: bool = False) -> str:
    """列出书库中定义的自定义列（按查找名引用，如 #status）。"""
    cmd = ["custom_columns"] + (["--details"] if details else [])
    rc, out, err = calibredb(*cmd)
    if rc != 0:
        return f"获取自定义列失败：{err or out or rc}"
    return out or "书库未定义自定义列。"


def tool_set_custom_column(book_id: int, column: str, value: str, append: bool = False) -> str:
    """设置（或追加）某本书的自定义列值。column 如 '#status'；多值列可用 append=True 追加。"""
    cmd = ["set_custom"] + (["--append"] if append else []) + [column, str(book_id), value]
    rc, out, err = calibredb(*cmd)
    if rc != 0:
        return f"设置自定义列失败：{err or out or rc}"
    return f"已{'追加' if append else '设置'}{column}='{value}' 至书本 {book_id}。\n{out}"


# set_metadata 支持的标准字段（calibredb set_metadata --list-fields 为准）
METADATA_FIELDS = [
    "title", "authors", "author_sort", "comments", "cover", "isbn", "languages",
    "pubdate", "publisher", "rating", "series", "series_index", "sort", "tags",
    "title_sort", "identifiers",
]


def tool_set_metadata(book_id: int, fields: dict[str, str]) -> str:
    """修改标准元数据字段（整字段替换）。字段：title, authors, author_sort, comments, cover, isbn,
    languages, pubdate, publisher, rating, series, series_index, sort, tags, title_sort, identifiers。
    多值用逗号分隔（tags 传全部新标签；identifiers 如 isbn:xxx,goodreads:xxx）。"""
    if not fields:
        return "未提供任何字段。"
    bad = [k for k in fields if k not in METADATA_FIELDS]
    if bad:
        return f"不支持的字段：{', '.join(bad)}。支持：{', '.join(METADATA_FIELDS)}"
    cmd = ["set_metadata", str(book_id)]
    for k, v in fields.items():
        cmd += ["--field", f"{k}:{v}"]
    rc, out, err = calibredb(*cmd)
    if rc != 0:
        return f"更新书本 {book_id} 失败：{err or out or rc}"
    return f"已更新书本 {book_id}：{', '.join(f'{k}={v}' for k, v in fields.items())}\n{out}"


def tool_add_book(path: str, title: str | None = None, authors: str | None = None,
                  tags: str | None = None, duplicate: bool = False) -> str:
    """把磁盘上的书文件（epub/mobi/pdf 等）或整个目录加入书库。可附加书名/作者/标签。"""
    cmd = ["add"]
    if duplicate:
        cmd += ["--duplicates"]
    if title:
        cmd += ["--title", title]
    if authors:
        cmd += ["--authors", authors]
    if tags:
        cmd += ["--tags", tags]
    cmd += [path]
    rc, out, err = calibredb(*cmd)
    if rc != 0:
        return f"添加书籍失败：{err or out or rc}"
    return f"已添加：{path}\n{out}"


def tool_delete_book(book_id: int, permanent: bool = False) -> str:
    """从书库删除指定 id 的书籍（默认进 Calibre 回收站；permanent=True 永久删除，不可恢复！）。"""
    cmd = ["remove"] + (["--permanent"] if permanent else []) + [str(book_id)]
    rc, out, err = calibredb(*cmd)
    if rc != 0:
        return f"删除书本 {book_id} 失败：{err or out or rc}"
    return f"已删除书本 {book_id}。\n{out}"


def tool_convert_book(book_id: int, output_format: str, options: list[str] | None = None) -> str:
    """把某本书转换为指定格式（epub/azw3/mobi/pdf/txt...）并作为新格式加入该书。"""
    rc, out, err = calibredb("list", "--for-machine", "--fields", "formats", "--search", f"id:{book_id}")
    if rc != 0:
        return f"查询书本 {book_id} 失败：{err or out or rc}"
    try:
        books = json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        return f"解析失败：{out}"
    if not books:
        return f"未找到 id={book_id} 的书籍。"
    formats = books[0].get("formats") or []
    src = next((f for f in formats if f.lower().endswith(".epub")), formats[0] if formats else None)
    if not src:
        return "该书没有任何可转换的格式文件。"
    fmt = output_format.lower().lstrip(".")
    workdir = tempfile.mkdtemp(prefix="calibre-mcp-")
    dst = os.path.join(workdir, f"converted.{fmt}")
    rc, out, err = run([EBOOK_CONVERT, src, dst, *(options or [])], timeout=300)
    if rc != 0:
        return f"转换失败：{err or out or rc}"
    rc2, out2, err2 = calibredb("add_format", str(book_id), dst)
    if rc2 != 0:
        return f"转换成功但加入书库失败：{err2 or out2 or rc2}（临时文件保留在 {dst}）"
    return f"已转换《{books[0].get('title')}》为 {fmt.upper()} 并加入书库 id={book_id}。\n{out2}"


def tool_get_library_stats() -> str:
    """书库统计：总藏书量、按格式计数。"""
    rc, out, err = calibredb("list", "--for-machine", "--fields", "id")
    if rc != 0:
        return f"统计失败：{err or out or rc}"
    try:
        ids = json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        return f"解析失败：{out}"
    count = len(ids)
    by_format: dict[str, int] = {}
    rc2, out2, err2 = calibredb("list", "--for-machine", "--fields", "formats")
    if rc2 == 0:
        try:
            for b in json.loads(out2) if out2.strip() else []:
                for f in b.get("formats") or []:
                    ext = os.path.splitext(f)[1].lstrip(".").upper() or "?"
                    by_format[ext] = by_format.get(ext, 0) + 1
        except json.JSONDecodeError:
            pass
    return json_ok({"total_books": count, "by_format": by_format})


# ---------------------------------------------------------------- 工具注册表

TOOLS: dict[str, tuple[str, dict]] = {
    "search_books": (
        "按 Calibre 搜索语法检索书库（支持 title:、author:、series:\"\"、tag:、id:、布尔组合），返回匹配书目的 id、题名、作者、系列、格式等。",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Calibre 搜索表达式，如 'author:刘慈欣' 或 'title:三体 AND tag:科幻'"},
                "limit": {"type": "integer", "description": "最多返回条数，默认 20"},
                "sort_by": {"type": "string", "description": "排序字段：title/authors/series/pubdate/rating/id 等，默认 title"},
                "fields": {"type": "string", "description": "逗号分隔的返回字段，默认 id,title,authors,series,series_index,rating,tags,publisher,formats,pubdate"},
            },
            "required": ["query"],
        },
    ),
    "get_book_info": (
        "获取某本书的完整元数据（按 id）。",
        {"type": "object", "properties": {"book_id": {"type": "integer"}}, "required": ["book_id"]},
    ),
    "get_epub_path": (
        "获取某本书 EPUB 文件的绝对路径（无 EPUB 时列出可用格式）。",
        {"type": "object", "properties": {"book_id": {"type": "integer"}}, "required": ["book_id"]},
    ),
    "list_series": (
        "列出指定系列的全部书籍，按系列序号排序。",
        {"type": "object", "properties": {
            "series_name": {"type": "string"},
            "limit": {"type": "integer", "description": "最多返回条数，默认 50"},
        }, "required": ["series_name"]},
    ),
    "get_custom_columns": (
        "列出书库自定义列（名称与查找名，供 set_custom_column 引用）。",
        {"type": "object", "properties": {"details": {"type": "boolean", "description": "是否显示列详情"}}},
    ),
    "set_custom_column": (
        "设置（或追加）某本书的自定义列值。",
        {"type": "object", "properties": {
            "book_id": {"type": "integer"},
            "column": {"type": "string", "description": "自定义列查找名，如 #status"},
            "value": {"type": "string"},
            "append": {"type": "boolean", "description": "多值列时追加而非覆盖"},
        }, "required": ["book_id", "column", "value"]},
    ),
    "set_metadata": (
        "修改某本书的标准元数据字段（整字段替换）。多值用逗号分隔；identifiers 形如 isbn:xxx,goodreads:yyy。",
        {"type": "object", "properties": {
            "book_id": {"type": "integer"},
            "fields": {"type": "object", "additionalProperties": {"type": "string"},
                       "description": f"字段名→新值，支持：{', '.join(METADATA_FIELDS)}"},
        }, "required": ["book_id", "fields"]},
    ),
    "add_book": (
        "把磁盘上的书文件或目录加入书库，可附加题名/作者/标签。",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "书文件或含书的目录的绝对路径"},
            "title": {"type": "string"},
            "authors": {"type": "string", "description": "作者，多作者用 & 连接"},
            "tags": {"type": "string", "description": "标签，逗号分隔"},
            "duplicate": {"type": "boolean", "description": "即使疑似重复也添加"},
        }, "required": ["path"]},
    ),
    "delete_book": (
        "从书库删除指定 id 的书籍（谨慎操作；默认进 Calibre 回收站）。",
        {"type": "object", "properties": {
            "book_id": {"type": "integer"},
            "permanent": {"type": "boolean", "description": "True 为永久删除（不可恢复）"},
        }, "required": ["book_id"]},
    ),
    "convert_book": (
        "把某本书转换为指定格式（epub/azw3/mobi/pdf/txt...）并作为新格式加入该书。",
        {"type": "object", "properties": {
            "book_id": {"type": "integer"},
            "output_format": {"type": "string", "description": "目标格式，如 azw3、mobi、pdf"},
            "options": {"type": "array", "items": {"type": "string"},
                        "description": "额外 ebook-convert 参数，如 ['--enable-heuristics']"},
        }, "required": ["book_id", "output_format"]},
    ),
    "get_library_stats": (
        "书库统计：藏书总量与按格式计数。",
        {"type": "object", "properties": {}},
    ),
}

HANDLERS = {
    "search_books": tool_search_books,
    "get_book_info": tool_get_book_info,
    "get_epub_path": tool_get_epub_path,
    "list_series": tool_list_series,
    "get_custom_columns": tool_get_custom_columns,
    "set_custom_column": tool_set_custom_column,
    "set_metadata": tool_set_metadata,
    "add_book": tool_add_book,
    "delete_book": tool_delete_book,
    "convert_book": tool_convert_book,
    "get_library_stats": tool_get_library_stats,
}


# ---------------------------------------------------------------- 协议循环

def send(msg: dict) -> None:
    # 直接写 UTF-8 字节：Windows 管道下 sys.stdout 默认按 GBK 编码，
    # 会让客户端（约定 UTF-8）把中文解码成乱码。
    sys.stdout.buffer.write(json.dumps(msg, ensure_ascii=False).encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def handle_request(req: dict) -> None:
    rid = req.get("id")
    method = req.get("method", "")
    params = req.get("params") or {}

    if method == "initialize":
        send({"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": params.get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }})
    elif method == "ping":
        send({"jsonrpc": "2.0", "id": rid, "result": {}})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": rid, "result": {
            "tools": [{"name": n, "description": d, "inputSchema": s} for n, (d, s) in TOOLS.items()],
        }})
    elif method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if handler is None:
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": f"未知工具：{name}"}], "isError": True,
            }})
            return
        try:
            text = handler(**args)
            send({"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": text}]}})
        except TypeError as e:
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": f"参数错误：{e}"}], "isError": True,
            }})
        except Exception as e:  # 工具内部意外错误也要回给客户端，而不是死循环
            log(f"tool {name} crashed: {e!r}")
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": f"执行失败：{e}"}], "isError": True,
            }})
    else:
        send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"不支持的方法：{method}"}})


def main() -> None:
    log(f"书库={LIBRARY_PATH}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            log(f"bad json: {e}")
            continue
        if req.get("id") is not None:
            try:
                handle_request(req)
            except Exception as e:  # 协议层崩溃也不能让连接断掉
                log(f"request failed: {e!r}")
                send({"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32603, "message": str(e)}})
        # 通知（id 为空）如 notifications/initialized 无需响应


if __name__ == "__main__":
    main()
