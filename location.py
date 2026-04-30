from csv import DictReader
import numpy as np, pandas as pd, geopandas as gpd
import matplotlib.pyplot as plt
from geopy.distance import geodesic
from typing import TypeVar, Callable, Optional
from initialisations import *
from json_handler import *
import math

logger = logging.getLogger(__name__)

class Region:
    '''
    An eBird region.
    '''
    def __init__(self, code: str, name: str, metro_data: dict, location_regex_list: list[tuple[str, int]], handlers: list[Callable]):
        '''
        Creates an eBird region object.
        
        :param code: the eBird-defined region code (e.g. "SG").
        :type code: str
        :param name: The region name (e.g. "Singapore").
        :type name: str
        :param metro_data: Contains the station data for the region, if it has a metro system.
        :type metro_data: dict
        :param location_regex_list: A list of regex strings used to shorten the location name.
        :type location_regex_list: list[tuple[str, int]]
        :param handlers: Description
        :type handlers: list[Callable]
        '''
        self.code = code
        self.name = name
        self.metro_data = metro_data
        self.location_regex = location_regex_list
        self.handlers = handlers
    
    def get_country_code(self) -> str | None:
        if self.code:
            return self.code[:2]
        logger.error("Region code is empty")
    
    def __str__(self):
        return f"{self.code} ({self.name})"

def parse_region_json(region_file: str):
    region = load_json(region_file)
    pass

class Location:
    def __init__(self, name: str, coords: tuple[float, float], region: str):
        self.name: str = name
        self.coords: tuple[float, float] = coords
        self.region: str = region
       
    def __str__(self) -> str:
        return self.name + " " + str(self.coords)
    def __eq__(self, other) -> bool:
        if not isinstance(other, Location):
            return NotImplemented
        return (self.name == other.name and self.coords == other.coords)
    def __hash__(self):
        return hash((self.name, self.coords))

# Station subclass
class Station(Location):
    '''
    An extension of the Location class, with an additional stn_code variable.
    Only supports SG MRT at the moment.
    '''
    def __init__(self, name: str, coords: tuple[float, float], stn_code: list[str], region: str):
        super().__init__(name, coords, region)
        self.stn_code: list[str] = stn_code
      
    def get_transit_type(self) -> str:
        '''
        Returns the transit type (MRT or LRT) as a string based on the instance's alphanumeric codes.
        
        :return: Returns "MRT", "LRT" or "MRT/LRT" depending on the transit type.
        :rtype: str
        '''
        metro_data = region_list[self.region].metro_data
        has_transit_types = {}
        for code in self.stn_code:
            for idx, char in enumerate(code):
                if not (char.isalpha()):
                    alphac = code[:idx]
                    break
            else:
                alphac = code
            for transit_type, alpha_codes in metro_data.items():
                if alphac in alpha_codes:
                    has_transit_types[transit_type] = True
                    break
            else: # runs only if loop ends naturally; no alphacode found
                has_transit_types.setdefault("Other", []).append(code)
                logger.error("Invalid code detected: " + code)
        return "/".join([key for key, is_transit in has_transit_types.items() if is_transit is True])
    
    def get_disp_str(self) -> str:
        '''
        Returns the station name as a string type, suitable for eBird widget usage.
        
        :return: The station name, plus its transit type (MRT/LRT)
        :rtype: str
        '''
        return f"{self.name} {self.get_transit_type()}"
    
    def __str__(self):
        '''
        Returns the station name as a string type.
        
        :return: The station name, its coordinates, plus its transit type (MRT/LRT)
        :rtype: str
        '''
        return self.name + " " + str(self.coords) + self.get_transit_type()
    def __eq__(self, other) -> bool:
        if not isinstance(other, Station):
            return NotImplemented
        return (self.name == other.name and self.coords == other.coords)

station_list: list[Station]

def retrieve_stns(stn_file: str, col_name: str, col_lat: str, col_lon: str, col_code: str, region: str) -> list:
    stn_list = []
    with open(stn_file, newline="", encoding="utf-8") as f:
        for row in DictReader(f):
            if row[col_lat] == "999" or row[col_lon] == "999":
                continue
            stn_list.append(Station(
                row[col_name],
                (float(row[col_lat]), float(row[col_lon])),
                (row[col_code].split("/")),
                region
            ))
    return stn_list
def get_stn_df() -> pd.DataFrame:
    stn_listed = [
        [
            stn.name,
            stn.coords[0],
            stn.coords[1],
            stn.get_transit_type()
        ] for stn in station_list
    ]
    stn_df = pd.DataFrame(
        stn_listed,
        columns=["Station Name", "Latitude", "Longitude", "Station Type"]
    )
    return stn_df

