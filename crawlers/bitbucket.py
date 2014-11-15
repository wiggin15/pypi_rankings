import requests
import time
from progress import Progress


def cleanup_url(url):
    url = url.lower()
    url = url.split("bitbucket.org/")[-1]
    url = url.split("#")[0]
    if url.endswith("/"):
        url = url[:-1]
    if url.endswith(".git"):
        url = url[:-4]
    url = "/".join(url.split("/")[:2])
    if len(url) == 0 or not url[-1].isalnum():
        return None
    return url


def get_bitbucket_list(conn):
    repo_cursor = conn.execute("SELECT name, homepage FROM packages WHERE LOWER(homepage) LIKE '%bitbucket.org%'")
    res = [(repo, cleanup_url(url)) for repo, url in repo_cursor]
    return [(repo, url) for repo, url in res if url is not None]


def save_data(conn, package_name, data_dict):
    conn.execute("REPLACE INTO scm(name, type, url, open_issues, last_change, crawl_time) "
                 "VALUES (?, ?, ?, ?, ?, ?)", (package_name,
                                               data_dict["scm_type"],
                                               data_dict["html_url"],
                                               data_dict["open_issues"],
                                               data_dict["pushed_at"],
                                               time.time()))
    conn.commit()


def crawl(conn, crawl_count=1):
    bitbucket_list = get_bitbucket_list(conn)
    total_count = len(bitbucket_list)
    progress = Progress("bitbucket", crawl_count, total_count)
    progress.start()
    for package_name, bitbucket_uri in bitbucket_list:
        try:
            url = "https://api.bitbucket.org/2.0/repositories/{}"
            meta_info = requests.get(url.format(bitbucket_uri)).json()
            open_issues = 0
            if meta_info["has_issues"]:
                url = "https://api.bitbucket.org/1.0/repositories/{}/issues?status=!resolved"
                open_issues = requests.get(url.format(bitbucket_uri)).json()["count"]
            save_data(conn, package_name, dict(
                open_issues=open_issues,
                html_url=meta_info["links"]["html"]["href"],
                pushed_at=meta_info["updated_on"],
                scm_type="Bitbucket - {}".format(meta_info["scm"])))
        except:
            pass
        progress.parse_count += 1
    progress.stop()


if __name__ == "__main__":
    from . import get_conn
    conn = get_conn()
    crawl(conn)
