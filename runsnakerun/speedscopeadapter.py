from __future__ import absolute_import
import wx, sys, os, logging

log = logging.getLogger(__name__)
from squaremap import squaremap
from .speedscopeloader import SpeedScopeFile


class BaseSpeedScopeAdapter(squaremap.DefaultAdapter):
    """Base class for the various adapters"""

    percentageView = False
    total = 0

    def filename(self, node):
        return getattr(getattr(node, "frame", None), "file", None)

    color_mapping = None

    def background_color(self, node, depth):
        """Create a (unique-ish) background color for each node"""
        if self.color_mapping is None:
            self.color_mapping = {}
        color = self.color_mapping.get(node.path)
        if color is None:
            depth = len(self.color_mapping)
            red = (depth * 10) % 255
            green = 200 - ((depth * 5) % 200)
            blue = (depth * 25) % 200
            self.color_mapping[node.path] = color = wx.Colour(red, green, blue)
        return color

    def SetPercentage(self, percent, total):
        """Set whether to display percentage values (and total for doing so)"""
        self.percentageView = percent
        self.total = total

    def parents(self, node):
        return getattr(node, "parents", [])

    def label(self, node):
        if self.percentageView and self.total:
            time = "%0.2f%%" % round(node.cumulative * 100.0 / self.total, 2)
        else:
            time = "%0.3fs" % round(node.cumulative, 3)
        return "%s [%s]" % (node.frame, time)


class SpeedScopeAdapter(BaseSpeedScopeAdapter):
    """Adapts a SpeedScope.Profile into a Squaremap-compatible structure"""

    def value(self, node, parent=None):
        if parent:
            return parent.child_cumulative_time(node)
        else:
            return node.cumulative

    def empty(self, node):
        """Calculate percentage of "empty" time"""
        return node.local / float(node.cumulative)


class SpeedScopeLoader(SpeedScopeFile):
    """SpeedScope loader subclass with knowledge of squaremap adapters"""

    @property
    def profile(self):
        for profile in self.profiles:
            return profile

    def functions_rows(self):
        """Get cProfile-like function metadata rows
        
        returns an ID: function mapping
        """
        return self.profile.parent_map

    # def location_rows( self ):
    #     """Get our location records (finalized)

    #     returns an module-name: Grouping mapping
    #     """
    #     self.info.finalize_modules()
    #     return self.info.modules

    ROOTS = [
        "functions",
        # 'location',
    ]

    def get_root(self, key):
        """Retrieve the given root by type-key"""
        for profile in self.profiles:
            return profile.root

    def get_rows(self, key):
        """Get the set of rows for the type-key"""
        for profile in self.profiles:
            return profile.parent_map

    def get_adapter(self, key):
        """Get an adapter for our given key"""
        if key == "functions":
            return SpeedScopeAdapter()
        # elif key == 'location':
        #     return ModuleAdapter()
        else:
            raise KeyError("""Unknown root type %s""" % (key,))