# Hotspot subclass
class Hotspot(Location):
    '''
    An eBird hotspot, as a Location class extension.
    '''
    def __init__(self, name: str, coords: tuple[float, float], region: str, radius: float=500, nearest_stn: Station|str|None=None):
        super().__init__(name, coords, region)
        self.radius: float = radius
        self.nearest_stn: Optional[Station]
        if isinstance(nearest_stn, Station): # Auto-add if Station instance is given
            self.nearest_stn = nearest_stn
        elif nearest_stn == "":
            for stn in station_list:
                if stn.name.lower() == name.lower():
                    self.nearest_stn = stn
                    break
        else: # Get nearest station using coordinates
            self.nearest_stn = ghandler_near_loc(coords, station_list)[0]

    def get_nearest_stn_dist(self) -> Optional[float]:
        if self.nearest_stn:
            return geodesic(self.coords, self.nearest_stn.coords).meters
    
    def __str__(self):
        return self.name + " " + str(self.coords) + " " + f"(Radius: {self.radius}m)"
    def __eq__(self, other):
        if not isinstance(other, Hotspot):
            return NotImplemented
        return (self.name == other.name and self.coords == other.coords)
    def __hash__(self):
        return hash((self.name, self.coords))

T = TypeVar("T", Location, Station, Hotspot)

def get_hotspot_df(hotspots_list: list[Hotspot]):
    hspt_listed = [
        [
            hspt.name,
            hspt.coords[0],
            hspt.coords[1]
        ] for hspt in hotspots_list
    ]
    hspt_df = pd.DataFrame(
        hspt_listed,
        columns=["Location", "Latitude", "Longitude"]
    )
    return hspt_df

# General location functions
def ghandler_near_loc(coords: tuple[float, float], loctype_list: list[T]) -> tuple[T, float]:
    np_loc = np.array([[
        loc,
        geodesic(coords, loc.coords).meters / (loc.radius if isinstance(loc, Hotspot) else 500)
    ] for loc in loctype_list])
    return np_loc[np.argmin(np_loc[:, 1])]
def ghandler_clean_loc_name(loc_name: str, coords: tuple[float, float], region: str) -> str:
    cleaned_loc_name = (loc_name.replace(f" ({coords[0]}, {coords[1]})", "")) # Remove coords from name
    loc_regexes = region_list[region].location_regex
    for regex in loc_regexes:
        new_loc_name = re.search(regex[0], cleaned_loc_name)
        if new_loc_name:
            return new_loc_name.group(regex[1]).strip()
    return cleaned_loc_name.strip()
def handler_predefined_loc(predefined_hotspots_store: list[dict], loc_name: str, coords: tuple[float, float]) -> tuple[str, tuple]:
    for pre_loc in predefined_hotspots_store:
        if ((aliases := pre_loc["Aliases"]) and
            (   
                any(is_substrings(loc_name, alias) for alias in aliases) or
                is_substrings(loc_name, pre_loc["Hotspot Name"]) or
                geodesic(coords, pre_loc["Coordinates"]).meters <= pre_loc["Radius"]
            )
        ):
            return pre_loc["Hotspot Name"], (
                tuple(pre_loc["Coordinates"]),
                pre_loc["Region"],
                pre_loc["Radius"],
                pre_loc["Nearest Station"]
            )
    return loc_name, tuple()

FOUND_HSPT_START = "Existing hotspot found based on "
def gen_location(loc_name: str, coords: tuple[float, float], region: str, predefined_hotspots_store: list[dict], target_hotspot_store: list[Hotspot]) -> Hotspot:
    '''
    Attempts to create a Hotspot(Location) class.
    This will check against existing locations and hotspots.
    
    :param loc_name: The desired location name.
    :type loc_name: str
    :param coords: The desired coordinates.
    :type coords: tuple[float, float]
    :rtype: Hotspot
    '''
    # Alias check
    (loc_name, hotspot_params) = handler_predefined_loc(predefined_hotspots_store, loc_name.strip(), coords)
    # Nearest hotspot check
    if target_hotspot_store:
        (nearest_hspt, dist_ratio) = ghandler_near_loc(coords, target_hotspot_store)
    else:
        (nearest_hspt, dist_ratio) = None, math.inf
    if nearest_hspt and dist_ratio <= 1:
        logger.debug(FOUND_HSPT_START + "distance ratio: " + str(dist_ratio) + ", name: " + loc_name + " -> " + nearest_hspt.name)
        return nearest_hspt
    # Similar name check
    for hspt in target_hotspot_store:
        if is_substrings(loc_name, hspt.name) and dist_ratio <= 1.2:
            logger.debug(FOUND_HSPT_START + "name similarity: " + loc_name + " -> " + hspt.name)
            return hspt
    
    if hotspot_params:
        new_hspt = Hotspot(loc_name, *hotspot_params)
    else:
        cleaned_loc_name = ghandler_clean_loc_name(loc_name, coords, region)
        if region_list[region].metro_data: # Nearest station + cleaned name check
            stn_out = ghandler_near_loc(coords, station_list)[0]
            if ((not cleaned_loc_name) or
                cleaned_loc_name.startswith("Singapore") or
                "Auto selected" in cleaned_loc_name
            ):
                cleaned_loc_name = stn_out.get_disp_str().strip()
                logger.debug(f"Using station {cleaned_loc_name}, originally {loc_name}")
        else:
            stn_out = None
        logger.debug(f"Creating new hotspot @ {cleaned_loc_name}, coords {coords}")
        new_hspt = Hotspot(cleaned_loc_name, coords, region=region, nearest_stn=stn_out)
    target_hotspot_store.append(new_hspt)
    return new_hspt

