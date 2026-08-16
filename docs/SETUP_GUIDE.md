# FreeCAD MCP Server — Setup & How It Works (from scratch)

> **Who this is for:** you, tomorrow, or any reviewer who clones the repo and wants to know exactly what exists, why each piece is there, and what breaks if something is wrong. Read top to bottom once; keep as reference.
>
> **State this doc describes:** end of Step 3A (MCP core skeleton). The server runs over **stdio**, answers `tools/list` with an empty list, and answers `tools/call` with a "not implemented" placeholder. No FreeCAD code is wired in yet (that's Step 4). Everything in here is verified working on this machine (macOS, Apple Silicon).

---

## 1. What this is (one paragraph)

An **MCP server** is a program that speaks JSON-RPC over a transport (stdio or HTTP) and exposes *tools* (functions the LLM can call), *resources* (context the app can read), and *prompts* (user-controlled templates). Clients — MCP Inspector, Claude Desktop, the OMP harness — spawn this program, do a handshake, ask `tools/list`, and call tools by name.

Our server wraps **FreeCAD headless** as a grounded tool: an LLM can ask it to create documents, build primitives, and export STEP/STL. That FreeCAD wiring happens in Step 4. **Step 3A = the server itself, protocol-correct, with placeholder handlers.**

```
[ OMP / Claude Desktop / MCP Inspector ]  ←JSON-RPC over stdio→  [ server.py ]  ←(Step 4)→  [ FreeCAD ]
```

---

## 2. Repo layout (what exists right now)

```
freecad-mcp/
├── .gitignore
├── .omp/mcp.json          ← placeholder for Step 3B (OMP harness config)
├── Dockerfile             ← spike image (FreeCAD 0.20.2, Debian bookworm)
├── README.md
├── pyproject.toml         ← package metadata + deps (mcp==1.29.0 pinned)
├── src/freecad_mcp/
│   ├── __init__.py        ← empty package marker
│   └── server.py          ← THE server (this guide explains every line)
└── tests/
    └── manual_smoke.py    ← hand-rolled client that verifies the server
```

**Private files (gitignored, NOT in the repo):** `PROJECT_MEMORY.md`, `Freecad-MCP-Plan.md`, job posting, `WATCHDOG.yml`.

---

## 3. Environment setup (do once)

### 3.1 Create the venv

```bash
cd /Users/Meltwater_User/freecad-mcp
python3 -m venv .venv
```

**Why:** a venv isolates your project's Python + packages from the system. **What if missing:** nothing — this just fails or you skip it; the next step errors instead.

### 3.2 Install the project (editable)

```bash
.venv/bin/pip install -e ".[dev]"
```

This reads `pyproject.toml` and:
- installs **`mcp==1.29.0`** (the official Python SDK, pinned — do not let it float to 2.x; the 2.x SDK is the "stateless rewrite" era and the whole project is pinned to stable spec 2025-06-18),
- installs **`pytest`** (the `[dev]` extra),
- installs the package itself **editable** — so `import freecad_mcp` resolves to your `src/` directory *live*; edits are picked up without reinstalling,
- registers the console script `freecad-mcp` (from `[project.scripts]` in pyproject).

**Failure modes:**
| Symptom | Cause |
|---|---|
| `ModuleNotFoundError: No module named 'mcp'` | install skipped or wrong interpreter (you ran system `python3`, not `.venv/bin/python`) |
| `ModuleNotFoundError: No module named 'freecad_mcp'` | package dir missing or misnamed — `import` names are **directory names**; must be `src/freecad_mcp/` with `__init__.py` inside, and pyproject must have `where = ["src"]` |

**Always use the venv's interpreter explicitly** (no activation needed):

```bash
.venv/bin/python -m freecad_mcp.server --help
```

### 3.3 Verify the import path

```bash
.venv/bin/python -c "import mcp; print(mcp.__file__)"
# → .../site-packages/mcp/__init__.py    ← source of truth lives here
```

**Why this matters (the #1 lesson of this project):** the *installed* package is the only code that runs. The GitHub repo (`main` branch) is the 2.x-era restructure — its file layout differs completely (`mcp-types/mcp_types/_v2025_11_25/`). If you read GitHub instead of your venv, every path you learn will be wrong. **When pinned, the installed package is the source of truth — not GitHub.**

---

## 4. `src/freecad_mcp/server.py` — every line explained

The full file (current working version):

```python
import mcp.types as types
from mcp.server import Server
import anyio
import argparse
from mcp.server.stdio import stdio_server

server = Server("freecad")

@server.list_tools()
async def list_tools():
    return []

@server.call_tool()
async def call_tool(name, arguments):
    return [types.TextContent(type="text", text="not implemented")]

async def run_server():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("-p", "--port", type=int, default=8000)
    args = parser.parse_args()
    if args.transport == "stdio":
        anyio.run(run_server)
    else:
        raise NotImplementedError("http transport comes later")

if __name__ == "__main__":
    main()
```

### 4.1 Imports

| Import | Why | If missing → |
|---|---|---|
| `import mcp.types as types` | all protocol types (`Tool`, `TextContent`, …) — you *reference* them, never copy them | `NameError: name 'types' is not defined` the moment a handler runs |
| `from mcp.server import Server` | the server class (dispatcher) | `NameError: name 'Server' is not defined` |
| `import anyio` | event loop — SDK is anyio-based, not asyncio | `NameError` at `anyio.run(...)` in `main()` |
| `import argparse` | command-line flag parsing | `NameError: name 'argparse' is not defined` in `main()` |
| `from mcp.server.stdio import stdio_server` | the stdio transport (async context manager) | `NameError` in `run_server()` |

### 4.2 `server = Server("freecad")`

Creates the dispatcher. The name matters: it's what clients see as `serverInfo.name`, and OMP builds tool names as `mcp__<server>_<tool>` → `mcp__freecad_*`. **Rename it and every OMP tool name changes.** Keep it `freecad` (letters only, snake_case discipline).

### 4.3 The two handlers — **registration, not execution**

```python
@server.list_tools()
async def list_tools():
    return []
```

The decorator **registers** your function inside the SDK. Nothing runs at import time. When a `tools/list` request arrives, the SDK calls YOUR function (see `lowlevel/server.py` — `results = await func(...)`). Mental model: **you write the functions, the SDK writes the loop.**

- `list_tools()` — called with **no arguments**, must return a **list of `Tool` objects**. `[]` is valid (zero tools). Returning `list[types.Tool]` is wrong — that's a type *annotation* (`GenericAlias`), not a value; the annotation belongs in the signature (`-> list[types.Tool]:`), the body returns a real list.

```python
@server.call_tool()
async def call_tool(name, arguments):
    return [types.TextContent(type="text", text="not implemented")]
```

- `call_tool(name, arguments)` — the SDK **always** calls it with exactly these two positional args (verified: `lowlevel/server.py` line 541 `await func(tool_name, arguments)`). Your signature must accept both.
- Must return an **iterable of content blocks** (`UnstructuredContent = Iterable[ContentBlock]`) — hence the list `[...]`, not a bare `TextContent`.
- `types.TextContent(type="text", text="...")` — a text content block the model can read. Check its fields in `types.py` (`TextContent` at line 1026 of your installed SDK).
- The SDK validates arguments against your tool's inputSchema *before* calling you (`validate_input=True` default) — free validation, Step 4 will lean on this.

### 4.4 `run_server()` — the engine room

```python
async def run_server():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

- `stdio_server()` — async context manager. On entry it wraps **this process's stdin/stdout** and yields two streams: `read_stream` = JSON-RPC **in**, `write_stream` = JSON-RPC **out**. **stdout is sacred** — never `print()` to it; logs go to stderr. If anything leaks to stdout, the client's JSON parsing breaks.
- `server.run(read, write, init_options)` — the main loop; blocks forever serving requests.
- `create_initialization_options()` — the SDK builds the handshake payload (implementation name/version, protocol version negotiation). Never hand-write this.
- **`await` is mandatory** — `run` is async. Missing `await` → "coroutine was never awaited" warning and nothing serves.

### 4.5 `main()` — the sync front door + argparse

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("-p", "--port", type=int, default=8000)
    args = parser.parse_args()
    if args.transport == "stdio":
        anyio.run(run_server)
    else:
        raise NotImplementedError("http transport comes later")
```

**Argparse mental model:** flags are *strings on the command line*; you declare which strings to look for, argparse reads `sys.argv`, and each flag becomes an attribute: `--transport` → `args.transport`. Three steps: create parser → `add_argument` per flag → `parse_args()`.

| Flag | Meaning | Failure mode if wrong |
|---|---|---|
| `-t/--transport` | channel | `choices=["stdio","http"]` → `--transport banana` is rejected by argparse itself with `invalid choice`; `default="stdio"` means no flag → stdio |
| `--host` | bind address (http, later) | `default="0.0.0.0"`; **do NOT use `-h`** — argparse owns `-h` for help; `parser.add_argument("-h", ...)` crashes at startup with `conflicting option string: -h` |
| `-p/--port` | port (http, later) | `type=int` converts the string `"8000"` → int `8000`; without it, `args.port` stays a string; `--port abc` → argparse `invalid int value` |

**Dispatch:** stdio is the built path → `anyio.run(run_server)`. http is not built → **`raise NotImplementedError`** — a loud refusal, by design (never silently start the wrong transport). Note `anyio.run(run_server)` passes the *function*, not `run_server()` — parens would execute it now and hand anyio a dead coroutine (`TypeError: 'coroutine' object is not callable`).

### 4.6 The `__main__` guard

```python
if __name__ == "__main__":
    main()
```

Runs `main()` only when executed as a script (`python -m freecad_mcp.server` or the `freecad-mcp` console script). When imported as a module (by tests, or the smoke client spawning it as a subprocess), nothing runs at import — the client drives it.

---

## 5. Running it

```bash
cd /Users/Meltwater_User/freecad-mcp
.venv/bin/python -m freecad_mcp.server --help
```

Expected output:

```
usage: server.py [-h] [-t {stdio,http}] [--host HOST] [-p PORT]

  -t {stdio,http}, --transport {stdio,http}
  --host HOST
  -p PORT, --port PORT
```

The `{stdio,http}` brackets are your `choices` validation visible on the wire; `-h, --help` being present proves you didn't claim `-h` for host.

Then prove the http branch refuses:

```bash
.venv/bin/python -m freecad_mcp.server --transport http
# → NotImplementedError  (a pass, not a failure — loud refusal by design)
```

`--transport stdio` (the default) **blocks forever** — that's correct: it's waiting for a client on stdin. That's what the smoke client provides.

---

## 6. `tests/manual_smoke.py` — the client side, line by line

```python
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession
import anyio


async def main():
    server_params = StdioServerParameters(
        command="/Users/Meltwater_User/freecad-mcp/.venv/bin/python",
        args=["-m", "freecad_mcp.server", "--transport", "stdio"],
        cwd="/Users/Meltwater_User/freecad-mcp",
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Available tools:", tools)


anyio.run(main)
```

The client is the **mirror image** of the server, with one asymmetry: the server *wraps* its own stdin/stdout; the client *spawns* the server as a subprocess and pipes to it.

**Step 1 — `StdioServerParameters`** (a Pydantic model describing the launch; the exact same info your future `.omp/mcp.json` will hold):

| Field | What it is | Wrong value → |
|---|---|---|
| `command` | executable to spawn | wrong path → subprocess fails; macOS has no bare `python` — use the venv's absolute path |
| `args` | CLI arguments | **must be `args=[...]` (list literal)** — `args=[...]` not `args[...]`; `args["-m", ...]` is subscripting a nonexistent name → `NameError` |
| `env` | environment dict or `None` (default = SDK's default env) | `env=""` → Pydantic `ValidationError` (type is `dict[str, str] | None`, never a string) — omit it if unused |
| `cwd` | working dir of the child | wrong dir silently breaks relative paths later (Step 4 writes `./exports/`) — use repo root |

**Step 2 — `stdio_client(server_params)`**: async context manager. Entering it spawns the subprocess, wires pipes, yields `(read_stream, write_stream)` — same tuple shape as the server side.

**Step 3 — `ClientSession(read_stream, write_stream)`**: the protocol brain. Entering it starts a task group + receive loop that continuously routes responses to waiting requests by ID. **Important (1.29.0): entering the session does NOT handshake.** `__aenter__` only starts the loops (`mcp/shared/session.py` line 221). The handshake is the explicit next line:

**Step 4 — `await session.initialize()`**: sends `initialize` (client info, protocol version, capabilities) → server replies with its `serverInfo` (that's where the `"freecad"` name surfaces) + negotiated protocol version → client sends `notifications/initialized`. **Skip this and the server will refuse/behave wrong.**

**Step 5 — `await session.list_tools()`**: the round trip we care about. Returns `ListToolsResult`. On the skeleton it prints:

```
Available tools: meta=None nextCursor=None tools=[]
```

- `meta=None` — no metadata; normal.
- `nextCursor=None` — no pagination; normal (6 tools later still fit one page).
- `tools=[]` — **your `list_tools()` handler's actual return value**, across the wire and back.

**`anyio.run(main)`** — pass the function, no parens (same rule as the server side).

**Import typos that bite** (spelling matters, the machine is literal): `StdioServerParamaters` ✗, `CleintSession` ✗ — both raise `ImportError` at line 1.

---

## 7. Verification checklist (Step 3A gate)

```bash
cd /Users/Meltwater_User/freecad-mcp
.venv/bin/python -m py_compile src/freecad_mcp/server.py        # 1. syntax
.venv/bin/python -c "import freecad_mcp.server"                  # 2. imports
.venv/bin/python -m freecad_mcp.server --help                    # 3. argparse
.venv/bin/python -m freecad_mcp.server --transport http          # 4. loud refusal
.venv/bin/python tests/manual_smoke.py                           # 5. THE gate: round trip
```

Gate passes when #5 prints `tools=[]` with no exception. That proves: spawn → pipes → handshake → version negotiation → request dispatch → **your handler** → serialized response → correlation.

---

## 8. Failure-mode quick reference (all seen in the wild on this project)

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'freecad_mcp.caching'` | server.py contains a copy of the 2.x SDK's `__init__.py` (imports `.caching/.context/.mcpserver` — don't exist in 1.29.0) | rewrite server.py against the **installed** 1.29.0 API; ignore GitHub `main` |
| `NameError: name 'types' is not defined` | `import mcp.types as types` missing | add it |
| `return list[types.Tool]` yields `GenericAlias`, not a list | annotation used as a value | annotation → signature `-> list[types.Tool]:`, body returns `[]` |
| `TabError: inconsistent use of tabs and spaces` | tabs and spaces mixed in one block | one indentation, 4 spaces, everywhere |
| `SyntaxError: unmatched ')'` / `invalid syntax` | stray `)` after `with ...:` / missing `(` on `add_argument` | balance the parens |
| `conflicting option string: -h` | `-h` claimed for host | `--host` only (long form) |
| `TypeError: 'coroutine' object is not callable` | `anyio.run(main())` | `anyio.run(main)` |
| `NameError: name 'args' is not defined` (in smoke client) | `args=["-m", ...]` written as `args["-m", ...]` | list literal with `=` |
| Pydantic `ValidationError` on `StdioServerParameters` | `env=""` or wrong type | omit `env` or pass a dict/`None` |
| push: `403 denied to MatyasMartonMeltwater` | gh keyring's **active** account ≠ repo owner (`matyasmarton`) | `gh auth switch --user matyasmarton` |

---

## 9. Git discipline & the push gotcha

- **One intent per commit, message style:** `scaffold:` → `feat:` → `docs:` → `test:` (see `git log --oneline` — 4 commits, each atomic).
- A commit captures the **staging area**, not the working tree — `git add` first, then check `git status` before committing.
- **Two GitHub accounts live in this machine's gh keyring:** `matyasmarton` (repo owner, token has `workflow` scope — needed for CI later) and `MatyasMartonMeltwater` (work account, *default active*). Git presents the **active** account's token on push; the active one is the work account → 403. Fix:

```bash
gh auth switch --user matyasmarton
git push -u origin main
```

Verify with `gh auth status` (expect `matyasmarton → Active account: true`). NOTE: `gh auth status` from a non-interactive shell may claim "not logged in" (keychain) — trust the interactive terminal.

---

## 10. Where this fits next (Step 3B preview)

The server is protocol-complete. Next:

1. **Step 3B:** wire `.omp/mcp.json` (OMP's MCP config) to spawn this server, verify `/mcp list` → `/mcp test freecad` → agent tool call. The config is *launch instructions* (command/args/transport) — exactly the fields `StdioServerParameters` already uses.
2. **Step 4:** the 6 tools wired to FreeCAD (in the Docker container), with Pydantic input schemas.
3. **Step 6:** Dockerfile gains `COPY` + `pip install .` (pyproject becomes the single source of truth — note the container currently has mcp **unpinned**, likely 2.0.0; Step 6 fixes that).

**Never forget (this project's core law):** *an interpreter can only import what is on its import path. Installed ≠ importable. When pinned, the installed package is the source of truth — not GitHub.*
