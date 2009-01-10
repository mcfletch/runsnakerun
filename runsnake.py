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
from squaremap import squaremap
from runsnakerun import pstatsloader


ID_OPEN = wx.NewId()
ID_EXIT = wx.NewId()
ID_PACKAGE_VIEW = wx.NewId()
ID_PERCENTAGE_VIEW = wx.NewId()

class PStatsAdapter( squaremap.DefaultAdapter ):
    def value( self, node, parent=None ):
        if isinstance( parent, pstatsloader.PStatGroup ):
            if parent.cummulative:
                return node.cummulative/parent.cummulative
            else:
                return 0
        return parent.child_cumulative_time( node )
    def label( self, node ):
        if isinstance( node, pstatsloader.PStatGroup ):
            return '%s / %s'%( node.directory, node.filename )
        return '%s:%s (%s)'%(node.filename,node.lineno,node.name)
    def empty( self, node ):
        if node.cummulative:
            return node.local/float( node.cummulative )
        return 0.0

class DirectoryViewAdapter( PStatsAdapter ):
    """Provides a directory-view-only adapter for PStats objects"""
    def children( self, node ):
        if isinstance( node, pstatsloader.PStatGroup ):
            return node.children 
        return []

class ColumnDefinition( object ):
    """Definition of a given column for display"""
    index = None
    name = None
    attribute = None
    sortOn = None
    format = None
    defaultOrder = False
    percentPossible = False
    def __init__( self, **named ):
        for key,value in named.items():
            setattr( self, key, value )
    def get( self, function ):
        """Get the value for this column from the function"""
        return getattr( function, self.attribute, '' )

class ProfileView( wx.ListCtrl ):
    """A sortable profile list control"""
    indicated = -1
    total = 0
    percentageView = False
    def __init__( 
        self, parent,
        id=-1, 
        pos=wx.DefaultPosition, size=wx.DefaultSize, 
        style=wx.LC_REPORT|wx.LC_VIRTUAL|wx.LC_VRULES|wx.LC_SINGLE_SEL, 
        validator=wx.DefaultValidator, 
        name="ProfileView",
    ):
        wx.ListCtrl.__init__( self, parent, id, pos, size, style, validator, name )
        self.sortOrder = [ (self.columns[2].defaultOrder,self.columns[2]), ]
        self.sorted = []
        self.CreateControls( )
    
    def SetPercentage( self, percent, total ):
        """Set whether to display percentage values (and total for doing so)"""
        self.percentageView = percent
        self.total = total 
        self.Refresh()
    
    def CreateControls( self ):
        """Create our sub-controls"""
        wx.EVT_LIST_COL_CLICK( self, self.GetId(), self.OnReorder )
        wx.EVT_LIST_ITEM_SELECTED( self, self.GetId(), self.OnNodeSelected )
        wx.EVT_MOTION( self, self.OnMouseMove )
        for i,column in enumerate( self.columns ):
            column.index = i
            self.InsertColumn( i, column.name )
            self.SetColumnWidth( i, wx.LIST_AUTOSIZE )
        self.SetItemCount(0)
    
    def OnNodeSelected( self, event ):
        """We have selected a node with the list control, tell the world"""
        try:
            node = self.sorted[ event.GetIndex() ]
        except IndexError, err: 
            print 'invalid index', event.GetIndex()
        else:
            wx.PostEvent( 
                self, 
                squaremap.SquareSelectionEvent( node=node, point=None, map=None ) 
            )
    def OnMouseMove( self, event ):
        point = event.GetPosition()
        item,where = self.HitTest( point )
        if item > -1:
            try:
                node = self.sorted[ item ]
            except IndexError, err:
                print 'invalid index', item 
            else:
                wx.PostEvent( 
                    self, 
                    squaremap.SquareHighlightEvent( node=node, point=point, map=None ) 
                )
    
    def SetIndicated( self, node ):
        """Set this node to indicated status"""
        self.indicated = self.NodeToIndex( node )
        self.Refresh(False)
        return self.indicated
    
    def NodeToIndex( self, node ):
        for i,n in enumerate( self.sorted ):
            if n is node:
                return i 
        return -1
    
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
        # TODO: store current selection and re-select after sorting...
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
    def integrateRecords( self, functions ):
        """Integrate records from the loader"""
        self.SetItemCount(len(functions))
        self.sorted = functions[:]
        self.reorder( )
        self.Refresh()
    indicated_attribute = wx.ListItemAttr()
    indicated_attribute.SetBackgroundColour( '#00ff00' )
    def OnGetItemAttr( self, item ):
        """Retrieve ListItemAttr for the given item (index)"""
        if self.indicated > -1 and item == self.indicated:
            return self.indicated_attribute
        return None
    def OnGetItemText(self, item, col):
        """Retrieve text for the item and column respectively"""
        # TODO: need to format for rjust and the like...
        try:
            column = self.columns[col]
            value = column.get(self.sorted[item])
        except IndexError, err:
            return None
        else:
            if column.percentPossible and self.percentageView and self.total:
                value = value/float( self.total ) * 100.00
            if column.format:
                return column.format%(value,)
            else:
                return str( value )
            
    columns = [
        ColumnDefinition(
            name = 'Name',
            attribute = 'name',
            defaultOrder = True,
        ),
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
            percentPossible = True,
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
            percentPossible = True,
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
            name = 'Line',
            attribute = 'lineno',
            sortOn = ('filename','lineno','directory'),
            defaultOrder = True,
        ),
    ]


