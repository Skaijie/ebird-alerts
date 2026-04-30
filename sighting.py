from species import Species as Sp, speciesStore
from datetime import date as dt
from location import Location as Loc
from api_handlers import call_api_ebird
from typing import Optional, TypeAlias
from datetime import datetime as dt2, timedelta
from initialisations import configStore
import logging

logger = logging.getLogger(__name__)

class Sighting:
    def __init__(self, species: Sp, sci_name: str, date: dt, location: Loc, confirmed: int, checklist: str, rare_sighting: Optional[bool] = None) -> None:
        self.species: Sp = species
        self.species_name: str = sci_name
        self.date: dt = date
        self.location: Loc = location
        self.confirmed = confirmed
        self.checklist: str = checklist
        self.rare_sighting: Optional[bool] = rare_sighting
        self.chash = self.species_name.rstrip(" ") + self.location.name
    
    def str_confirmed(self, alert: bool=False) -> str:
        if not self.confirmed: return ""
        if alert: return "[C]"
        return "confirmed"
    def str_rare(self, alert: bool=False) -> str:
        if not self.rare_sighting: return ""
        if alert: return "[R]"
        return "rare"
    def str_sighting_stats(self) -> str:
        if (stats := f"({'/'.join((self.str_confirmed(), self.str_rare()))}) "):
            return stats
        return ""
    
    def __eq__(self, other):
        return (self.species_name == other.species_name and self.date == other.date and self.location == other.location)
    def __hash__(self):
        species_name = getattr(self, 'species_name', None)
        date = getattr(self, 'date', None)
        location = getattr(self, 'location', None)
        return hash((species_name, date, location))
    def __str__(self):
        return f"{self.str_sighting_stats()}{self.species.common_name} reported at {str(self.location)} on {self.date.strftime('%Y-%m-%d')}"
    
notifStore: TypeAlias = set[Sighting]
sightingStore: TypeAlias = dict[str, Sighting]

def str_alert(sighting: Sighting) -> str:
    """Generates a location text snippet.

    Args:
        sighting (Sighting): The sighting to process.

    Returns:
        str: A string in the following format:
        location_name [R][C]
    """
    return f"{sighting.location.name} {sighting.str_rare(True)}{sighting.str_confirmed(True)}".strip()

def fmt_species_sighting_date(sightings: set) -> dict[str, dict[dt, str]]:
    sighting_strings: dict[str, dict[dt, str]] = {}
    for sighting in sightings:
        region = sighting.location.region
        date = sighting.date
        string = sighting_strings.setdefault(region, {}).setdefault(date, "")
        if string:
            sighting_strings[region][date] += ", "
        sighting_strings[region][date] += str_alert(sighting)
    
    return sighting_strings


def validate_sighting(sighting: Sighting, config_store: configStore, validation_store: dict[str, list[dict]]) -> bool:
    """
    Checks whether a sighting still exists in eBird via an API call.
    This is useful for checking if a sighting was removed and the same should be done in the widget database.

    Args:
        sighting (Sighting): The sighting to validate.

    Returns:
        bool: Returns True if the sighting was found in eBird, otherwise returns False.
    """
    species_code = sighting.species.species_code
    if species_code in validation_store:
        ebird_data = validation_store[species_code]
    else:
        if "max_days" not in config_store:
            config_store["max_days"] = 7 # default
        species_url = f"https://api.ebird.org/v2/data/obs/{sighting.location.region}/recent/{sighting.species.species_code}?back={config_store['max_days']}&includeProvisional=true"
        ebird_data = call_api_ebird(species_url)
        if ebird_data:
            print(ebird_data)
            validation_store[species_code] = ebird_data
    if ebird_data:
        logger.debug("Existing sightings:\n" + str(ebird_data))
        for ebird_sighting in ebird_data:
            if sighting.checklist == ebird_sighting["subId"]:
                return True
    return False

def gen_sighting(species: Sp, date: dt, location: Loc, confirmed: int, checklist: str, rare_sighting: Optional[bool], sighting_list: sightingStore) -> Optional[Sighting]:
    """Generates a Sighting object.

    Args:
        species (Sp): The species for which to add a sighting for.
        date (dt): The sighting date.
        location (Loc): Where the sighting occurred.
        confirmed (int): Whether the sighting was reviewed by eBird and confirmed.
        checklist (str): The eBird checklist ID.
        rare_sighting (Optional[bool]): Whether the sighting is considered rare.
        sighting_list (list[Sighting]): The list of sightings (for all species) to add this sighting to.

    Returns:
        Optional[Sighting]: The sighting itself if one was generated.
    """
    if (species_chash := (species.sci_name.rstrip(" ") + location.name)) in sighting_list:
        existing_sighting = sighting_list[species_chash]
        logging.info(f"Found an identical sighting at {str(existing_sighting.location)}")
        if confirmed:
            sighting_list[species_chash].confirmed = True
        
        return
    sighting = Sighting(species, species.sci_name, date, location, confirmed, checklist, rare_sighting)
    sighting_list[species_chash] = sighting
    species.sightings[species_chash] = sighting
    return sighting

def del_condemned_sightings(condemned_sightings: set[Sighting], sightings_store: sightingStore):
    for sighting in condemned_sightings:
        sp = sighting.species
        del sp.sightings[sighting.chash]
        del sightings_store[sighting.chash]

def del_sighting_multi(species: Optional[Sp], date: Optional[dt], location: Optional[Loc], sightings_store: sightingStore):
    if not (species or date or location):
        logging.error("At least one parameter must be specified")
        return
    condemned_sightings: set[Sighting] = set()
    if species:
        if (date and location):
            for sighting in species.sightings:
                if (sighting.date == date and sighting.location == location):
                    condemned_sightings = {sighting}
                    break
        elif date:
            condemned_sightings = {sighting for sighting in species.sightings if sighting.date == date}
        elif location:
            condemned_sightings = {sighting for sighting in species.sightings if sighting.location == location}
    elif date:
        condemned_sightings = {sighting for sighting in sightings_store.values() if sighting.date == date}
    elif location:
        condemned_sightings = {sighting for sighting in sightings_store.values() if sighting.location == location}
    
    del_condemned_sightings(condemned_sightings, sightings_store)

def sightings_purge_old(sightings_store: sightingStore, config_store: configStore):
    condemned_sightings: set[Sighting] = set()
    validation_store = {}
    for sighting in sightings_store.values():
        if (sighting.date < (dt2.now() - timedelta(days=7)).date() or
            (not sighting.confirmed and not validate_sighting(sighting, config_store, validation_store))):
            condemned_sightings.add(sighting)
    
    del_condemned_sightings(condemned_sightings, sightings_store)

def main():
    data = call_api_ebird(f"https://api.ebird.org/v2/data/obs/geo/recent/whbyuh1?lat=1.4095070&lng=103.9888647477404&back=14&includeProvisional=true")
    print(data)

if __name__ == "__main__":
    main()
    
'''
Species
    comName
    sciName
    eID
    need = set of regions
    sightings = set()
    
Sighting
UFDS by date
    Sp = species
    dt = date
    Loc = location
    bool = confirmed
    str = checklist
    Optional[bool] = rare_sighting
'''