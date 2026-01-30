#!/usr/bin/env python3
"""SSH host selector — TUI to list hosts from ~/.ssh/config and connect (same list style as theme selector)."""

import os
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static


def get_ssh_config_path() -> Path:
    """SSH config path (respects SSH_CONFIG_ENV or default ~/.ssh/config)."""
    path = os.environ.get("SSH_CONFIG_ENV", "").strip()
    if path:
        return Path(path).expanduser().resolve()
    return Path.home() / ".ssh" / "config"


def parse_ssh_config(config_path: Path) -> list[tuple[str, str, str | None]]:
    """
    Parse OpenSSH config and return list of (display_name, host_alias, theme_or_none).
    display_name can include User@Host; host_alias is what we pass to ssh.
    theme_or_none is read from a comment line in the Host block:
      # kitty theme: theme.conf   or   # kitty theme=theme.conf
    SSH ignores comments, so this does not affect normal ssh.
    """
    if not config_path.is_file():
        return []
    entries: list[tuple[str, str, str | None]] = []
    try:
        text = config_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    current_hosts: list[str] = []
    current_user: str | None = None
    current_theme: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.lower().startswith("host "):
            if current_hosts:
                for alias in current_hosts:
                    if alias and alias != "*":
                        display = f"{current_user}@{alias}" if current_user else alias
                        entries.append((display, alias, current_theme))
            parts = line.split(None, 1)
            current_hosts = parts[1].split() if len(parts) > 1 else []
            current_user = None
            current_theme = None
            continue
        if not line:
            continue
        if line.startswith("#"):
            # Optional: # kitty theme: value  or  # kitty theme=value (value kept as-is)
            rest = line[1:].strip()
            rlower = rest.lower()
            if rlower.startswith("kitty theme:") or rlower.startswith("kitty theme="):
                sep = ":" if ":" in rest else "="
                value = rest.split(sep, 1)[1].strip()
                if value:
                    current_theme = value
            continue
        key_value = line.split(None, 1)
        if len(key_value) >= 2 and key_value[0].lower() == "user":
            current_user = key_value[1].strip()
    if current_hosts:
        for alias in current_hosts:
            if alias and alias != "*":
                display = f"{current_user}@{alias}" if current_user else alias
                entries.append((display, alias, current_theme))
    # Dedupe by alias, keep first occurrence
    seen: set[str] = set()
    unique: list[tuple[str, str, str | None]] = []
    for display, alias, theme in entries:
        if alias not in seen:
            seen.add(alias)
            unique.append((display, alias, theme))
    unique.sort(key=lambda x: (x[0].lower(), x[1]))
    return unique


class SSHHostSelectorApp(App[None]):
    """TUI to pick an SSH host and connect (kitten ssh or ssh)."""

    TITLE = "SSH host selector"
    SUB_TITLE = "↑/↓ move · Enter connect · / filter · q quit"
    CSS = """
    Screen {
        layout: vertical;
    }
    #host-list {
        height: 1fr;
        padding: 1 2;
        border: solid $primary;
    }
    ListView {
        padding: 0 1;
    }
    ListItem {
        padding: 0 1;
    }
    ListItem:focus {
        background: $primary 20%;
    }
    #search {
        width: 100%;
        margin: 0 2 1 2;
        max-width: 60;
    }
    #status {
        height: auto;
        padding: 0 2 1 2;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("/", "focus_search", "Filter", show=True),
    ]

    def __init__(self, *, use_kitten_ssh: bool = True) -> None:
        super().__init__()
        self.use_kitten_ssh = use_kitten_ssh
        self.hosts: list[tuple[str, str, str | None]] = []
        self._filtered: list[tuple[str, str, str | None]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Filter hosts...", id="search")
        yield VerticalScroll(
            ListView(id="host-list"),
            id="list-container",
        )
        yield Static("", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        config_path = get_ssh_config_path()
        self.hosts = parse_ssh_config(config_path)
        self._filtered = list(self.hosts)
        await self._refresh_list()
        search = self.query_one("#search", Input)
        search.display = False
        status = self.query_one("#status", Static)
        status.update(f"{len(self._filtered)} host(s) from {config_path}")

    async def _refresh_list(self) -> None:
        lv = self.query_one("#host-list", ListView)
        await lv.clear()
        await lv.extend([
            ListItem(Label(display)) for display, _alias, _theme in self._filtered
        ])

    def _connect(self, host_alias: str, theme: str | None = None) -> bool:
        """Launch SSH in a new kitty tab if possible; otherwise take over current terminal via exec."""
        if self.use_kitten_ssh:
            # Build: kitten ssh [--kitten color_scheme=THEME] host
            ssh_argv = ["kitten", "ssh"]
            if theme:
                ssh_argv.extend(["--kitten", f"color_scheme={theme}"])
            ssh_argv.append(host_alias)
            # Prefer opening a new tab so the selector can close cleanly
            try:
                r = subprocess.run(
                    ["kitten", "@", "launch", "--type=tab", "--cwd", "current"]
                    + ssh_argv,
                    capture_output=True,
                    timeout=5,
                )
                if r.returncode == 0:
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            # Fallback: exec in current process so this terminal becomes the SSH session
            try:
                os.execvp("kitten", ssh_argv)
            except FileNotFoundError:
                pass
            try:
                os.execvp("ssh", ["ssh", host_alias])
            except FileNotFoundError:
                return False
        else:
            # Plain ssh: try new tab first, then exec in current terminal
            try:
                r = subprocess.run(
                    ["kitten", "@", "launch", "--type=tab", "--cwd", "current", "ssh", host_alias],
                    capture_output=True,
                    timeout=5,
                )
                if r.returncode == 0:
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            try:
                os.execvp("ssh", ["ssh", host_alias])
            except FileNotFoundError:
                return False
        return False

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.index
        if idx < 0 or idx >= len(self._filtered):
            return
        display, host_alias, theme = self._filtered[idx]
        if self._connect(host_alias, theme):
            self.notify(f"Connecting to {display}…", severity="information", timeout=2)
            self.exit()
        else:
            self.notify(
                "Could not run kitten ssh or ssh (not in PATH)",
                severity="error",
                timeout=5,
            )

    def action_focus_search(self) -> None:
        search = self.query_one("#search", Input)
        if search.display:
            search.blur()
            search.display = False
        else:
            search.display = True
            search.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        query = (event.value or "").strip().lower()
        if not query:
            self._filtered = list(self.hosts)
        else:
            self._filtered = [
                (d, a, t) for d, a, t in self.hosts
                if query in d.lower() or query in a.lower()
            ]
        self.run_worker(self._refresh_list())
        status = self.query_one("#status", Static)
        status.update(f"{len(self._filtered)} host(s)")


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="SSH host selector — list hosts from ~/.ssh/config and connect.")
    p.add_argument(
        "--ssh",
        action="store_true",
        help="Use plain 'ssh' instead of 'kitten ssh'",
    )
    args = p.parse_args()
    app = SSHHostSelectorApp(use_kitten_ssh=not args.ssh)
    app.run()


if __name__ == "__main__":
    main()
