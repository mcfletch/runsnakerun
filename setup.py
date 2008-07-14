#!/usr/bin/env python
"""Installs RunSnakeRun using distutils

Run:
	python setup.py install
to install the package from the source archive.
"""
from setuptools import setup

if __name__ == "__main__":
	extraArguments = {
		'classifiers': [
			"""License :: OSI Approved :: BSD License""",
			"""Programming Language :: Python""",
			"""Topic :: Software Development :: Libraries :: Python Modules""",
			"""Intended Audience :: Developers""",
		],
		'keywords': 'hotshot,profile,gui,wxPython',
		'long_description' : """GUI Viewer for Hotshot profiling runs

Simple GUI client to load and display Hotshot profiler runs,
displays the profile results incrementally, loading in the 
background as you browse the results.""",
		'platforms': ['Any'],
	}
	### Now the actual set up call
	setup (
		name = "RunSnakeRun",
		version = '1.0.4',
		url = "http://www.vrplumber.com/programming/runsnakerun/",
		download_url = "http://www.vrplumber.com/programming/runsnakerun/",
		description = "GUI Viewer for Hotshot/cProfile profiling runs",
		author = "Mike C. Fletcher",
		author_email = "mcfletch@vrplumber.com",
		license = "BSD",

		package_dir = {
			'runsnakerun':'.',
		},
		packages = [
			'runsnakerun',
		],
		options = {
			'sdist':{'force_manifest':1,'formats':['gztar','zip'],},
		},
		zip_safe=False,
		entry_points = {
			'gui_scripts': [
				'runsnake=runsnakerun.runsnake:main',
			],
		},
		**extraArguments
	)

