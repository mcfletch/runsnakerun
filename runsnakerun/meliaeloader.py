#! /usr/bin/env python
"""Module to load meliae memory-profile dumps

Trees:

    * has-a
        * module root 
        * each held reference contributes a weighted cost to the parent 
        * hierarchy of held objects, so globals, classes, functions, and their children
        * held modules do not contribute to cost
        
        * module 
            * instance-tree

    * is-a
        * class/type root 
            * instances contribute to their type 
                * summary-by-type 
            

"""
import wx, sys, os, logging
import wx.lib.newevent
log = logging.getLogger( 'squaremap' )
#log.setLevel( logging.DEBUG )
try:
    import json 
except ImportError, err:
    import simplejson as json
import sys
from squaremap import squaremap

def recurse( record, index, stop_types=None,already_seen=None, type_group=False ):
    """Depth first traversal of a tree, all children are yielded before parent
    
    record -- dictionary record to be recursed upon 
    index -- mapping 'address' ids to dictionary records 
    stop_types -- types which will *not* recurse 
    already_seen -- set storing already-visited nodes 
    
    yields the traversed nodes
    """
    if already_seen is None:
        already_seen = set()
    if stop_types is None:
        stop_types = set()
    if record['address'] not in already_seen:
        already_seen.add(record['address'])
        if 'refs' in record:
            if type_group:
                for typ in children_by_type( record, index ):
                    if typ['type'] not in stop_types:
                        for child in typ['children']:
                            for descendant in recurse( child, index, stop_types, already_seen=already_seen, type_group=type_group ):
                                if descendant['type'] not in stop_types:
                                    yield descendant
                        if len(typ['children']) > 5:
                            yield typ 
            else:
                for child in children( record, index ):
                    if child['type'] not in stop_types:
                        for descendant in recurse( child, index, stop_types, already_seen=already_seen, type_group=type_group ):
                            if descendant['type'] not in stop_types:
                                yield descendant
        yield record 

def children( record, index, key='refs' ):
    """Retrieve children records for given record"""
    for ref in record.get( key,[]):
        try:
            if isinstance( ref, dict ):
                yield ref 
            else:
                yield index[ref]
        except KeyError, err:
            pass 

def children_by_type( record, index, key='refs' ):
    """Get children grouped by type 
    
    returns (typ,[children]) for all children 
    """
    types = {}
    for child in children( record, index, key ):
        if child['type'] not in types:
            typ = index.get( child['type'] )
            if typ is None:
                typ = {
                    'address':None,
                    'type': child['type'] + ' (unknown)',
                }
            types[child['type']] = typ = {
                'address': typ['address'],
                'type': 'references to %s'%(typ['type'],),
                'name': typ.get('name'),
                'size': 0, # just a collection here...
                'parents': [record['address']],
                'children': [],
                'refs': [],
            }
        types[child['type']]['children'].append( child )
    return types.values()
    

def group_types( children, types ):
    """Take a group of children nodes, coalesce into typed groups"""
    size_info = {}
    for child in children:
        typ = size_info.get( child['type'] )
        if not typ:
            typ = types.get( child['type'] )
            if not typ:
                continue 
            else:
                size_info[ child['type']] = typ 
        # add child to typ...
        typ['rsize'] += child['rsize']
    values = size_info.values()
    for value in values:
        value['totsize'] = value['size'] + value['rsize']
    return sorted( values, key = lambda m: m.get('totsize',0))

def recurse_module( overall_record, index, shared, types=None, stop_types=None, already_seen=None, size_info=None ):
    """Creates a has-a recursive-cost hierarchy
    
    Mutates objects in-place to produce a hierarchy of memory usage based on 
    reference-holding cost assignment
    """
    if size_info is None:
        size_info = {} # address to size-info mapping
    count = 0
    for record in recurse( 
        overall_record, index, 
        stop_types=stop_types, 
        already_seen=already_seen, 
        type_group=True,
    ):
        if record['address'] in size_info:
            continue 
        count += 1
        if not count % 1000:
            print 'count', count
        #print '%(type)s %(name)s'%{ 'type':record.get('type'), 'name': record.get('name') }
        size_info[record['address']] = rinfo = {
            'address':record['address'],'type':record['type'],'name':record.get('name'),
            'size':record['size'],'module':overall_record['name'],
            'parents': shared.get(record['address'],[]),
        }
        if not record['refs']:
            rinfo['rsize'] = 0
            rinfo['children'] = []
        else:
            # TODO: track shared versus owned cost separately...
            # TODO: provide a flag to coalesce based on e.g. type at each level or throughout...
            rinfo['children'] = rinfo_children = list ( children( record, size_info ) )
            rinfo['rsize'] = sum([
                (
                    child.get('totsize',0)/len(shared.get( child['address'], [])) or 1
                )
                for child in rinfo_children
            ], 0 )
        rinfo['totsize'] = record['size'] + rinfo['rsize']
    for key,record in size_info.items():
        record['parents'] = list(children( record, size_info, 'parents' ))
    
    return size_info

