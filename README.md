# freecad-mcp

Hand-coded Python MCP server exposing parametric FreeCAD operations as LLM tools — the same tool-use plumbing used to give LLMs access to document stores, applied to a grounded CAD environment.

## Project status

**Stage: foundation complete — server under construction.**

- ✅ Repo hygiene: `.gitignore`, README
- 🔜 `pyproject.toml` (content ready — pins MCP SDK)
- 🔜 `.omp/mcp.json` placeholder (OMP harness config)
- ✅ **Step 2 — FreeCAD headless spike: proven natively (macOS) and in a Docker container**
- 🔜 Steps 3A+ — MCP server skeleton, six tools, OMP harness wiring, verification

The server code does not exist yet. This README documents the foundation and the environment decisions everything else builds on.

## Architecture

- **In-process headless FreeCAD**: the server imports `FreeCAD`/`Part` and runs geometry operations in its own process — no GUI, no separate CAD instance, no RPC bridge.
- **Container runtime**: the server runs in a Docker image where FreeCAD is installed as a Python library alongside the interpreter. This is the only setup where `import FreeCAD` is guaranteed to work for any reviewer.
- **Why not native macOS?** FreeCAD.app ships its Python bindings sealed inside the app bundle, compiled against its own embedded Python. Importing them from an external venv is fragile and machine-specific (a fight with rpaths and versions that breaks on every FreeCAD update). The container is reproducible by construction — and it exercises Docker, which is a stated requirement for this role.

## Prerequisites

- Docker Desktop (any platform) — server and FreeCAD live in the image.
- Python ≥ 3.10 locally (for server development and tests).

## Quick start (current stage: spike verification)

```bash
# Build the dev image (Debian bookworm, FreeCAD 0.20.2, Python 3.11 venv, MCP SDK)
docker build -t freecad-mcp .

# Verify FreeCAD imports inside the container
docker run --rm freecad-mcp app_env/bin/python -c "import FreeCAD; print(FreeCAD.Version())"

# Headless pipeline smoke: document → box → recompute → export STEP
docker run --rm freecad-mcp app_env/bin/python -c "import FreeCAD, Part; doc=FreeCAD.newDocument('t'); Part.show(Part.makeBox(10,10,10),'Box'); doc.recompute(); Part.export([doc.Objects[0]], '/tmp/t.step'); print('ok')"
```

## Known quirks (hard-won)

- **Debian's `freecad-python3` installs its bindings to `/usr/lib/freecad-python3/lib`** — a non-standard path that Python never searches by default. The image sets `ENV PYTHONPATH=/usr/lib/freecad-python3/lib` to wire it up.
- **Debian's `python3` strips `ensurepip`**, so creating a venv requires the `python3-venv` package (`python3 -m venv` fails without it).
- **The macOS FreeCAD installer ships no `FreeCADCmd` binary** — headless use on macOS goes through the app's bundled Python (`/Applications/FreeCAD.app/Contents/Resources/bin/python`) with `PYTHONPATH` pointing at `Contents/Resources/lib`.
- **Docker Desktop's daemon must be running** before docker commands work (`open -a Docker` on macOS).

## Roadmap

- [x] `.gitignore`, README
- [ ] `pyproject.toml` — Python ≥ 3.10, MCP SDK pinned (stable 1.x, spec 2025-06-18)
- [ ] `.omp/mcp.json` placeholder
- [ ] MCP server skeleton (official SDK, stdio first) — `src/freecad_mcp/server.py`
- [ ] Six tools: `create_document`, `create_primitive`, `execute_python`, `export_model`, `list_objects`, `get_object`
- [ ] OMP harness wiring + verification (`/mcp list`, `/mcp test freecad`)
- [ ] Security hardening (sandboxed `execute_python`, export path guards, doc limits)
- [ ] Verification: MCP Inspector, Claude Desktop, OMP harness; pytest; CI

## License

MIT
