# Permissions audit (Step 3d, chat only)

Moved out of SKILL.md (2026-11-05, ops 85a02946: the body was over the 500-line limit).
Its output goes in Step 4 under "Permissions & setup gaps".

Scan the session for every permission request, tool denial, or capability gap
that required Baylee's intervention or degraded the response. Three categories:

1. **Tool permission prompts.** Any time Claude requested access to a tool
   and Baylee had to grant it (location, calendar, reminders, etc.). Note
   which tool triggered the prompt and whether it could be pre-authorized.
2. **Missing or disconnected connectors.** Any time Claude suggested
   connecting an MCP app, searched the registry, or fell back to web search
   because a connector wasn't available. Note the connector name.
3. **Settings-gated capabilities.** Any time a response was limited because
   a setting was off — web search disabled, code execution unavailable,
   memory/past-chat search toggled off, artifacts disabled, etc.

For each item found, determine the **preventive action** — the one-time
setup step that would eliminate the permission request in future sessions:

| Gap type | Preventive action |
|----------|-------------------|
| Tool permission prompt | Grant persistent access in Claude Settings → Privacy |
| Missing MCP connector | Connect it in Claude Settings → Connected apps |
| Setting toggled off | Enable in Claude Settings → Feature controls |
| Connector auth expired | Re-authenticate in Connected apps |
| No preventive action possible | Note as inherent (e.g., first-use tool grants on iOS) |

**Output goes in Step 4** under "Permissions & setup gaps." If zero items
found, skip — don't mention permissions in the summary.

**Encoding:** If a gap recurred across multiple sessions (check
`conversation_search`), create a memory edit or Grove task to track it.
One-time grants don't need encoding — the summary is sufficient.
