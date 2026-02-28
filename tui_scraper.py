import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import concurrent.futures
import threading
import json
import sys

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll, Vertical, Center
from textual.screen import ModalScreen
from textual.widgets import (
    Header,
    Footer,
    Input,
    Button,
    Log,
    ProgressBar,
    Label,
    Static,
    Select,
    SelectionList,
    DataTable,
)
from textual.widgets.selection_list import Selection
from textual import work
from textual.worker import get_current_worker

# Import our scraper logic and mapping to avoid duplication
from scraper import fetch_game_info, download_media, MEDIA_MAPPING


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def load_esde_systems():
    mapping = {}
    try:
        path = resource_path("systems.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        short, full = line.split(":", 1)
                        # Normalize: lowercase and remove all non-alphanumeric
                        clean_full = "".join(c for c in full.lower() if c.isalnum())
                        mapping[clean_full] = short.strip().lower()
    except Exception:
        pass
    return mapping


class ConfigPanel(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Vertical(id="config-sidebar"):
            # ── Scrape actions ──────────────────────────────────────────
            yield Static(" ▶  SCRAPE ACTIONS ", classes="section-header")
            yield Static("Batch or Fix modes", classes="section-desc")
            with Horizontal(id="main-actions"):
                yield Button("▶ START", id="start-btn", variant="success")
                yield Button("⚙ FIX", id="fix-btn", variant="warning")
                yield Button("■ STOP", id="stop-btn", variant="error", disabled=True)

            # ── Credentials ─────────────────────────────────────────────
            yield Static(" ☁  API CREDENTIALS ", classes="section-header")
            yield Static("Screenscraper Account & Dev Info", classes="section-desc")
            yield Input(placeholder="SS Username", id="user")
            yield Input(placeholder="SS Password", password=True, id="password")
            yield Input(placeholder="Developer ID", id="devid")
            yield Input(placeholder="Developer Password", password=True, id="devpassword")

            # ── Folders ──────────────────────────────────────────────────
            yield Static(" 📁  FOLDERS ", classes="section-header")
            yield Static("ROM & Media paths", classes="section-desc")
            yield Input(placeholder="Root ROMs Dir", id="rom-dir")
            yield Input(placeholder="Media Dir", id="scrape-dir")
            yield Input(placeholder="Gamelists Dir (Opt)", id="gamelist-dir")

            # ── Performance ──────────────────────────────────────────────
            yield Static(" ⚡  PERFORMANCE ", classes="section-header")
            yield Static("Thread count", classes="section-desc")
            with Horizontal(id="thread-config"):
                yield Input(value="6", placeholder="Threads", id="threads", type="integer")

class SelectionPanel(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Vertical(id="selection-sidebar"):
            # ── Utility actions ──────────────────────────────────────────
            yield Static(" ⚒  UTILITIES ", classes="section-header")
            yield Static("Audit & Config", classes="section-desc")
            with Horizontal(id="utility-actions"):
                yield Button("⊕ DETECT", id="detect-btn")
                yield Button("✔ CHECK", id="check-btn")
                yield Button("↓ SAVE", id="save-btn")
                yield Button("↑ LOAD", id="load-btn")

            yield Static(" 🎮  SYSTEMS ", classes="section-header")
            yield Static("Select systems", classes="section-desc")
            
            with Horizontal(classes="selection-actions"):
                yield Button("SELECT ALL", id="select-all-systems", variant="default")
                yield Button("DESELECT ALL", id="deselect-all-systems", variant="default")
            
            system_selections = []
            esde_map = load_esde_systems()
            try:
                path = resource_path("screenscraper_system_ids.json")
                with open(path, "r") as f:
                    systems_data = json.load(f)
                    for name_raw, eid in sorted(systems_data.items()):
                        def clean(s):
                            return "".join(c for c in s.lower() if c.isalnum())
                        display_name = name_raw.title()
                        name_clean = clean(name_raw)
                        es_short = esde_map.get(name_clean)
                        # ... mapping logic ... (reusing existing)
                        if not es_short:
                            for prefix in ["nintendo", "sega", "sony", "atari", "commodore", "nec", "snk", "bandai"]:
                                if esde_map.get(prefix + name_clean):
                                    es_short = esde_map.get(prefix + name_clean)
                                    break
                        if not es_short:
                            for prefix in ["nintendo", "sega", "sony", "atari", "commodore", "nec", "snk", "bandai"]:
                                if name_clean.startswith(prefix):
                                    if esde_map.get(name_clean[len(prefix):]):
                                        es_short = esde_map.get(name_clean[len(prefix):])
                                        break
                        if name_clean == "megadrive":
                            es_short = "megadrive"
                        if name_clean == "supernintendo":
                            es_short = "snes"
                        if name_clean == "gamecube":
                            es_short = "gc"
                        if name_clean == "playstation":
                            es_short = "psx"
                        
                        label = f"{display_name}" + (f" [{es_short}]" if es_short else "")
                        val = f"{eid}|{es_short or name_raw.lower()}"
                        system_selections.append(Selection(label, val, False))
            except Exception:
                pass
            yield SelectionList(*system_selections, id="systems-list")

            # ── Media types ──────────────────────────────────────────────
            yield Static(" 🖼  MEDIA ", classes="section-header")
            yield Static("Choose assets", classes="section-desc")

            with Horizontal(classes="selection-actions"):
                yield Button("SELECT ALL", id="select-all-media", variant="default")
                yield Button("DESELECT ALL", id="deselect-all-media", variant="default")
            media_names = {
                "box-2D": "Box 2D", "box-3D": "Box 3D", "screenmarquee": "Marquee",
                "mixrbv2": "Mix Image", "ss": "Screenshot", "video": "Video",
                "wheel": "Wheel", "fanart": "Fan-Art", "manual": "Manual"
            }
            media_selections = [
                Selection(media_names.get(m, m), m, m in ["box-2D", "ss", "screenmarquee"])
                for m in MEDIA_MAPPING.keys()
            ]
            yield SelectionList(*media_selections, id="media-list")


class ConfigWizard(ModalScreen):
    """A centered modal for initial configuration."""

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="wizard-card"):
                yield Label(" 🚀  mcScrapiscrape INITIAL SETUP ", id="wizard-title")
                yield Label(
                    "It looks like you're starting fresh. Please provide your core settings to begin.",
                    id="wizard-desc",
                )

                with VerticalScroll(id="wizard-inputs"):
                    yield Label(" Screenscraper Credentials ", classes="wiz-section-label")
                    yield Input(placeholder="Screenscraper Username", id="wiz-user")
                    yield Input(
                        placeholder="Screenscraper Password", password=True, id="wiz-password"
                    )
                    yield Input(placeholder="Developer ID", id="wiz-devid")
                    yield Input(
                        placeholder="Developer Password",
                        password=True,
                        id="wiz-devpassword",
                    )

                    yield Label(" Folder Paths ", classes="wiz-section-label")
                    yield Input(
                        placeholder="Root ROMs Dir (e.g. D:\\ROMs\\)", id="wiz-rom-dir"
                    )
                    yield Input(
                        placeholder="Media Dir (e.g. D:\\ES-DE\\downloaded_media)", id="wiz-scrape-dir"
                    )

                with Horizontal(id="wizard-actions"):
                    yield Button("SAVE & START", variant="success", id="wiz-save-btn")
                    yield Button("SKIP", variant="default", id="wiz-skip-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "wiz-save-btn":
            # Pass data back or just dismiss with a signal
            self.dismiss(True)
        else:
            self.dismiss(False)


class TuiScraperApp(App):
    CSS = """
    Screen {
        background: $surface;
    }

    /* ── Columns ── */
    ConfigPanel {
        width: 25%;
        background: $surface;
        border-right: tall $primary;
        padding: 0 1;
    }

    #log-container {
        width: 50%;
        padding: 1;
        background: $surface;
    }

    SelectionPanel {
        width: 25%;
        background: $surface;
        border-left: tall $primary;
        padding: 0 1;
    }

    /* ── Core Styles ── */
    .section-header {
        width: 1fr;
        height: 1;
        content-align: left middle;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 0 1;
        margin: 1 0 0 0;
    }

    .section-desc {
        width: 1fr;
        height: auto;
        color: $text-muted;
        text-style: italic;
        padding: 0 1;
        margin: 0 0 1 0;
    }

    #main-actions, #utility-actions, #thread-config, .selection-actions {
        height: auto;
        width: 1fr;
        margin: 0 0 1 0;
    }

    .selection-actions Button {
        height: 1;
        min-width: 0;
        margin: 0;
        border: none;
        background: $surface;
        text-style: underline;
    }
    .selection-actions Button:hover {
        background: $primary;
        color: $text;
    }

    Button {
        width: 1fr;
        min-width: 0;
        margin: 0 0;
        height: 3;
    }

    Input {
        margin: 0 0 1 0;
        border: tall $primary;
        height: 3;
    }

    SelectionList {
        height: 1fr;
        min-height: 10;
        border: tall $primary;
        margin-bottom: 1;
    }

    #systems-list {
        height: 18;
    }
    #media-list {
        height: 12;
    }

    /* ── Main Panel ── */
    #progress-area {
        height: auto;
        border: thick $primary;
        padding: 1;
        margin-bottom: 1;
        background: $boost;
    }

    #thread-container {
        height: 10;
        border: solid $accent;
        padding: 0 1;
        margin-bottom: 1;
        background: $surface;
    }

    Log {
        border-top: heavy $primary;
        background: $surface;
        height: 1fr;
    }

    DataTable {
        height: 10;
        border: thick $accent;
        margin-top: 1;
        background: $boost;
        display: none;
    }
    DataTable.visible {
        display: block;
    }

    /* ── Wizard Styles ── */
    ConfigWizard {
        align: center middle;
    }
    #wizard-card {
        width: 70;
        height: auto;
        max-height: 40;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #wizard-title {
        width: 1fr;
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $primary;
        color: $text;
        margin-bottom: 1;
    }
    #wizard-desc {
        color: $text-muted;
        text-align: center;
        height: auto;
        margin-bottom: 1;
    }
    .wiz-section-label {
        margin-top: 1;
        text-style: bold;
        color: $accent;
    }
    #wizard-inputs {
        height: auto;
        max-height: 25;
        border: solid $primary 20%;
        padding: 0 1;
    }
    #wizard-actions {
        margin-top: 2;
        height: 3;
    }
    #wizard-actions Button {
        width: 1fr;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            yield ConfigPanel()
            with Vertical(id="log-container"):
                with Vertical(id="progress-area"):
                    yield Label("Overall Scrape Progress")
                    yield ProgressBar(id="progress", show_eta=True)

                yield Label("⚙ Live Thread Activity")
                with VerticalScroll(id="thread-container"):
                    pass

                yield Label("📋 Console Log")
                yield Log(id="log_view", highlight=True)

                yield Label("📊 Audit Summary", id="table-label", classes="hidden")
                yield DataTable(id="audit_table")
            yield SelectionPanel()
        yield Footer()

    def on_mount(self):
        self.log_view = self.query_one("#log_view", Log)
        self.progress_bar = self.query_one("#progress", ProgressBar)
        self.xml_lock = threading.Lock()
        self.title = "mcScrapiscrape TUI"
        self.sub_title = "Press 'q' to quit"

        # Auto-run startup logic
        self.call_after_refresh(self.check_initial_config)

    def check_initial_config(self) -> None:
        """Handles first-run wizard or automatic loading and auditing."""
        if not os.path.exists("config.json"):
            # Show Wizard and handle result via callback
            self.push_screen(ConfigWizard(), callback=self.handle_wizard_result)
        else:
            self.load_config_file()
            self.run_startup_tasks()

    def handle_wizard_result(self, result: bool) -> None:
        """Called when the wizard is dismissed."""
        if result:
            # Wizard was saved, copy values from wizard to main UI
            # Note: The wizard screen is still accessible during dismissal callback
            wizard_screen = self.query_one(ConfigWizard)
            self.query_one("#user", Input).value = wizard_screen.query_one("#wiz-user", Input).value
            self.query_one("#password", Input).value = wizard_screen.query_one("#wiz-password", Input).value
            self.query_one("#devid", Input).value = wizard_screen.query_one("#wiz-devid", Input).value
            self.query_one("#devpassword", Input).value = wizard_screen.query_one("#wiz-devpassword", Input).value
            self.query_one("#rom-dir", Input).value = wizard_screen.query_one("#wiz-rom-dir", Input).value
            self.query_one("#scrape-dir", Input).value = wizard_screen.query_one("#wiz-scrape-dir", Input).value
            
            # Save it now
            self.save_config_file()
            self.run_startup_tasks()
        else:
            self.log_view.write_line("[!] Wizard skipped. Please configure manually.")

    def run_startup_tasks(self) -> None:
        """Runs the automated detect and check tasks."""
        self.auto_detect_systems()
        self.run_check_media_worker()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-btn":
            await self.start_scraping()
        elif event.button.id == "stop-btn":
            self.stop_scraping()
        elif event.button.id == "detect-btn":
            self.auto_detect_systems()
        elif event.button.id == "check-btn":
            self.run_check_media_worker()
        elif event.button.id == "fix-btn":
            await self.start_scraping(fix_mode=True)
        elif event.button.id == "save-btn":
            self.save_config_file()
        elif event.button.id == "load-btn":
            self.load_config_file()
        elif event.button.id == "select-all-systems":
            self.query_one("#systems-list", SelectionList).select_all()
        elif event.button.id == "deselect-all-systems":
            self.query_one("#systems-list", SelectionList).deselect_all()
        elif event.button.id == "select-all-media":
            self.query_one("#media-list", SelectionList).select_all()
        elif event.button.id == "deselect-all-media":
            self.query_one("#media-list", SelectionList).deselect_all()

    def auto_detect_systems(self):
        rom_dir = self.get_input_value("rom-dir")
        if not rom_dir or not os.path.exists(rom_dir):
            self.log_view.write_line("[!] Please enter a valid Base ROM Directory first.")
            return

        try:
            subdirs = [d.lower() for d in os.listdir(rom_dir) if os.path.isdir(os.path.join(rom_dir, d))]
            if not subdirs:
                self.log_view.write_line("[!] No subdirectories found in ROM directory.")
                return

            widget = self.query_one("#systems-list", SelectionList)
            found_count = 0
            
            # SelectionList values are "eid|es_short"
            for option in widget._options:
                val = option.value
                if "|" in val:
                    _, es_short = val.split("|", 1)
                    if es_short.lower() in subdirs:
                        widget.select(val)
                        found_count += 1
            
            if found_count > 0:
                self.log_view.write_line(f"[*] Auto-detected and selected {found_count} systems matching your folders.")
            else:
                self.log_view.write_line("[!] No system folders matching ES-DE names were found.")
        except Exception as e:
            self.log_view.write_line(f"[!] Error during auto-detection: {e}")

    def stop_scraping(self):
        self.log_view.write_line("[!] Stopping scrape...")
        for worker in self.workers:
            worker.cancel()
        self.query_one("#stop-btn", Button).disabled = True

    def get_input_value(self, id: str):
        try:
            widget = self.query_one(f"#{id}")
            if isinstance(widget, Select):
                val = widget.value
                return str(val) if val != Select.BLANK and val is not None else ""
            if isinstance(widget, SelectionList):
                return widget.selected
            return widget.value.strip()
        except Exception:
            return ""

    def save_config_file(self):
        config_data = {
            "rom-dir": self.get_input_value("rom-dir"),
            "scrape-dir": self.get_input_value("scrape-dir"),
            "user": self.get_input_value("user"),
            "password": self.get_input_value("password"),
            "devid": self.get_input_value("devid"),
            "devpassword": self.get_input_value("devpassword"),
            "gamelist-dir": self.get_input_value("gamelist-dir"),
            "threads": self.get_input_value("threads"),
            "systems-list": self.get_input_value("systems-list"),
            "media-list": self.get_input_value("media-list"),
        }
        try:
            with open("config.json", "w") as f:
                json.dump(config_data, f, indent=4)
            self.log_view.write_line("Successfully saved config.json!")
        except Exception as e:
            self.log_view.write_line(f"[!] Error saving config: {e}")

    def load_config_file(self):
        if not os.path.exists("config.json"):
            return

        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)

            for key, val in config_data.items():
                try:
                    widget = self.query_one(f"#{key}")
                    if isinstance(widget, SelectionList):
                        widget.deselect_all()
                        for v in val:
                            try:
                                widget.select(v)
                            except Exception:
                                pass
                    else:
                        widget.value = str(val)
                except Exception:
                    pass
            self.log_view.write_line("Successfully loaded config.json!")
        except Exception as e:
            self.log_view.write_line(f"[!] Error loading config.json: {e}")

    async def start_scraping(self, fix_mode=False):
        rom_dir = self.get_input_value("rom-dir")
        scrape_dir = self.get_input_value("scrape-dir")
        user = self.get_input_value("user")
        password = self.get_input_value("password")
        devid = self.get_input_value("devid")
        devpassword = self.get_input_value("devpassword")
        gamelist_dir = self.get_input_value("gamelist-dir")
        threads_str = self.get_input_value("threads")
        
        selected_eids = self.get_input_value("systems-list")
        selected_media = self.get_input_value("media-list")

        # Validation
        if not all([rom_dir, scrape_dir, user, password, devid, devpassword]):
            self.log_view.write_line(
                "[!] Please fill in all required fields (Credentials, ROM Dir, Media Dir)."
            )
            return
        
        if not selected_eids:
            self.log_view.write_line("[!] Please select at least one system to scrape.")
            return

        threads = int(threads_str) if threads_str.isdigit() else 6

        # Disable UI
        for inp in self.query(Input):
            inp.disabled = True
        for sel in self.query(SelectionList):
            sel.disabled = True
        self.query_one("#start-btn", Button).disabled = True
        if self.query("#fix-btn"):
            self.query_one("#fix-btn", Button).disabled = True
        self.query_one("#stop-btn", Button).disabled = False

        self.log_view.clear()

        # Setup thread widgets
        thread_container = self.query_one("#thread-container")
        await thread_container.remove_children()
        for i in range(threads):
            lbl = Static(
                f"Thread {i + 1}: Idle", id=f"thread-{i}", classes="thread-status"
            )
            thread_container.mount(lbl)

        # Parse the combined values (eid|es_short)
        systems_to_scrape = []
        for val in selected_eids:
            if "|" in val:
                parts = val.split("|", 1)
                eid = parts[0]
                es_short = parts[1]
                systems_to_scrape.append({"name": es_short, "eid": eid})
            else:
                systems_to_scrape.append({"name": val, "eid": val})

        if not systems_to_scrape:
            self.log_view.write_line("[!] Please select at least one system to scrape.")
            return

        mode_text = "FIX" if fix_mode else "BATCH"
        self.log_view.write_line(f"Starting {mode_text} scrape for {len(systems_to_scrape)} systems...")

        self.run_scrape_worker(
            rom_dir,
            scrape_dir,
            systems_to_scrape,
            user,
            password,
            devid,
            devpassword,
            selected_media,
            gamelist_dir,
            threads,
            fix_mode=fix_mode
        )

    @work(exclusive=True, thread=True)
    def run_scrape_worker(
        self,
        base_rom_dir,
        scrape_dir,
        systems,
        user,
        password,
        devid,
        devpassword,
        selected_media_types,
        gamelist_dir,
        threads,
        fix_mode=False
    ):
        worker = get_current_worker()

        rom_exts = (
            ".nes", ".nez", ".fc", ".fds", ".sfc", ".smc", ".fig", ".z64", ".v64", ".n64",
            ".gb", ".gbc", ".gba", ".nds", ".dsi", ".srl", ".3ds", ".cci", ".rvz", ".wua", ".vb",
            ".md", ".smd", ".gen", ".32x", ".sms", ".gg", ".gdi", ".cdi", ".pbp", ".cso", ".vpk", ".psvita",
            ".j64", ".jag", ".abs", ".cof", ".lnx", ".a26", ".a52", ".a78", ".ws", ".wsc", ".pce", ".sgx",
            ".ngp", ".ngc", ".d64", ".prg", ".tap", ".t64", ".hdi", ".fdi", ".d98", ".dim", ".hdm", ".d88",
            ".dat", ".iso", ".bin", ".cue", ".img", ".chd", ".ccd", ".nrg", ".mds", ".zip", ".7z", ".rar",
            ".lha", ".ips", ".ups", ".bps", ".xdelta", ".rom", ".bin",
        )

        all_systems_roms = []
        for sys_info in systems:
            s_name = sys_info["name"]
            s_eid = sys_info["eid"]
            s_rom_dir = os.path.join(base_rom_dir, s_name)

            if not os.path.exists(s_rom_dir):
                # Try the direct base_rom_dir if it's only one system or if the folder name doesn't match
                if len(systems) == 1:
                    s_rom_dir = base_rom_dir
                else:
                    self.call_from_thread(
                        self.log_view.write_line,
                        f"[!] Warning: ROM directory {s_rom_dir} not found. Skipping {s_name}.",
                    )
                    continue

            roms = [f for f in os.listdir(s_rom_dir) if f.lower().endswith(rom_exts)]
            if not roms:
                continue

            sys_media_dir = os.path.join(scrape_dir, s_name)
            # Create directories only for selected media
            try:
                for m_type in selected_media_types:
                    if m_type in MEDIA_MAPPING:
                        folder, ext = MEDIA_MAPPING[m_type]
                        os.makedirs(os.path.join(sys_media_dir, folder), exist_ok=True)
            except Exception as e:
                self.call_from_thread(
                    self.log_view.write_line, f"[!] Error creating directories for {s_name}: {e}"
                )
                continue

            # Load existing gamelist for audit if in fix mode
            games_with_metadata = set()
            if fix_mode:
                gamelist_path = os.path.join(gamelist_dir or scrape_dir, s_name, "gamelist.xml")
                if os.path.exists(gamelist_path):
                    try:
                        tree = ET.parse(gamelist_path)
                        for game in tree.findall("game"):
                            path_node = game.find("path")
                            desc_node = game.find("desc")
                            if path_node is not None and desc_node is not None:
                                text = (desc_node.text or "").strip()
                                if text:
                                    r_name = os.path.basename(path_node.text).lower()
                                    games_with_metadata.add(r_name)
                    except Exception:
                        pass

            # Filtering logic
            roms_to_scrape = []
            for rom_name in roms:
                if worker.is_cancelled:
                    break
                base_name = os.path.splitext(rom_name)[0]
                
                # Check media
                missing_media = False
                for m_type in selected_media_types:
                    if m_type in MEDIA_MAPPING:
                        folder, ext = MEDIA_MAPPING[m_type]
                        out_path = os.path.join(sys_media_dir, folder, f"{base_name}.{ext}")
                        if not os.path.exists(out_path):
                            missing_media = True
                            break
                
                # In FIX mode, we check metadata too
                should_scrape = missing_media
                if fix_mode and not should_scrape:
                    if rom_name.lower() not in games_with_metadata:
                        should_scrape = True
                
                # In START (FULL) mode, we currently act as "smart" (only missing)
                # If the user wants a true "FORCE", we could add a mode for that.
                # For now, START is "Missing Media" and FIX is "Missing Media OR Metadata".
                
                if should_scrape:
                    roms_to_scrape.append((rom_name, s_name, s_eid, s_rom_dir, sys_media_dir))

            all_systems_roms.extend(roms_to_scrape)
            if worker.is_cancelled:
                break

        if not all_systems_roms:
            self.call_from_thread(
                self.log_view.write_line, "No ROMs found to scrape across all selected systems!"
            )
            self.call_from_thread(self.reset_ui)
            return

        self.call_from_thread(
            self.log_view.write_line, f"Found {len(all_systems_roms)} ROMs to scrape in total."
        )
        self.call_from_thread(self.setup_progress, len(all_systems_roms))

        # Prepare system groups (load existing or create new)
        system_groups = {}
        effective_gl_dir = gamelist_dir or scrape_dir
        for sys_info in systems:
            s_name = sys_info["name"]
            gl_path = os.path.join(effective_gl_dir, s_name, "gamelist.xml")
            if os.path.exists(gl_path):
                try:
                    tree = ET.parse(gl_path)
                    system_groups[s_name] = tree.getroot()
                except Exception:
                    system_groups[s_name] = ET.Element("gameList")
            else:
                system_groups[s_name] = ET.Element("gameList")

        completed = 0
        total_tasks = len(all_systems_roms)

        def update_progress():
            nonlocal completed
            completed += 1
            self.call_from_thread(self.progress_bar.advance, 1)
            if completed % 10 == 0:
                save_all_gamelists(silent=True)

        def save_all_gamelists(silent=False):
            effective_gl_dir = gamelist_dir or scrape_dir
            with self.xml_lock:
                for s_name, root_elem in system_groups.items():
                    gl_dir = os.path.join(effective_gl_dir, s_name)
                    os.makedirs(gl_dir, exist_ok=True)
                    xmlstr = minidom.parseString(ET.tostring(root_elem)).toprettyxml(indent="  ")
                    # Clean up empty lines from prettyxml
                    xmlstr = "\n".join([line for line in xmlstr.split("\n") if line.strip()])
                    gl_path = os.path.join(gl_dir, "gamelist.xml")
                    with open(gl_path, "w", encoding="utf-8") as f:
                        f.write(xmlstr)
                    if not silent:
                        safe_log(f"Saved gamelist for {s_name} to {gl_path}")

        def safe_log(msg):
            self.call_from_thread(self.log_view.write_line, msg)

        def update_thread_status(thread_idx, text, active=True):
            try:
                def modify_lbl():
                    lbl = self.query_one(f"#thread-{thread_idx}", Static)
                    lbl.update(f"Thread {thread_idx + 1}: {text}")
                    if active:
                        lbl.add_class("active")
                    else:
                        lbl.remove_class("active")
                self.call_from_thread(modify_lbl)
            except Exception:
                pass

        thread_assignment_lock = threading.Lock()
        thread_pool_registry = {}
        next_thread_idx = 0

        def get_thread_display_idx():
            nonlocal next_thread_idx
            tid = threading.get_ident()
            with thread_assignment_lock:
                if tid not in thread_pool_registry:
                    thread_pool_registry[tid] = next_thread_idx % threads
                    next_thread_idx += 1
                return thread_pool_registry[tid]

        def process_rom_task(task_info):
            if worker.is_cancelled:
                return

            rom_name, system_name, system_eid, rom_path, media_path = task_info
            t_idx = get_thread_display_idx()
            update_thread_status(t_idx, f"[{system_name}] {rom_name}")

            base_name = os.path.splitext(rom_name)[0]
            info = fetch_game_info(
                rom_name, devid, devpassword, "mcScrapiscrape",
                user, password, system_eid
            )

            with self.xml_lock:
                root = system_groups[system_name]
                # Avoid duplicates: find existing game entry by path
                game_elem = None
                search_paths = [f"./{rom_name}", rom_name, f".\\{rom_name}"]
                for g in root.findall("game"):
                    p_node = g.find("path")
                    if p_node is not None and p_node.text in search_paths:
                        game_elem = g
                        break
                
                if game_elem is None:
                    game_elem = ET.SubElement(root, "game")
                    ET.SubElement(game_elem, "path").text = f"./{rom_name}"
                else:
                    # Clear existing metadata if we're doing a fresh fetch
                    # Note: We keep path and any unique metadata if needed, 
                    # but usually it's cleaner to refresh major tags.
                    for tag in ["name", "desc", "releasedate", "developer", "publisher", "genre", "players", "rating"]:
                        existing = game_elem.find(tag)
                        if existing is not None:
                            game_elem.remove(existing)

            response_data = info.get("response", {}) if info else {}
            status = "Success" if (info and "jeu" in response_data) else "Not Found / Error"
            safe_log(f"[{completed + 1}/{total_tasks}] [{system_name}] {rom_name}... {status}")

            if not info or "jeu" not in response_data:
                with self.xml_lock:
                    ET.SubElement(game_elem, "name").text = base_name
                update_progress()
                return

            jeu = response_data["jeu"]

            # Metadata extraction
            def get_text(d, keys, default=""):
                curr = d
                for k in keys:
                    if isinstance(curr, list) and isinstance(k, int):
                        if k < len(curr):
                            curr = curr[k]
                        else:
                            return default
                    elif isinstance(curr, dict) and k in curr:
                        curr = curr[k]
                    else:
                        return default
                return curr if isinstance(curr, str) else default

            name = get_text(jeu, ["noms", 0, "text"], base_name)
            desc = get_text(jeu, ["synopsis", 0, "text"], "")
            releasedate = get_text(jeu, ["dates", 0, "text"], "")
            if releasedate and len(releasedate) == 10:
                releasedate = releasedate.replace("-", "") + "T000000"
            elif releasedate and len(releasedate) == 4:
                releasedate = releasedate + "0101T000000"

            developer = get_text(jeu, ["developpeur", "text"], "")
            publisher = get_text(jeu, ["editeur", "text"], "")
            genre = get_text(jeu, ["genres", 0, "noms", 0, "text"], "")
            players = get_text(jeu, ["joueurs", "text"], "1")
            rating_raw = get_text(jeu, ["note", "text"], "0")
            rating = str(float(rating_raw) / 20.0) if rating_raw.replace(".", "").isdigit() else "0"

            with self.xml_lock:
                ET.SubElement(game_elem, "name").text = name
                ET.SubElement(game_elem, "desc").text = desc
                if releasedate:
                    ET.SubElement(game_elem, "releasedate").text = releasedate
                if developer:
                    ET.SubElement(game_elem, "developer").text = developer
                if publisher:
                    ET.SubElement(game_elem, "publisher").text = publisher
                if genre:
                    ET.SubElement(game_elem, "genre").text = genre
                if players:
                    ET.SubElement(game_elem, "players").text = str(players)
                if rating != "0":
                    ET.SubElement(game_elem, "rating").text = rating

            # Media download
            try:
                medias = jeu.get("medias", [])
                tag_mapping = {
                    "box-2D": "image", "box-3D": "thumbnail", "screenmarquee": "marquee",
                    "video": "video", "wheel": "marquee", "fanart": "fanart",
                    "ss": "image"
                }
                
                for m in medias:
                    m_type = m.get("type")
                    if m_type in selected_media_types and m_type in MEDIA_MAPPING:
                        folder, ext = MEDIA_MAPPING[m_type]
                        orig_url = m.get("url", "")
                        if not orig_url:
                            continue

                        # Auth for media URL
                        if "ssid=" not in orig_url and user:
                            sep = "&" if "?" in orig_url else "?"
                            orig_url += f"{sep}ssid={user}&sspassword={password}"
                            if devid:
                                orig_url += f"&devid={devid}&devpassword={devpassword}&softname=mcScrapiscrape"

                        media_file = f"{base_name}.{ext}"
                        out_path = os.path.join(media_path, folder, media_file)
                        relative_es_path = f"../downloaded_media/{system_name}/{folder}/{media_file}"

                        success = False
                        if not os.path.exists(out_path):
                            success = download_media(orig_url, out_path)
                            if success:
                                safe_log(f"    - [{system_name}] Downloaded {m_type} for {base_name}")
                        else:
                            success = True

                        if success:
                            node_tag = tag_mapping.get(m_type)
                            if node_tag:
                                with self.xml_lock:
                                    if game_elem.find(node_tag) is None:
                                        ET.SubElement(game_elem, node_tag).text = relative_es_path
            except Exception as e:
                safe_log(f"  [!] Error parsing media for {rom_name}: {e}")

            update_progress()
            update_thread_status(t_idx, "Idle", active=False)

        if not worker.is_cancelled:
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                executor.map(process_rom_task, all_systems_roms)

        # Save all gamelists
        if not worker.is_cancelled:
            save_all_gamelists()

        safe_log("\nScraping complete!")
        for i in range(threads):
            try:
                self.call_from_thread(
                    lambda idx=i: self.query_one(f"#thread-{idx}", Static).update(f"Thread {idx + 1}: Finished")
                )
            except Exception:
                pass
        self.call_from_thread(self.reset_ui)

    @work(exclusive=True, thread=True)
    def run_check_media_worker(self):
        base_rom_dir = self.get_input_value("rom-dir")
        scrape_dir = self.get_input_value("scrape-dir")
        gamelist_dir = self.get_input_value("gamelist-dir")
        selected_eids = self.get_input_value("systems-list")
        selected_media_types = self.get_input_value("media-list")

        if not all([base_rom_dir, scrape_dir]):
            self.call_from_thread(self.log_view.write_line, "[!] Please provide at least Base ROM and Media directories.")
            return

        if not selected_eids:
            self.call_from_thread(self.log_view.write_line, "[!] Please select systems to check.")
            return

        systems = []
        for val in selected_eids:
            if "|" in val:
                _, es_short = val.split("|", 1)
                systems.append(es_short)
            else:
                systems.append(val)

        self.call_from_thread(self.log_view.clear)
        self.call_from_thread(self.log_view.write_line, f"[*] Auditing {len(systems)} systems...\n")

        # Prepare table
        def setup_table():
            table = self.query_one("#audit_table", DataTable)
            table.add_class("visible")
            table.clear(columns=True)
            table.add_columns("System", "Total", "Miss Media", "Miss Desc", "No Gamelist")
            return table

        self.call_from_thread(setup_table)

        rom_exts = (".nes", ".sfc", ".smc", ".n64", ".gb", ".gbc", ".gba", ".nds", ".3ds", ".iso", ".bin", ".cue", ".chd", ".pbp", ".zip", ".7z")

        for s_name in systems:
            self.call_from_thread(self.log_view.write_line, f"--- [{s_name}] ---")
            s_rom_dir = os.path.join(base_rom_dir, s_name)
            
            stats = {"total": 0, "miss_media": 0, "miss_desc": 0, "no_gamelist": 0}

            if not os.path.exists(s_rom_dir):
                self.call_from_thread(self.log_view.write_line, f"  [!] ROM folder not found: {s_rom_dir}")
                self.call_from_thread(lambda: self.query_one("#audit_table", DataTable).add_row(s_name, "N/A", "N/A", "N/A", "N/A"))
                continue

            roms = [f for f in os.listdir(s_rom_dir) if f.lower().endswith(rom_exts)]
            if not roms:
                self.call_from_thread(self.log_view.write_line, "  [!] No ROMs found.")
                self.call_from_thread(lambda: self.query_one("#audit_table", DataTable).add_row(s_name, "0", "0", "0", "0"))
                continue

            stats["total"] = len(roms)

            # Load gamelist if exists
            gamelist_path = os.path.join(gamelist_dir or scrape_dir, s_name, "gamelist.xml")
            games_metadata = {}
            if os.path.exists(gamelist_path):
                try:
                    tree = ET.parse(gamelist_path)
                    for game in tree.findall("game"):
                        path_node = game.find("path")
                        if path_node is not None and path_node.text:
                            r_name = os.path.basename(path_node.text).lower()
                            games_metadata[r_name] = {
                                "has_desc": bool((game.findtext("desc") or "").strip()),
                                "has_rating": bool((game.findtext("rating") or "").strip()),
                            }
                except Exception as e:
                    self.call_from_thread(self.log_view.write_line, f"  [!] Error reading gamelist: {e}")

            missing_total = 0
            for rom in roms:
                base_name = os.path.splitext(rom)[0]
                status_msgs = []
                
                # Check media
                m_missing = False
                for m_type in selected_media_types:
                    if m_type in MEDIA_MAPPING:
                        folder, ext = MEDIA_MAPPING[m_type]
                        m_path = os.path.join(scrape_dir, s_name, folder, f"{base_name}.{ext}")
                        if not os.path.exists(m_path):
                            status_msgs.append(f"Missing {m_type}")
                            m_missing = True
                
                if m_missing:
                    stats["miss_media"] += 1

                # Check metadata
                meta = games_metadata.get(rom.lower())
                if not meta:
                    status_msgs.append("No Gamelist Entry")
                    stats["no_gamelist"] += 1
                else:
                    if not meta["has_desc"]:
                        status_msgs.append("Missing Description")
                        stats["miss_desc"] += 1
                
                if status_msgs:
                    self.call_from_thread(self.log_view.write_line, f"  [!] {rom}: {', '.join(status_msgs)}")
                    missing_total += 1
            
            # Update table row
            self.call_from_thread(
                lambda s=s_name, st=stats: self.query_one("#audit_table", DataTable).add_row(
                    s, str(st["total"]), str(st["miss_media"]), str(st["miss_desc"]), str(st["no_gamelist"])
                )
            )

            if missing_total == 0:
                self.call_from_thread(self.log_view.write_line, "  [+] All ROMs have complete media and metadata!")
            else:
                self.call_from_thread(self.log_view.write_line, f"\n  [!] Total incomplete ROMs for {s_name}: {missing_total}")

        self.call_from_thread(self.log_view.write_line, "\nAudit Complete!")

    def setup_progress(self, total):
        self.progress_bar.total = total
        self.progress_bar.progress = 0

    def reset_ui(self):
        for widget in self.query(Input):
            widget.disabled = False
        for widget in self.query(Select):
            widget.disabled = False
        for widget in self.query(SelectionList):
            widget.disabled = False
        self.query_one("#start-btn", Button).disabled = False
        self.query_one("#fix-btn", Button).disabled = False
        self.query_one("#stop-btn", Button).disabled = True


if __name__ == "__main__":
    app = TuiScraperApp()
    app.run()
