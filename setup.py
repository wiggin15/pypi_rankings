from setuptools import setup
from setuptools import find_packages

setup(
    name='pypi_rankings',
    version='0.0.1',
    description='Collect and show statistics and rankings of packages in PyPI',
    author='Arnon Yaari',
    author_email='arnony@infinidat.com',
    url='https://github.com/wiggin15/pypi_rankings',
    package_dir = {'pypi_rankings': ''},
    packages=find_packages(),
    install_requires=["requests", "infi.execute", "infi.pypi_manager", "itertools_recipes", "Flask"],
    entry_points = dict(
        console_scripts = ['start_pypi_rankings = pypi_rankings.webserver:main']
    )
)