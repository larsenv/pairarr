# UPDATE as of February 1, 2026 - This project is archived. It has come to my attention a couple months ago that [tubifarry](http://github.com/TypNull/Tubifarry/) has support to add Radarr and Sonarr soundtracks, and does a better job. While I lament that by coincidence that they added these features just a day after I launched this project, their tool currently offers a more complete solution. As a result, I have decided to discontinue it

# Pairarr

This is a basic script that scans your Radarr and Sonarr libraries to find the official soundtrack made for a TV show or movie. When it finds a match using the MusicBrainz API, it will add it to your Lidarr

# Usage

Edit `config.json.example` with your Lidarr, Radarr, and Sonarr URLs and API keys. Also, set the root folder path for Lidarr. Rename to `config.json`.

Run `pip install -r requirements.txt`, then run either `python pairarr.py radarr` or you can run `python pairarr.py sonarr`

Whatever albums it finds will be saved to a cache, therefore the next time you run the script it will not scan that again
