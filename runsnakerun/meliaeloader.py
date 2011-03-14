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
try:
    import json 
except ImportError, err:
    import simplejson as json
import sys

def recurse( record, index, stop_types=None,already_seen=None, ):
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
            for childaddress in record['refs']:
                try:
                    child = index[childaddress]
                except KeyError, err:
                    pass 
                else:
                    if child['type'] not in stop_types:
                        yield child 
        yield record 

def children( record, index ):
    """Retrieve children records for given record"""
    for ref in record.get( 'refs',[]):
        try:
            yield index[ref]
        except KeyError, err:
            pass 

def recurse_module( record, index, shared, already_seen=None, stop_types=None ):
    """Creates a has-a recursive-cost hierarchy
    
    Mutates objects in-place to produce a hierarchy of memory usage based on 
    reference-holding cost assignment
    """
    for record in recurse( record, index, stop_types=stop_types, already_seen=already_seen ):
        if not record['refs']:
            record['rsize'] = 0
        else:
            record['rsize'] = sum([
                (
                    child.get('totsize',0)/shared.get( child['address'], 1) or 1
                )
                for child in children( record, index )
            ], 0 )
        record['totsize'] = record['size'] + record['rsize']
    
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
            shared[ref] = shared.get( ref,0) + 1
        if struct['type'] == 'module':
            modules.add( struct['address'] )
        elif struct['type'] == 'type':
            types[struct['name']] = struct
            struct['instances'] = []
#    for address,parent in index.iteritems():
#        if parent.get('type') in types:
#            types[parent['type']].append( address )
    modules = [
        x for x in index.itervalues() 
        if x['type'] == 'module'
    ]
    for m in modules:
        recurse_module( m, index, shared, stop_types=['module'] )
    modules.sort( key = lambda m: m.get('totsize',0))
    return modules, index

if __name__ == "__main__":
    modules = load( sys.argv[1])
