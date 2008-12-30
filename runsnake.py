#! /usr/bin/python
"""The main script for the RunSnakeRun profile viewer

What we want to be able to do:
	Sort by any of:
		numcalls
		num recursive calls
		local time 
		(local/numcalls)
		cummulative time
		(cummulative/numcalls)
		filename
		function name
"""
import wx, sys, os
import pstats


class ColumnDefinition( object ):
	"""Definition of a given column for display"""
	index = None
	name = None
	attribute = None
	sortOn = None
	format = None
	defaultOrder = False
	def __init__( self, **named ):
		for key,value in named.items():
			setattr( self, key, value )
	def get( self, function ):
		"""Get the value for this column from the function"""
		return getattr( function, self.attribute )

class PStatRow( object ):
	"""Simulates a HotShot profiler record using PStats module"""
	def __init__( self, key, raw ):
		file,line,func = key
		try:
			dirname,basename = os.path.dirname(file),os.path.basename(file)
		except ValueError, err:
			dirname = ''
			basename = file
		cc, nc, tt, ct, callers = raw
		(
			self.calls, self.recursive, self.local, self.localPer,
			self.cummulative, self.cummulativePer, self.directory,
			self.filename, self.name, self.lineno
		) = (
			cc, 
			nc,
			tt,
			tt/nc,
			ct,
			ct/cc,
			dirname,
			basename,
			func,
			line,
		)

class ProfileView( wx.ListCtrl ):
	"""A sortable profile list control"""
	def __init__( 
		self, parent, filename,
		id=-1, 
		pos=wx.DefaultPosition, size=wx.DefaultSize, 
		style=wx.LC_REPORT|wx.LC_VIRTUAL|wx.LC_VRULES, 
		validator=wx.DefaultValidator, 
		name="ProfileView",
	):
		wx.ListCtrl.__init__( self, parent, id, pos, size, style, validator, name )
		self.sortOrder = [ (self.columns[2].defaultOrder,self.columns[2]), ]
		self.files = {}
		self.functions = {}
		self.sorted = []
		self.CreateControls( )
		wx.CallAfter( self.load, filename )
	def CreateControls( self ):
		"""Create our sub-controls"""
		wx.EVT_LIST_COL_CLICK( self, self.GetId(), self.OnReorder )
		for i,column in enumerate( self.columns ):
			column.index = i
			self.InsertColumn( i, column.name )
			self.SetColumnWidth( i, wx.LIST_AUTOSIZE )
		self.SetItemCount(0)
	def columnByAttribute( self, name ):
		for column in self.columns:
			if column.attribute == name:
				return column 
		return None
	def OnReorder( self, event ):
		"""Given a request to reorder, tell us to reorder"""
		column = self.columns[event.GetColumn()]
		if column.sortOn:
			# multiple sorts for the click...
			columns = [ self.columnByAttribute( attr ) for attr in column.sortOn ]
			diff = [ (a,b) for a,b in zip( self.sortOrder, columns ) if b is not a[1]]
			if not diff:
				self.sortOrder[0] = (not self.sortOrder[0][0], column)
			else:
				self.sortOrder = [
					(c.defaultOrder,c) for c in columns 
				] + [ (a,b) for (a,b) in self.sortOrder if b not in columns]
		else:
			if column is self.sortOrder[0][1]:
				# reverse current major order
				self.sortOrder[0] = (not self.sortOrder[0][0], column)
			else:
				self.sortOrder = [(column.defaultOrder,column)] + [
					(a,b) 
					for (a,b) in self.sortOrder if b is not column 
				]
		self.reorder()
		self.Refresh()
		
	def reorder( self ):
		"""Force a reorder of the displayed items"""
		self.sorted.sort(self.compareFunction)
	def compareFunction( self, first, second ):
		"""Compare two functions according to our current sort order"""
		for ascending,column in self.sortOrder:
			aValue,bValue = column.get(first),column.get(second)
			diff = cmp(aValue,bValue)
			if diff:
				if not ascending:
					return - diff 
				else:
					return diff 
		return 0
	def load( self, filename ):
		"""Load our hotshot dataset (iteratively)"""
		from runsnakerun import hotshotreader
		try:
			for count, files, functions in hotshotreader.loadHotshot( filename, 20000 ):
				if not count % 200000:
					try:
						self.integrateRecords( files, functions )
					except wx.PyDeadObjectError, err:
						return
				wx.Yield()
			try:
				self.integrateRecords( files, functions )
			except wx.PyDeadObjectError, err:
				return
		except ValueError, err:
			# likely a cProfile version...
			s = pstats.Stats( filename )
			s.sort_stats('calls')
			records = {}
			_,funcs = s.get_print_list(())
			for raw in funcs:
				#print raw, s.stats.get( raw )
				stat = s.stats.get(raw, None)
				if stat is not None:
					records[raw] = PStatRow(raw,stat)
			self.integrateRecords( [filename], records)
			
	def integrateRecords( self, files, functions ):
		"""Integrate records from the loader"""
		self.SetItemCount(len(functions))
		self.sorted = functions.values()
		self.reorder( )
		self.Refresh()
	def OnGetItemText(self, item, col):
		"""Retrieve text for the item and column respectively"""
		# XXX need for format for rjust and the like...
		try:
			column = self.columns[col]
			value = column.get(self.sorted[item])
		except IndexError, err:
			return None
		else:
			if column.format:
				return column.format%(value,)
			else:
				return str( value )
			
	columns = [
		ColumnDefinition(
			name = 'Calls',
			attribute = 'calls',
		),
		ColumnDefinition(
			name = 'RCalls',
			attribute = 'recursive',
		),
		ColumnDefinition(
			name = 'Local',
			attribute = 'local',
			format = '%0.5f',
		),
		ColumnDefinition(
			name = '/Call',
			attribute = 'localPer',
			format = '%0.5f',
		),
		ColumnDefinition(
			name = 'Cum',
			attribute = 'cummulative',
			format = '%0.5f',
		),
		ColumnDefinition(
			name = '/Call',
			attribute = 'cummulativePer',
			format = '%0.5f',
		),
		ColumnDefinition(
			name = 'Directory',
			attribute = 'directory',
			sortOn = ('directory','filename','lineno'),
			defaultOrder = True,
		),
		ColumnDefinition(
			name = 'File',
			attribute = 'filename',
			sortOn = ('filename','lineno','directory',),
			defaultOrder = True,
		),
		ColumnDefinition(
			name = 'Name',
			attribute = 'name',
			defaultOrder = True,
		),
		ColumnDefinition(
			name = 'Line',
			attribute = 'lineno',
			sortOn = ('filename','lineno','directory'),
			defaultOrder = True,
		),
	]

	


