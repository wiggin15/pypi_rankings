from infi.pypi_manager import PyPI
import requests
import json
import os
import sys
import time
import datetime
import threading
import itertools
import sqlite3

SQLITE_FILE = "pypi.sqlite"

TABLE_VALUES = dict(name="TEXT UNIQUE NOT NULL PRIMARY KEY",
    downloads_total="INTEGER",
    downloads_month="INTEGER",
    downloads_week="INTEGER",
    downloads_day="INTEGER",
    python3="INTEGER",
    author="TEXT",
    crawl_time="REAL",
    summary="TEXT",
    homepage="TEXT",
    latest_sdist="TEXT")

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
        d = json.loads(requests.get("https://pypi.python.org/pypi/{}/json".format(package)).text)
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

parse_count = preloaded = 0
dependency_data = dict()

def progress(crawl_type, crawl_count, total_count, timer_close_event):
    start_time = time.time()
    def output(remaining):
        elapsed = time.time() - start_time
        elapsed_str = str(datetime.timedelta(seconds=int(elapsed)))
        sys.stdout.write("\r" + " " * 100 + "\r")
        msg = "{} {} - {}/{} (elapsed {}, {})"
        sys.stdout.write(msg.format(crawl_type, crawl_count, parse_count, total_count, elapsed_str, remaining))
        sys.stdout.flush()
    while not timer_close_event.wait(1):
        try:
            elapsed = time.time() - start_time
            remaining = float(total_count - parse_count) / (float(parse_count - preloaded) / float(elapsed))
            remaining = str(datetime.timedelta(seconds=int(remaining)))
            remaining = "est. " + remaining
        except:
            remaining = "calculating time remaining"
        output(remaining)
    output("finished")
    print

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

def get_conn():
    import sqlite3
    if os.path.exists(SQLITE_FILE):
        conn = sqlite3.Connection(SQLITE_FILE)
    else:
        conn = sqlite3.Connection(SQLITE_FILE)
        conn.execute("CREATE TABLE packages ({})".format(", ".join([" ".join(item) for item in TABLE_VALUES.items()])))
        conn.execute("CREATE TABLE versions(package TEXT, version TEXT, upload_time TEXT, downloads INTEGER, "
            "CONSTRAINT u1 UNIQUE (package, version))")
        conn.execute("CREATE TABLE dependencies(name TEXT, raw_dependencies TEXT, dependency TEXT, crawl_time REAL, "
            "CONSTRAINT u2 UNIQUE (name, raw_dependencies), CONSTRAINT u3 UNIQUE (name, dependency))")
        conn.execute("CREATE TABLE scm(name TEXT UNIQUE NOT NULL PRIMARY KEY, "
            "type TEXT, url TEXT, open_issues INTEGER, last_change TEXT, crawl_time REAL)")
    return conn

def remove_deleted_packages(conn, packages_in_db, packages_in_pypi):
    for package in (set(packages_in_db) - set(packages_in_pypi)):
        conn.execute("DELETE FROM packages WHERE name=?", (package,))
        conn.execute("DELETE FROM versions WHERE package=?", (package,))
        conn.execute("DELETE FROM dependencies WHERE name=?", (package,))
        conn.execute("DELETE FROM scm WHERE name=?", (package,))
    conn.commit()

def crawl(conn, crawl_count):
    global parse_count
    global preloaded
    parse_count = preloaded = 0
    existing_packages = set([x[0] for x in list(conn.execute("SELECT name FROM packages"))])
    conn = get_conn()
    client = PyPI()._client
    packages = client.list_packages()
    remove_deleted_packages(conn, existing_packages, packages)
    total_count = len(packages)
    timer_close_event = threading.Event()
    timer_thread = threading.Thread(target=progress, args=("packages", crawl_count, total_count, timer_close_event))
    timer_thread.daemon = True
    timer_thread.start()
    for package in packages:
        parse_count += 1
        # for the first crawl skip the packages that we already know of. Only the second crawl onward will replace data
        if crawl_count == 1 and package in existing_packages:
            preloaded += 1
            continue
        package_data = per_package(package)
        save_package_data(conn, package, package_data)
    timer_close_event.set()
    timer_thread.join()

def crawl_forever(crawler_ready_event=None):
    conn = get_conn()
    if crawler_ready_event:
        crawler_ready_event.set()
    for crawl_count in itertools.count(1):
        crawl(conn, crawl_count)
        time.sleep(60 * 60 * 24)

if __name__ == '__main__':
    crawl_forever()