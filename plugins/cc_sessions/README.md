# Claude Code Sessions

Browse and view Claude Code session history through the WenZi launcher.

## Features

### Session Search

Open the launcher and type `cc ` to search your Claude Code sessions.

**Search capabilities:**
- Fuzzy search by session title, project name, git branch, or message count
- Filter by project: type `@projectname` followed by your query (e.g., `@WenZi window`)
- Searches session summaries and first user messages

**Each result displays:**
- Session title (custom title, summary, or first prompt)
- Project name, relative time (e.g., "2 hours ago"), and git branch
- Message count badge
- Auto-generated project avatar

### Actions

| Key | Action |
|-----|--------|
| `Enter` | Open session in the detailed viewer |
| `Cmd+Enter` | Copy session file path to clipboard |
| `Delete` | Move session to Trash (with confirmation) |

### Preview Panel

When browsing results, a preview panel shows:
- Session title and metadata tags (project, branch, Claude version, message/token counts)
- Time information (created, modified, duration)
- Last 10 conversation turns with text preview

### Session Viewer

Press Enter on a session to open the full viewer:
- Renders the complete conversation with Markdown formatting and syntax-highlighted code blocks
- Expandable tool use blocks and thinking sections
- Copy-to-clipboard buttons on code blocks
- **Live auto-reload** — the viewer updates in real-time as an active session progresses
- Subagent support — detects and links to spawned subagent sessions

### Cache Management

Use the launcher command `cc-sessions:clear-cache` to reset cached session metadata and force a full rescan.

## Usage

1. Open the WenZi launcher
2. Type `cc ` followed by your search query
3. Browse results and press Enter to view a session
4. Use `@project` syntax to filter by project

## Requirements

- WenZi ≥ 0.1.12
- Claude Code sessions stored in `~/.claude/projects/`
