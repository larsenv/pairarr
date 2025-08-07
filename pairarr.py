import xmltodict
import sys
import requests
import pickle
import os
import json
import difflib
import datetime


def color(text, style):
    styles = {
        "red": "\033[1m\033[91m",
        "green": "\033[1m\033[92m",
        "yellow": "\033[1m\033[93m",
        "blue": "\033[1m\033[94m",
        "cyan": "\033[1m\033[96m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }
    return f"{styles.get(style, '')}{text}{styles['reset']}"


def version():
    print(color("pairarr by larsenv\n", "cyan"))


def is_docker():
    return os.getenv("IN_DOCKER") is not None


def get_version_file():
    return (
        os.path.join(os.getcwd(), "/data/version.txt") if is_docker() else "version.txt"
    )


def is_latest():
    version = get_version_file()
    if not os.path.exists(version):
        with open(version, "w") as f:
            f.write("1.1")
        return False
    with open(version, "r") as f:
        if f.read() != "1.1":
            with open(version, "w") as f:
                f.write("1.1")
            return False
    return True


def load_config():
    path = (
        os.path.join(os.getcwd(), "/data/config.json") if is_docker() else "config.json"
    )
    with open(path, "r") as f:
        return json.load(f)


def get_cache_path():
    return os.path.join(os.getcwd(), "/data/cache.db") if is_docker() else "cache.db"


def should_scan(service):
    env = os.getenv(f"SCAN_{service.upper()}")
    return env == "true" or (len(sys.argv) > 1 and sys.argv[1] == service)


def simplify_string(s):
    for token in ["[", "(", "Soundtrack", "<", "-", ":", "{"]:
        s = s.split(token)[0]
    return s.strip().lower()


def similar(a, b):
    return difflib.SequenceMatcher(None, simplify_string(a), b.lower()).ratio()


def search_musicbrainz(title):
    try:
        response = requests.get(
            f"https://musicbrainz.org/ws/2/release-group?query={title} AND type:soundtrack&limit=25",
            headers={"User-Agent": "pairarr"},
        ).content
        data = xmltodict.parse(response)

        print(data)

        release_groups = (
            data.get("metadata", {})
            .get("release-group-list", {})
            .get("release-group", [])
        )
        if isinstance(release_groups, dict):
            release_groups = [release_groups]

        matches = []

        for release in release_groups:
            rg_title = release.get("title", "")
            rg_score = int(release.get("@score", "0"))
            secondarytype = release.get("secondary-type-list", {}).get(
                "secondary-type", []
            )

            if isinstance(secondarytype, dict):
                secondarytype = [secondarytype]

            if isinstance(secondarytype, list):
                texts = [
                    item.get("#text", "") if isinstance(item, dict) else str(item)
                    for item in secondarytype
                ]
                if not any("Soundtrack" in t for t in texts):
                    continue

            artist_credit = release.get("artist-credit", {}).get("name-credit", {})
            if isinstance(artist_credit, list):
                artist_name = artist_credit[0].get("artist", {}).get("name", "")
            else:
                artist_name = artist_credit.get("artist", {}).get("name", "")

            match_score = max(similar(rg_title, title), similar(artist_name, title))
            combined_score = rg_score / 100.0 + match_score

            if match_score > 0.85:
                print(
                    color(
                        f"  ✔ Found a match: ",
                        "green",
                    )
                    + color(f"{artist_name} - {rg_title}", "bold")
                    + color(f" (Score: {combined_score})", "yellow")
                )
                matches.append(
                    {
                        "artist": artist_name,
                        "album_id": release.get("@id"),
                        "sound_title": rg_title,
                        "title": rg_title,
                    }
                )

        return matches if matches else None

    except Exception as e:
        print(
            f"{color('  ✖ Error: - query failed for', 'red')}",
            f"{color(title, 'bold')} - {color(str(e), 'red')}",
        )
        return None


def process_items(config, movies, cache, cache_path):
    path = config["path"].rstrip("/")
    i = 0
    for service, entries in movies.items():
        for entry in entries:
            title = entry["title"]
            if title in cache[service]:
                continue

            print(
                f"{color('▶ Processing', 'cyan')} {color(str(i+1), 'yellow')}/{color(str(len(entries)), 'yellow')} "
                f"{color(f'({service.capitalize()})', 'blue')} - {color(title, 'bold')}"
            )
            cache[service].append(title)
            i += 1

            mb_matches = search_musicbrainz(title)
            if not mb_matches:
                continue

            for mb_data in mb_matches:
                lidarr_results = requests.get(
                    f"{config['lidarr_host'].rstrip('/')}/api/v1/search",
                    headers={"X-Api-Key": config["lidarr_api_key"]},
                    params={"term": mb_data["title"]},
                ).json()

                for result in lidarr_results:

                    if "album" not in result:
                        continue
                    album = result["album"]
                    if album.get("foreignAlbumId") != mb_data["album_id"]:
                        continue

                    artist = album["artist"]

                    print(
                        color("  ▶ Adding ", "blue")
                        + color(f"{artist['artistName']} - {album['title']}", "bold")
                    )

                    artist.update(
                        {
                            "path": f"{path}/{artist['artistName']}",
                            "qualityProfileId": 1,
                            "metadataProfileId": 2,
                            "cleanName": artist["artistName"].lower(),
                            "sortName": artist["artistName"].lower(),
                            "added": datetime.datetime.utcnow().strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                            "monitored": True,
                            "rootFolderPath": path,
                            "id": 10000 + i,
                        }
                    )
                    album.update(
                        {
                            "addOptions": {
                                "searchForNewAlbum": True,
                                "monitor": "all",
                                "albumsToMonitor": [],
                                "monitored": True,
                            },
                            "monitored": True,
                            "artistId": 10000 + i,
                        }
                    )

                    r = requests.post(
                        f"{config['lidarr_host'].rstrip('/')}/api/v1/album",
                        headers={"X-Api-Key": config["lidarr_api_key"]},
                        json=album,
                    )
                    if (
                        r.status_code == 400
                        and isinstance(r.json(), list)
                        and r.json()[0].get("errorMessage")
                        == "This album has already been added."
                    ):
                        print(
                            color(f"    ⚠ Already added: ", "yellow")
                            + color(f"{artist['artistName']} - {title}", "bold")
                        )
                    elif r.status_code != 201:
                        print(
                            f"{color('    ✖ Error adding album:', 'red')} {color(title, 'bold')} "
                            f"{color(f'[{r.status_code}]', 'yellow')} {color(r.text, 'red')}"
                        )

            with open(cache_path, "wb") as f:
                pickle.dump(cache, f)


def main():
    version()

    config = load_config()
    cache_path = get_cache_path()
    cache = {"radarr": [], "sonarr": []}

    if os.path.exists(cache_path) and not is_latest():
        os.remove(cache_path)

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cache = pickle.load(f)

    if not should_scan("radarr") and not should_scan("sonarr"):
        print("Usage: pairarr.py <sonarr/radarr>")
        sys.exit(1)

    movies = {}
    if should_scan("radarr"):
        print(color("▶ Querying Radarr...\n", "cyan"))
        movies["radarr"] = requests.get(
            f"{config['radarr_host'].rstrip('/')}/api/v3/movie",
            headers={"X-Api-Key": config["radarr_api_key"]},
        ).json()

    if should_scan("sonarr"):
        print(color("▶ Querying Sonarr...\n", "cyan"))
        movies["sonarr"] = requests.get(
            f"{config['sonarr_host'].rstrip('/')}/api/v3/series",
            headers={"X-Api-Key": config["sonarr_api_key"]},
        ).json()

    process_items(config, movies, cache, cache_path)


if __name__ == "__main__":
    main()
