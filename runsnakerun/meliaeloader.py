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
"""
import logging, sys, weakref
log = logging.getLogger( __name__ )
try:
    import json 
except ImportError, err:
    import simplejson as json
import sys

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
                for typ in children_by_type( record, index, stop_types=stop_types ):
                    if typ['name'] not in stop_types:
                        for child in typ['children']:
                            for descendant in recurse( 
                                child, index, stop_types, 
                                already_seen=already_seen, type_group=type_group,
                            ):
                                if descendant['type'] not in stop_types:
                                    yield descendant
                        if len(typ['children']) > 5:
                            yield typ 
            else:
                for child in children( record, index, stop_types=stop_types ):
                    for descendant in recurse( 
                        child, index, stop_types, 
                        already_seen=already_seen, type_group=type_group,
                    ):
                        yield descendant
        yield record 

def children( record, index, key='refs', stop_types=None ):
    """Retrieve children records for given record"""
    for ref in record.get( key,[]):
        try:
            if isinstance( ref, dict ):
                record = ref 
            else:
                record = index[ref]
        except KeyError, err:
            pass 
        else:
            if (not stop_types) or (record['type'] not in stop_types):
                yield record 

def children_by_type( record, index, key='refs', stop_types=None ):
    """Get children grouped by type 
    
    returns (typ,[children]) for all children 
    """
    types = {}
    for child in children( record, index, key, stop_types=stop_types ):
        if child['type'] not in types:
            typ = index.get( child['type'] )
            if typ is None:
                typ = {
                    'address':new_address(index),
                    'type': child['type'],
                }
            types[child['type']] = typ = {
                'address': typ['address'],
                'type': 'type',
                'name': child['type'],
                'size': 0, # just a collection here...
                'parents': [record['address']],
                'children': [],
                'refs': [],
            }
        types[child['type']]['children'].append( child )
    return types.values()
    

def recurse_module( overall_record, index, shared, stop_types=None, already_seen=None, size_info=None, min_size=0 ):
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
        type_group=False,
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
            'parents': record['parents'],
        }
        if 'value' in record:
            rinfo['value'] = record['value']
        if not record['refs']:
            rinfo['rsize'] = 0
            rinfo['children'] = []
        else:
            # TODO: track shared versus owned cost separately...
            # TODO: provide a flag to coalesce based on e.g. type at each level or throughout...
            rinfo['children'] = rinfo_children = list ( children( record, size_info, stop_types=stop_types ) )
            rinfo['rsize'] = sum([
                (
                    child.get('totsize',0.0)/float(len(shared.get( child['address'], [])) or 1)
                )
                for child in rinfo_children
            ], 0.0 )
        rinfo['totsize'] = record['size'] + rinfo['rsize']
    for key,record in size_info.items():
        # clear out children references if they are not reasonably sized...
        if record['totsize'] < min_size and record['children']:
            del record['children'][:]
            print 'ignoring', record['totsize'], 'in', record['type'], record.get('name')
        #record['parents'] = list(children( record, size_info, 'parents' ))
    
    return size_info
    
def as_id( x ):
    if isinstance( x, dict ):
        return x['address']
    else:
        return x

def rewrite_refs( targets, old,new, index, key='refs' ):
    """Rewrite key in all targets (from index if necessary) to replace old with new"""
    for parent in targets:
        if not isinstance( parent, dict ):
            try:
                parent = index[parent]
            except KeyError, err:
                continue 
        parent[key] = rewrite_references( parent[key], old, new )

def rewrite_references( sequence, old, new ):
    """Rewrite parents to point to new in old
    
    sequence -- sequence of id references 
    old -- old id 
    new -- new id
    
    returns rewritten sequence
    """
    old,new = as_id(old),as_id(new)
    def rewritten( n ):
        if n == old:
            return new
        return n
    return [ x for x in [rewritten(n) for n in sequence] if n is not None]

def simplify_core( index, shared ):
    """Eliminate "noise" records for core type (strs, ints, etc)"""
    compress_whole = set( ['int','long','str','unicode',] )
    to_delete = set()
    # compress out objects which are to be entirely compressed
    for to_simplify in iterindex(index):
        if not isinstance( to_simplify, dict ):
            continue
        if to_simplify['type'] in compress_whole:
            # don't compress out these values if they hold references to something...
            if not to_simplify['refs']:
                # okay, so we are "just data", add our uniqueness to our parent...
                parent_ids = shared.get( to_simplify['address'])
                parents = [x for x in [index.get(x) for x in parent_ids] if x]
                if parents and len(parents) == 1:
                    # all our parents are accounted for...
                    cost = to_simplify['size']/float(len(parents))
                    for parent in parents:
                        parent['size'] = parent['size'] + cost 
                        
                    rewrite_refs( 
                        parents, 
                        to_simplify['address'], None, 
                        index = index 
                    )
                    to_delete.add( to_simplify['address'] )
    
    for item in to_delete:
        del index[item]
        del shared[item]
    

def simplify_index( index, shared ):
    """Eliminate "noise" records from the index 
    
    index -- overall index of objects (including metadata such as type records)
    shared -- parent-count mapping for records in index
    
    module/type/class dictionaries
    """
    simplify_core( index, shared )
    
    # things which will have their dictionaries compressed out
    simplify_dicts = set( ['module','type','classobj'])
    # things which will be themselves eliminated, adding their uniqueness to their parents
    
    to_delete = set()
    
    for to_simplify in iterindex(index):
        if not isinstance( to_simplify, dict ):
            continue
        if to_simplify['address'] in to_delete:
            continue 
        to_simplify['parents'] = shared.get( to_simplify['address'], [] )
        if to_simplify['type'] in simplify_dicts:
            refs = to_simplify['refs']
            to_simplify['refs'] = []
            for ref in refs:
                child = index.get( ref )
                if child is not None and child['type'] == 'dict':
                    child_referrers = shared.get(child['address'],[])
                    if len(child_referrers) == 1:
                        to_simplify['refs'].extend(child['refs'])
                        to_simplify['size'] += child['size']
                        # we were the only thing referencing dict, so we don't need to 
                        # rework it's parent references (we don't want to be our own parent)
                        
                        # TODO: now rewrite grandchildren to point to root obj instead of dict
                        for grandchild in child['refs']:
                            parent_set = shared.get( grandchild, ())
                            if parent_set:
                                shared[grandchild][:] = rewrite_references( 
                                    parent_set, 
                                    child,
                                    to_simplify,
                                )
                        to_delete.add( child['address'] )
    for item in to_delete:
        del index[item]
        del shared[item]
    
    return index



class _syntheticaddress( object ):
    current = -1
    def __call__( self, target ):
        while self.current in target:
            self.current -= 1
        target[self.current] = True
        return self.current 
new_address = _syntheticaddress()

def iterindex( index ):
    for (k,v) in index.iteritems():
        if (
            isinstance(v,dict) and 
            isinstance(k,(int,long))
        ):
            yield v
def load( filename ):
    index = {
    } # address: structure
    shared = dict() # address: [parent addresses,...]
    modules = set()
    
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
        elif struct['type'] in ( 'type', 'classobj'):
            index[struct['name']] = struct
    
    simplify_index( index,shared )
            
    modules = [
        v for v in iterindex( index )
        if v['type'] == 'module'
    ]
    
    records = []
    size_info = {}
    for m in modules:
        if m.get('name') != 'sys':
            records.append( recurse_module(
                m, index, shared, stop_types=set([
                    'module',
                ]), size_info=size_info
            ))
    root_address = new_address( index )
    module_info = [x for x in size_info.itervalues() if x['type'] == 'module']
    module_info.sort( key = lambda m: m.get('totsize',0))
    for module in module_info:
        module['parents'].append( root_address )
    all_modules = sum([x['totsize'] for x in module_info],0)
    root = {
        'type':'dump',
        'name': filename,
        'children': module_info,
        'totsize': all_modules,
        'rsize': all_modules,
        'size': 0,
        'address': root_address,
    }
    size_info[root_address] = root
    index_ref = Ref( size_info )
    root_ref = Ref( root )
    for item in size_info.itervalues():
        item['index'] = index_ref 
        item['root'] = root_ref
    return root, size_info

class Ref(object):
    def __init__( self, target ):
        self.target = target
    def __call__( self ):
        return self.target
