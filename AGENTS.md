# Project context

Shared project notes: `C:/Users/USER/Documents/Project Knowledge/Projects/KuhaMo/KuhaMo.md` and `KuhaMo Current Work.md` in that folder. Read only when relevant to the task.

For cross-file relationships, query the local graph using PowerShell:
`& "$env:USERPROFILE\.local\bin\graphify.exe" query "QUESTION" --budget 1200`

Use direct lookup for known files. Verify graph results against source; the code-only graph does not fully model Django templates, runtime routes, or configuration. Refresh after meaningful code changes with `graphify update .`. Generated graph data is ignored by git. Do not load the full graph JSON or report for focused questions.
