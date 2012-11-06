"""Adapter for RunSnakeRun to load coldshot profiles"""
import wx, sys, os, logging
log = logging.getLogger( __name__ )
from squaremap import squaremap
from coldshot import stack

class BaseColdshotAdapter( squaremap.DefaultAdapter):
    """Base class for the various adapters"""
    percentageView = False
    total = 0
    def filename( self, node ):
        return getattr(node,'path',None)
    color_mapping = None

    def background_color(self, node, depth):
        """Create a (unique-ish) background color for each node"""
        if self.color_mapping is None:
            self.color_mapping = {}
        color = self.color_mapping.get(node.key)
        if color is None:
            depth = len(self.color_mapping)
            red = (depth * 10) % 255
            green = 200 - ((depth * 5) % 200)
            blue = (depth * 25) % 200
            self.color_mapping[node.key] = color = wx.Colour(red, green, blue)
        return color

    def SetPercentage(self, percent, total):
        """Set whether to display percentage values (and total for doing so)"""
        self.percentageView = percent
        self.total = total

    def parents(self, node):
        return getattr(node, 'parents', [])
    def label(self, node):
        if self.percentageView and self.total:
            time = '%0.2f%%' % round(node.cumulative * 100.0 / self.total, 2)
        else:
            time = '%0.3fs' % round(node.cumulative, 3)
        return '%s@%s:%s [%s]' % (node.name, node.filename, node.line, time)

class ColdshotAdapter(BaseColdshotAdapter):
    """Adapts a coldshot.loader.Loader into a Squaremap-compatible structure"""

    def value(self, node, parent=None):
        return parent.child_cumulative_time(node)
    
    def empty(self, node):
        """Calculate percentage of "empty" time"""
        return node.empty

#
#class ColdshotCallsAdapter( BaseColdshotAdapter ):
#    def value(self, node, parent=None):
#        return node.cumulative / parent.cumulative
#    
#    def empty(self, node):
#        """Calculate percentage of "empty" time"""
#        return node.empty

class ModuleAdapter( ColdshotAdapter ):
    """Currently doesn't do anything different"""
    def label(self, node):
        if isinstance( node, stack.FunctionInfo ):
            return super( ModuleAdapter, self ).label( node )
        if self.percentageView and self.total:
            time = '%0.2f%%' % round(node.cumulative * 100.0 / self.total, 2)
        else:
            time = '%0.3fs' % round(node.cumulative, 3)
        return '%s [%s]'%(node.key or 'PYTHONPATH', time)
    def parents( self, node ):
        if isinstance( node, stack.FunctionInfo ):
            parent = node.loader.modules.get( node.module )
            if parent:
                return [parent]
            return []
        else:
            return getattr( node, 'parents', [] )
        