class MainFrame( wx.Frame ):
	"""The root frame for the display of a single data-set"""
	def __init__( 
		self, parent=None, id=-1, 
		title="Run Snake Run", 
		pos=wx.DefaultPosition, 
		size=wx.DefaultSize,
		style=wx.DEFAULT_FRAME_STYLE|wx.CLIP_CHILDREN,
		name= "RunSnakeRun",
	):
		"""Initialise the Frame"""
		wx.Frame.__init__( self, parent, id, title, pos, size, style, name )
		self.CreateControls()
	def CreateControls( self ):
		"""Create our sub-controls"""
		self.splitter = wx.SplitterWindow(
			self, 
		)
		self.listControl = ProfileView(
			self.splitter, sys.argv[1]
		)
		self.heatMap = HeatMapView(
			self.splitter, 
		)
		self.splitter.SplitHorizontally( self.listControl, self.heatMap )
		self.Maximize(True)


class RunSnakeRunApp(wx.App):
	"""Basic application for holding the viewing Frame"""
	def OnInit(self):
		"""Initialise the application"""
		wx.InitAllImageHandlers()
		frame = MainFrame(
		)
		frame.Show(True)
		self.SetTopWindow(frame)
		return True

usage = """runsnake.py profilefile

profilefile -- a file generated by a HotShot profile run from Python
"""
def main():
	"""Mainloop for the application"""
	if not sys.argv[1:]:
		print usage
	else:
		app = RunSnakeRunApp(0)
		app.MainLoop()



if __name__ == "__main__":
	main()
