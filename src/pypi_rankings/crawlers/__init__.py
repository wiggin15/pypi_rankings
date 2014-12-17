import sqlite3
from collections import OrderedDict
import threading
import itertools
import os
import time


SQLITE_FILE = "pypi.sqlite"

TABLE_VALUES = OrderedDict([("name", "TEXT UNIQUE NOT NULL PRIMARY KEY"),
                            ("downloads_total", "INTEGER"),
                            ("downloads_month", "INTEGER"),
                            ("downloads_week", "INTEGER"),
                            ("downloads_day", "INTEGER"),
                            ("python3", "INTEGER"),
                            ("author", "TEXT"),
                            ("crawl_time", "REAL"),
                            ("summary", "TEXT"),
                            ("homepage", "TEXT"),
                            ("latest_sdist", "TEXT"),])


def get_conn():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, SQLITE_FILE))
    if os.path.exists(path):
        conn = sqlite3.Connection(path)
    else:
        conn = sqlite3.Connection(path)
        conn.execute("CREATE TABLE packages ({})".format(", ".join([" ".join(item) for item in TABLE_VALUES.items()])))
        conn.execute("CREATE TABLE versions(package TEXT, version TEXT, upload_time TEXT, downloads INTEGER, "
                     "CONSTRAINT u1 UNIQUE (package, version))")
        conn.execute("CREATE TABLE dependencies(name TEXT, raw_dependencies TEXT, dependency TEXT, crawl_time REAL, "
                     "CONSTRAINT u2 UNIQUE (name, raw_dependencies), CONSTRAINT u3 UNIQUE (name, dependency))")
        conn.execute("CREATE TABLE scm(name TEXT UNIQUE NOT NULL PRIMARY KEY, "
                     "type TEXT, url TEXT, open_issues INTEGER, last_change TEXT, crawl_time REAL)")
    return conn


def do_dependency_crawl(conn, crawl_count):
    from .dependencies import crawl as dependency_crawl
    from multiprocessing import Process
    new_only = (crawl_count % 10 != 0)
    proc = Process(target=dependency_crawl, args=(conn, crawl_count, new_only))
    proc.start()
    proc.join()


def crawl_forever():
    from .pypi import crawl as pypi_crawl
    from .github import crawl as github_crawl
    from .bitbucket import crawl as bitbucket_crawl
    conn = get_conn()
    for crawl_count in itertools.count(1):
        pypi_crawl(conn, crawl_count, new_only=(crawl_count == 1))
        if crawl_count > 1:
            github_crawl(conn, crawl_count)
        if crawl_count % 2 == 0:
            bitbucket_crawl(conn, crawl_count)
        do_dependency_crawl(conn, crawl_count)
        time.sleep(60 * 60 * 24)


def start_crawlers():
    crawl_thread = threading.Thread(target=crawl_forever)
    crawl_thread.daemon = True
    crawl_thread.start()
