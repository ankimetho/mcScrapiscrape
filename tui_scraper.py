import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import concurrent.futures
import threading
import urllib.parse
import json

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll, Vertical
from textual.widgets import Header, Footer, Input, Button, Log, ProgressBar, Label, Static
from textual import work
from textual.worker import Worker, get_current_worker

# Import our scraper logic and mapping to avoid duplication
from scraper import fetch_game_info, download_media, MEDIA_MAPPING

class ScraperConfigForm(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Horizontal(id="action-buttons"):
            yield Button("Start Scrape", id="start-btn", variant="success")
            yield Button("Save Config", id="save-btn", variant="primary")
            yield Button("Load Config", id="load-btn")
        
        yield Label("Screenscraper API Credentials")
        yield Input(placeholder="Screenscraper Username", id="user")
        yield Input(placeholder="Screenscraper Password", password=True, id="password")
        yield Input(placeholder="Developer ID", id="devid")
        yield Input(placeholder="Developer Password", password=True, id="devpassword")
        
        yield Label("Scrape Settings")
        yield Input(placeholder="System Name (e.g., snes, psx)", id="system")
        yield Input(placeholder="System ID (e.g., 4)", id="systemeid")
        yield Input(value="6", placeholder="Threads", id="threads", type="integer")
        
        yield Label("Directories")
        yield Input(placeholder="ROM Directory (e.g., /path/to/roms/snes)", id="rom-dir")
        yield Input(placeholder="ES-DE Downloaded Media Directory", id="scrape-dir")
        yield Input(placeholder="ES-DE Gamelists Directory (Optional)", id="gamelist-dir")

class TuiScraperApp(App):
    CSS = """
    Screen {
        layout: horizontal;
    }
    ScraperConfigForm {
        width: 1fr;
        padding: 1;
        border-right: solid green;
    }
    #log-container {
        width: 2fr;
        padding: 1;
    }
    Input {
        margin-bottom: 1;
    }
    Label {
        padding-bottom: 1;
        text-style: bold;
        color: $accent;
    }
    #progress {
        margin-bottom: 1;
    }
    #thread-container {
        height: auto;
        border: solid gray;
        margin-bottom: 1;
        padding: 1;
        background: $boost;
    }
    .thread-status {
        width: 1fr;
        color: $text;
        text-style: dim;
    }
    .thread-status.active {
        color: $success;
        text-style: none;
    }
    #action-buttons {
        height: auto;
        margin-bottom: 1;
    }
    #action-buttons Button {
        margin-right: 1;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit")
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            yield ScraperConfigForm()
            with Vertical(id="log-container"):
                yield Label("Overall Progress")
                yield ProgressBar(id="progress", show_eta=True)
                yield Label("Active Threads")
                with VerticalScroll(id="thread-container"):
                    pass # We will populate this dynamically based on thread count
                yield Log(id="log_view", highlight=True)
        yield Footer()

    def on_mount(self):
        self.log_view = self.query_one("#log_view", Log)
        self.progress_bar = self.query_one("#progress", ProgressBar)
        self.xml_lock = threading.Lock()
        self.title = "mcScrapiscrape TUI"
        self.sub_title = "Press 'q' to quit"
        
        # Auto-load config on startup
        self.call_after_refresh(self.load_config_file)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-btn":
            await self.start_scraping()
        elif event.button.id == "save-btn":
            self.save_config_file()
        elif event.button.id == "load-btn":
            self.load_config_file()

    def get_input_value(self, id: str) -> str:
        try:
            return self.query_one(f"#{id}", Input).value.strip()
        except:
            return ""

    def save_config_file(self):
        config_data = {
            "rom-dir": self.get_input_value("rom-dir"),
            "scrape-dir": self.get_input_value("scrape-dir"),
            "system": self.get_input_value("system"),
            "user": self.get_input_value("user"),
            "password": self.get_input_value("password"),
            "devid": self.get_input_value("devid"),
            "devpassword": self.get_input_value("devpassword"),
            "systemeid": self.get_input_value("systemeid"),
            "gamelist-dir": self.get_input_value("gamelist-dir"),
            "threads": self.get_input_value("threads")
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
                    self.query_one(f"#{key}", Input).value = str(val)
                except:
                    pass
            self.log_view.write_line("Successfully loaded config.json!")
        except Exception as e:
            self.log_view.write_line(f"[!] Error loading config.json: {e}")

    async def start_scraping(self):
        rom_dir = self.get_input_value("rom-dir")
        scrape_dir = self.get_input_value("scrape-dir")
        system = self.get_input_value("system")
        user = self.get_input_value("user")
        password = self.get_input_value("password")
        devid = self.get_input_value("devid")
        devpassword = self.get_input_value("devpassword")
        systemeid = self.get_input_value("systemeid")
        gamelist_dir = self.get_input_value("gamelist-dir")
        threads_str = self.get_input_value("threads")
        
        # Validation
        if not all([rom_dir, scrape_dir, system, user, password, devid, devpassword]):
            self.log_view.write_line("[!] Please fill in all required fields (Credentials, System, ROM Dir, Media Dir).")
            return

        threads = int(threads_str) if threads_str.isdigit() else 6
        
        # Disable UI
        for inp in self.query(Input):
            inp.disabled = True
        self.query_one("#start-btn", Button).disabled = True

        self.log_view.clear()
        
        # Setup thread widgets
        thread_container = self.query_one("#thread-container")
        await thread_container.remove_children()
        for i in range(threads):
            lbl = Static(f"Thread {i+1}: Idle", id=f"thread-{i}", classes="thread-status")
            thread_container.mount(lbl)
            
        self.log_view.write_line(f"Starting scrape for {system} in {rom_dir}...")
        
        self.run_scrape_worker(rom_dir, scrape_dir, system, user, password, devid, devpassword, systemeid, gamelist_dir, threads)

    @work(exclusive=True, thread=True)
    def run_scrape_worker(self, rom_dir, scrape_dir, system, user, password, devid, devpassword, systemeid, gamelist_dir, threads):
        worker = get_current_worker()

        rom_exts = (".zip", ".sfc", ".nes", ".md", ".bin", ".iso", ".chd", ".smc", ".fig", ".pce", ".pce-cd", ".32x", ".ngp", ".ngpc", ".pcf", ".pcf-cd")   
        roms = []
        if os.path.exists(rom_dir):
            for f in os.listdir(rom_dir):
                if f.lower().endswith(rom_exts):
                    roms.append(f)
        else:
            self.call_from_thread(self.log_view.write_line, f"[!] Error: ROM directory {rom_dir} does not exist.")
            self.call_from_thread(self.reset_ui)
            return

        self.call_from_thread(self.log_view.write_line, f"Found {len(roms)} ROMs total.")
        
        sys_media_dir = os.path.join(scrape_dir, system)
        try:
            for folder, ext in MEDIA_MAPPING.values():
                os.makedirs(os.path.join(sys_media_dir, folder), exist_ok=True)
        except Exception as e:
            self.call_from_thread(self.log_view.write_line, f"[!] Error creating directories: {e}")
            self.call_from_thread(self.reset_ui)
            return

        roms_to_scrape = []
        for rom_name in roms:
            base_name = os.path.splitext(rom_name)[0]
            missing_media = False
            for folder, ext in MEDIA_MAPPING.values():
                out_path = os.path.join(sys_media_dir, folder, f"{base_name}.{ext}")
                if not os.path.exists(out_path):
                    missing_media = True
                    break
            if missing_media:
                roms_to_scrape.append(rom_name)
                
        skipped = len(roms) - len(roms_to_scrape)
        if skipped > 0:
            self.call_from_thread(self.log_view.write_line, f"Skipping {skipped} ROMs that already have all local media downloaded.")
        
        if len(roms_to_scrape) == 0:
             self.call_from_thread(self.log_view.write_line, "All ROMs are fully scraped. Nothing to do!")
             self.call_from_thread(self.reset_ui)
             return

        self.call_from_thread(self.setup_progress, len(roms_to_scrape))
        
        root = ET.Element("gameList")
        
        completed = 0
        def update_progress():
            nonlocal completed
            completed += 1
            self.call_from_thread(self.progress_bar.advance, 1)

        def safe_log(msg):
            self.call_from_thread(self.log_view.write_line, msg)
            
        def update_thread_status(thread_idx, text, active=True):
            try:
                def modify_lbl():
                    lbl = app.query_one(f"#thread-{thread_idx}", Static)
                    lbl.update(f"Thread {thread_idx+1}: {text}")
                    if active:
                        lbl.add_class("active")
                    else:
                        lbl.remove_class("active")
                self.call_from_thread(modify_lbl)
            except:
                pass

        # Use an index to assign tasks to our visual "threads"
        thread_assignment_lock = threading.Lock()
        thread_pool_registry = {} # mapping thread ID to 0-based index
        next_thread_idx = 0
        
        def get_thread_display_idx():
            nonlocal next_thread_idx
            tid = threading.get_ident()
            with thread_assignment_lock:
                if tid not in thread_pool_registry:
                    thread_pool_registry[tid] = next_thread_idx
                    next_thread_idx += 1
                return thread_pool_registry[tid]

        def process_rom_task(rom_name):
            if worker.is_cancelled:
                return
            
            t_idx = get_thread_display_idx()
            update_thread_status(t_idx, f"Processing {rom_name}...")

            base_name = os.path.splitext(rom_name)[0]
            info = fetch_game_info(rom_name, devid, devpassword, "mcScrapiscrape", user, password, systemeid)
            
            with self.xml_lock:
                game_elem = ET.SubElement(root, "game")
                ET.SubElement(game_elem, "path").text = f"./{rom_name}"

            response_data = info.get("response", {}) if info else {}
            status = "Success" if (info and "jeu" in response_data) else "Not Found / Error"
            safe_log(f"[{completed+1}/{len(roms_to_scrape)}] Processing {rom_name}... {status}")

            if not info or "jeu" not in response_data:
                with self.xml_lock:
                    ET.SubElement(game_elem, "name").text = base_name
                update_progress()
                return
                
            jeu = response_data["jeu"]
            
            # Simple extraction blocks
            try: name = jeu.get("noms", [{}])[0].get("text", base_name)
            except: name = base_name

            try: desc = jeu.get("synopsis", [{}])[0].get("text", "")
            except: desc = ""

            try: 
                releasedate = jeu.get("dates", [{}])[0].get("text", "")
                if releasedate and len(releasedate) == 10:
                    releasedate = releasedate.replace("-", "") + "T000000"
            except: releasedate = ""

            try: developer = jeu.get("developpeur", {}).get("text", "")
            except: developer = ""

            try: publisher = jeu.get("editeur", {}).get("text", "")
            except: publisher = ""

            try: genre = jeu.get("genres", [{}])[0].get("noms", [{}])[0].get("text", "")
            except: genre = ""

            try: players = jeu.get("joueurs", {}).get("text", "1")
            except: players = "1"

            with self.xml_lock:
                ET.SubElement(game_elem, "name").text = name
                ET.SubElement(game_elem, "desc").text = desc
                if releasedate: ET.SubElement(game_elem, "releasedate").text = releasedate
                if developer: ET.SubElement(game_elem, "developer").text = developer
                if publisher: ET.SubElement(game_elem, "publisher").text = publisher
                if genre: ET.SubElement(game_elem, "genre").text = genre
                if players: ET.SubElement(game_elem, "players").text = str(players)

            try:
                medias = jeu.get("medias", [])
                for m in medias:
                    m_type = m.get("type")
                    if m_type in MEDIA_MAPPING:
                        folder, ext = MEDIA_MAPPING[m_type]
                        orig_url = m.get("url", "")
                        if orig_url:
                            parsed_url = urllib.parse.urlparse(orig_url)
                            qparams = urllib.parse.parse_qs(parsed_url.query)
                            if "ssid" not in qparams and user:
                                orig_url += f"&ssid={user}&sspassword={password}"
                                if devid:
                                    orig_url += f"&devid={devid}&devpassword={devpassword}&softname=mcScrapiscrape"
                            
                            media_file = f"{base_name}.{ext}"
                            out_path = os.path.join(sys_media_dir, folder, media_file)
                            relative_es_path = f"../downloaded_media/{system}/{folder}/{media_file}"
                            
                            success = False
                            if not os.path.exists(out_path):
                                success = download_media(orig_url, out_path)
                                if success:
                                    safe_log(f"    - Downloaded {m_type} for {base_name}")
                            else:
                                success = True
                                
                            if success:
                                tag_mapping = {
                                    "box-2D": "image",
                                    "box-3D": "thumbnail",
                                    "screenmarquee": "marquee",
                                }
                                node_tag = tag_mapping.get(m_type)
                                if node_tag:
                                    with self.xml_lock:
                                        ET.SubElement(game_elem, node_tag).text = relative_es_path
            except Exception as e:
                safe_log(f"  [!] Error parsing media for {rom_name}: {e}")

            update_progress()
            update_thread_status(t_idx, "Idle", active=False)

        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            executor.map(process_rom_task, roms_to_scrape)

        if gamelist_dir:
            gl_dir = os.path.join(gamelist_dir, system)
            os.makedirs(gl_dir, exist_ok=True)
            xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
            xmlstr = '\n'.join([line for line in xmlstr.split('\n') if line.strip()])
            
            gl_path = os.path.join(gl_dir, "gamelist.xml")
            with open(gl_path, "w", encoding="utf-8") as f:
                f.write(xmlstr)
            safe_log(f"\nSaved gamelist to {gl_path}")

        safe_log("\nScraping complete!")
        for i in range(threads):
            try:
                self.call_from_thread(lambda idx=i: app.query_one(f"#thread-{idx}", Static).update(f"Thread {idx+1}: Finished"))
            except:
                pass
        self.call_from_thread(self.reset_ui)

    def setup_progress(self, total):
        self.progress_bar.total = total
        self.progress_bar.progress = 0

    def reset_ui(self):
        for inp in self.query(Input):
            inp.disabled = False
        self.query_one("#start-btn", Button).disabled = False

if __name__ == "__main__":
    app = TuiScraperApp()
    app.run()
