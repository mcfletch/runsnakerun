#!/usr/bin/env python
"""Installs RunSnakeRun using distutils

Run:
    python setup.py install
to install the package from the source archive.
"""
import os, sys
from setuptools import setup

version = [
    (line.split('=')[1]).strip().strip('"').strip("'")
    for line in open(
        os.path.join(os.path.dirname(__file__), 'runsnakerun', '__init__.py')
    )
    if line.startswith('__version__')
][0]

if __name__ == "__main__":
    ### Now the actual set up call
    if sys.platform == 'darwin':
        gui_commands = [
            'runsnake=runsnakerun.macshim:macshim',
            'runsnake32=runsnakerun.runsnake:main',
            'runsnakemem=runsnakerun.runsnake:meliaemain',
        ]
    else:
        gui_commands = [
            'runsnake=runsnakerun.runsnake:main',
            'runsnakemem=runsnakerun.runsnake:meliaemain',
        ]
    setup(
        name="RunSnakeRun",
        version=version,
        url="https://github.com/mcfletch/runsnakerun",
        download_url="https://pypi.org/project/RunSnakeRun/",
        description="GUI Viewer for Python profiling runs",
        author="Mike C. Fletcher",
        author_email="mcfletch@vrplumber.com",
        install_requires=[
            'pathlib2',  # dependency for wxPython
            'six',
            'SquareMap >= 1.0.5',  # to work with python 3.x and Pheonix
            'wxPython',
        ],
        license="BSD",
        package_dir={'runsnakerun': 'runsnakerun',},
        packages=['runsnakerun',],
        options={'sdist': {'force_manifest': 1, 'formats': ['gztar', 'zip'],},},
        zip_safe=False,
        entry_points={'gui_scripts': gui_commands,},
        install_package_data=True,
        classifiers=[
            """License :: OSI Approved :: BSD License""",
            """Programming Language :: Python :: 2""",
            """Programming Language :: Python :: 3""",
            """Topic :: Software Development :: Libraries :: Python Modules""",
            """Intended Audience :: Developers""",
        ],
        keywords='profile,gui,wxPython,squaremap',
        long_description="""GUI Viewer for Python profiling runs

Provides explorability and overall visualization of the call tree
and package/module structures.""",
        platforms=['Any'],
    )
