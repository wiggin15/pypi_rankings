import requests
import json
import time
import re
import pypi_crawler


MAX_REPOS = 100     # we never want to fetch more than 100 repos at a time because github doesn't allows more per page
AUTH = None         # to crawl faster, this can be a tuple of (username, password) of a github user


def cleanup_url(url):
    url = url.lower()
    if 'github.io' in url:
        matchobj = re.search("([^/.]+)\.github\.io/(.*)", url)
        if not matchobj:
            return None
        url = "/".join(matchobj.groups())
    url = url.split("github.com/")[-1]
    url = url.split("#")[0]
    if url.endswith("/"):
        url = url[:-1]
    if url.endswith(".git"):
        url = url[:-4]
    url = "/".join(url.split("/")[:2])
    if len(url) == 0 or not url[-1].isalnum():
        return None
    return url


def get_github_list(conn):
    repo_cursor = conn.execute("SELECT name, homepage FROM packages WHERE LOWER(homepage) LIKE '%github.%'")
    res = [(repo, cleanup_url(url)) for repo, url in repo_cursor]
    return [(repo, url) for repo, url in res if url is not None]


def build_url(start, github_list):
    url = "https://api.github.com/search/repositories?per_page=100&q="
    repo_count = 0
    for name, repo in github_list[start:start+MAX_REPOS]:
        # we add a \n after each repo to break the url. If it's too and not broken into lines it will be rejected
        url += "repo:{}\n".format(repo)
        repo_count += 1
    return repo_count, url


def save_data(conn, github_json, github_list, start, repo_count):
    for github_repo_info in github_json["items"]:
        repo_part = github_repo_info["html_url"].split("github.com/")[-1]
        package_name = [name for name, repo in github_list[start:start+repo_count+1]
                        if repo.lower() == repo_part.lower()]
        if len(package_name) == 0:
            continue
        conn.execute("REPLACE INTO scm(name, type, url, open_issues, last_change, crawl_time) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (package_name[0],
                                                   "github",
                                                   github_repo_info["html_url"],
                                                   github_repo_info["open_issues"],
                                                   github_repo_info["pushed_at"],
                                                   time.time()))
    conn.commit()


def get_rate_limit():
    url = "https://api.github.com/rate_limit"
    return json.loads(requests.get(url, auth=AUTH).text)["resources"]["search"]["remaining"]


def crawl(conn, crawl_count=1):
    pypi_crawler.parse_count = 0
    github_list = get_github_list(conn)
    start = 0
    rate_limit = get_rate_limit()
    total_count = len(github_list)
    pypi_crawler.start_progress("github", crawl_count, total_count)
    while start < total_count:
        repo_count, url = build_url(start, github_list)
        github_response = requests.get(url, auth=AUTH).text
        github_json = json.loads(github_response)
        if "items" in github_json:
            save_data(conn, github_json, github_list, start, repo_count)
        #    print len(github_json["items"])
        #else:
        #    print github_json
        pypi_crawler.parse_count += repo_count
        rate_limit -= 1
        if rate_limit <= 0:
            #print "sleeping"
            time.sleep(65)
            rate_limit = get_rate_limit()
        start += repo_count
    pypi_crawler.stop_progress()


if __name__ == '__main__':
    conn = pypi_crawler.get_conn()
    crawl(conn)