def get_gdf_generic(df: pd.DataFrame) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(
            df["Longitude"], df["Latitude"]
        ), crs="EPSG:4326"
    )
    return gdf
def show_loc_plot(station_gdf: gpd.GeoDataFrame, hotspot_gdf: gpd.GeoDataFrame):
    if not is_vscode():
        return
    sg = gpd.read_file('datasets\\National Map Polygon.geojson')
    fig, ax = plt.subplots(figsize=(6, 8))
    ax.set_xlim(103.59, 104.15)
    ax.set_ylim(1.15, 1.5)
    sg.plot(ax=ax, color="lightgrey", edgecolor="black", aspect=1)
    station_gdf.plot(ax=ax, color="red", markersize=5, aspect=1)
    hotspot_gdf.plot(ax=ax, color="forestgreen", markersize=11, aspect=1)
    plt.show()

def is_substrings(str_1: str, str_2: str) -> bool:
    str_1, str_2 = str_1.lower(), str_2.lower()
    return (str_1 in str_2) or (str_2 in str_1)
transit_prefix_sg = {
    "MRT": ["NS", "EW", "CC", "CG", "CE", "NE", "DT", "TE", "JE", "JW", "JS", "CR", "CP", "RTS"],
    "LRT": ["BP", "SE", "SW", "PE", "PW", "SK", "STC", "PTC"]
}
transit_prefix_tpe = {
    "TPE-MRT": ["R", "Y", "G", "BL", "O", "BR"], # Tamsui-Xinyi/Circular/Songshan-Xindian/Bannan/Zhonghe-Xinlu/Wenhu
    "TPE-LRT": ["V", "K"], # Danhai/Ankeng
    "TYU-MRT": ["A"], # Taoyuan
}
tw_regex = [
    # Case 1: English parens with double dash. Matches "(Region--Place),"
    # Captures the text after the double dash, allowing nested (...) inside the name.
    (r'\([^\)]+?--(.+?)\)(?:\[.*?\])?(?:,[A-Za-z ]+)?$', 1),

    # Case 3: Chinese double dash with area code suffix (e.g. 10-2).
    # Captures text between -- and the digit-hyphen code.
    (r'--(.+?)\d+-\d+,\s*', 1),

    # Case 6: eBird Code "TW-..." identifier.
    # Captures everything before the " TW-" code.
    (r'^(.+?)\s+TW-[A-Za-z\u4e00-\u9fa5]+', 1),

    # Case 5: Address/Coords format "..., City, TW  , Taipei City".
    # Captures everything before the City
    (r'^(.+?),\s*[\u4e00-\u9fa5]{2,5}[縣市],\s*TW\s*', 1),

    # Generic case
    (r'^([^,]+),?', 1)
]

'''
    "TW-TPE": Region("TW-TPE", "Taipei City", transit_prefix_tpe, tw_regex,
        handlers=[]),
    "TW-TNN": Region("TW-TNN", "Tainan City", {}, tw_regex,
        handlers=[])'''

region_list = {
    "SG": Region("SG", "Singapore", transit_prefix_sg, [(r"^(.*?)(?:$|[^\d\w\s])", 1)], 
        handlers=[handler_predefined_loc]),
}
station_list = retrieve_stns("datasets\\stations.csv", "STN_NAME", "Latitude", "Longitude", "STN_NO", "SG")
#台北捷運 = retrieve_stns("datasets\\taipei.csv", "station_name_en", "lat", "lon", "station_code", "TW-TPE")

def debug_location_list(loc_list: list[T]):
    for loc in loc_list:
        print(loc)