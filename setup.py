#!/usr/bin/env python
"""Installs RunSnakeRun using distutils

Run:
	python setup.py install
to install the package from the source archive.
"""

if __name__ == "__main__":
	import sys,os, string
	from distutils.sysconfig import *
	from distutils.core import setup

	##############
	## Following is from Pete Shinners,
	## apparently it will work around the reported bug on
	## some unix machines where the data files are copied
	## to weird locations if the user's configuration options
	## were entered during the wrong phase of the moon :) .
	from distutils.command.install_data import install_data
	class smart_install_data(install_data):
		def run(self):
			#need to change self.install_dir to the library dir
			install_cmd = self.get_finalized_command('install')
			self.install_dir = getattr(install_cmd, 'install_lib')
			# should create the directory if it doesn't exist!!!
			return install_data.run(self)
	##############
	def npFilesFor( dirname ):
		"""Return all non-python-file filenames in dir"""
		result = []
		allResults = []
		for name in os.listdir(dirname):
			path = os.path.join( dirname, name )
			if os.path.isfile( path) and os.path.splitext( name )[1] not in ('.py','.pyc','.pyo'):
				result.append( path )
			elif os.path.isdir( path ) and name.lower() !='cvs':
				allResults.extend( npFilesFor(path))
		if result:
			allResults.append( (dirname, result))
		return allResults
	dataFiles = npFilesFor( 'doc') 

	from sys import hexversion
	if hexversion >= 0x2030000:
		# work around distutils complaints under Python 2.2.x
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
	else:
		extraArguments = {
		}
	### Now the actual set up call
	setup (
		name = "RunSnakeRun",
		version = '1.0.3',
		url = "http://www.vrplumber.com/programming/",
		description = "GUI Viewer for Hotshot profiling runs",
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
		data_files = dataFiles,
		cmdclass = {'install_data':smart_install_data},
		**extraArguments
	)

