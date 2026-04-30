from species import Species, speciesStore
from location import Region, Hotspot, gen_location, region_list
from api_handlers import *
from initialisations import *
from typing import Tuple, Optional
from datetime import date as dt
from sighting import sightingStore
from json_handler import load_pkl
from sighting import gen_sighting

logger = logging.getLogger(__name__)
DATE_RE = re.compile(r"Reported (.+?) by")
COORDS_RE = re.compile(r"(-?\d+[\.,]\d+)[ ,]+(-?\d+[\.,]\d+)")
SPECIES_RE = re.compile(r"\(([^)]+)\)")

def _parse_species_header(line: str, sci_lookup: speciesStore) -> Optional[Species]:
    line = line.lower()
    metadata = SPECIES_RE.findall(line)
    for segment in metadata:
        clean_seg = segment.strip()
        if clean_seg in sci_lookup:
            return sci_lookup[clean_seg]
    
    logger.error(f"Could not find species in line: {line}")
def _parse_date(line: str) -> Optional['dt']:
    if not (obs_date := DATE_RE.search(line)):
        logger.info(f"Could not find date: {line}")
        return
    try:
        date_str = obs_date.group(1)[:12] 
        return dt2.strptime(date_str, "%b %d, %Y").date()
    except ValueError:
        logger.info(f"Date parse failed for string: {line}")
def _parse_region(line: str, valid_regions: dict[str, Region]) -> Optional[str]:
    for region_code, region in valid_regions.items():
        if region.name in line:
            return region_code
    logger.info(f"Region not found: {line}")
def _parse_coords(line: str) -> Optional[Tuple[float, float]]:
    match = COORDS_RE.search(line)
    if match:
        return (float(match.group(1).strip()), float(match.group(2).strip()))
    
    logger.info(f"Could not find coords: {line}")
    return None
def _parse_checklist(line: str) -> Optional[str]:
    if ((index := line.rfind("S")) != -1):
        return line[index:]

def parse_species_gmail(
        snippets: list[list[str]], predefined_hotspots_store: list[dict], hotspots_store: list[Hotspot], sightings_store: sightingStore, sci_lookup: speciesStore, config_data: configStore) -> set:
    '''
    Takes in raw text data (list[str]) and parses a Species object.
    
    This is assumed to be formatted correctly, else an error will be thrown.
    '''
    notify_list = set()
    for snip in snippets:
        try:
            name_line, date_line, loc_line, coords_line, checklist_line = snip[:5]
            loc_line = loc_line[2:]
        except ValueError:
            logger.error(f"Snippet does not have enough lines: {snip}")
            continue
        if (not
            (
                (species := _parse_species_header(name_line, sci_lookup)) and
                (date := _parse_date(date_line)) and
                (region := _parse_region(loc_line, region_list)) and
                (coords := _parse_coords(coords_line)) and
                (checklist := _parse_checklist(checklist_line))
            )
        ):
            logger.warning("Could not parse for the following snippet:\n" + "\n".join(snip))
            continue
        elif species.ignore_need: continue
        if date < (dt2.today().date() - timedelta(days=7)):
            logger.info("Skipped a sighting older than the cutoff date:\n" + "\n".join(snip))
            continue
        confirmed = ("CONFIRMED" in name_line)
        loc = gen_location(loc_line, coords, region, predefined_hotspots_store, hotspots_store)
        species.need.add(region)
        if (sighting := gen_sighting(species, date, loc, confirmed, checklist, None, sightings_store)):
            notify_list.add(sighting)
    return notify_list
      
def load_offline_gmail(predefined_hotspots_store: list[dict], target_hotspot_store: list[Hotspot], sightings_store, sci_lookup: speciesStore, config_data: configStore):
    mail_store = "email_bodies.pkl"
    try:
        raw_mail_data = load_pkl(mail_store)
        if not raw_mail_data:
            return
        snippets_data = parse_species_snippets(raw_mail_data)
        parse_species_gmail(snippets_data, predefined_hotspots_store, target_hotspot_store, sightings_store, sci_lookup, config_data)
    except Exception as e:
        logger.error(e)

def parse_species_ebird(sightings_raw: list,
                        species_dict: speciesStore,
                        predefined_store: list[dict],
                        target_hotspot_store: list[Hotspot],
                        region: str,
                        sightings_store: sightingStore
    ) -> set:
    '''
    Calls the API to retrieve bird sightings.
    Used for rares alert and recent observations.

    :param all_sightings: The list of recent sightings to input.
    :type all_sightings: list
    :param target_store: Where all species are stored.
    :type target_store: speciesStore
    :param assume_rare: Whether to assume the species is rare (for rare alert).
    :type assume_rare: bool
    :param chk_dupe: Whether to assume that the species is a duplicate of an existing one in the list (for recent sightings).
    :type chk_dupe: bool
    '''
    logger.info("Parsing data...")
    new_sightings = set()
    for obs in sightings_raw:
        species = species_dict[obs['speciesCode']]
        if (species.ignore_need):
            continue
        location = gen_location(obs['locName'], (obs['lat'], obs['lng']), region, predefined_store, target_hotspot_store)
        if (sighting := gen_sighting(
            species,
            dt.fromisoformat(obs['obsDt'][:10]),
            location,
            obs['obsReviewed'],
            obs['subId'],
            True,
            sightings_store
        )):
            new_sightings.add(sighting)
        
    logger.info(f"eBird parsing finished for {region}")
    return new_sightings

def load_offline_all(
    regions: set[str],
    target_alert_store: speciesStore,
    predefined_hotspots_store: list[dict],
    target_hotspot_store: list[Hotspot],
    sightings_store: sightingStore,
    sci_lookup: speciesStore,
    config_data: configStore):
    for region in regions:
        if (offline_ebird := load_offline_ebird(region)):
            parse_species_ebird(offline_ebird, target_alert_store, predefined_hotspots_store, target_hotspot_store, region, sightings_store)
    
    if (offline_gmail := load_offline_gmail(predefined_hotspots_store, target_hotspot_store, sightings_store, sci_lookup, config_data)):
        parse_species_gmail(
            parse_species_snippets(offline_gmail[0]),
            predefined_hotspots_store,
            target_hotspot_store,
            sightings_store,
            sci_lookup,
            config_data
        )

def call_api_all(
    regions: set[str], target_alert_store: speciesStore,
    predefined_hotspots_store: list[dict],
    target_hotspot_store: list[Hotspot],
    sightings_store,
    error_list: set,
    sciname_map: speciesStore,
    config_data: configStore) -> set:
    notify_store = set()
    for region in regions:
        if (raw_sightings := call_api_ebird_rare(region, str(config_data["max_days"]))):
            notify_store = parse_species_ebird(
                raw_sightings,
                target_alert_store, predefined_hotspots_store, target_hotspot_store,
                region, sightings_store
            )
        else:
            error_list.add(f"eBird {region}")
    
    if (gmail_data := call_api_gmail()):
        snippet_list = parse_species_snippets(gmail_data[0])
        notify_store = notify_store.union(
            parse_species_gmail(snippet_list,
                predefined_hotspots_store, target_hotspot_store,
                sightings_store,
                sciname_map, config_data
            )
        )
        set_timestamp_unix(gmail_data[1])
    else:
        error_list.add("Gmail API")
    return notify_store