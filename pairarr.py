import xmltodict
import sys
import requests
import pickle
import os
import json
import difflib
import datetime

config = json.load(open("config.json", "r"))

if len(sys.argv) != 2:
    print("Usage: pairarr.py <sonarr/radarr>")
    sys.exit(1)

if sys.argv[1] == "sonarr":
    movie = requests.get(
        config["sonarr_host"] + "/api/v3/series",
        headers={"X-Api-Key": config["sonarr_api_key"]},
    ).json()
elif sys.argv[1] == "radarr":
    movie = requests.get(
        config["radarr_host"] + "/api/v3/movie",
        headers={"X-Api-Key": config["radarr_api_key"]},
    ).json()

path = config["path"]

if path[-1] == "/":
    path = path[:-1]

i = 0

if os.path.exists("cache.db"):
    cache = pickle.load(open("cache.db", "rb"))
else:
    cache = {"sonarr": [], "radarr": []}

for f in movie:
    f = f["title"]
    if sys.argv[1] == "sonarr":
        if f in cache["sonarr"]:
            continue
        cache["sonarr"].append(f)
    elif sys.argv[1] == "radarr":
        if f in cache["radarr"]:
            continue
        cache["radarr"].append(f)
    i += 1
    print("Processing" + " " + str(i) + "/" + str(len(movie)) + " " + "-" + " " + f)
    try:
        search = xmltodict.parse(
            requests.get(
                "https://musicbrainz.org/ws/2/release?query="
                + f
                + " "
                + "soundtrack"
                + "&limit=1&offset=0"
            ).content
        )

        title = search["metadata"]["release-list"]["release"]["title"]
        album_id = search["metadata"]["release-list"]["release"]["release-group"]["@id"]
    except:
        continue

    try:
        if (
            search["metadata"]["release-list"]["release"]["release-group"][
                "@type"
            ].lower()
            != "soundtrack"
        ):
            continue
    except:
        continue

    if (
        difflib.SequenceMatcher(
            None,
            title.split("[")[0]
            .split("(")[0]
            .split("Soundtrack")[0]
            .split("<")[0]
            .split("-")[0]
            .split(":")[0]
            .split("{")[0],
            f,
        ).ratio()
        > 0.85
    ):
        print("Found match")
    else:
        continue

    with open("cache.db", "wb") as g:
        g.write(pickle.dumps(cache))

    for result in requests.get(
        config["lidarr_host"] + "/api/v1/search",
        headers={"X-Api-Key": config["lidarr_api_key"]},
        params={"term": title},
    ).json():
        if "album" in result:
            if result["album"]["foreignAlbumId"] == album_id:
                result["album"]["addOptions"] = {
                    "searchForNewAlbum": True,
                    "monitor": "all",
                    "albumsToMonitor": [],
                    "monitored": True,
                }
                result["album"]["monitored"] = True
                result["album"]["artist"]["path"] = (
                    "/media/sdc1/hydrobleach/Media/Music"
                    + "/"
                    + result["album"]["artist"]["artistName"]
                )
                result["album"]["artist"]["qualityProfileId"] = 1
                result["album"]["artist"]["metadataProfileId"] = 2
                result["album"]["artist"]["cleanName"] = result["album"]["artist"][
                    "artistName"
                ].lower()
                result["album"]["artist"]["sortName"] = result["album"]["artist"][
                    "artistName"
                ].lower()
                result["album"]["artist"]["added"] = datetime.datetime.now().strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                result["album"]["artist"]["monitored"] = True
                result["album"]["artist"]["rootFolderPath"] = path
                result["album"]["artistId"] = 10000 + i
                result["album"]["artist"]["id"] = 10000 + i
                requests.post(
                    config["lidarr_host"] + "/api/v1/album",
                    headers={"X-Api-Key": config["lidarr_api_key"]},
                    json=result["album"],
                ).json()
