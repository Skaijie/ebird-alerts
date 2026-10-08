from initialisations import configStore
from species import Species as Sp, speciesStore
from datetime import date as dt
from location import Location as Loc
from api_handlers import call_api_ebird
from typing import Optional, TypeAlias
from datetime import datetime as dt2, timedelta
import logging

logger = logging.getLogger(__name__)

class Sighting:
    def __init__(self, species: Sp, sci_name: str, date: dt, location: Loc, confirmed: int, checklist: str, rare_sighting: Optional[bool] = None) -> None:
        """_Represents sightings on eBird, with some special cases._

        Args:
            species (Sp): _The species code (based on eBird)_
            sci_name (str): _The species's scientific name (based on eBird)_
            date (dt): _The date the sighting was recorded. If two sightings share the same species, location, and date, they will be merged together._
            location (Loc): _Where the sighting was recorded._
            confirmed (int): _Whether the sighting was confirmed, with the following ruleset:_
        
                -1: The sighting was not found in eBird, and is pending removal from the local database. This should never exist if the widget is not refreshing.

                0: The sighting is not confirmed.

                1: The sighting is confirmed.

                2: The sighting does not have a confirmation status; it is not a rare sighting.
            
            checklist (str): _The checklist ID (based on eBird)_
            rare_sighting (Optional[bool], optional): _Whether this is a rare sighting. Defaults to None (i.e. false)._
        """
        self.species: Sp = species
        self.species_name: str = sci_name
        self.date: dt = date
        self.location: Loc = location
        self.confirmed = confirmed
        self.checklist: str = checklist
        self.rare_sighting: Optional[bool] = rare_sighting
        self.chash = self.species_name.rstrip(" ") + self.location.name + self.date.isoformat()
    
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
    return (sighting.location.name + " "
            + sighting.str_rare(True)
            + sighting.str_confirmed(True))

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

def validate_sighting(sighting: Sighting, config: configStore) -> bool:
    """
    Checks whether a sighting still exists in eBird.
    This is useful for checking if a sighting was removed and the same should be done in the widget database.

    Args:
        sighting (Sighting): The sighting to validate.

    Returns:
        bool: Returns True if the sighting was found in eBird, otherwise returns False.
    """
    recent_obs_url = f"https://api.ebird.org/v2/data/obs/{sighting.location.region}/recent/{sighting.species}?back={config['AlertHistoryDays']}"
    reference_sightings = call_api_ebird(recent_obs_url)
    if not reference_sightings: # list is empty = no sightings found, or API call failed
        return True
    
    for existing_sighting in reference_sightings:
        if existing_sighting["subId"] == sighting.checklist and existing_sighting["speciesCode"] == sighting.species.species_code:
            return True
    
    return False # not found in eBird

def gen_sighting(species: Sp, date: dt, location: Loc, confirmed: int, checklist: str, is_rare: bool, sighting_list: sightingStore) -> Optional[Sighting]:
    """Generates a Sighting object.

    Args:
        species (Sp): The species for which to add a sighting for.
        date (dt): The sighting date.
        location (Loc): Where the sighting occurred.
        confirmed (int): Whether the sighting was reviewed by eBird and confirmed.
        checklist (str): The eBird checklist ID.
        is_rare (bool): Whether the sighting is considered rare.
        sighting_list (list[Sighting]): The list of sightings (for all species) to add this sighting to.

    Returns:
        Optional[Sighting]: The sighting itself if one was generated.
    """
    species_chash = species.sci_name.rstrip(" ") + location.name + date.isoformat()
    if species_chash in sighting_list:
        existing_sighting = sighting_list[species_chash]
        logging.info(f"Found an identical sighting at {str(existing_sighting.location)}")
        if confirmed:
            sighting_list[species_chash].confirmed = confirmed # Update existing sighting to true if any sighting confirmed for that date
        return
    
    sighting = Sighting(species, species.sci_name, date, location, confirmed, checklist, is_rare)
    sighting_list[species_chash] = sighting
    species.sightings[species_chash] = sighting
    return sighting

def del_condemned_sightings(condemned_sightings: set[Sighting], sightings_store: sightingStore):
    for sighting in condemned_sightings:
        sighting.species.sightings.pop(sighting.chash, None)
        sightings_store.pop(sighting.chash, None)

def del_sighting_multi(sightings_store: sightingStore, species: Optional[Sp], date: Optional[dt], location: Optional[Loc]):
    if not (species or date or location):
        logging.error("At least one parameter must be specified")
        return
    
    if (date and location) and not species:
        logging.error("Date and location cannot be specified together without species")
        return
    
    search = species.sightings.values() if species else sightings_store.values()

    condemned_sightings: set[Sighting] = set()

    for sighting in search:
        if (date and sighting.date != date) or (location and sighting.location != location):
            continue
        condemned_sightings.add(sighting)
        if species and date and sighting:
            break
    else: # iterated through all sightings without finding a target
        logging.warning("No sighting with the given parameters found.")

    del_condemned_sightings(condemned_sightings, sightings_store)

def sightings_purge_old(sightings_store: sightingStore, config: configStore):
    condemned_sightings: set[Sighting] = set()
    for sighting in sightings_store.values():
        if (
            sighting.date < (dt2.now() - timedelta(days=7)).date()
            or (
                sighting.rare_sighting
                and not sighting.confirmed
                and not validate_sighting(sighting, config)
                )
            ):
            condemned_sightings.add(sighting)
    
    del_condemned_sightings(condemned_sightings, sightings_store)

def main():
    data = call_api_ebird(f"https://api.ebird.org/v2/data/obs/geo/recent/whbyuh1?lat=1.4095070&lng=103.9888647477404&back=14&includeProvisional=true")
    print(data)

if __name__ == "__main__":
    main()