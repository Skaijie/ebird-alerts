from species import Species, speciesStore
from location import Region, Hotspot, gen_location, region_list
from api_handlers import *
from initialisations import *
from typing import Tuple, Optional
from datetime import date as dt
from sighting import sightingStore
from json_handler import load_pkl
from sighting import gen_sighting, sightings_purge_old

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
            logger.debug(f"Added {str(sighting)}")
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

def parse_species_ebird(raw_sightings: dict[str, list[dict]],
                        species_dict: speciesStore,
                        predefined_hotspots_store: list[dict],
                        target_hotspot_store: list[Hotspot],
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
    for region, regional_sightings in raw_sightings.items():
        for obs in regional_sightings:
            species = species_dict[obs['speciesCode']]
            if (species.ignore_need):
                continue
            location = gen_location(obs['locName'], (obs['lat'], obs['lng']), region, predefined_hotspots_store, target_hotspot_store)
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
    
    logger.info("eBird parsing finished")
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
        if isinstance(offline_ebird := load_offline_ebird(region), dict):
            parse_species_ebird({region: [offline_ebird]}, target_alert_store, predefined_hotspots_store, target_hotspot_store, sightings_store)
    
    if (offline_gmail := load_offline_gmail(predefined_hotspots_store, target_hotspot_store, sightings_store, sci_lookup, config_data)):
        parse_species_gmail(
            parse_species_snippets(offline_gmail[0]),
            predefined_hotspots_store,
            target_hotspot_store,
            sightings_store,
            sci_lookup,
            config_data
        )

def get_ebird_data(regions: set[str], error_list: dict, config_data: configStore) -> dict[str, list[dict]]:
    '''
    Calls the API to retrieve bird sightings.
    Used for rares alert and recent observations.
    
    :param url: The URL of the API to call.
    :type url: str
    :param region: The region of which to get eBird data for.
    :type region: str
    :param target_file: The file of which sighting details will be written to.
    :type target_file: str
    '''
    all_ebird_sightings = {}

    for region in regions:
        rare_url = f"https://api.ebird.org/v2/data/obs/{region}/recent/notable?back={config_data['max_days']}&sppLocale=en_UK&includeProvisional=true"
        
        logger.info(f'Calling API for rare alerts in region [{region}]')
        regional_sightings = call_api_ebird(rare_url)
        if regional_sightings is False:
            error_list.setdefault("eBird", set()).add(region)
            logger.error(f"Could not load eBird regional data for {region}")
        else:
            all_ebird_sightings[region] = regional_sightings
            logger.info(f"Loaded eBird regional data for {region}")
    
    save_ebird_data(all_ebird_sightings)
    return all_ebird_sightings

def save_ebird_data(api_sightings: dict[str, list[dict]]):
    for region, regional_sightings in api_sightings.items():
        target_file = f"Raw eBird Data\\rare_obs_{region}.json"
        save_json(target_file, regional_sightings)
    
def process_gmail_data(predefined_hotspots_store: list[dict],
    target_hotspot_store: list[Hotspot],
    sightings_store,
    error_list: dict,
    sciname_map: speciesStore,
    config_data: configStore) -> set:
    if (gmail_sightings := call_api_gmail()):
        snippet_list = parse_species_snippets(gmail_sightings[0])
        notify_list = parse_species_gmail(snippet_list,
                predefined_hotspots_store, target_hotspot_store,
                sightings_store,
                sciname_map, config_data
        )
        set_timestamp_unix(gmail_sightings[1])
    else:
        error_list["Gmail"] = True
    
    return notify_list

def call_api_all(
    regions: set[str], target_alert_store: speciesStore,
    predefined_hotspots_store: list[dict],
    target_hotspot_store: list[Hotspot],
    sightings_store,
    error_list: dict,
    sciname_map: speciesStore,
    config_data: configStore) -> set:
    notify_store = set()
    all_ebird_api_sightings = get_ebird_data(regions, error_list, config_data)
    new_ebird_api_sightings = parse_species_ebird(all_ebird_api_sightings, target_alert_store, predefined_hotspots_store, target_hotspot_store, sightings_store)
    sightings_purge_old(sightings_store, all_ebird_api_sightings)
    new_gmail_sightings = process_gmail_data(predefined_hotspots_store, target_hotspot_store, sightings_store, error_list, sciname_map, config_data)
    new_sightings = new_ebird_api_sightings.union(new_gmail_sightings)
    return new_sightings