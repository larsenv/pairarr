import xmltodict
import sys
import requests
import pickle
import os
import json
import difflib
import datetime


def is_docker():
    return os.getenv("IN_DOCKER") is not None


def is_latest():
    if is_docker():
        version = os.path.join(os.getcwd(), "/data/version.txt")
    else:
        version = "version.txt"
    if not os.path.exists(version):
        with open(version, "w") as f:
            f.write("1")
        return False
    else:
        with open(version, "r") as f:
            if f.read() != "1":
                with open(version, "w") as f:
                    f.write("1")
                return False
            else:
                return True


movie = {}

if is_docker():
    config = json.load(open(os.path.join(os.getcwd(), "/data/config.json")))
    cache_db = os.path.join(os.getcwd(), "/data/cache.db")

    if not is_latest():
        os.remove(cache_db)

else:
    config = json.load(open("config.json", "r"))
    cache_db = "cache.db"

    if os.path.exists(cache_db) and not is_latest():
        os.remove(cache_db)

    if (
        len(sys.argv) != 2
        and os.getenv("SCAN_RADARR") != "true"
        and os.getenv("SCAN_SONARR") != "true"
    ):
        print("Usage: pairarr.py <sonarr/radarr>")
        sys.exit(1)

if len(sys.argv) > 1 and sys.argv[1] == "radarr" or os.getenv("SCAN_RADARR") == "true":
    movie["radarr"] = requests.get(
        config["radarr_host"] + "/api/v3/movie",
        headers={"X-Api-Key": config["radarr_api_key"]},
    ).json()

if len(sys.argv) > 1 and sys.argv[1] == "sonarr" or os.getenv("SCAN_SONARR") == "true":
    movie["sonarr"] = requests.get(
        config["sonarr_host"] + "/api/v3/series",
        headers={"X-Api-Key": config["sonarr_api_key"]},
    ).json()


path = config["path"]

if path[-1] == "/":
    path = path[:-1]

if os.path.exists(cache_db):
    cache = pickle.load(open(cache_db, "rb"))
else:
    cache = {"radarr": [], "sonarr": []}

for m in movie.items():
    i = 0
    for f in m[1]:
        f = f["title"]
        if m[0] == "radarr":
            if f in cache["radarr"]:
                continue
            cache["radarr"].append(f)

        elif m[0] == "sonarr":
            if f in cache["sonarr"]:
                continue
            cache["sonarr"].append(f)

        i += 1
        print(
            "Processing"
            + " "
            + str(i)
            + "/"
            + str(len(m[1]))
            + " "
            + "("
            + m[0][0].upper()
            + m[0][1:]
            + ")"
            + " "
            + "-"
            + " "
            + f
        )

        try:
            search = xmltodict.parse(
                requests.get(
                    "https://musicbrainz.org/ws/2/release?query="
                    + f
                    + " "
                    + "AND type:soundtrack"
                    + "&limit=1&offset=0",
                    headers={"User-Agent": "pairarr"},
                ).content
            )

            title = search["metadata"]["release-list"]["release"]["title"]
            album_id = search["metadata"]["release-list"]["release"]["release-group"][
                "@id"
            ]
        except:
            continue

        with open(cache_db, "wb") as g:
            g.write(pickle.dumps(cache))

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
                        path + "/" + result["album"]["artist"]["artistName"]
                    )
                    result["album"]["artist"]["qualityProfileId"] = 1
                    result["album"]["artist"]["metadataProfileId"] = 2
                    result["album"]["artist"]["cleanName"] = result["album"]["artist"][
                        "artistName"
                    ].lower()
                    result["album"]["artist"]["sortName"] = result["album"]["artist"][
                        "artistName"
                    ].lower()
                    result["album"]["artist"][
                        "added"
                    ] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                    result["album"]["artist"]["monitored"] = True
                    result["album"]["artist"]["rootFolderPath"] = path
                    result["album"]["artistId"] = 10000 + i
                    result["album"]["artist"]["id"] = 10000 + i
                    requests.post(
                        config["lidarr_host"] + "/api/v1/album",
                        headers={"X-Api-Key": config["lidarr_api_key"]},
                        json=result["album"],
                    ).json()
