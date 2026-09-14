# zephyr-ai-platform

Production-grade Embedded AI platform for Zephyr RTOS: an MCP server plus a
cross-agent skill set covering the build → flash → test → debug lifecycle.

## Features

- **west lifecycle** — build, flash, debugserver, build-info
- **Kconfig intelligence** — English goal → verified minimal `CONFIG_*` diff
- **Devicetree** — author overlays and inspect the merged `zephyr.dts`
- **Testing** — Twister harness runs and Renode simulation
- **Device console** — serial / SEGGER RTT capture and shell interaction
- **Static analysis** — cppcheck / clang-tidy with severity-grouped findings
- **MCUboot** — signed-image header inspection
- **Manifest reasoning** — west workspace, projects, and board metadata

## Install

```sh
git clone <repo> && cd zephyr-ai-platform
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_server.py          # starts the MCP server
```

### Dependencies

- `mcp<2` — pinned to the MCP 1.x release line because the server uses the
  `FastMCP` API, which was removed in MCP 2.0.
- `pyyaml`, `lxml`, `rich`, `networkx`, `pyserial` (see `requirements.txt`)

### Claude Desktop integration

```json
{
  "mcpServers": {
    "zephyr-ai-platform": {
      "command": "<path_to_venv>/.venv/bin/python",
      "args": ["<path_to_repo>/run_server.py"],
      "disabled": false
    }
  }
}
```

## Skills

Agent skills live in `skills/` — the canonical, agent-agnostic location.
Committed symlinks (`.agents/skills`, `.claude/skills`, `.cursor/skills`)
point at it, so any agent opened on this repo finds them automatically.

To expose the skills to agents opened on an **enclosing workspace**, run:

```sh
./scripts/sync-skills.sh [workspace-root]   # default: parent dir of this repo
```

It links each skill into `<root>/.agents/skills/` and the known per-agent
dirs (`.agent`, `.claude`, `.commandcode`, `.cortex`, `.cursor`, `.windsurf`).
Re-run it after adding or renaming a skill — it is idempotent.

### Supported agents

| Agent                              | How skills are discovered                                           |
| ---------------------------------- | ------------------------------------------------------------------- |
| Devin CLI / Windsurf               | `.agents/skills/` natively; `.windsurf/skills/` via sync            |
| Claude Code                        | `.claude/skills` symlink (repo) or synced links                     |
| Cursor                             | `.cursor/skills` symlink (repo) or synced links                     |
| Other agentskills-compatible tools | `.agents/skills/` (`.agent`, `.commandcode`, `.cortex`, …) via sync |

### Included skills

| Skill                      | Purpose                                                       |
| -------------------------- | ------------------------------------------------------------- |
| `west-build-flash`         | Build / flash / debugserver lifecycle via `west`              |
| `build-doctor`             | Classify failed builds into a structured diagnosis            |
| `twister-runner`           | Run `west twister` and parse the JSON report                  |
| `renode-runner`            | Boot a built ELF under Renode and assert on output            |
| `kconfig-tuner`            | English goal → minimal verified `CONFIG_*` diff               |
| `devicetree-author`        | Author/edit `.dts` / `.overlay` with binding citations        |
| `devicetree-inspector`     | Report enabled nodes, chosen entries, aliases from merged DT  |
| `west-workspace-inspector` | Workspace shape, Zephyr version, manifest, boards, shields    |
| `zephyr-bsp-scaffold`      | Scaffold a new board/BSP from a reference board               |
| `device-console-bridge`    | Serial / RTT capture sessions and device shell interaction    |
| `mcuboot-image-inspector`  | Decode MCUboot image headers (magic, version, flags, size)    |
| `static-analysis-runner`   | cppcheck / clang-tidy over a scoped path, grouped by severity |
| `embedded_c_cpp`           | Embedded C/C++ with Clean Code + secure-coding review         |
| `embedded_rust`            | no_std / bare-metal Rust (embassy, rtic, cortex-m)            |
| `embedded_python`          | Host-side Python tooling, tests, and validation               |
| `embedded_bash`            | Bash for build / flash / CI scripts (shellcheck-clean)        |
| `embedded-skill-author`    | Codify a stable procedure as a new tested skill               |

See `.devin/MCP-TO-CLI-GUIDE.md` for the full MCP-tool → skill mapping.
