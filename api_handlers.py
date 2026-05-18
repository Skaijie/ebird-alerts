from base64 import urlsafe_b64decode
import authentication
import logging
import re
from initialisations import *
from json_handler import *
from tqdm import tqdm
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from typing import Optional

logger = logging.getLogger(__name__)

'''
Gmail API handlers
'''
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
LAST_PROCESSED_FILE = "last_processed_email.txt"
TOKEN_FILE = "token.json"

# Text parsers

def get_last_recent_timestamp() -> int:
    '''
    Returns the unix timestamp of the previously processed email.
    '''
    try:
        return int(Path(LAST_PROCESSED_FILE).read_text().strip())
    except ValueError:
        return int(dt2.now().timestamp())
def set_unix_timestamp(timestamp: int):
    Path(LAST_PROCESSED_FILE).write_text(str(timestamp))
    logger.debug("Wrote timestamp " + str(timestamp) + " to file")

def get_gmail_service() -> Resource:
    '''Authenticates and returns the Gmail service.'''
    logger.info("Calling Gmail API")
    creds = None
    if os.path.exists(TOKEN_FILE) and Path(TOKEN_FILE).read_text():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        logger.info("Refreshing credential token. A prompt may appear to login")
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        Path(TOKEN_FILE).write_text(creds.to_json())
        logger.info("Refreshed token successfully")
    logger.info("Obtained Gmail credentials")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)
def decode_part(body_data) -> str:
    data = body_data.get("data", "")
    if not data:
        return ""
    # Fix padding and decode
    return urlsafe_b64decode(data + "===").decode(errors="ignore")
def get_mail_body(payload) -> Optional[str]:
    """Decodes the email body from the payload dictionary."""
    mime_type = payload.get("mimeType", "")

    # 1. Simple text/plain
    if mime_type == "text/plain" or not mime_type.startswith("multipart/"):
        return decode_part(payload.get("body", {}))

    # 2. Multipart: Walk parts to find text/plain
    if mime_type.startswith("multipart/"):
        parts = payload.get("parts", [])
        stack = parts[:]
        while stack:
            part = stack.pop()
            part_mime = part.get("mimeType", "")
            if part_mime == "text/plain":
                return decode_part(part.get("body", {}))
            if part_mime.startswith("multipart/") and "parts" in part:
                stack.extend(part["parts"])

def get_gmail_bodies(service, max_results: int=500, cutoff: int = 7) -> tuple[list, int]:
    """
    Fetches bodies of all 'photography' emails newer than the local record.
    Returns a list of strings (email bodies).
    """
    cutoff = cutoff + 1         # Shift the cutoff date by 1, as the gmail request is sent as "after:date"
    email_file = "email_bodies.pkl"
    last_recent_timestamp = get_last_recent_timestamp()
    unix_timestamp_latest = last_recent_timestamp
    email_bodies = []
    page_token = None
    regions_local = "Singapore"
    cutoff_dt_gmail = (dt2.now() - timedelta(days=cutoff)).strftime("%Y/%m/%d")
    logger.info("Getting mail list...")
    logger.debug(f"Cutoff date: {cutoff_dt_gmail}")
    
    while True:
        # List IDs of messages with the label
        list_resp = service.users().messages().list(
            userId="me",
            q=f"{regions_local} label:photography after:{cutoff_dt_gmail}",
            maxResults=max_results,
            pageToken=page_token,
            ).execute()
        messages_meta = list_resp.get("messages", [])
        if not messages_meta:
            logger.info("No messages found.")
            break
        logger.info(f"Found {len(messages_meta)} messages, processing...\n")
        iter_mails = tqdm(messages_meta, unit=" mails", colour="green")
        
        for mail_meta in iter_mails:
            full_msg = (service.users().messages()
                            .get(userId="me", id=mail_meta['id'], format='full')
                            .execute())
            
            current_mail_timestamp = int(full_msg['internalDate'])
            
            if current_mail_timestamp <= last_recent_timestamp: # Email 
                iter_mails.close()
                logger.info("Reached previously parsed email. Timestamp: " + str(current_mail_timestamp))
                break
            elif current_mail_timestamp > unix_timestamp_latest:
                unix_timestamp_latest = current_mail_timestamp
            
            body_text = get_mail_body(full_msg.get("payload", {}))
            if body_text:
                email_bodies.append(body_text)
        
        page_token = list_resp.get("nextPageToken")
        if not page_token:
            break
    
    save_pkl(email_file, email_bodies)
    return email_bodies, int(unix_timestamp_latest)
def parse_species_snippets(bodies: list[str]) -> list[list[str]]:
    logger.info("Parsing gmail bodies...")
    start_line = "eBird encourages safe, responsible birding."
    end_line = "***********"

    snippets = []
    for body in bodies:
        start_idx = body.find(start_line) # Find the line before the species details
        if start_idx == -1:
            continue
        end_idx = body.find(end_line, start_idx) # Find the end line (*********)
        
        observation_list = list(
            map( # 
                lambda snip: [line.strip() for line in snip.splitlines() if (line.strip())], # Get non-empty lines
                re.split(r"\n\s*\n(?=(?:.*?\(.*?\) \(.*?\))|\*)", # Use regex to determine species snips
                body[start_idx:end_idx])[1:] # Search in culled part of body
            )
        )
        for snip in observation_list:
            new_snip = [snip[0]]
            for line in snip[1:]:
                if line[0] == "-": # Next information line
                    new_snip.append(line)
                else:              # Overflow of info to next line
                    new_snip[-1] += f" {line}"
            snippets.append(new_snip) # Add formatted snip to data
    return snippets

def call_api_gmail() -> tuple[list, int] | None:
    try:
        gmail_svc = get_gmail_service()
        bodies, timestamp = get_gmail_bodies(gmail_svc)
        return bodies, timestamp
    except Exception as e:
        logger.error("Error while retrieving data from Gmail API:")
        logger.error(e)

'''
eBird API handlers
'''
def call_api_ebird(url: str) -> Optional[list[dict] | bool]:
    '''
    Calls the eBird API to retrieve bird sighting data.
    
    :param url: The URL of the API to call.
    :type url: str
    '''
    logger.info(f'Calling eBird API: {url}')
    try:
        payload = {}
        headers = {'X-eBirdApiToken': authentication.ebird_auth}
        sightings_ebird: list[dict] = requests.request("GET", url, headers=headers, data=payload).json()
        return sightings_ebird
    except Exception as e:
        logger.error("Failed to call the eBird API:")
        logger.error(e)
        return False