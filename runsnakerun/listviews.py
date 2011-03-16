import wx, sys, os, logging
from gettext import gettext as _
from squaremap import squaremap

if sys.platform == 'win32':
    windows = True
else:
    windows = False

log = logging.getLogger(__name__)

class ColumnDefinition(object):
    """Definition of a given column for display using attribute access"""

    index = None
    name = None
    attribute = None
    sortOn = None
    format = None
    defaultOrder = False
    percentPossible = False
    targetWidth = None
    getter = None

    def __init__(self, **named):
        for key, value in named.items():
            setattr(self, key, value)

    def get(self, function):
        """Get the value for this column from the function"""
        if self.getter:
            value = self.getter( function )
        else:
            value = getattr(function, self.attribute, '')
        return value

class DictColumn( ColumnDefinition ):
    def get( self, record ):
        if self.getter:
            value = self.getter( record )
        else:
            value = record.get(self.attribute, '')
        return value


class DataView(wx.ListCtrl):
    """A sortable profile list control"""

    indicated = -1
    total = 0
    percentageView = False
    activated_node = None
    selected_node = None
    indicated_node = None

    def __init__(
        self, parent,
        id=-1,
        pos=wx.DefaultPosition, size=wx.DefaultSize,
        style=wx.LC_REPORT|wx.LC_VIRTUAL|wx.LC_VRULES|wx.LC_SINGLE_SEL,
        validator=wx.DefaultValidator,
        columns=None,
        sortOrder=None,
        name=_("ProfileView"),
    ):
        wx.ListCtrl.__init__(self, parent, id, pos, size, style, validator,
                             name)
        if columns is not None:
            self.columns = columns
        
        self.sortOrder = [ (self.columns[5].defaultOrder, self.columns[5]), ]
        self.sorted = []
        self.CreateControls()

    def SetPercentage(self, percent, total):
        """Set whether to display percentage values (and total for doing so)"""
        self.percentageView = percent
        self.total = total
        self.Refresh()

    def CreateControls(self):
        """Create our sub-controls"""
        wx.EVT_LIST_COL_CLICK(self, self.GetId(), self.OnReorder)
        wx.EVT_LIST_ITEM_SELECTED(self, self.GetId(), self.OnNodeSelected)
        wx.EVT_MOTION(self, self.OnMouseMove)
        wx.EVT_LIST_ITEM_ACTIVATED(self, self.GetId(), self.OnNodeActivated)
        self.CreateColumns()
    def CreateColumns( self ):
        """Create/recreate our column definitions from current self.columns"""
        self.SetItemCount(0)
        # clear any current columns...
        for i in range( self.GetColumnCount())[::-1]:
            self.DeleteColumn( i )
        # now create
        for i, column in enumerate(self.columns):
            column.index = i
            self.InsertColumn(i, column.name)
            if not windows or column.targetWidth is None:
                self.SetColumnWidth(i, wx.LIST_AUTOSIZE)
            else:
                self.SetColumnWidth(i, column.targetWidth)
    def SetColumns( self, columns ):
        """Set columns to a set of values other than the originals and recreates column controls"""
        self.columns = columns 
        self.CreateColumns()

    def OnNodeActivated(self, event):
        """We have double-clicked for hit enter on a node refocus squaremap to this node"""
        try:
            node = self.sorted[event.GetIndex()]
        except IndexError, err:
            log.warn(_('Invalid index in node activated: %(index)s'),
                     index=event.GetIndex())
        else:
            wx.PostEvent(
                self,
                squaremap.SquareActivationEvent(node=node, point=None,
                                                map=None)
            )

    def OnNodeSelected(self, event):
        """We have selected a node with the list control, tell the world"""
        try:
            node = self.sorted[event.GetIndex()]
        except IndexError, err:
            log.warn(_('Invalid index in node selected: %(index)s'),
                     index=event.GetIndex())
        else:
            if node is not self.selected_node:
                wx.PostEvent(
                    self,
                    squaremap.SquareSelectionEvent(node=node, point=None,
                                                   map=None)
                )

    def OnMouseMove(self, event):
        point = event.GetPosition()
        item, where = self.HitTest(point)
        if item > -1:
            try:
                node = self.sorted[item]
            except IndexError, err:
                log.warn(_('Invalid index in mouse move: %(index)s'),
                         index=event.GetIndex())
            else:
                wx.PostEvent(
                    self,
                    squaremap.SquareHighlightEvent(node=node, point=point,
                                                   map=None)
                )

    def SetIndicated(self, node):
        """Set this node to indicated status"""
        self.indicated_node = node
        self.indicated = self.NodeToIndex(node)
        self.Refresh(False)
        return self.indicated

    def SetSelected(self, node):
        """Set our selected node"""
        self.selected_node = node
        index = self.NodeToIndex(node)
        if index != -1:
            self.Focus(index)
            self.Select(index, True)
        return index

    def NodeToIndex(self, node):
        for i, n in enumerate(self.sorted):
            if n is node:
                return i
        return -1

    def columnByAttribute(self, name):
        for column in self.columns:
            if column.attribute == name:
                return column
        return None

    def OnReorder(self, event):
        """Given a request to reorder, tell us to reorder"""
        column = self.columns[event.GetColumn()]
        return self.ReorderByColumn( column )
    def ReorderByColumn( self, column ):
        """Reorder the set of records by column"""
        # TODO: store current selection and re-select after sorting...
        self.SetNewOrder( column )
        self.reorder()
        self.Refresh()

    def SetNewOrder( self, column ):
        if column.sortOn:
            # multiple sorts for the click...
            columns = [self.columnByAttribute(attr) for attr in column.sortOn]
            diff = [(a, b) for a, b in zip(self.sortOrder, columns)
                    if b is not a[1]]
            if not diff:
                self.sortOrder[0] = (not self.sortOrder[0][0], column)
            else:
                self.sortOrder = [
                    (c.defaultOrder, c) for c in columns
                ] + [(a, b) for (a, b) in self.sortOrder if b not in columns]
        else:
            if column is self.sortOrder[0][1]:
                # reverse current major order
                self.sortOrder[0] = (not self.sortOrder[0][0], column)
            else:
                self.sortOrder = [(column.defaultOrder, column)] + [
                    (a, b)
                    for (a, b) in self.sortOrder if b is not column
                ]

    def reorder(self):
        """Force a reorder of the displayed items"""
        self.sorted.sort(self.compareFunction)

    def compareFunction(self, first, second):
        """Compare two functions according to our current sort order"""
        for ascending, column in self.sortOrder:
            aValue, bValue = column.get(first), column.get(second)
            diff = cmp(aValue, bValue)
            if diff:
                if not ascending:
                    return -diff
                else:
                    return diff
        return 0

    def integrateRecords(self, functions):
        """Integrate records from the loader"""
        self.SetItemCount(len(functions))
        self.sorted = functions[:]
        self.reorder()
        self.Refresh()

    indicated_attribute = wx.ListItemAttr()
    indicated_attribute.SetBackgroundColour('#00ff00')

    def OnGetItemAttr(self, item):
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
                value = value / float(self.total) * 100.00
            if column.format:
                try:
                    return column.format % (value,)
                except Exception, err:
                    log.warn('Column %s could not format %r value: %s',
                        column.name, type(value), value
                    )
                    if isinstance(value,(unicode,str)):
                        return value
                    return unicode(value)
            else:
                if isinstance(value,(unicode,str)):
                    return value
                return unicode(value)
