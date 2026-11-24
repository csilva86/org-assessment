# queries/

One SOQL query per file, used by the collectors with `sf data query --file`.

Why files and not `--query "..."`: on Windows, `sf` is a `.cmd` script, and `cmd.exe` strips the
outer quotes of a command line that holds several quotes. A quoted SOQL string then breaks the
path `C:\Program Files\sf\...` at the space. Reading the query from a file avoids quotes entirely,
and keeps every query versioned and easy to review.

- `<area>/<name>.soql` → saved as `<snapshot>/<area>/<name>.json`
- Files ending in `.tooling.soql` run with `--use-tooling-api`.
