from infi.pypi_manager import PyPI
import requests
import time
from progress import Progress


def parse_releases(package_json):
    releases = package_json["releases"]
    res = []
    total_downloads = 0
    for release, urls in releases.items():
        release_date = None if len(urls) == 0 else urls[0]["upload_time"]
        release_downloads = sum(url["downloads"] for url in urls)
        total_downloads += release_downloads
        res.append([release, release_date, release_downloads])
    return res, total_downloads


def get_latest_sdist(package_json):
    from itertools_recipes import flatten
    urls = flatten(package_json["releases"].values())
    sdist_urls = [u for u in urls if u["packagetype"] == "sdist"]
    try:
        return sorted(sdist_urls, key=lambda u: u["upload_time"], reverse=True)[0]["url"]
    except:
        return None


def per_package(package):
    try:
        d = requests.get("https://pypi.python.org/pypi/{}/json".format(package)).json()
        downloads = d["info"]["downloads"]
        release_history, total_downloads = parse_releases(d)
        latest_sdist = get_latest_sdist(d)
        downloads["total"] = total_downloads
        python3 = "Python :: 3" in "".join(d["info"]["classifiers"])
        return dict(downloads=downloads,
                    python3=python3,
                    author=d["info"]["author"],
                    crawl_time=time.time(),
                    release_history=release_history,
                    summary=d["info"]["summary"],
                    homepage=d["info"]["home_page"],
                    latest_sdist=latest_sdist)
    except ValueError:
        return None
    except Exception as e:
        print "ERROR", package, e
        return None


def save_package_data(conn, package, package_data):
    data_to_insert = dict(name=package)
    if package_data is not None:
        downloads = package_data.pop("downloads")
        package_data["downloads_total"] = downloads["total"]
        package_data["downloads_month"] = downloads["last_month"]
        package_data["downloads_week"] = downloads["last_week"]
        package_data["downloads_day"] = downloads["last_day"]
        package_data["python3"] = 1 if package_data.pop("python3") else 0
        for release in package_data.pop("release_history"):
            conn.execute("REPLACE INTO versions (package, version, upload_time, downloads) VALUES (?, ?, ?, ?)",
                         [package] + release)
        data_to_insert.update(package_data)
    conn.execute(u"REPLACE INTO packages ({}) VALUES ({})".format(", ".join(data_to_insert.keys()),
                 ("?," * len(data_to_insert))[:-1]), data_to_insert.values())
    conn.commit()


def remove_deleted_packages(conn, packages_in_db, packages_in_pypi):
    for package in (set(packages_in_db) - set(packages_in_pypi)):
        conn.execute("DELETE FROM packages WHERE name=?", (package,))
        conn.execute("DELETE FROM versions WHERE package=?", (package,))
        conn.execute("DELETE FROM dependencies WHERE name=?", (package,))
        conn.execute("DELETE FROM scm WHERE name=?", (package,))
    conn.commit()


def crawl(conn, crawl_count=1, new_only=False):
    existing_packages = set([x[0] for x in list(conn.execute("SELECT name FROM packages"))])
    client = PyPI()._client
    packages = client.list_packages()
    remove_deleted_packages(conn, existing_packages, packages)
    total_count = len(packages)
    progress = Progress("packages", crawl_count, total_count)
    progress.start()
    for package in packages:
        progress.parse_count += 1
        # for the first crawl skip the packages that we already know of. Only the second crawl onward will replace data
        if new_only and package in existing_packages:
            progress.preloaded += 1
            continue
        package_data = per_package(package)
        save_package_data(conn, package, package_data)
    progress.stop()


if __name__ == '__main__':
    from . import get_conn
    conn = get_conn()
    crawl(conn)
