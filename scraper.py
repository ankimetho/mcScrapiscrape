import os
import sys
import json
import urllib.request
import urllib.parse
from urllib.error import HTTPError
import xml.etree.ElementTree as ET
from xml.dom import minidom
import argparse
import time
import concurrent.futures
import threading

API_BASE = "https://www.screenscraper.fr/api2/"

# Map Screenscraper media types to ES-DE folder names
MEDIA_MAPPING = {
    "box-2D": ("covers", "png"),
    "box-3D": ("3dboxes", "png"),
    "screenmarquee": ("marquees", "png"),
    "mixrbv2": ("miximages", "png"),
    "ss": ("screenshots", "png")
}

def build_api_url(endpoint, params):
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return f"{API_BASE}{endpoint}?{query}"

def fetch_game_info(rom_name, devid, devpassword, softname, ssid, sspassword, systemeid=None):
    params = {
        "devid": devid,
        "devpassword": devpassword,
        "softname": softname,
        "ssid": ssid,
        "sspassword": sspassword,
        "romnom": rom_name,
        "output": "json"
    }
    if systemeid:
        params["systemeid"] = systemeid
        
    url = build_api_url("jeuInfos.php", params)
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data
    except HTTPError as e:
        if e.code == 430:
            print(f"  [!] HTTP 430: Quota exceeded or invalid credentials/softname for {rom_name}")
        elif e.code == 404:
            print(f"  [!] Game not found on Screenscraper: {rom_name}")
        elif e.code == 400:
            print(f"  [!] HTTP 400: Bad Request (Likely missing systemeid or invalid auth params) for {rom_name}")
        else:
            print(f"  [!] HTTP {e.code} for {rom_name}: {e.reason}")
        return None
    except Exception as e:
        print(f"  [!] Error fetching info for {rom_name}: {e}")
        return None


