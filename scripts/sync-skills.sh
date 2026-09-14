#!/usr/bin/env bash
#
# sync-skills.sh -- propagate this repo's skills/ into the agent-skill
# directories of a workspace root so every AI agent sees them.
#
# Layout produced (agentskills convention):
#   <root>/.agents/skills/<name>  -> <repo>/skills/<name>   (canonical link)
#   <root>/.<agent>/skills/<name> -> ../../.agents/skills/<name>
#
# Idempotent: re-running skips correct links, fixes stale ones, and
# warns on real (non-symlink) paths it will not touch.
#
# Usage: ./scripts/sync-skills.sh [workspace-root]
#        default workspace-root: parent directory of this repo

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_SRC="$REPO_ROOT/skills"
TARGET_ROOT="$(cd "${1:-$REPO_ROOT/..}" && pwd)"

if [[ "$TARGET_ROOT" == "$REPO_ROOT" ]]; then
    echo "Target root is the repo itself; nothing to sync." >&2
    exit 0
fi

# Agent dirs that receive per-skill links into <root>/.agents/skills/.
# .agents itself is the canonical target; agentskills-aware tools
# (Devin, etc.) read it directly and need no per-agent copy.
AGENT_DIRS=(.agent .claude .commandcode .cortex .cursor .windsurf)

created=0
skipped=0
fixed=0
conflicts=0

link() {
    local target="$1" name="$2" cur
    if [[ -L "$name" ]]; then
        cur="$(readlink "$name")"
        if [[ "$cur" == "$target" ]]; then
            skipped=$((skipped + 1))
            return
        fi
        ln -snf "$target" "$name"
        fixed=$((fixed + 1))
        return
    fi
    if [[ -e "$name" ]]; then
        printf 'WARN: %s exists and is not a symlink; leaving untouched\n' "$name" >&2
        conflicts=$((conflicts + 1))
        return
    fi
    ln -s "$target" "$name"
    created=$((created + 1))
}

for skill_dir in "$SKILLS_SRC"/*/; do
    [[ -f "$skill_dir/SKILL.md" ]] || continue
    name="$(basename "$skill_dir")"

    canon_dir="$TARGET_ROOT/.agents/skills"
    mkdir -p "$canon_dir"
    link "$(realpath --relative-to="$canon_dir" "$skill_dir")" "$canon_dir/$name"

    for agent in "${AGENT_DIRS[@]}"; do
        dir="$TARGET_ROOT/$agent/skills"
        mkdir -p "$dir"
        link "../../.agents/skills/$name" "$dir/$name"
    done
done

printf 'sync-skills: %d created, %d already ok, %d fixed, %d conflicts (root: %s)\n' \
    "$created" "$skipped" "$fixed" "$conflicts" "$TARGET_ROOT"
