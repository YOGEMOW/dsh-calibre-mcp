# Calibre MCP 服务器（零依赖实现）

通过 MCP（Model Context Protocol，stdio）把 Calibre 书库操作暴露为工具，
供 DSH / 思源笔记 / Claude Code 等 MCP 客户端直接调用。

- **无第三方依赖**：仅用 Python 标准库（json / subprocess），无需 pip、npm、uv。
  本机 Python 3.10 直接可跑（避开本机 pip 网络异常）。
- **安全写库**：全部操作经 `calibredb` / `ebook-convert` 官方命令行，由 Calibre
  自身锁与原子写保护，不直接改 `metadata.db`。
  **注意**：Calibre GUI（或内容服务器）打开该书库期间，calibredb 会拒绝并行访问
  ——此时工具返回明确提示"请关闭 Calibre 再试"；如需边开 GUI 边操作，可在
  `server.py` 顶部把 `LIBRARY_PATH` 换成内容服务器 URL
  （如 `http://localhost:8080/#library_id`）。
- **书库**：默认 `G:\Calibre 书库`（环境变量 `CALIBRE_LIBRARY_PATH` 可覆盖）。

## 目录

- `server.py`：MCP stdio 服务器本体
- `verify_sdk.mjs`：用官方 @modelcontextprotocol/sdk 的自检脚本
  （`node verify_sdk.mjs`，连接 → 列工具 → 搜索 → 统计），改动后可复验
- `vendor/calibre-mcp-upstream/`：上游 xmkevinchen/calibre-mcp 源码副本
  （FastMCP 实现，需 `uv` 与 Python ≥3.11；本目录为免依赖部署版，功能兼容）

## 运行

```powershell
python E:\DSH-workspace\calibre-mcp\server.py
```

## 工具（MCP 名称带 `mcp__calibre__` 前缀，由客户端加命名空间）

| 工具 | 说明 |
|---|---|
| search_books | Calibre 搜索语法检索（title:/author:/series:/tag:/id:、布尔组合） |
| get_book_info | 单本书完整元数据 |
| get_epub_path | 获取 EPUB 绝对路径（无 EPUB 时列出可用格式） |
| list_series | 系列书目，按 series_index 排序 |
| get_custom_columns | 列出自定义列（查找名如 `#status`） |
| set_custom_column | 设置/追加自定义列值 |
| set_metadata | 改标准字段：title/authors/tags/series/rating/publisher/identifiers 等 |
| add_book | 把磁盘书文件/目录加入书库 |
| delete_book | 移除书籍（默认进 Calibre 回收站，permanent 为不可恢复） |
| convert_book | 转格式（epub/azw3/mobi/pdf...）并加入该书 |
| get_library_stats | 藏书量与按格式计数 |

## DSH 接入（已完成）

`~/.dsh/profiles/web/cordis.patch.yml` 已插入一行 `@deepseek-ai/dsh-mcp-client`，
serverName=`calibre`，模型侧工具形如 `mcp__calibre__search_books`，命令指向本目录
的 `server.py`。热重载后新建会话即可看到；若未见工具，重启 `dsh web`。

## 思源笔记接入（用户在设置里操作）

设置 → AI → MCP 服务器（或 MCP → 服务器）里新增（stdio 类型）：

- 命令：`C:\Users\YOGIMOV\AppData\Local\Programs\Python\Python310\python.exe`
- 参数：`E:\DSH-workspace\calibre-mcp\server.py`
- 无需环境变量（服务端内置书库路径；如需自定义再填
  `CALIBRE_LIBRARY_PATH=G:\Calibre 书库`）。

## 分享给其他人

给对方的**全部前置条件**：本机安装了 Python 3.10+、本机安装了 Calibre。

### 对方拿到什么

- `server.py`：完整服务器（零第三方依赖，无需 pip/uv/npm）
- `README.md`：本文档
- `verify_sdk.mjs`（可选）：官方 MCP SDK 自检脚本
- `vendor/calibre-mcp-upstream/`（可选）：上游参考实现（MIT，功能兼容，需 uv + Python 3.11）

交付方式任选：直接拷贝整个目录 / `git clone`（见下方版本与打包）/ 解压 `calibre-mcp.zip`。

### 对方仅需两处配置

**1) 书库路径**（二选一）：

- 推荐：启动时用环境变量（不用改代码）
  ```
  CALIBRE_LIBRARY_PATH=D:\我的书库
  CALIBREDB_PATH=C:\Program Files\Calibre2\calibredb.exe   # calibredb 已在 PATH 时可省略
  EBOOK_CONVERT_PATH=C:\Program Files\Calibre2\ebook-convert.exe  # 可选，仅转换功能需要
  ```
- 或直接改 `server.py` 顶部的 `DEFAULT_LIBRARY` / `CALIBREDB_EXE`。

**2) 在 MCP 客户端注册**（任一即可）：

- **DSH**（`~/.dsh/profiles/<profile>/cordis.patch.yml`）：
  ```yaml
  - insert:
      - id: calibre-mcp
        name: '@deepseek-ai/dsh-mcp-client'
        config:
          serverName: calibre
          transport: stdio
          command: C:/.../python.exe        # 对方的 Python 绝对路径
          args: [E:/.../calibre-mcp/server.py]
          env:
            CALIBRE_LIBRARY_PATH: 'D:\我的书库'
  ```
- **思源笔记 / Claude Desktop**（stdio 类型）：
  - 命令：`<python绝对路径>`
  - 参数：`<server.py绝对路径>`
  - 环境变量：`CALIBRE_LIBRARY_PATH=<书库路径>`（按需）

### 对方自检

```powershell
node verify_sdk.mjs     # 可选；输出 NO_REPLACEMENT_CHARS: true 且列出 11 个工具即通过
```
或在客户端直接问："书库里有多少本书？"——应返回藏书统计。

### 注意

- 服务器零网络监听，只对该 stdio 通道工作，没有额外安全面。
- 写操作（`set_metadata`/`add_book`/`delete_book`/`convert_book`）与 Calibre GUI 互斥：
  对方 GUI 打开书库时会被拒绝并收到中文提示，属正常保护。
- 服务器显式输出 UTF-8 字节，Windows 客户端无乱码（构建约定：协议消息走 `stdout`，
  必须保持 UTF-8，勿改回 `sys.stdout.write` 字符串形式）。

## 版本与打包

```powershell
git status && git log --oneline          # 已 git init 时的提交历史
Compress-Archive -Path calibre-mcp\* -DestinationPath calibre-mcp.zip
```

## 备注

- 服务器日志输出到 stderr；stdout 仅承载 MCP 协议消息。