def download_media(media_url, out_path):
    try:
        req = urllib.request.Request(media_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with open(out_path, "wb") as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"      [!] Failed to download media {media_url}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Scrape from screenscraper.fr to ES-DE format.")
    parser.add_argument("--rom-dir", required=True, help="Path to directory containing ROMs.")
    parser.add_argument("--scrape-dir", required=True, help="Path to ES-DE downloaded_media directory.")
    parser.add_argument("--system", required=True, help="System name (e.g., snes).")
    parser.add_argument("--user", required=True, help="Screenscraper Username.")
    parser.add_argument("--password", required=True, help="Screenscraper Password.")
    parser.add_argument("--devid", required=True, help="Screenscraper Developer ID.")
    parser.add_argument("--devpassword", required=True, help="Screenscraper Developer Password.")
    parser.add_argument("--softname", default="mcScrapiscrape", help="Your software name registered with Screenscraper.")
    parser.add_argument("--gamelist-dir", default=None, help="Path to ES-DE gamelists directory to generate gamelist.xml.")
    parser.add_argument("--systemeid", default=None, help="Screenscraper system ID (e.g. 4 for SNES). Strongly recommended to avoid HTTP 400 errors.")
    parser.add_argument("--threads", type=int, default=6, help="Number of concurrent threads (default: 6).")

    args = parser.parse_args()

    rom_exts = (".zip", ".sfc", ".nes", ".md", ".bin", ".iso", ".chd", ".smc", ".fig", ".pce", ".pce-cd", ".32x", ".ngp", ".ngpc", ".pcf", ".pcf-cd")   
    roms = []
    if os.path.exists(args.rom_dir):
        for f in os.listdir(args.rom_dir):
            if f.lower().endswith(rom_exts):
                roms.append(f)
    else:
        print(f"ROM directory {args.rom_dir} does not exist.")
        sys.exit(1)

    print(f"Found {len(roms)} ROMs in {args.rom_dir}. Starting scrape with {args.threads} threads...\n")
    
    # Setup media directories
    sys_media_dir = os.path.join(args.scrape_dir, args.system)
    for folder, ext in MEDIA_MAPPING.values():
        os.makedirs(os.path.join(sys_media_dir, folder), exist_ok=True)
        
    # Filter ROMs down to only those that are missing media
    roms_to_scrape = []
    for rom_name in roms:
        base_name = os.path.splitext(rom_name)[0]
        missing_media = False
        
        for folder, ext in MEDIA_MAPPING.values():
            media_file = f"{base_name}.{ext}"
            out_path = os.path.join(sys_media_dir, folder, media_file)
            if not os.path.exists(out_path):
                missing_media = True
                break
                
        if missing_media:
            roms_to_scrape.append(rom_name)
            
    skipped_count = len(roms) - len(roms_to_scrape)
    if skipped_count > 0:
        print(f"Skipping {skipped_count} ROMs that already have all local media downloaded.")
        
    roms = roms_to_scrape
    
    # XML structure
    root = ET.Element("gameList")
    
    count = 0
    total_roms = len(roms)
    xml_lock = threading.Lock()
    print_lock = threading.Lock()

    def process_rom(rom_name):
        nonlocal count
        base_name = os.path.splitext(rom_name)[0]
        
        info = fetch_game_info(rom_name, args.devid, args.devpassword, args.softname, args.user, args.password, args.systemeid)
        
        with xml_lock:
            game_elem = ET.SubElement(root, "game")
            ET.SubElement(game_elem, "path").text = f"./{rom_name}"
            
        with print_lock:
            count += 1
            response_data = info.get("response", {}) if info else {}
            status = "Success" if (info and "jeu" in response_data) else "Not Found / Error"
            print(f"[{count}/{total_roms}] Processing {rom_name}... {status}")
            
        # If no info found, just save a basic stub
        if not info or "jeu" not in response_data:
            with xml_lock:
                ET.SubElement(game_elem, "name").text = base_name
            return
        
        jeu = response_data["jeu"]

        # Parse game info
        try:
            name = jeu.get("noms", [{}])[0].get("text", base_name)
        except:
            name = base_name
        
        try:
            desc = jeu.get("synopsis", [{}])[0].get("text", "")
        except:
            desc = ""

        try:
            releasedate = jeu.get("dates", [{}])[0].get("text", "")
            if releasedate and len(releasedate) == 10:
                releasedate = releasedate.replace("-", "") + "T000000"
        except:
            releasedate = ""

        try:
            developer = jeu.get("developpeur", {}).get("text", "")
        except:
            developer = ""

        try:
            publisher = jeu.get("editeur", {}).get("text", "")
        except:
            publisher = ""

        try:
            genre = jeu.get("genres", [{}])[0].get("noms", [{}])[0].get("text", "")
        except:
            genre = ""
            
        try:
            players = jeu.get("joueurs", {}).get("text", "1")
        except:
            players = "1"
            
        # Add properties to XML
        with xml_lock:
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
            
        # Download media
        try:
            medias = jeu.get("medias", [])
            for m in medias:
                m_type = m.get("type")
                if m_type in MEDIA_MAPPING:
                    folder, ext = MEDIA_MAPPING[m_type]
                    # Original formats from URL
                    orig_url = m.get("url", "")
                    if orig_url:
                        # Ensure we use correct auth for the media URL too!
                        parsed_url = urllib.parse.urlparse(orig_url)
                        qparams = urllib.parse.parse_qs(parsed_url.query)
                        if "ssid" not in qparams and args.user:
                            # Reconstruct media url
                            orig_url += f"&ssid={args.user}&sspassword={args.password}"
                            if args.devid:
                                orig_url += f"&devid={args.devid}&devpassword={args.devpassword}&softname={args.softname}"
                        
                        media_file = f"{base_name}.{ext}"
                        out_path = os.path.join(sys_media_dir, folder, media_file)
                        relative_es_path = f"../downloaded_media/{args.system}/{folder}/{media_file}"
                        
                        success = False
                        if not os.path.exists(out_path):
                            success = download_media(orig_url, out_path)
                            with print_lock:
                                if success:
                                    print(f"    - Downloaded {m_type}")
                        else:
                            success = True
                            
                        # Add node to gamelist
                        if success:
                            tag_mapping = {
                                "box-2D": "image",       # In ES-DE, covers go into <image>
                                "box-3D": "thumbnail",   # 3dboxes go into <thumbnail>
                                "screenmarquee": "marquee", # marquees into <marquee>
                            }
                            node_tag = tag_mapping.get(m_type)
                            if node_tag:
                                with xml_lock:
                                    ET.SubElement(game_elem, node_tag).text = relative_es_path
                                
        except Exception as e:
            with print_lock:
                print(f"  [!] Error parsing media for {rom_name}: {e}")

    # Process all roms currently in the directory using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        executor.map(process_rom, roms)

    # Save XML
    if args.gamelist_dir:
        gl_dir = os.path.join(args.gamelist_dir, args.system)
        os.makedirs(gl_dir, exist_ok=True)
        xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
        
        # Remove empty lines that minidom often adds
        xmlstr = '\n'.join([line for line in xmlstr.split('\n') if line.strip()])
        
        gl_path = os.path.join(gl_dir, "gamelist.xml")
        with open(gl_path, "w", encoding="utf-8") as f:
            f.write(xmlstr)
        print(f"\nSaved gamelist to {gl_path}")
    else:
        print("\nNo --gamelist-dir provided, skipping gamelist.xml generation.")
        
    print("Scraping complete!")

if __name__ == "__main__":
    main()
