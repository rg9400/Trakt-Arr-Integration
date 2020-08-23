# Trakt-Arr-Integration
Python scripts to push data from Radarr/Sonarr into your Trakt collection.

All 3 scripts require you to have Radarr aphrodite and have set up the Trakt connection in Radarr.

Requires Python3 (developed with Python 3.8). You need the requests model, i.e. `python -m pip install requests` replacing python with whatever your python3 binary is.

**Force Resync** will first delete ALL your movie or show data in your collections (depending on the script) before pushing the data from Sonarr/Radarr. The benefit is that this removes any possible entities in Trakt that are not in Sonarr, forcing them to be fully in sync. If False, it will update the relevant data for existing items while adding new items in Sonarr/Radarr but not Trakt.

**Use Collected Date** will utilize the download date from Sonarr/Radarr when syncing the data to your Trakt collection. If True, it will replace existing items' dates with those in the Arrs. If False, it will keep any existing item dates, and if a new item is being added, then it will use the airdate/release date  for that item instead.

**Chunk Size** was recommended by the Trakt developer. It slows down the runtime for the syncs and increases API calls, but higher values can result in Trakt being unable to process your request. If you do a forced resync, then Trakt will handle larger chunk sizes and be generally faster as there is no validation or data matching happening.

## Desriptions of scripts

1. radarr_collection_sync will use Radarr data to upload downloaded movie info to Trakt

2. sonarr_collection_sync will use Sonarr data to upload downloaded episode info to Trakt

3. sonarr_trakt_connection is a temporary script that can be used as a connection in Sonarr, similar to the one in Radarr, to push new episode downloads into your Trakt collection to keep it up to date. A native connection PR is open at https://github.com/Sonarr/Sonarr/pull/3917 and should hopefully be added in the near future to make this script obsolete.

## Limitations

1. Current metadata mapping is based on the available options in Trakt or the Arrs. It is fairly robust already and handles multiple edge cases; however, there are limitations.
- Detailed HDR/3D info in the Arrs is not available, so we cannot map these in Trakt. 
- Trakt does not have a category for TV/PVR releases yet, so we map them to DVDs (might switch to VHS). 
- Trakt does not differentiate between TrueHD ATMOS and Dolby Digital Plus ATMOS, so both are mapped to ATMOS.
- Trakt does not have an option for DTS-ES
- Trakt does not differentiate between Vorbis and Opus OGG tracks
- Trakt does not differentiate between MP3 and MP2 tracks

2. Radarr/Sonarr do not have an On Delete notification yet, though there is a PR open at https://github.com/Radarr/Radarr/pull/4869 to add this in Radarr that should hopefully be added soon. This means that deletions in the Arrs are not going to result in deletions in Trakt, so these have to be done manually or via script for now
