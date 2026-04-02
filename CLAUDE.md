# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repository Is

This is `~/.cursor` — the Cursor IDE user data directory tracked in git for version history and rollback. It is **not** a software project; there are no build steps, tests, or package managers.

GitHub remote: `frankieinc13/claude-project-one`

## Git Workflow

After any meaningful change, commit and push:

```bash
cd C:/Users/Owner/.cursor
git add <files>
git commit -m "description"
git push
```

Git identity is configured locally:
- `user.name`: frankieinc13
- `user.email`: frankieinc13@users.noreply.github.com

## What Gets Tracked

The `.gitignore` uses an allowlist (deny-by-default). Tracked paths:

| Path | Contents |
|------|----------|
| `skills-cursor/` | Cursor built-in agent skills (read-only, managed by Cursor) |
| `skills/` | Personal agent skills (user-created) |
| `commands/` | Personal slash commands |
| `plugins/` | Plugin cache (rules, skills, agents) |
| `projects/*/mcps/` | MCP server descriptors for each project |
| `projects/*/terminals/` | Terminal session output files |
| `projects/*/agent-transcripts/` | Agent transcripts |
| `projects/*/agent-notes/` | Conversation scratchpad notes |
| `projects/*/agent-tools/` | Large tool output files |
| `rules/`, `plans/`, `subagents/` | If created by user |

Excluded: `extensions/`, `ai-tracking/`, `argv.json`, `ide_state.json`, and all other Cursor internals.

## Skills Architecture

Skills live in `skills-cursor/` (Cursor-managed built-ins, never edit) or `~/.cursor/skills/` (personal, user-created).

Each skill is a directory containing a `SKILL.md` with YAML frontmatter:

```markdown
---
name: skill-name          # lowercase, hyphens, max 64 chars
description: ...          # what it does + when to use it (third person)
---
```

The `description` field controls when Cursor auto-applies the skill — be specific and include trigger terms. Keep `SKILL.md` under 500 lines; put reference material in sibling files linked from the main skill file.

**Built-in skills** (in `skills-cursor/`): `canvas`, `create-rule`, `create-skill`, `create-subagent`, `cursor-blame`, `migrate-to-skills`, `shell`, `update-cursor-settings`.

## MCP Servers

`projects/<project-id>/mcps/<server-name>/` stores MCP tool descriptors:
- `INSTRUCTIONS.md` — agent instructions for using the MCP server
- `SERVER_METADATA.json` — server registration metadata

The `cursor-ide-browser` MCP enables browser automation. Key constraint: `browser_navigate` must come before `browser_lock`; always call `browser_unlock` when done.

## Cursor Settings

User settings are at `%APPDATA%\Cursor\User\settings.json` (not tracked in this repo). Use the `update-cursor-settings` skill to modify them.
