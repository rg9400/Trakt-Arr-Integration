import requests
import json
import time

##################################### CONFIG BELOW #####################################
RADARR_API_KEY = ""
RADARR_LOCAL_URL = 'http://localhost:7878/radarr/' # Make sure you include the trailing /
TRAKT_FORCE_RESYNC = False #Set to True to delete all movies from Trakt's collection before pushing Radarr's list
CHUNK_SIZE = 1000 #number of movies to send to Trakt in a single API paylod
USE_RADARR_COLLECTED_DATE = True #If False, Trakt will use its existing collected date if available (won't work on resync) or the item's release date
########################################################################################
#We rely on Radarr for Trakt oAuth. This requires you to have a Trakt connection already setup in Radarr and authenticated
#The below Trakt Client ID should not need to be changed, but you can verify if it is still accurate by checking the one found at 
#https://github.com/Radarr/Radarr/blob/c05209c5159139f55ad2c7caeb7c0a66926aa127/src/NzbDrone.Core/Notifications/Trakt/TraktProxy.cs#L27
TRAKT_CLIENT_ID = "64508a8bf370cee550dde4806469922fd7cd70afb2d5690e3ee7f75ae784b70e"
#########################################################################################


### CODE BELOW ###

def divide_chunks(l, n): 
    for i in range(0, len(l), n):  
        yield l[i:i + n]

radarr_notifications_url = '{}api/v3/notification?apikey={}'.format(RADARR_LOCAL_URL, RADARR_API_KEY)
radarr_notifications = requests.get(radarr_notifications_url).json()
trakt_notification = next(notification for notification in radarr_notifications if notification['implementation'] == "Trakt")
access_token = next(token for token in trakt_notification['fields'] if token['name'] == "accessToken")
TRAKT_BEARER_TOKEN = access_token['value'] 

trakt_api_url = 'https://api.trakt.tv/sync/collection'
trakt_headers = {"Content-Type": "application/json", "Authorization": "Bearer {}".format(TRAKT_BEARER_TOKEN),
                "trakt-api-version": "2", "trakt-api-key": TRAKT_CLIENT_ID, 'User-Agent': 'Radarr Trakt Collection Syncer v0.1'}

if TRAKT_FORCE_RESYNC:
    deletion_list = []
    print('Removing all movies from your Trakt collection to start fresh')
    trakt_movies = requests.get('{}/movies'.format(trakt_api_url), headers=trakt_headers).json()
    for movie in trakt_movies:
        deletion_list.append(movie['movie'])
    chunked_deletion_list = divide_chunks(deletion_list, CHUNK_SIZE)
    for deletion_sublist in chunked_deletion_list:
        deletion_payload = json.dumps({"movies":deletion_sublist})
        trakt_delete_response = requests.post('{}/remove'.format(trakt_api_url), headers=trakt_headers, data=deletion_payload)
        print("HTTP Response Code: {}".format(trakt_delete_response.status_code))
        print(trakt_delete_response.json())
        time.sleep(5)

radarr_api_url = '{}api/v3/movie?apikey={}'.format(RADARR_LOCAL_URL, RADARR_API_KEY)
radarr_movies = requests.get(radarr_api_url).json()

movie_list = []
print('Pushing all downloaded movies from Radarr into your Trakt collection')
downloaded_movies = (movie for movie in radarr_movies if movie['sizeOnDisk'] > 0)
for movie in downloaded_movies:
    title = movie['title']
    year = movie.get('year', None)
    imdb_id = movie.get('imdbId', None)
    tmdb_id = movie['tmdbId']

    source = movie['movieFile']['quality']['quality']['source']
    source_mapping = {
        "webdl":"digital",
        "webrip":"digital",
        "bluray":"bluray",
        "tv":"dvd",
        "dvd":"dvd"
        }
    media_type = source_mapping.get(source, None)

    radarr_resolution = movie['movieFile']['quality']['quality']['resolution']
    scan_type = movie['movieFile']['mediaInfo']['scanType']
    resolution_mapping = {
        2160:"uhd_4k",
        1080:"hd_1080",
        720:"hd_720p",
        480:"sd_480",
        576:"sd_576"
        }
    resolution = resolution_mapping.get(radarr_resolution, None)
    if resolution in ["hd_1080", "sd_480", "sd_576"]:
        if scan_type in ['Interlaced', 'MBAFF', 'PAFF']:
            resolution = '{}i'.format(resolution)
        else:
            resolution = '{}p'.format(resolution)

    audio_codec = movie['movieFile']['mediaInfo']['audioCodec']
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

    audio_channel_count = movie['movieFile']['mediaInfo']['audioChannels']
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

    media_object = {
        "title": title,
        "year": year,
        "ids": {
            "imdb": imdb_id,
            "tmdb": tmdb_id
        },
        "media_type": media_type,
        "resolution": resolution,
        "audio": audio,
        "audio_channels": audio_channels
    }
    if USE_RADARR_COLLECTED_DATE:
        collected_at = movie['movieFile']['dateAdded']
        media_object["collected_at"] = collected_at

    movie_list.append(media_object)

chunked_movie_list = divide_chunks(movie_list, CHUNK_SIZE)
for movie_sublist in chunked_movie_list:
    payload = json.dumps({"movies": movie_sublist})
    trakt_response = requests.post(trakt_api_url, headers=trakt_headers, data=payload)
    print("HTTP Response Code: {}".format(trakt_response.status_code))
    print(trakt_response.json())
    time.sleep(1)