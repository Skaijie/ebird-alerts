import collections, logging
from initialisations import *

CONFIG_FILE = "@Resources\\Settings.inc"

config_data, regions_data = get_config(CONFIG_FILE)
log_init(config_data)
from api_handlers import *
from location import *
from species import Species as Sp, speciesStore, species_alert_prename, map_names
from parse_ebird_data import call_api_all
from sighting import sightingStore, sightings_purge_old, str_alert
from datetime import date as dt, datetime as dt2
from parse_taxonomy_file import taxonomy_to_obj

logger = logging.getLogger(__name__)

Time = collections.namedtuple("time_data", ("init_time", "init_date_str",
"alert_cutoff_time", "alert_cutoff_time_epoch",
"alert_cutoff_date", "alert_cutoff_date_str"))

# Output and text parse
def build_status_message(configs: configStore, is_night: int, error_flags: set|None=None):
    text_status = f"Synced {dt2.strftime(dt2.now(), '%d %b %Y %H:%M')}\n"
    if error_flags: text_status += "API error: " + ", ".join(error_flags) + "\n"
    
    if configs["debug"] == 1: text_status += "Debug mode on\n"
    elif configs["debug"] == 2: text_status += "Refreshed via VSCode\n"

    if is_night: text_status += f"Refresh rate: {configs['night_refresh_rate']} mins"
    else: text_status += f"Refresh rate: {configs['normal_refresh_rate']} mins"
    Path("api_status.txt").write_text(text_status, encoding="utf-8")

def status_message():
    pass

PATTERN_WRAPPER = re.compile(r"(\[[CU]\])|([\u4e00-\u9fff])|(\s)|(-)")
def wrap_text_with_correction(text: str, max_disp_chars: int) -> list[str]:
    """
    Splits text into lines based on display width corrections.
    Returns a list of strings.
    """
    newline_startidx = []
    
    for match in PATTERN_WRAPPER.finditer(text):
        if match.group(1): # Confirmation status found, use index of next char, correct width by -4
            newline_startidx.append((match.end(), match.start() - match.end()))
        elif match.group(2): # CJK found, correct width by 1
            newline_startidx.append((match.start(), 1))
        elif match.group(3): # Space found, use its index
            newline_startidx.append((match.start(), 0))
        else: # Hyphen found, use index of next char
            newline_startidx.append((match.end(), 0))

    # Wrapping logic
    lines = []
    line_start = 0
    line_end = 0
    char_length_correction = 0
    prev_correction = 0

    for match_end_idx, correction in newline_startidx:
        current_segment_len = match_end_idx - line_start
        if current_segment_len + char_length_correction > max_disp_chars:
            lines.append(text[line_start:line_end])
            line_start = line_end + (not bool(prev_correction))
        else:
            line_end = match_end_idx
            char_length_correction += correction
        prev_correction = correction

    # Append remaining text
    if line_start < len(text):
        lines.append(text[line_start:])
        
    return lines
def push_alert(sightings_store: set, is_notify: bool, region: Optional[str]=None):
    if sightings_store:
        sightings_formatted: (
            dict[
                dt, dict[ # Date: dict
                    Sp, list[str]]] # Species: list of locations
            ) = {}
        for sighting in sightings_store:
            location_string = str_alert(sighting)
            (sightings_formatted
            .setdefault(sighting.date, {})
            .setdefault(sighting.species, [])
            .append(location_string))
        if is_notify:
            alert_text = "New sightings\n"
        else:
            alert_text = ""
        for date, species_list in sorted(sightings_formatted.items(), reverse=True):
            alert_text += date.isoformat() + "\n"
            for species, locations in sorted(species_list.items(), key=lambda species: species[0]):
                locations_sorted = sorted(locations, key=lambda loc: (loc[-2]!="R"))
                alert_text += "\n".join(wrap_text_with_correction(species_alert_prename(species) + ", ".join(locations_sorted) + "\n", 58))
            alert_text += "\n"
    else: alert_text = ""
    alert_text = alert_text.strip()
    logger.debug(alert_text)
    if is_notify: Path("Notify\\notif.txt").write_text(alert_text, encoding="utf-8")
    else: Path(f"bird_alert_{region}.txt").write_text(alert_text, encoding="utf-8")

