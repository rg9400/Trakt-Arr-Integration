from datetime import datetime
from logging.handlers import RotatingFileHandler
from logging import DEBUG, INFO, getLogger, Formatter
import requests
import json
import os
import sys

from requests.api import delete

##################################### CONFIG BELOW #####################################
RADARR_API_KEY = ""
RADARR_LOCAL_URL = 'http://localhost:7878/radarr/' # Make sure you include the trailing /
CUSTOM_LIST = '' # Leave blank if not deleting from a custom list, else set to the trakt slug/ID (from the URL of the list)
DELETE_FROM_WATCHLIST = True # Set to False to not delete from watchlist
########################################################################################
#The below Trakt Client ID should not need to be changed, but you can verify if it is still accurate by checking the one found at 
#https://github.com/Radarr/Radarr/blob/aphrodite/src/NzbDrone.Core/Notifications/Trakt/TraktProxy.cs#L27
TRAKT_CLIENT_ID = "64508a8bf370cee550dde4806469922fd7cd70afb2d5690e3ee7f75ae784b70e"
#########################################################################################


### CODE BELOW ###
# Set up the rotating log files
size = 10*1024*1024  # 5MB
max_files = 5  # Keep up to 7 logs
log_filename = os.path.join(os.path.dirname(sys.argv[0]), 'radarr_notification.log')
file_logger = RotatingFileHandler(log_filename, maxBytes=size, backupCount=max_files)
file_logger.setLevel(INFO)
logger_formatter = Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s')
file_logger.setFormatter(logger_formatter)
log = getLogger('Trakt')
log.setLevel(INFO)
log.addHandler(file_logger)

# Check if test from Sonarr, mark succeeded and exit
eventtype = os.environ.get('radarr_eventtype')
if eventtype == 'Test':
    log.info('Radarr script test succeeded.')
    sys.exit(0)

radarr_notifications_url = '{}api/v3/notification?apikey={}'.format(RADARR_LOCAL_URL, RADARR_API_KEY)
radarr_notifications = requests.get(radarr_notifications_url).json()
trakt_notification = next(notification for notification in radarr_notifications if notification['implementation'] == "Trakt")
access_token = next(token for token in trakt_notification['fields'] if token['name'] == "accessToken")
auth_user = next(token for token in trakt_notification['fields'] if token['name'] == "authUser")['value']
TRAKT_BEARER_TOKEN = access_token['value']

imdb_id = os.environ.get('radarr_movie_imdbid')
tmdb_id = os.environ.get('radarr_movie_tmdbid')

trakt_watchlist_url = 'https://api.trakt.tv/sync/watchlist/remove'
trakt_list_url = 'https://api.trakt.tv/users/{}/lists/{}/items/remove'.format(auth_user, CUSTOM_LIST)
trakt_headers = {"Content-Type": "application/json", "Authorization": "Bearer {}".format(TRAKT_BEARER_TOKEN),
                "trakt-api-version": "2", "trakt-api-key": TRAKT_CLIENT_ID, 'User-Agent': 'Radarr Trakt Connection v0.1'}

delete_data = [{"ids":{}}]
delete_data[0]['ids']['tmdb'] = tmdb_id
if imdb_id:
    delete_data[0]['ids']['imdb'] = imdb_id

message = {"movies": delete_data}
payload = json.dumps(message)
log.info("Payload: {}".format(json.dumps(message, sort_keys=True, indent=4, separators=(',', ': '))))
if DELETE_FROM_WATCHLIST:
    watchlist_response = requests.post(trakt_watchlist_url, headers=trakt_headers, data=payload)
    log.info("HTTP Response Code: {}".format(watchlist_response.status_code))
    watchlist_message = watchlist_response.json()
    log.info("Response: {}".format(json.dumps(watchlist_message, sort_keys=True, indent=4, separators=(',', ': '))))
if CUSTOM_LIST:
    list_response = requests.post(trakt_list_url, headers=trakt_headers, data=payload)
    log.info("HTTP Response Code: {}".format(list_response.status_code))
    list_message = list_response.json()
    log.info("Response: {}".format(json.dumps(list_message, sort_keys=True, indent=4, separators=(',', ': '))))
