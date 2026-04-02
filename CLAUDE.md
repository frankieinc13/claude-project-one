# CLAUDE.md

This is `~/.cursor` — Cursor IDE user data tracked in git. Not a software project. GitHub: `frankieinc13/claude-project-one`.

## Git Workflow

Commit and push after every meaningful unit of work. Never let changes accumulate.

- Imperative mood: "Add X", "Update Y", "Fix Z"
- Describe what changed and why
- One logical change per commit

Git identity: `frankieinc13` / `frankieinc13@users.noreply.github.com`

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
