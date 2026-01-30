#!/usr/bin/env python3
"""Kitty theme selector — TUI to list and apply themes from ~/.config/kitty."""

import os
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static


def get_kitty_config_dir() -> Path:
    """Kitty config directory (respects KITTY_CONFIG_DIRECTORY)."""
    env = os.environ.get("KITTY_CONFIG_DIRECTORY")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".config" / "kitty"


def collect_themes(config_dir: Path) -> list[tuple[str, Path]]:
    """Collect all .conf theme files under config_dir, sorted by display name."""
    if not config_dir.is_dir():
        return []
    themes: list[tuple[str, Path]] = []
    seen_stems: set[str] = set()
    for path in sorted(config_dir.rglob("*.conf")):
        stem = path.stem
        if stem in seen_stems:
            continue
        seen_stems.add(stem)
        try:
            rel = path.relative_to(config_dir)
            display = f"{rel.parent / stem}" if rel.parent != Path(".") else stem
        except ValueError:
            display = stem
        themes.append((display, path))
    themes.sort(key=lambda t: t[0].lower())
    return themes


class ThemeSelectorApp(App[None]):
    """TUI to pick a kitty theme and apply it."""

    TITLE = "Kitty theme selector"
    SUB_TITLE = "↑/↓ move · Enter apply · / filter · q quit"
    CSS = """
    Screen {
        layout: vertical;
    }
    #theme-list {
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

    def __init__(self) -> None:
        super().__init__()
        self.themes: list[tuple[str, Path]] = []
        self._filtered: list[tuple[str, Path]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Filter themes...", id="search")
        yield VerticalScroll(
            ListView(id="theme-list"),
            id="list-container",
        )
        yield Static("", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        config_dir = get_kitty_config_dir()
        self.themes = collect_themes(config_dir)
        self._filtered = list(self.themes)
        await self._refresh_list()
        search = self.query_one("#search", Input)
        search.display = False

    async def _refresh_list(self) -> None:
        lv = self.query_one("#theme-list", ListView)
        await lv.clear()
        await lv.extend([
            ListItem(Label(display)) for display, _path in self._filtered
        ])

    def _apply_theme(self, path: Path, display: str) -> bool:
        # Prefer kitten (official remote-control binary); fall back to kitty
        last_err: str | None = None
        for cmd in (["kitten", "@", "set-colors", "-a", str(path)], ["kitty", "@", "set-colors", "-a", str(path)]):
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=30,
                    text=True,
                )
                if result.returncode == 0:
                    return True
                last_err = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                self.notify(
                    "Timed out waiting for kitty (try again or increase timeout)",
                    severity="error",
                    timeout=6,
                )
                return False
        self.notify(
            last_err or "Neither kitten nor kitty found in PATH",
            severity="error",
            timeout=6,
        )
        return False

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.index
        if idx < 0 or idx >= len(self._filtered):
            return
        display, path = self._filtered[idx]
        if self._apply_theme(path, display):
            self.notify(f"Applied: {display}", severity="information", timeout=2)
            status = self.query_one("#status", Static)
            status.update(f"Current: {display}")

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
            self._filtered = list(self.themes)
        else:
            self._filtered = [(d, p) for d, p in self.themes if query in d.lower()]
        self.run_worker(self._refresh_list())
        status = self.query_one("#status", Static)
        status.update(f"{len(self._filtered)} theme(s)")


def main() -> None:
    app = ThemeSelectorApp()
    app.run()


if __name__ == "__main__":
    main()