def setup_taxonomy() -> speciesStore:
    TAXO_FILE = "datasets\\eBird_taxonomy_v2025.csv"
    SPECIES_FILE = "datasets\\ebird_taxonomy.pkl"
    if not isinstance(species_dict := load_pkl(SPECIES_FILE), dict):
        species_dict = taxonomy_to_obj(TAXO_FILE, SPECIES_FILE)
    return species_dict

def setup_sightings() -> sightingStore:
    SIGHTINGS_FILE = "datasets\\sightings_list.pkl"
    if not isinstance(sightings_dict := load_pkl(SIGHTINGS_FILE), dict):
        sightings_dict = sightingStore()
    return sightings_dict

def debug_console(com_lookup: speciesStore):
    while True:
        user_input = input("Check data for (species/sighting/location): ").lower()
        if user_input == "species":
            species_input = input("Enter species name: ").lower()
            if species_input in com_lookup:
                print(str(com_lookup[species_input]))
            else: print("Could not find search term")
        elif user_input == "sighting":
            print("Not implemented yet, try another")
            continue
            '''date_input = input("Enter a date (YYYY-MM-DD): ")
            try: dt.fromisoformat(date_input)
            except Exception:
                print("Invalid date")
                continue
            species_input = input("Enter species name: ")
            if species_input in com_lookup:
                str(com_lookup[species_input])
            else:
                print("Could not find search term")
                continue'''
        elif user_input == "exit":
            sys.exit()

def main():
    start_time = dt2.now()
    HOTSPOTS_INIT_FILE = "datasets\\predefined_hotspots.json"
    HOTSPOTS_FILE = "datasets\\generated_hotspots.pkl"
    SIGHTINGS_FILE = "datasets\\sightings_list.pkl"
    '''SP_LIFER_FILE = "datasets\\ebird_world_life_list.csv"
    SP_EXCLUSION_FILE = "species_excluded.txt"'''
    logger.info("Initialising updater")
    status_night = chk_night_mode()                                     # Check night status
    status_connection = chk_connection(config_data)                     # Check connection
    hotspot_list = load_pkl(HOTSPOTS_FILE)                              # Load existing hotspots
    if not hotspot_list:
        hotspot_list = []
    com_name_map = None
    if status_connection:                                               # Prepare API status call
        build_status_message(config_data, status_night)                 # Update status
        errors = set()
        species_dict = setup_taxonomy()
        sightings_dict = setup_sightings()
        sightings_purge_old(sightings_dict, config_data)                # Delete "old" sightings
        (sci_name_map, com_name_map) = map_names(species_dict)
        """excluded_species = parse_excluded_species(
            SP_EXCLUSION_FILE, com_name_map, sci_name_map)              # Get excluded species"""
        predefined_hotspots = load_json(HOTSPOTS_INIT_FILE)
        logger.info("Starting API calls...")
        sightings_notification = call_api_all(                          # Call APIs
            regions_data, species_dict, predefined_hotspots, hotspot_list,
            sightings_dict, errors, sci_name_map, config_data
        )
        save_pkl(HOTSPOTS_FILE, hotspot_list)
        save_pkl(SIGHTINGS_FILE, sightings_dict)
        build_status_message(config_data, status_night, errors)          # Update API call status
        for region in regions_data:                                      # Generate alert text
            push_alert(set(sightings_dict.values()), False, region)
        push_alert(sightings_notification, True)                         # Generate notification text
    else:
        build_status_message(config_data, status_night)
    #debug_species(species_store)
    end_time = dt2.now()
    done = f'Done! Took {end_time - start_time}'
    logger.info(done)
    if com_name_map:
        debug_console(com_name_map)
    #show_loc_plot(get_gdf_generic(get_stn_df()), get_gdf_generic(get_hotspot_df(hotspot_list)))
    return done

if __name__ == "__main__":
    main()
    
'''
species
  common_name
  sci_name
  ebird_code
  parent
  need // for location.region
 
sighting
  datetime
  location
  confirmed
  rare // ebird-allocated

location
  name
  region
  coords (latlon)
  nearest_stn
'''
