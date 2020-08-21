import requests
import json
import time

##################################### CONFIG BELOW #####################################
SONARR_API_KEY = ""
SONARR_LOCAL_URL = 'http://localhost:8989/sonarr/' # Make sure you include the trailing /
TRAKT_FORCE_RESYNC = False #Set to True to delete all movies from Trakt's collection before pushing Sonarr's list
CHUNK_SIZE = 1000 #number of items to send to Trakt to send to Trakt in a single API payload
USE_SONARR_COLLECTED_DATE = True #If False, Trakt will use its existing collected date if available (won't work on resync) or the item's release date
#We rely on Radarr for Trakt oAuth. This requires you to have a Trakt connection already setup in Radarr and authenticated
RADARR_API_KEY = ""
RADARR_LOCAL_URL = 'http://localhost:7878/radarr/' # Make sure you include the trailing /
########################################################################################
#The below Trakt Client ID should not need to be changed, but you can verify if it is still accurate by checking the one found at 
#https://github.com/Radarr/Radarr/blob/c05209c5159139f55ad2c7caeb7c0a66926aa127/src/NzbDrone.Core/Notifications/Trakt/TraktProxy.cs#L27
TRAKT_CLIENT_ID = "64508a8bf370cee550dde4806469922fd7cd70afb2d5690e3ee7f75ae784b70e"
#########################################################################################


### CODE BELOW ###

def divide_chunks(l, n): 
    for i in range(0, len(l), n):  
        yield l[i:i + n]

def split_by_nested_count(lst, key_1, key_2, n):
    collected = []
    i = 0
    for d in lst:
        count = 0
        for e in d[key_1]:
            count += len(e[key_2])
        if i + count > n:
            yield collected
            collected = []
            collected.append(d)
            i = count
        else:
            i += count
            collected.append(d)
    if collected:  # yield any remainder
        yield collected

def find(lst, key, value):
    for i, dic in enumerate(lst):
        if dic[key] == value:
            return i
    return None

radarr_notifications_url = '{}api/v3/notification?apikey={}'.format(RADARR_LOCAL_URL, RADARR_API_KEY)
radarr_notifications = requests.get(radarr_notifications_url).json()
trakt_notification = next(notification for notification in radarr_notifications if notification['implementation'] == "Trakt")
access_token = next(token for token in trakt_notification['fields'] if token['name'] == "accessToken")
TRAKT_BEARER_TOKEN = access_token['value']

trakt_api_url = 'https://api.trakt.tv/sync/collection'
trakt_headers = {"Content-Type": "application/json", "Authorization": "Bearer {}".format(TRAKT_BEARER_TOKEN),
                "trakt-api-version": "2", "trakt-api-key": TRAKT_CLIENT_ID, 'User-Agent': 'Sonarr Trakt Collection Syncer v0.1'}

if TRAKT_FORCE_RESYNC:
    deletion_list = []
    print('Removing all shows from your Trakt collection to start fresh')
    trakt_shows = requests.get('{}/shows'.format(trakt_api_url), headers=trakt_headers).json()
    for show in trakt_shows:
        deletion_list.append(show['show'])
    chunked_deletion_list = divide_chunks(deletion_list, CHUNK_SIZE)
    for deletion_sublist in chunked_deletion_list:
        deletion_payload = json.dumps({"shows":deletion_sublist})
        trakt_delete_response = requests.post('{}/remove'.format(trakt_api_url), headers=trakt_headers, data=deletion_payload)
        print("HTTP Response Code: {}".format(trakt_delete_response.status_code))
        print(trakt_delete_response.json())
        time.sleep(5)

sess = requests.Session()

sonarr_series_api_url = '{}api/v3/series?apikey={}'.format(SONARR_LOCAL_URL, SONARR_API_KEY)
sonarr_series = sess.get(sonarr_series_api_url).json()

series_list = []
print('Pushing all downloaded episodes from Sonarr into your Trakt collection')
downloaded_series = (series for series in sonarr_series if series.get('statistics', {}).get('sizeOnDisk', 0) > 0)
for series in downloaded_series:
    title = series['title']
    year = series.get('year', None)
    imdb_id = series.get('imdbId', None)
    tvdb_id = series['tvdbId']
    series_id = series['id']

    sonarr_episode_api_url = '{}api/v3/episode?seriesId={}&apikey={}'.format(SONARR_LOCAL_URL, series_id, SONARR_API_KEY)
    sonarr_episodes = sess.get(sonarr_episode_api_url).json()
    downloaded_episodes = (episode for episode in sonarr_episodes if episode['episodeFileId'] != 0)
    season_list = []
    
    for episode in downloaded_episodes:
        season_number = episode['seasonNumber']
        episode_number = episode['episodeNumber']
        episode_file_id = episode['episodeFileId']

        sonarr_episode_file_api_url = '{}api/v3/episodefile/{}?apikey={}'.format(SONARR_LOCAL_URL, episode_file_id, SONARR_API_KEY)
        episode_file = sess.get(sonarr_episode_file_api_url).json()

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
        
        episode_info = {
            "number": episode_number,
            "media_type": media_type,
            "resolution": resolution,
            "audio": audio,
            "audio_channels": audio_channels
        }

        if USE_SONARR_COLLECTED_DATE:
            collected_at = episode_file['dateAdded']
            episode_info['collected_at'] = collected_at

        if not any(season['number'] == season_number for season in season_list):
            season_list.append({
                "number": season_number,
                "episodes": [episode_info]
            })
        else:
            index_number = find(season_list, 'number', season_number)
            season_list[index_number]['episodes'].append(episode_info)

    media_object = {
        "title": title,
        "year": year,
        "ids": {
            "imdb": imdb_id,
            "tvdb": tvdb_id
        },
        "seasons": season_list
    }
    series_list.append(media_object)

chunked_series_list = split_by_nested_count(series_list, 'seasons', 'episodes', CHUNK_SIZE)
for series_sublist in chunked_series_list:
    payload = json.dumps({"shows": series_sublist})
    trakt_response = requests.post(trakt_api_url, headers=trakt_headers, data=payload)
    print("HTTP Response Code: {}".format(trakt_response.status_code))
    print(trakt_response.json())
    time.sleep(1)