# Pairarr

This is a basic script that scans your Radarr and Sonarr libraries to find the official soundtrack made for a TV show or movie. When it finds a match using the MusicBrainz API, it will add it to your Lidarr

# Usage

Edit `config.json.example` with your Lidarr, Radarr, and Sonarr URLs and API keys. Also, set the root folder path for Lidarr. Rename to `config.json`.

Run `pip install -r requirements.txt`, then run either `python pairarr.py radarr` or you can run `python pairarr.py sonarr`

Whatever albums it finds will be saved to a cache, therefore the next time you run the script it will not scan that again