class MainFrame( wx.Frame ):
    """The root frame for the display of a single data-set"""
    loader = None
    percentageView = False
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
        self.CreateMenuBar()
        self.CreateStatusBar()
        self.leftSplitter = wx.SplitterWindow(
            self
        )
        self.rightSplitter = wx.SplitterWindow(
            self.leftSplitter
        )
        self.listControl = ProfileView(
            self.leftSplitter,
        )
        self.adapter = PStatsAdapter()
        self.squareMap = squaremap.SquareMap(
            self.rightSplitter, 
            padding = 6,
            adapter = self.adapter,
        )
        self.tabs = wx.Notebook(
            self.rightSplitter,
        )
        
        self.calleeListControl = ProfileView(
            self.tabs,
        )
        self.allCalleeListControl = ProfileView(
            self.tabs,
        )
        self.allCallerListControl = ProfileView(
            self.tabs,
        )
        self.callerListControl = ProfileView(
            self.tabs,
        )
        self.ProfileListControls = [
            self.listControl,
            self.calleeListControl,
            self.allCalleeListControl,
            self.callerListControl,
            self.allCallerListControl,
        ]
        self.tabs.AddPage( self.calleeListControl, 'Callees', True )
        self.tabs.AddPage( self.allCalleeListControl, 'All Callees', False )
        self.tabs.AddPage( self.callerListControl, 'Callers', False )
        self.tabs.AddPage( self.allCallerListControl, 'All Callers', False )
        self.rightSplitter.SetSashSize( 10 )
        self.Maximize(True)
        # calculate size as proportional value for initial display...
        width,height = wx.GetDisplaySize()
        rightsplit = 2*(height//3)
        leftsplit = width//3
        print 'splits', leftsplit,rightsplit
        self.rightSplitter.SplitHorizontally( self.squareMap, self.tabs, rightsplit )
        self.leftSplitter.SplitVertically( self.listControl, self.rightSplitter, leftsplit )
        squaremap.EVT_SQUARE_HIGHLIGHTED( self.squareMap, self.OnSquareHighlightedMap )
        squaremap.EVT_SQUARE_HIGHLIGHTED( self.listControl, self.OnSquareHighlightedList )
        squaremap.EVT_SQUARE_SELECTED( self.listControl, self.OnSquareSelectedList )
        squaremap.EVT_SQUARE_SELECTED( self.squareMap, self.OnSquareSelectedMap )
        if sys.argv[1:]:
            wx.CallAfter( self.load, sys.argv[1] )
    def CreateMenuBar( self ):
        """Create our menu-bar for triggering operations"""
        menubar = wx.MenuBar()
        menu = wx.Menu( )
        menu.Append( ID_OPEN, '&Open', 'Open a new profile file' )
        menu.AppendSeparator()
        menu.Append( ID_EXIT, 'E&xit', 'Close RunSnakeRun' )
        menubar.Append( menu, '&File'  )
        menu = wx.Menu( )
        menu.Append( ID_PACKAGE_VIEW, '&Package View', 'View time spent by package/module' )
        menu.Append( ID_PERCENTAGE_VIEW, '&Percentage View', 'View time spent as percent of overall time' )
        menubar.Append( menu, '&View'  )
        self.SetMenuBar( menubar )
        
        wx.EVT_MENU( self, ID_EXIT, lambda evt: self.Close(True) )
        wx.EVT_MENU( self, ID_OPEN, self.OnOpenFile )
        wx.EVT_MENU( self, ID_PACKAGE_VIEW, self.OnPackageView )
        wx.EVT_MENU( self, ID_PERCENTAGE_VIEW, self.OnPercentageView )
    
    def OnOpenFile( self, event ):
        """Request to open a new profile file"""
        dialog = wx.FileDialog( self, style=wx.OPEN )
        if dialog.ShowModal( ) == wx.ID_OK:
            path = dialog.GetPath()
            if os.path.exists( path ):
                if self.loader:
                    # we've already got a displayed data-set, open new window...
                    frame = MainFrame()
                    frame.Show( True )
                    frame.load( path )
                else:
                    self.load( path )
    def OnPackageView( self, event ):
        if self.loader:
            self.adapter = DirectoryViewAdapter()
            self.squareMap.SetModel( self.loader.location_tree, self.adapter)
    def OnPercentageView( self, event ):
        self.percentageView = not self.percentageView
        total = self.loader.tree.cummulative
        for control in self.ProfileListControls:
            control.SetPercentage( self.percentageView, total )
        
    def OnSquareHighlightedMap( self, event ):
        self.SetStatusText( self.adapter.label( event.node ) )
        self.listControl.SetIndicated( event.node )
    def OnSquareHighlightedList( self, event ):
        self.SetStatusText( self.adapter.label( event.node ) )
        self.squareMap.SetHighlight( event.node, propagate=False  )
    
    def OnSquareSelectedList( self, event ):
        self.SetStatusText( self.adapter.label( event.node ) )
        self.squareMap.SetSelected( event.node )
        self.OnSquareSelected( event )
    
    def OnSquareSelectedMap( self, event ):
        index = self.listControl.NodeToIndex( event.node )
        self.listControl.Focus( index )
        self.listControl.Select( index, True )
        self.OnSquareSelected( event )
    
    def OnSquareSelected( self, event ):
        """Update all views to show selection children/parents"""
        self.calleeListControl.integrateRecords( event.node.children )
        self.callerListControl.integrateRecords( event.node.parents )
        self.allCalleeListControl.integrateRecords( event.node.descendants() )
        self.allCallerListControl.integrateRecords( event.node.ancestors() )
    
    def load( self, filename ):
        """Load our hotshot dataset (iteratively)"""
        self.loader = pstatsloader.PStatsLoader( filename )
        self.listControl.integrateRecords( self.loader.rows.values())
        self.squareMap.SetModel( self.loader.tree )


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
    app = RunSnakeRunApp(0)
    app.MainLoop()



if __name__ == "__main__":
    main()
