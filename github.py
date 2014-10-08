import requests
import sqlite3
import json
import time
import re
from pypi_crawler import SQLITE_FILE

MAX_URL = 1500
MAX_REPOS = 100
AUTH = None

def get_github_list(conn):
    repo_list = list(conn.execute("SELECT name, homepage FROM packages WHERE LOWER(homepage) LIKE '%github.%'"))
    def cleanup_url(url):
        url = url.lower()
        if 'github.io' in url:
            try:
                url = "/".join(re.search("([^/.]+)\.github\.io/(.*)", url).groups())
            except:
                pass
        url = url.split("github.com/")[-1]
        url = url.split("#")[0]
        if url.endswith("/"):
            url = url[:-1]
        if url.endswith(".git"):
            url = url[:-4]
        url = "/".join(url.split("/")[:2])
        return url
    return [(repo, cleanup_url(url)) for repo, url in repo_list]

def build_url(start, github_list):
    url = "https://api.github.com/search/repositories?per_page=100&q="
    repo_count = 0
    while True:
        if start + repo_count >= len(github_list):
            break
        repo = github_list[start + repo_count][1]
        if len(url + "%20repo:" + repo) > MAX_URL or repo_count >= MAX_REPOS:
            break
        url += "%20repo:" + repo
        repo_count += 1
    return repo_count, url

def save_data(conn, j, github_list, start, repo_count):
    for github_repo_info in j["items"]:
        repo_part = github_repo_info["html_url"].split("github.com/")[-1]
        package_name = [name for name, repo in github_list[start:start+repo_count+1]
                        if repo.lower() == repo_part.lower()]
        if len(package_name) == 0:
            continue
        conn.execute("REPLACE INTO scm(name, type, url, open_issues, last_change, crawl_time) "
            "VALUES (?, ?, ?, ?, ?, ?)",
                (package_name[0],
                "github",
                github_repo_info["html_url"],
                github_repo_info["open_issues"],
                github_repo_info["pushed_at"],
                time.time()))
    conn.commit()

def get_rate_limit():
    url = "https://api.github.com/rate_limit"
    return json.loads(requests.get(url, auth=AUTH).text)["resources"]["search"]["remaining"]

def crawl():
    start_time = time.time()
    conn = sqlite3.connect(SQLITE_FILE)
    github_list = get_github_list(conn)
    start = 0
    rate_limit = get_rate_limit()
    while True:
        repo_count, url = build_url(start, github_list)
        github_response = requests.get(url, auth=AUTH).text
        j = json.loads(github_response)
        if "items" not in j:
            print j
        else:
            save_data(conn, j, github_list, start, repo_count)
            print start, repo_count, len(j["items"])
        rate_limit -= 1
        if rate_limit <= 0:
            print "sleeping"
            time.sleep(65)
            rate_limit = get_rate_limit()
        if (start + repo_count) >= len(github_list):
            break
        start += repo_count
    print "Time taken:", time.time() - start_time

if __name__ == '__main__':
    crawl()

