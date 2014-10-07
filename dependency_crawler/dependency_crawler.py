import os
import json
import threading
import shutil
import tarfile
import zipfile
import sqlite3
from urllib import urlretrieve
from infi.execute import execute_assert_success, CommandTimeout
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import pypi_crawler

def extract_tar(fname):
    if fname.endswith("gz"):
        tfile = tarfile.open(fname, 'r:gz')
        names = set([tfname.lstrip("./").split("/")[0] for tfname in tfile.getnames()])
    elif fname.endswith(".zip"):
        tfile = zipfile.ZipFile(fname)
        names = set([tfname.lstrip("./").split("/")[0] for tfname in tfile.namelist()])
    else:
        return
    if len(names) > 1:
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
            output = execute_assert_success(["python", "setup_executor.py"], timeout=60).get_stdout().strip()
            res = eval(output.splitlines()[-1])
            #print res
            return res
        finally:
            os.chdir(old_dir)
            [shutil.rmtree(d) for d in new_dirs]
    finally:
        os.remove(fname)

def per_package(package, url):
    try:
        return get_dependencies(url)
    except IndexError, ValueError:
        return None
    except CommandTimeout:
        print "TIMEOUT", package
        return None
    except Exception as e:
        #print "ERROR", package, e
        return None

def save_package_data(conn, package, dependencies, real_package_lookup):
    conn.execute("DELETE FROM dependencies WHERE name=?", (package,))       # remove old data
    conn.execute("REPLACE INTO dependencies(name, raw_dependencies) VALUES (?, ?)",
        (package, json.dumps(dependencies) if dependencies is not None else None,))
    if dependencies is not None:
        for dependency in dependencies:
            if isinstance(dependency, basestring) and len(dependency) > 0:
                dependency = dependency.split('>')[0].split('<')[-1].split('=')[0].strip().lower()
                if dependency in real_package_lookup:
                    real_dependency = real_package_lookup[dependency]
                    conn.execute("REPLACE INTO dependencies(name, dependency) VALUES (?, ?)",
                        (package, real_dependency,))
    conn.commit()

def crawl(conn, crawl_count=1, only_new=True):
    pypi_crawler.parse_count = 0
    all_packages = set(x[0] for x in conn.execute("SELECT name FROM packages"))
    real_package_lookup = dict((package_name.lower(), package_name) for package_name in all_packages)
    package_query = "SELECT name, latest_sdist FROM packages WHERE latest_sdist IS NOT NULL"
    if only_new:
        package_query += " AND name NOT IN (SELECT DISTINCT name FROM dependencies)"
    packages = list(conn.execute(package_query))
    total_count = len(packages)
    timer_close_event = threading.Event()
    timer_thread = threading.Thread(target=pypi_crawler.progress,
                                    args=("dependencies", crawl_count, total_count, timer_close_event))
    timer_thread.daemon = True
    timer_thread.start()
    for package, url in packages:
        pypi_crawler.parse_count += 1
        dependencies = per_package(package, url)
        save_package_data(conn, package, dependencies, real_package_lookup)
    timer_close_event.set()
    timer_thread.join()

if __name__ == '__main__':
    conn = sqlite3.connect(os.path.join(os.path.pardir, pypi_crawler.SQLITE_FILE))
    crawl(conn, only_new=False)