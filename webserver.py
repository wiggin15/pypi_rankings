from flask import Flask, render_template, jsonify, request, abort
import datetime
import time
import threading
import pypi_crawler
import sqlite3

app = Flask(__name__)

conn = None

def get_downloads_data(download_key="downloads_total"):
    d = list(conn.execute("SELECT name, {0}, python3 FROM packages "
                          "WHERE {0} IS NOT NULL ORDER BY {0} DESC".format(download_key)))
    return [(rank, package, download_count, py3) for (rank, (package, download_count, py3)) in enumerate(d, 1)]

def get_dependency_data():
    res = list(conn.execute("SELECT dependency, COUNT(name) FROM dependencies "
                            "WHERE dependency IS NOT NULL GROUP BY dependency ORDER BY COUNT(name) DESC"))
    def lookup_py3(package_name):
        return next(conn.execute("SELECT python3 FROM packages WHERE name=?", (package_name,))) == 1
    return [(rank, package, depdendency_count, lookup_py3(package))
            for (rank, (package, depdendency_count)) in enumerate(res, 1)]

def get_author_data():
    res = list(conn.execute("SELECT author, COUNT(author) FROM packages "
                            "WHERE author NOT IN ('', 'UNKNOWN', 'AUTHOR') "
                            "GROUP BY author ORDER BY COUNT(author) DESC"))
    return [(rank, author, package_count, False) for (rank, (author, package_count)) in enumerate(res, 1)]


def format_time(timestr):
    if timestr is None:
        return "N/A"
    return timestr.replace("T", ' ').replace('-', '/')

def format_data_for_table(data, data_type="package"):
    draw = int(request.args.get('draw'))
    start = int(request.args.get('start'))
    count = int(request.args.get('length'))
    search = request.args.get('search[value]')
    format_package = lambda key: u'<a href="/{0}/{1}">{1}</a>'.format(data_type, key)
    format_py3 = lambda py3: '<img src="/static/three.png" class="three_icon">' if py3 else ''
    format_value = lambda dc: "{:,d}".format(dc)
    filtered_data = [(rank, format_package(package), format_value(value), format_py3(py3))
                     for (rank, package, value, py3) in data if search.lower() in package.lower()]
    final_data = filtered_data[start:start+count]
    return jsonify(dict(data=final_data, draw=draw, recordsTotal=len(data), recordsFiltered=len(filtered_data)))

@app.route('/downloads_total')
def downloads_total():
    return format_data_for_table(get_downloads_data("downloads_total"))
@app.route('/downloads_monthly')
def downloads_monthly():
    return format_data_for_table(get_downloads_data("downloads_month"))
@app.route('/downloads_weekly')
def downloads_weekly():
    return format_data_for_table(get_downloads_data("downloads_week"))
@app.route('/downloads_daily')
def downloads_daily():
    return format_data_for_table(get_downloads_data("downloads_day"))
@app.route('/dependencies')
def dependencies():
    return format_data_for_table(get_dependency_data())
@app.route('/authors')
def authors():
    return format_data_for_table(get_author_data(), "author")

@app.route("/more_stats")
def more_stats():
    homepages = [x[0] for x in conn.execute("SELECT homepage FROM packages WHERE homepage IS NOT NULL")]
    scm = list()
    for scm_name, scm_url_pattern in [("Github", "github.com"), ("Sourceforge", "sourceforge.net"),
                                      ("Google Code", "code.google.com"), ("Bitbucket", "bitbucket")]:
        scm.append((scm_name, len([h for h in homepages if h is not None and scm_url_pattern in h.lower()])))
    scm.sort(key=lambda x: x[1], reverse=True)
    len_py3 = [x[0] for x in conn.execute("SELECT python3 FROM packages")].count(True)
    no_releases = len(list(conn.execute("SELECT homepage FROM packages WHERE homepage IS NULL")))
    no_downloads = [x[0] for x in conn.execute("SELECT downloads_total FROM packages")].count(0)
    dependency_data = next(conn.execute("SELECT count(*) FROM dependencies WHERE raw_dependencies IS NOT NULL"))[0]
    total_len = next(conn.execute("SELECT COUNT(*) FROM packages"))[0]
    no_sdist = next(conn.execute("SELECT COUNT(*) FROM packages WHERE latest_sdist IS NULL"))[0]
    return render_template("more_stats.html", scm=scm, len_py3=len_py3, total_len=total_len, no_sdist=no_sdist,
        no_releases=no_releases, no_downloads=no_downloads, dependency_data=dependency_data)

@app.route('/package/<package_name>')
def package(package_name):
    try:
        package_data = next(conn.execute("SELECT * FROM packages WHERE name=?", (package_name,)))
    except StopIteration:
        abort(404)
    package_data = dict(zip(pypi_crawler.TABLE_VALUES.keys(), package_data))
    versions = list(conn.execute("SELECT * FROM versions WHERE package=? "
                                 "ORDER BY upload_time DESC, version DESC", (package_name,)))
    rank = [rank for rank, package, _, _ in get_downloads_data() if package==package_name][0]
    last_update = datetime.datetime.fromtimestamp(package_data["crawl_time"]).ctime()
    dependencies = list(conn.execute("SELECT dependency FROM dependencies "
                                     "WHERE dependency IS NOT NULL AND name=?", (package_name,)))
    dependencies = [x[0] for x in dependencies]
    has_dependency_data = len(list(conn.execute("SELECT raw_dependencies FROM dependencies "
                                                "WHERE name=? AND raw_dependencies IS NOT NULL", (package_name,)))) > 0
    show_all_packages = bool(request.args.get('show_all'))
    def dependent_packages():
        res = list(conn.execute("SELECT name FROM dependencies WHERE dependency=?", (package_name,)))
        res = [x[0] for x in res]
        if len(res) > 10 and not show_all_packages:
            res[10] = "... {} more".format(len(res) - 10)
            res = res[:11]
        return res
    return render_template("package.html",
        last_update=last_update, rank=rank, format_time=format_time,
        has_dependency_data=has_dependency_data, dependencies=dependencies, dependent_packages=dependent_packages(),
        len=len, release_history=versions,
        **package_data)

@app.route('/author/<author_name>')
def author(author_name):
    packages = list(conn.execute("SELECT name FROM packages WHERE author=?", (author_name,)))
    packages = [x[0] for x in packages]
    rank = [rank for rank, author, _, _ in get_author_data() if author==author_name][0]
    return render_template("author.html", author_name=author_name, rank=rank, packages=packages, len=len)

@app.route('/')
def index():
    kwargs = dict(
        search=request.args.get('search'),
        length=request.args.get('length'),
        start=request.args.get('start'),
        source=request.args.get('source', "downloads_total")
        )
    return render_template("index.html", **kwargs)

def main():
    global conn
    crawler_ready = threading.Event()
    crawl_thread = threading.Thread(target=pypi_crawler.crawl_forever, args=(crawler_ready,))
    crawl_thread.daemon = True
    crawl_thread.start()
    crawler_ready.wait()
    conn = sqlite3.connect(pypi_crawler.SQLITE_FILE)
    app.run(host="0.0.0.0", debug=True, use_reloader=False)

if __name__ == '__main__':
    main()