def load( filename ):
    index = {} # address: structure
    back_refs = {} # referred: [referencer,referencer,...]
    shared = dict()
    modules = set()
    types = {}
    
    for line in open( filename ):
        struct = json.loads( line.strip())
        index[struct['address']] = struct 
        refs = struct['refs']
        for ref in refs:
            parents = shared.get( ref )
            if parents is None:
                shared[ref] = []
            shared[ref].append( struct['address'])
        if struct['type'] == 'module':
            modules.add( struct['address'] )
        elif struct['type'] == 'type':
            types[struct['name']] = struct
    modules = [
        x for x in index.itervalues() 
        if x['type'] == 'module'
    ]
    # expand module dictionaries
    for module in modules:
        if len(module['refs']) == 1:
            child = index.get( module['refs'][0] )
            if child is not None and child['type'] == 'dict':
                module['refs'] = child['refs']
                del index[child['address']]
    
    records = []
    size_info = {}
    for m in modules:
        if m.get('name') != 'sys':
            records.append( recurse_module(
                m, index, shared, types=None, stop_types=set(['module']), size_info=size_info
            ))
    size_info = [x for x in size_info.values() if x['type'] == 'module']
    size_info.sort( key = lambda m: m.get('totsize',0))
    all_modules = sum([x['totsize'] for x in size_info],0)
    return {
        'type':'dump',
        'name': filename,
        'children': size_info,
        'totsize': all_modules,
        'rsize': all_modules,
        'size': 0,
        'address': None,
    }

class MeliaeAdapter( squaremap.DefaultAdapter ):
    """Default adapter class for adapting node-trees to SquareMap API"""
    def children( self, node ):
        """Retrieve the set of nodes which are children of this node"""
        return node['children']
    def value( self, node, parent=None ):
        """Return value used to compare size of this node"""
        return node['totsize']
    def label( self, node ):
        """Return textual description of this node"""
        return ":".join([
            n for n in [
                node.get(k) for k in ['type','name','module']
            ] if n 
        ])
    def overall( self, node ):
        """Calculate overall size of the node including children and empty space"""
        return node.get('totsize',0)
    def children_sum( self, children,node ):
        """Calculate children's total sum"""
        return node.get('rsize',0)
    def empty( self, node ):
        """Calculate empty space as a fraction of total space"""
        overall = self.overall( node )
        if overall:
            return (overall - self.children_sum( self.children(node), node))/float(overall)
        return 0
    def parents( self, node ):
        """Retrieve/calculate the set of parents for the given node"""
        return node.get('parents',[])

    color_mapping = None
    def background_color(self, node, depth):
        """Create a (unique-ish) background color for each node"""
        if self.color_mapping is None:
            self.color_mapping = {}
        color = self.color_mapping.get(node['type'])
        if color is None:
            depth = len(self.color_mapping)
            red = (depth * 10) % 255
            green = 200 - ((depth * 5) % 200)
            blue = (depth * 25) % 200
            self.color_mapping[node['type']] = color = wx.Colour(red, green, blue)
        return color


class TestApp(wx.App):
    """Basic application for holding the viewing Frame"""
    def OnInit(self):
        """Initialise the application"""
        wx.InitAllImageHandlers()
        self.frame = frame = wx.Frame( None,
        )
        frame.CreateStatusBar()

        model = model = self.get_model( sys.argv[1])
        self.sq = squaremap.SquareMap( frame, model=model, adapter = MeliaeAdapter())
        squaremap.EVT_SQUARE_HIGHLIGHTED( self.sq, self.OnSquareSelected )
        frame.Show(True)
        self.SetTopWindow(frame)
        return True
    def get_model( self, path ):
        return load( path )
    def OnSquareSelected( self, event ):
        text = self.sq.adapter.label( event.node )
        self.frame.SetToolTipString( text )

usage = 'meliaeloader.py somefile'

def main():
    """Mainloop for the application"""
    if not sys.argv[1:]:
        print usage
    else:
        app = TestApp(0)
        app.MainLoop()

if __name__ == "__main__":
    main()
