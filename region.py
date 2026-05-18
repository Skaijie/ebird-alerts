
from typing import Callable, Optional
import logging

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
    
    def get_country_code(self) -> Optional[str]:
        if self.code:
            return self.code[:2]
        logger.error("Region code is empty")
    
    def __str__(self):
        return f"{self.code} ({self.name})"
