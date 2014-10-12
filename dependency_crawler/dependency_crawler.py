import os
import json
import threading
import shutil
import tarfile
import zipfile
import time
from urllib import urlretrieve
from infi.execute import execute_assert_success
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import pypi_crawler


def extract_tar(fname):
    if fname.endswith("gz"):
        tfile = tarfile.open(fname, 'r:gz')
        names = tfile.getnames()
    elif fname.endswith(".zip"):
        tfile = zipfile.ZipFile(fname)
        names = tfile.namelist()
    else:
        return
    dirnames = set([tfname.lstrip("./").split("/")[0] for tfname in names])
    nodirs = all('/' not in name for name in names)
    if len(dirnames) > 1 or nodirs:
        os.mkdir("package_dir")
        tfile.extractall("package_dir")
    else:
        tfile.extractall(".")


def get_dependencies(url):
    global required
    fname, _ = urlretrieve(url)
    try:
        extract_tar(fname)
        old_dir = os.getcwd()
        new_dirs = [d for d in os.listdir(".") if os.path.isdir(d)]
        shutil.copy("setup_executor.py", new_dirs[0])
        os.chdir(new_dirs[0])
        try:
            output = execute_assert_success(["python", "setup_executor.py"], timeout=60*5).get_stdout().strip()
            res = eval(output.splitlines()[-1])
            return res
        finally:
            os.chdir(old_dir)
            [shutil.rmtree(d) for d in new_dirs]
    finally:
        os.remove(fname)


def per_package(package, url):
    try:
        return get_dependencies(url)
    except (IndexError, ValueError):
        return None
    except Exception as e:
        #print "ERROR", package, e
        return None


def save_package_data(conn, package, dependencies, real_package_lookup):
    conn.execute("DELETE FROM dependencies WHERE name=?", (package,))       # remove old data
    conn.execute("REPLACE INTO dependencies(name, raw_dependencies, crawl_time) VALUES (?, ?, ?)",
                 (package, json.dumps(dependencies) if dependencies is not None else None, time.time()))
    if dependencies is not None:
        for dependency in dependencies:
            if isinstance(dependency, basestring) and len(dependency) > 0:
                dependency = dependency.split('>')[0].split('<')[-1].split('=')[0].strip().lower()
                if dependency in real_package_lookup:
                    real_dependency = real_package_lookup[dependency]
                    conn.execute("REPLACE INTO dependencies(name, dependency) VALUES (?, ?)",
                                 (package, real_dependency,))
    conn.commit()


def crawl(conn, crawl_count=1, new_only=True):
    pypi_crawler.parse_count = 0
    all_packages = set(x[0] for x in conn.execute("SELECT name FROM packages"))
    real_package_lookup = dict((package_name.lower(), package_name) for package_name in all_packages)
    package_query = "SELECT name, latest_sdist FROM packages WHERE latest_sdist IS NOT NULL"
    if new_only:
        package_query += " AND name NOT IN (SELECT DISTINCT name FROM dependencies)"
    packages = list(conn.execute(package_query))
    total_count = len(packages)
    pypi_crawler.start_progress("dependencies", crawl_count, total_count)
    for package, url in packages:
        pypi_crawler.parse_count += 1
        dependencies = per_package(package, url)
        save_package_data(conn, package, dependencies, real_package_lookup)
    pypi_crawler.stop_progress()


if __name__ == '__main__':
    conn = pypi_crawler.get_conn()
    crawl(conn, new_only=False)
