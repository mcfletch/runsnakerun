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
import logging, sys
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
        typ = index.get( child['type'] )
        if typ is None:
            typ = {
                'address':None,
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

def recurse_module( overall_record, index, shared, stop_types=None, already_seen=None, size_info=None, min_size=32 ):
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
            'parents': record['parents'],
        }
        if not record['refs']:
            rinfo['rsize'] = 0
            rinfo['children'] = []
        else:
            # TODO: track shared versus owned cost separately...
            # TODO: provide a flag to coalesce based on e.g. type at each level or throughout...
            rinfo['children'] = rinfo_children = list ( children( record, size_info, stop_types=stop_types ) )
            rinfo['rsize'] = sum([
                (
                    child.get('totsize',0)/len(shared.get( child['address'], [])) or 1
                )
                for child in rinfo_children
            ], 0 )
        rinfo['totsize'] = record['size'] + rinfo['rsize']
    for key,record in size_info.items():
        # clear out children references if they are not reasonably sized...
        if record['totsize'] < min_size and record['children']:
            del record['children'][:]
            print 'ignoring', record['totsize'], 'in', record['type'], record.get('name')
        #record['parents'] = list(children( record, size_info, 'parents' ))
    
    return size_info

def rewrite_refs( targets, old,new, index ):
    def rewritten( n ):
        if n == old:
            return new
        return n
    for parent in targets:
        if not isinstance( parent, dict ):
            try:
                parent = index[parent]
            except KeyError, err:
                continue 
        parent['refs'] = [rewritten(n) for n in parent['refs']]

def simplify_dicts( index, shared ):
    """eliminate module/type/class dictionaries"""
    simplify_dicts = set( ['module','type','classobj'])
    to_delete = []
    
    for to_simplify in index.itervalues():
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
                        # anything referencing module dict is now referencing module
                        to_simplify['parents'].extend(child_referrers)
                        
                        rewrite_refs( 
                            child_referrers, 
                            child['address'], to_simplify['address'], 
                            index = index 
                        )
                        to_delete.append( child['address'] )
    for item in to_delete:
        del index[item]
    
    return index

def load( filename ):
    index = {} # address: structure
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
    
    simplify_dicts( index,shared )
            
    modules = [
        x for x in index.itervalues() 
        if x['type'] == 'module'
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

