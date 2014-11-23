This script crawls PyPI (http://pypi.python.org) and collects information about all Python packages.
Data collected includes:
* number of downloads (total, monthly, weekly and daily)
* release history
* author
* dependencies
* source control data, if the package is hosted on Github or Bitbucket.

The information is displayed via a web page which ranks the packages by different categories (e.g. the package
with the most downloads, the most dependencies, etc.), and the user can search for packages and navigate the ranking
tables. The web page also contains views for every package and author with additional information.

Screenshot
==========
![Alt text](/screenshot.png?raw=true)

Usage
=====
After cloning this repository, run:
* `python setup.py install`
* `start_pypi_rankings`

This script opens a web server on the running machine, on port 5000. You can open the browser and navigate to
http://localhost:5000

* Note: crawling may take a while... The crawling process includes multiple crawl processes - one collects metadata,
another collects dependency data, and more... Initial crawl may take around 20 hours or more, but there is progress
indication, with very rough time estimation.

* Warning: As part of the dependency crawling process, this script
tries to run the `setup.py` file from all packages on PyPI, which may affect the filesystem on the running machine.
It is highly recommended to run this script in a virtual environment (a VM) and not on your personal computer.