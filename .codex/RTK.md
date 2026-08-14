# RTK Shell Commands

Read this file before running shell commands in this repository.

## Required prefix

Prefix every command with `rtk`. RTK applies a compact output filter when one exists and otherwise passes the command through unchanged.

Prefix every command in a chain:

```sh
rtk git add path/to/file && rtk git commit -m "message" && rtk git push
```

Examples:

```sh
rtk npm test
rtk npm run build
rtk git status --short
rtk git diff
rtk rg "pattern" path
```

Use `rtk proxy <command>` only when RTK filtering hides output required for diagnosis. Use `rtk --help` and command help instead of maintaining a copied command catalog here.
