#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author:       /u/RG9400
# Requires:     requests
from datetime import datetime
from logging.handlers import RotatingFileHandler
from logging import DEBUG, INFO, getLogger, Formatter
import requests
import json
import os
import sys

##################################### CONFIG BELOW #####################################
SONARR_API_KEY = ""
SONARR_LOCAL_URL = 'http://localhost:8989/sonarr/' # Make sure you include the trailing /

#We rely on Radarr for Trakt oAuth. This requires you to have a Trakt connection already setup in Radarr and authenticated
RADARR_API_KEY = ""
RADARR_LOCAL_URL = 'http://localhost:7878/radarr/' # Make sure you include the trailing /

########################################################################################
#The below Trakt Client ID should not need to be changed, but you can verify if it is still accurate by checking the one found at 
#https://github.com/Radarr/Radarr/blob/aphrodite/src/NzbDrone.Core/Notifications/Trakt/TraktProxy.cs#L27
TRAKT_CLIENT_ID = "64508a8bf370cee550dde4806469922fd7cd70afb2d5690e3ee7f75ae784b70e"
#########################################################################################


### CODE BELOW ###
# Set up the rotating log files
size = 10*1024*1024  # 5MB
max_files = 5  # Keep up to 7 logs
log_filename = os.path.join(os.path.dirname(sys.argv[0]), 'sonarr_trakt_connection.log')
file_logger = RotatingFileHandler(log_filename, maxBytes=size, backupCount=max_files)
file_logger.setLevel(INFO)
logger_formatter = Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s')
file_logger.setFormatter(logger_formatter)
log = getLogger('Trakt')
log.setLevel(INFO)
log.addHandler(file_logger)

# Check if test from Sonarr, mark succeeded and exit
eventtype = os.environ.get('sonarr_eventtype')
if eventtype == 'Test':
    log.info('Sonarr script test succeeded.')
    sys.exit(0)

radarr_notifications_url = '{}api/v3/notification?apikey={}'.format(RADARR_LOCAL_URL, RADARR_API_KEY)
radarr_notifications = requests.get(radarr_notifications_url).json()
trakt_notification = next(notification for notification in radarr_notifications if notification['implementation'] == "Trakt")
access_token = next(token for token in trakt_notification['fields'] if token['name'] == "accessToken")
TRAKT_BEARER_TOKEN = access_token['value']

season_number = os.environ.get('sonarr_episodefile_seasonnumber')
episode_numbers = os.environ.get('sonarr_episodefile_episodenumbers')
tvdb_id = os.environ.get('sonarr_series_tvdbid')
scene_name = os.environ.get('sonarr_episodefile_scenename')
title = os.environ.get('sonarr_series_title')
imdb_id = os.environ.get('sonarr_series_imdbid')
episodefile_id = os.environ.get('sonarr_episodefile_id')
series_id = os.environ.get('sonarr_series_id')

def utc_now_iso():
    utcnow = datetime.utcnow()
    return utcnow.isoformat()

episodes = episode_numbers.split(",")

trakt_api_url = 'https://api.trakt.tv/sync/collection'
trakt_headers = {"Content-Type": "application/json", "Authorization": "Bearer {}".format(TRAKT_BEARER_TOKEN),
                "trakt-api-version": "2", "trakt-api-key": TRAKT_CLIENT_ID, 'User-Agent': 'Sonarr Trakt Connection v0.1'}

sonarr_api_url = '{}api/v3/episodefile/{}?apikey={}'.format(SONARR_LOCAL_URL, episodefile_id, SONARR_API_KEY)
episode_file = requests.get(sonarr_api_url).json()

sonarr_series_api_url = '{}api/v3/series/{}?apikey={}'.format(SONARR_LOCAL_URL, series_id, SONARR_API_KEY)
sonarr_series_data = requests.get(sonarr_series_api_url).json()

year = sonarr_series_data.get('year', None)

source = episode_file['quality']['quality']['source']
source_mapping = {
    "web":"digital",
    "webRip":"digital",
    "blurayRaw":"bluray",
    "bluray":"bluray",
    "television":"dvd",
    "televisionRaw":"dvd",
    "dvd":"dvd"
    }
media_type = source_mapping.get(source, None)

sonarr_resolution = episode_file['quality']['quality']['resolution']
scan_type = episode_file['mediaInfo']['scanType']
resolution_mapping = {
    2160:"uhd_4k",
    1080:"hd_1080",
    720:"hd_720p",
    480:"sd_480",
    576:"sd_576"
    }
resolution = resolution_mapping.get(sonarr_resolution, None)
if resolution in ["hd_1080", "sd_480", "sd_576"]:
    if scan_type in ['Interlaced', 'MBAFF', 'PAFF']:
        resolution = '{}i'.format(resolution)
    else:
        resolution = '{}p'.format(resolution)

audio_codec = episode_file['mediaInfo']['audioCodec']
audio_mapping = {
    "AC3":"dolby_digital",
    "EAC3":"dolby_digital_plus",
    "TrueHD":"dolby_truehd",
    "EAC3 Atmos":"dolby_atmos",
    "TrueHD Atmos":"dolby_atmos",
    "DTS":"dts",
    "DTS-ES":"dts",
    "DTS-HD MA":"dts_ma",
    "DTS-HD HRA":"dts_hr",
    "DTS-X":"dts_x",
    "MP3":"mp3",
    "MP2":"mp3",
    "Vorbis":"ogg",
    "WMA":"wma",
    "AAC":"aac",
    "PCM":"lpcm",
    "FLAC":"flac",
    "Opus":"ogg"
    }
audio = audio_mapping.get(audio_codec, None)

audio_channel_count = episode_file['mediaInfo']['audioChannels']
channel_mapping = str(audio_channel_count)
audio_channels = channel_mapping
#Below is when DTS-X is used and MediaInfo does not give object counts
if audio_channel_count == 8.0:
    audio_channels = "7.1"
#Below incorrect count can sometimes be 6.1 for DTS-HR tracks, but the vast majority of time, it is for 7.1 tracks
#It happens when channels_original and channels differ. Out of 17 such cases, only 3 were actually 6.1, rest were 7.1
elif audio_channel_count == 6.0 and audio == "dts_ma":
    audio_channels = "7.1"
elif audio_channel_count == 6.0 and audio != "dts_ma":
    audio_channels = "6.1"
#Not sure why this happens, but I noticed a few older 1.0 PCM tracks coming as 0.0 channel count in Radarr
elif audio_channel_count == 0.0:
    audio_channels = "1.0"

collected_at = utc_now_iso()

episode_list = []
for episode in episodes:    
    episode_info = {
        "number": int(episode),
        "collected_at": collected_at,
        "media_type": media_type,
        "resolution": resolution,
        "audio": audio,
        "audio_channels": audio_channels
    }
    episode_list.append(episode_info)

media_object = {
    "title": title,
    "year": year,
    "ids": {
        "imdb": imdb_id,
        "tvdb": tvdb_id
    },
    "seasons": [
        {
        "number": int(season_number),
        "episodes": episode_list
    }
    ]
}
show_list = []
show_list.append(media_object)
payload = json.dumps({"shows": show_list})
log.info(payload)
trakt_response = requests.post(trakt_api_url, headers=trakt_headers, data=payload)
log.info("HTTP Response Code: {}".format(trakt_response.status_code))
log.info(trakt_response.json())
