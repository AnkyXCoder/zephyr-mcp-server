# zephyr_mcp

Zephyr AI Platform MCP server for embedded Zephyr RTOS workflows.

## Dependencies

- `mcp<2` — pinned to the MCP 1.x release line because the server uses the `FastMCP` API, which was removed in MCP 2.0.

## Skills

Agent skills live in `skills/` (agent-agnostic, canonical). The committed
symlinks `.agents/skills`, `.claude/skills`, and `.cursor/skills` point at it,
so any agent opened on this repo finds them automatically.

To expose the skills to agents opened on an enclosing workspace, run:

```sh
./scripts/sync-skills.sh [workspace-root]   # default: parent dir of this repo
```

It links each skill into `<root>/.agents/skills/` and the known per-agent
dirs (`.agent`, `.claude`, `.commandcode`, `.cortex`, `.cursor`, `.windsurf`).
Re-run it after adding or renaming a skill — it is idempotent.
