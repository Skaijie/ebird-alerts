from functools import total_ordering
from location import *
from pathlib import Path
from typing import TypeAlias
import pandas as pd

sightingsDict: TypeAlias = dict[tuple[dt, Hotspot], int]
confirmation_status: dict = {0: "[U]", 1: "[C]"}
@total_ordering
class Species:
    def __init__(self, species_code: str, common_name: str, sci_name: str, need: set[str], parent: str | None=None):
        '''
        Creates a Species class for a bird species, as defined by eBird.
        
        :param species_code:
            The eBird-defined species code. This is typically fixed.
        :type species_code: str
        :param common_name:
            The eBird-defined common name. This is typically fixed.
        :type common_name: str
        :param sighting_detail: A dictionary of each sighting of the particular bird species.
            A sighting consists of the date (str) and location (Location) the species was sighted, 
            and whether the sighting is confirmed (int).
        :type sightings: set
        :type rare: list[str]
        :param need:
            Whether the bird is considered 'needed' (a.k.a. not on life-list) for the user.
        :type need: list[str]
        '''
        self.species_code: str = species_code
        self.common_name: str = common_name
        self.sci_name: str = sci_name
        self.parent: Optional[str] = parent
        self.sightings: dict = {}
        self.need = need
        self.ignore_need = False

    def check_region_need(self, region: str) -> Optional[bool]:
        return region in self.need
    def toggle_need(self, region: str, toggle: bool|None=None):
        if toggle is None:
            toggle = region not in self.need

        if toggle:
            self.need.add(region)
        else:
            self.need.discard(region)

    def get_need_prefix(self, region: Optional[str]=None) -> str:
        return "[N] " if ((not self.ignore_need) and
                         (region in self.need or
                          region is None and self.need)) else ""
    
    
    def str_locations(self) -> str:
        return '\n'.join([str(sighting) for sighting in self.sightings])
    
    def __gt__(self, other):
        if not isinstance(other, Species):
            return NotImplemented
        return self.sci_name > other.sci_name
    def __eq__(self, other) -> bool:
        if not isinstance(other, Species):
            return NotImplemented
        return (self.sci_name == other.sci_name and self.species_code == other.species_code)
    def __hash__(self):
        sci_name = getattr(self, 'sci_name', None)
        species_code = getattr(self, 'species_code', None)
        return hash((sci_name, species_code))
    def __str__(self):
        return f"{self.common_name} ({self.sci_name}, ID {self.species_code})\nNeed: {str(self.need)}\nIgnore need: {self.ignore_need}\nSightings: {self.str_locations()}"

speciesStore: TypeAlias = dict[str, Species]
# -------------------------
# Species parser functions
# -------------------------

def get_sighting_dates(species: Species) -> set[dt]:
    if not species.sightings:
        return set()
    return set([sighting.date for sighting in species.sightings])

def get_regions(species: Species) -> set:
    region_set = set()
    for sighting in species.sightings:
        region_set.add(sighting.location.region)
    return region_set

def map_names(target_store: speciesStore) -> tuple[speciesStore, speciesStore]:
    sci_lookup = {}
    name_lookup = {}
    for species in target_store.values():
        sci_lookup[species.sci_name.lower()] = species
        name_lookup[species.common_name.lower()] = species
    return sci_lookup, name_lookup

def species_alert_prename(species: Species, region: Optional[str]=None) -> str:
    return f"{species.get_need_prefix(region)}{species.common_name}: "
def filter_sightings(species: Species, target_date: Optional[dt]=None, region: Optional[str]=None, confirmed: bool=False) -> set:
    filtered_sightings: set = set()
    if not filtered_sightings:
        for sighting in species.sightings:
            if ((target_date and target_date != sighting.date) or
                (region and region != sighting.location.region) or
                (confirmed and not sighting.confirmed)):
                continue
            filtered_sightings.add(sighting)
    return filtered_sightings

def parse_excluded_species(lifer_sp_path: str, excluded_sp_path: str, name_lookup: speciesStore, sci_lookup: speciesStore):
    excluded_sp_sci_name = set(pd.read_csv(lifer_sp_path)["Scientific Name"].tolist())
    excluded_species = set()
    
    for sci_name in excluded_sp_sci_name:
        sci_lookup[sci_name].ignore_need = True
        excluded_species.add(sci_lookup[sci_name].common_name)
    
    for com_name in (Path(excluded_sp_path).read_text("utf-8").split("\n")):
        if com_name.lower() in name_lookup:
            name_lookup[com_name.lower()].ignore_need = True
            excluded_species.add(com_name)

def debug_species_store(species_store: speciesStore):
    for species in species_store.values():
        if species.sightings:
            print(f"{species.common_name} ({species.sci_name}) ({species.species_code})")
            print(f"Need regions: {str(species.need)}")
            print("Sightings:")
            for sighting in species.sightings:
                print(str(sighting))