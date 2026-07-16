# RTK - Rust Token Killer (Codex CLI)

**Usage:** Token-optimized CLI proxy for shell commands.

## Rule

Use RTK only when the command has a supported subcommand or `rtk rewrite` says it can be rewritten:

```bash
rtk rewrite &lt;cmd&gt;
```

If rewrite prints nothing, run the raw command. If exact output matters, use:

```bash
rtk proxy &lt;cmd&gt;
```

Good defaults:

```bash
rtk git status
rtk git diff --stat
rtk rg "pattern" path/
rtk pytest tests -q
rtk ruff check path/
rtk find . -name "*.py"
```

Do not prefix unsupported interactive or exact-output commands directly.

## Meta Commands

```bash
rtk gain            # Token savings analytics
rtk gain --history  # Recent command savings history
rtk proxy <cmd>     # Run raw command without filtering
```

## Output Policy

- Use normal RTK output; do not use `--ultra-compact` unless asked.
- When RTK prints a saved tee file for a failure, inspect that file before re-running.
- For a single hook bypass, use `RTK_DISABLED=1 <cmd>`.

