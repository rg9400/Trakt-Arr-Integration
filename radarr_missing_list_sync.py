import requests
import json
import time

##################################### CONFIG BELOW #####################################
RADARR_API_KEY = ""
RADARR_LOCAL_URL = 'http://localhost:7878/radarr/' # Make sure you include the trailing /
CUSTOM_LIST = '' # Leave blank if not syncing to a custom list, else set to the trakt slug/ID (from the URL of the list)
SYNC_WATCHLIST = True # Set to False to not sync to your watchlist
FORCE_RESYNC = False # Set to True to delete everything on the lists prior to pushing
CHUNK_SIZE = 1000
########################################################################################
#The below Trakt Client ID should not need to be changed, but you can verify if it is still accurate by checking the one found at 
#https://github.com/Radarr/Radarr/blob/aphrodite/src/NzbDrone.Core/Notifications/Trakt/TraktProxy.cs#L27
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
auth_user = next(token for token in trakt_notification['fields'] if token['name'] == "authUser")['value']
TRAKT_BEARER_TOKEN = access_token['value']

trakt_watchlist_url = 'https://api.trakt.tv/sync/watchlist'
trakt_list_url = 'https://api.trakt.tv/users/{}/lists/{}/items'.format(auth_user, CUSTOM_LIST)
trakt_headers = {"Content-Type": "application/json", "Authorization": "Bearer {}".format(TRAKT_BEARER_TOKEN),
                "trakt-api-version": "2", "trakt-api-key": TRAKT_CLIENT_ID, 'User-Agent': 'Radarr Trakt Connection v0.1'}

if FORCE_RESYNC:
    if CUSTOM_LIST:
        print("Removing all movies from list {} for user {} to start fresh".format(CUSTOM_LIST, auth_user))
        deletion_list = []
        trakt_movies = requests.get('{}/movies'.format(trakt_list_url), headers=trakt_headers).json()
        for movie in trakt_movies:
            deletion_list.append(movie['movie'])
        chunked_deletion_list = divide_chunks(deletion_list, CHUNK_SIZE)
        for deletion_sublist in chunked_deletion_list:
            deletion_payload = json.dumps({"movies": deletion_sublist})
            trakt_delete_response = requests.post('{}/remove'.format(trakt_list_url), headers=trakt_headers, data=deletion_payload)
            print("HTTP Response Code: {}".format(trakt_delete_response.status_code))
            message = trakt_delete_response.json()
            print("Response: {}".format(json.dumps(message, sort_keys=True, indent=4, separators=(',', ': '))))
            time.sleep(1)

    if SYNC_WATCHLIST:
        print("Removing all movies from watchlist for user {} to start fresh".format(auth_user))
        deletion_list = []
        trakt_movies = requests.get('{}/movies'.format(trakt_watchlist_url), headers=trakt_headers).json()
        for movie in trakt_movies:
            deletion_list.append(movie['movie'])
        chunked_deletion_list = divide_chunks(deletion_list, CHUNK_SIZE)
        for deletion_sublist in chunked_deletion_list:
            deletion_payload = json.dumps({"movies": deletion_sublist})
            trakt_delete_response = requests.post('{}/remove'.format(trakt_watchlist_url), headers=trakt_headers, data=deletion_payload)
            print("HTTP Response Code: {}".format(trakt_delete_response.status_code))
            message = trakt_delete_response.json()
            print("Response: {}".format(json.dumps(message, sort_keys=True, indent=4, separators=(',', ': '))))
            time.sleep(1)

radarr_api_url = '{}api/v3/movie?apikey={}'.format(RADARR_LOCAL_URL, RADARR_API_KEY)
radarr_movies = requests.get(radarr_api_url).json()
sync_list = (movie for movie in radarr_movies if movie['hasFile'] == False)

movie_list = []
for movie in sync_list:
    movie_object = {"ids":{}}
    imdb_id = movie['imdbId']
    if imdb_id:
        movie_object['ids']['imdb'] = imdb_id
    movie_object['ids']['tmdb'] = movie['tmdbId']
    movie_object['title'] = movie['title']
    movie_object['year'] = movie['year']
    movie_list.append(movie_object)

chunked_movie_list = divide_chunks(movie_list, CHUNK_SIZE)
print("Pushing all missing movies into your requested lists")
for movie_sublist in chunked_movie_list:
    message = {"movies": movie_sublist}
    payload = json.dumps(message)
    if CUSTOM_LIST:
        list_response = requests.post(trakt_list_url, headers=trakt_headers, data=payload)
        print("HTTP Response Code: {}".format(list_response.status_code))
        list_message = list_response.json()
        print("Response: {}".format(json.dumps(list_message, sort_keys=True, indent=4, separators=(',', ': '))))
        time.sleep(1)
    if SYNC_WATCHLIST:
        watchlist_response = requests.post(trakt_watchlist_url, headers=trakt_headers, data=payload)
        print("HTTP Response Code: {}".format(watchlist_response.status_code))
        watchlist_message = watchlist_response.json()
        print("Response: {}".format(json.dumps(watchlist_message, sort_keys=True, indent=4, separators=(',', ': '))))
        time.sleep(1)
