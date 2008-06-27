"""Module implementing the hotshot profile-data reader"""
from hotshot import _hotshot
import os
import parser
import symbol
import sys
import Numeric
import time

class FileRecord( object ):
	"""Record for a source-file in the system"""
	def __init__( self, fileno, filename ):
		"""Create the record for this file"""
		self.fileno = fileno 
		self.filename = filename
		self.functions = {}

class FunctionRecord( object ):
	def __init__( self, fileno,lineno, name, file ):
		"""Initialise the record for this function"""
		self.fileno = fileno
		self.lineno = lineno 
		self.file = file # note, this is a circular reference!
		self.key = (fileno,lineno)
		self.name = name 
		# accumArray being (local, cummulative) time elapsed
		self.accumArray = Numeric.zeros( (2,), 'd' )
		# callArray being (direct, recursive) call counts
		self.callArray = Numeric.zeros( (2,), 'l' )
	def get_local( self ):
		return self.accumArray[0]
	def get_localPer( self ):
		return self.accumArray[0]/(self.callArray[0] or 1)
	def get_cummulative( self ):
		return self.accumArray[1]
	def get_cummulativePer( self ):
		return self.accumArray[1]/(self.callArray[0] or 1)
	def get_calls( self ):
		return self.callArray[0]
	def get_recursive( self ):
		return self.callArray[1]
	def get_directory( self ):
		return os.path.dirname( self.file.filename )
	def get_filename( self ):
		return os.path.basename( self.file.filename )
	local = property( get_local, None, None, """Local elapsed time""" )
	cummulative = property( get_cummulative, None, None, """Cummulative elapsed time""" )
	localPer = property( get_localPer, None, None, """Local elapsed time per call (average)""" )
	cummulativePer = property( get_cummulativePer, None, None, """Cummulative elapsed time per call (average)""" )
	calls = property( get_calls, None, None, """Total number of calls to the function""" )
	recursive = property( get_recursive, None, None, """Calls to the function where the function is already on the call stack""" )
	directory = property( get_directory, None, None, """Directory in which our file is stored""" )
	filename = property( get_filename, None, None, """The (base) file name in which we are defined""" )

GIVES_DELTA = {
	_hotshot.WHAT_LINENO:1,
	_hotshot.WHAT_EXIT:1,
	_hotshot.WHAT_ENTER:1,
}
SECONDS_FRACTION = .000001



def loadHotshot( filename, yieldCount=10000 ):
	"""Given a hotshot profile file, load to in-memory structures
	
	yields recordCount, { fileno: filename, ... }, { (fileno,lineno): FunctionRecord, ...}
	
	for every yieldCount records in the file
	"""
	reader = _hotshot.logreader(filename)
	files = {}
	functions = {}
	stackSize = sys.getrecursionlimit() * 2
	frames = [None]*stackSize
	localDeltas = Numeric.zeros( (stackSize,), 'l' )
	# make this local for speed...
	givesDelta = GIVES_DELTA.has_key
	
	secondsFraction = SECONDS_FRACTION
	getFunction = functions.get
	defineFile = _hotshot.WHAT_DEFINE_FILE
	defineFunction = _hotshot.WHAT_DEFINE_FUNC
	whatEnter = _hotshot.WHAT_ENTER
	whatExit = _hotshot.WHAT_EXIT
	depth = -1
	i = 0
	for i, (what, tdelta, fileno, lineno) in enumerate(reader):
		if (not i%yieldCount) and i:
			yield i, files, functions
		if givesDelta( what ):
			if what == whatEnter:
				key = (fileno,lineno)
				function = getFunction( key )
				depth += 1
				try:
					localDeltas[depth] = 0
				except IndexError, err:
					print 'extend localDeltas'
					localDeltas = Numeric.resize( localDeltas, (depth+200,))
				if function is not None:
					try:
						frames[depth] = function.accumArray
					except IndexError, err:
						print 'extend frames'
						frames.extend( [None]*((depth+200)-len(frames)) )
					function.callArray[0]+=1
					# XXX like to get rid of this copy eventually...
					for frame in frames[:depth]:
						if frame is function.accumArray:
							function.callArray[1] += 1
							break
				else:
					try:
						frames[depth] = None
					except IndexError, err:
						print 'extend frames'
						frames.extend( [None]*((depth+200)-len(frames)) )
			# should both enter and exit tdelta get credited to the lower function?
			# current does so
			localDeltas[depth] += tdelta
			if what == whatExit:
				# add time spent in this frame to cummulative for all open frames
				localDelta = localDeltas[depth]*secondsFraction
				# XXX should avoid this list-copy somehow...
				for frame in frames[:depth]:
					if frame is not None:
						frame[1] += localDelta
				try:
					# add time spent in this instance of this frame to local cummulative for this frame
					depth -= 1
					if frames[depth] is not None:
						frames[depth][0] += localDelta
				except IndexError, err:
					print 'Warning frame underflow!'
		elif what == defineFile:
			files[ fileno ] = FileRecord( fileno, tdelta )
		elif what == defineFunction:
			file = files.get( fileno )
			record = FunctionRecord( fileno,lineno,tdelta, file)
			functions[ (fileno,lineno) ] = record
			if file is not None:
				file.functions[ lineno ] = record
		else:
			print 'unrecognised what', what
			for name in [n for n in dir(_hotshot) if n.startswith( 'WHAT_')]:
				if getattr( _hotshot,name) == what:
					print ' == %s'%(name,)
					break

	yield i, files, functions


if __name__ == "__main__":
	startTime = time.time()
	for i, files, functions in loadHotshot( sys.argv[1], 100000 ):
		t2 = time.time()
		print '%s records in %ss: %s records/second'%(
			i, t2-startTime, i/((t2-startTime) or 1),
		)
	completion = time.time()
	print 'FUNCTIONS'
	functionValues = functions.items()
	functionValues.sort()
	for (fileno,lineno),value in functionValues:
		key = (fileno,lineno)
		print files.get(fileno).filename, lineno,
		print value.calls, value.recursive, value.local, value.cummulative
	print 'read %i records in %s seconds'%( i, completion-startTime )
