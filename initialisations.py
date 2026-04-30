import logging, os, sys, re, requests
from time import sleep
from traceback import extract_tb
from configparser import ConfigParser
from datetime import date as dt, datetime as dt2, timedelta
from typing import TypeAlias
    
configStore: TypeAlias = dict[str, int|float|str|dt|dt2]
'''
{
        "Hotspot Name":"",
        "Coordinates":[],
        "Region":"SG",
        "Radius":,
        "Nearest Station":"",
        "Aliases": [""]
    }, 
Target feature sets

v0.1.1 alpha:
- Full settings list
v0.1.2 alpha:
- Allow adding lifer species
- Remove excluded species on refresh

v0.2 alpha:
- Refactor code
- Send Wong to try try

v0.3 alpha:
- Refreshed design
- Click on species to toggle lifer status

v0.3.1 alpha:
- Language support

v0.4 alpha:
- Accessibility improvements

v0.1 beta:
- Display map
    - SG/TW (whole island) only

v0.2 beta:
- Display map 2.0
    - Interactable (hover for species, click for Gmaps link)
    - Hide/show metro lines (sg/tw only)
    - Support for multiple regions (Gmaps integration?)
'''
# VSCode mode
def is_vscode() -> bool:
    return ("TERM_PROGRAM" in os.environ and os.environ["TERM_PROGRAM"] == "vscode")

def get_config(config_file: str) -> tuple[configStore, set]:
    """
    Gets the configurations and regions from Settings.inc.
    """
    config = ConfigParser()
    config.optionxform = lambda optionstr: optionstr
    config.read(config_file)
    config_data = {}
    regions_data: set[str] = set()
    for key, value in config["Variables"].items():
        if key.startswith("Region") and value:
            regions_data.add(value)
            continue
        key = re.sub(r"(.)([A-Z])", r"\1_\2", key).lower().replace("setting_", "")
        try:
            int_value = int(value)
            config_data[key] = int_value
        except (ValueError, TypeError) as e:
            config_data[key] = value
    
    if is_vscode():
        config_data["debug"] = 2

    config_data["now"] = dt2.now()
    config_data["cutoff_time"] = config_data["now"] - timedelta(days=int(config_data["max_days"]))
    config_data["cutoff_unix"] = int(config_data["cutoff_time"].timestamp())
    config_data["cutoff_date"] = config_data["cutoff_time"].date()
    config_data["cutoff_date_str"] = config_data["cutoff_date"].isoformat()
    return config_data, regions_data

def log_init(config_data: configStore) -> logging.Logger:
    '''
    Initialises the Logger.
    
    :param latest_log: The log file to write to.
    :type latest_log: str
    :return: The Logger object to log messages to.
    :rtype: Logger
    '''''
    logger = logging.getLogger()
    if logger.handlers:
        return logger
    __CURR_LOG = "ebird_latest.log"
    __PREV_LOG = "ebird_prev.log"
    __TMP_LOG = "tempy.log"
    with open(__CURR_LOG, 'r') as file:
        content = file.read(10)
    file.close()
    if content != dt2.now().date().isoformat():
        os.rename(__CURR_LOG, __TMP_LOG)
        with open(__PREV_LOG, 'w') as f:
            pass
        os.rename(__PREV_LOG, __CURR_LOG)
        os.rename(__TMP_LOG, __PREV_LOG)
    
    format = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(__CURR_LOG, encoding="utf-8")
    if config_data["debug"] or is_vscode():
        fh.setLevel(logging.DEBUG)
    else:
        fh.setLevel(logging.INFO)
    fh.setFormatter(format)
    logger.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(format)
    logger.addHandler(ch)
    return logger

logger = logging.getLogger(__name__)

# Time
def chk_night_mode() -> int:
    '''
    Checks the night mode status.
    
    :param curr_time: The current time.
    :type curr_time: dt2
    :return: The night mode status.
        
        0 indicates that it is currently day.
        
        1 indicates that it is currently night.
    :rtype: int
    '''
    
    return int(not 6 < dt2.now().hour < 20)

# Internet
def chk_connection(config_data: configStore) -> int:
    '''
    Checks for internet connection.
    
    :return: An integer depending on the connection status:
        
        - 0: Connection failed.
        - 1: Connection successful.
        - 2: Offline mode, regardless of connection. (no APIs will be called)
    :rtype: int
    '''
    if config_data["offline_mode"]:
        logger.info("Offline mode is on. No internet connection required")
        return 2
    for count in range(3):
        try:
            requests.get("https://www.google.com/search", timeout=10)
            logger.info("Internet connection established")
            return 1 # Connected successfully
        except (requests.ConnectionError, requests.Timeout):
            logger.error('Could not establish a connection! Trying again in 10 seconds')
            sleep(10)
    logger.error('Failed to establish a connection.')
    return 0 # Connection failed

# Other
def error_output(e):
    exc_traceback = sys.exc_info()[2]
    tb_list = extract_tb(exc_traceback)
    line_number_local = tb_list[0].lineno
    line_number = tb_list[-1].lineno
    error_msg = f"Error at local line {line_number_local} @ traceback end line {line_number}: {e}"
    logger.error(error_msg)
def char_diff_check(str_1: str, str_2: str) -> float:
    str_1, str_2 = str_1.lower(), str_2.lower()
    if str_1 is None or str_2 is None:
        return None
    diff = sum(c1 != c2 for c1, c2 in zip(str_1, str_2))
    return diff + abs(len(str_1) - len(str_2))
def toggle_flag(current: bool, new_value: bool|None=None) -> bool:
    if isinstance(new_value, bool):
        return new_value
    return not current