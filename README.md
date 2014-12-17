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
* Install by running `easy_install pypi_rankings`
* Start by running `start_pypi_rankings`

This script starts collecting data, and opens a web server on the running machine, on port 5000.
You can open a browser and navigate to http://localhost:5000

* Note: crawling may take a while... The process of collecting the data includes multiple crawl steps - one
collects metadata, another collects dependency data, and more...
Initial crawl may take around 20 hours or more. When crawling, progress indication is shown, with (very rough)
time estimation.

* Warning: As part of the dependency crawling process, this script
tries to run the `setup.py` file from all packages on PyPI, which may affect the filesystem on the running machine.
It is highly recommended to run this script in a virtual environment (a VM) and not on your personal computer.

Development
===========
To install this package from source and for development purposes, clone this repository and run the following:
* `easy_install infi.projector`
* `projector devenv build`
These commands will retrieve the project dependencies and create the command line script that runs the current source.