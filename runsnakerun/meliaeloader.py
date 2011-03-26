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
    from _meliaejson import loads as json_loads
except ImportError, err:
    try:
        from json import loads as json_loads
    except ImportError, err:
        from simplejson import loads as json_loads
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
            if type_group and False:
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
    result = []
    for ref in record.get( key,[]):
        try:
            if isinstance( ref, dict ):
                record = ref 
            else:
                record = index[ref]
        except KeyError, err:
            print 'no record for %s address'%(key,), ref 
        else:
            if (not stop_types) or (record['type'] not in stop_types):
                result.append(  record  )
    return result

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
            index[typ['address']] = types[child['type']] = typ = {
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
    

def recurse_module( overall_record, index, shared, stop_types=None, already_seen=None, min_size=0 ):
    """Creates a has-a recursive-cost hierarchy
    
    Mutates objects in-place to produce a hierarchy of memory usage based on 
    reference-holding cost assignment
    """
    for record in recurse( 
        overall_record, index, 
        stop_types=stop_types, 
        already_seen=already_seen, 
        type_group=True,
    ):
        # anything with a totsize we've already processed...
        if record.get('totsize') is not None:
            continue 
        rinfo = record 
        rinfo['module'] = overall_record.get('name','<non-module-references>' )
        if not record['refs']:
            rinfo['rsize'] = 0
            rinfo['children'] = []
        else:
            # TODO: provide a flag to coalesce based on e.g. type at each level or throughout...
            rinfo['children'] = rinfo_children = list ( children( record, index, stop_types=stop_types ) )
            rinfo['rsize'] = sum([
                (
                    child.get('totsize',0.0)/float(len(shared.get( child['address'], [])) or 1)
                )
                for child in rinfo_children
            ], 0.0 )
        rinfo['totsize'] = record['size'] + rinfo['rsize']
    
    return None
    
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
        rewrite_references( parent[key], old, new )

def rewrite_references( sequence, old, new ):
    """Rewrite parents to point to new in old
    
    sequence -- sequence of id references 
    old -- old id 
    new -- new id
    
    returns rewritten sequence
    """
    old,new = as_id(old),as_id(new)
    to_delete = []
    for i,n in enumerate(sequence):
        if n == old:
            if new is None:
                to_delete.append( i )
            else:
                sequence[i] = new 
    if to_delete:
        to_delete.reverse()
        for i in to_delete:
            del sequence[i]
    return sequence

def simplify_core( index, shared ):
    """Eliminate "noise" records for core type (strs, ints, etc)"""
    compress_whole = set( ['int','long','str','unicode',] )
    to_delete = set()
    # compress out objects which are to be entirely compressed
    # things which will be eliminated add their uniqueness to their parents
    for to_simplify in iterindex(index):
        if not isinstance( to_simplify, dict ):
            continue
        if to_simplify['type'] in compress_whole:
            # don't compress out these values if they hold references to something...
            if not to_simplify['refs']:
                # okay, so we are "just data", add our uniqueness to our parent...
                parent_ids = shared.get( to_simplify['address'])
                raw_parents = [index.get(x) for x in parent_ids]
                parents = [x for x in raw_parents if x]
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
    #simplify_core( index, shared )
    
    # things which will have their dictionaries compressed out
    simplify_dicts = set( ['module','type','classobj'])
    
    to_delete = set()
    
    for to_simplify in iterindex(index):
        if not isinstance( to_simplify, dict ):
            continue
        if to_simplify['address'] in to_delete:
            continue 
        to_simplify['parents'] = shared.get( to_simplify['address'], [] )
        if to_simplify['type'] in simplify_dicts:
            refs = to_simplify['refs']
            for ref in refs:
                child = index.get( ref )
                if child is not None and child['type'] == 'dict':
                    child_referrers = shared.get(child['address'],[])
                    if len(child_referrers) == 1:
                        to_simplify['refs'] = child['refs']
                        to_simplify['size'] += child['size']
                        # we were the only thing referencing dict, so we don't need to 
                        # rework it's parent references (we don't want to be our own parent)
                        
                        # TODO: now rewrite grandchildren to point to root obj instead of dict
                        for grandchild in child['refs']:
                            parent_set = shared.get( grandchild, ())
                            if parent_set:
                                rewrite_references( 
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
def load( filename, include_interpreter=False ):
    index = {
    } # address: structure
    shared = dict() # address: [parent addresses,...]
    modules = set()
    
    root_address = new_address( index )
    root = {
        'type':'dump',
        'name': filename,
        'children': [],
        'totsize': 0,
        'rsize': 0,
        'size': 0,
        'address': root_address,
    }
    index[root_address] = root
    index_ref = Ref( index )
    root_ref = Ref( root )
    
    root['root'] = root_ref 
    root['index'] = index_ref
    
    raw_total = 0
    
    for line in open( filename ):
        struct = json_loads( line.strip())
        index[struct['address']] = struct 
        
        struct['root'] = root_ref
        struct['index'] = index_ref

        refs = struct['refs']
        for ref in refs:
            parents = shared.get( ref )
            if parents is None:
                shared[ref] = []
            shared[ref].append( struct['address'])
        raw_total += struct['size']
        if struct['type'] == 'module':
            modules.add( struct['address'] )
    
    simplify_index( index,shared )
    
    modules = []
    for v in iterindex( index ):
        v['parents'] = shared.get( v['address'], [] )
        if v['type'] == 'module':
            modules.append( v )
    
    records = []
    for m in modules:
        recurse_module(
            m, index, shared, stop_types=set([
                'module',
            ])
        )
    modules.sort( key = lambda m: m.get('totsize',0))
    for module in modules:
        module['parents'].append( root_address )
    
    if include_interpreter:
        # Meliae produces quite a few of these un-referenced records, they aren't normally useful AFAICS
        # reachable from any module, but are present in the dump...
        disconnected = [
            x for x in iterindex( index )
            if x.get('totsize') is None 
        ]
        for pseudo_module in find_roots( disconnected, index, shared ):
            pseudo_module['root'] = root_ref
            pseudo_module['index'] = index_ref 
            pseudo_module.setdefault('parents',[]).append( root_address )
            modules.append( pseudo_module )
    else:
        to_delete = []
        for v in iterindex(index):
            if v.get('totsize') is None:
                to_delete.append( v['address'] )
        for k in to_delete:
            del index[k]

    all_modules = sum([x.get('totsize',0) for x in modules],0)
    
    diff = raw_total - all_modules
    if diff:
        log.error(
            "Lost %s bytes in processing dump", diff 
        )
        raw_index = sum( [v.get('size') for v in iterindex( index )])
        log.error(
            "References missing (i.e. not just bookkeeping/accounting errors): %s", raw_total - raw_index 
        )

    root['totsize'] = all_modules
    root['rsize'] = all_modules
    root['size'] = 0
    root['children'] = modules
    
    return root, index

def find_roots( disconnected, index, shared ):
    """Find appropriate "root" objects from which to recurse the hierarchies
    
    Will generate a synthetic root for anything which doesn't have any parents...
    """
    log.warn( '%s disconnected objects in %s total objects', len(disconnected), len(index))
    natural_roots = [x for x in disconnected if x.get('refs') and not x.get('parents')]
    log.warn( '%s objects with no parents at all' ,len(natural_roots))
    for natural_root in natural_roots:
        recurse_module(
            natural_root, index, shared, stop_types=set([
                'module',
            ])
        )
        yield natural_root
    rest = [x for x in disconnected if x.get( 'totsize' ) is None]
    un_found = {
        'type': 'module',
        'name': '<disconnected objects>',
        'children': rest,
        'parents': [ ],
        'size': 0,
        'totsize': sum([x['size'] for x in rest],0),
        'address': new_address( index ),
    }
    index[un_found['address']] = un_found
    yield un_found

class Ref(object):
    def __init__( self, target ):
        self.target = target
    def __call__( self ):
        return self.target


if __name__ == "__main__":
    import logging
    logging.basicConfig( level=logging.DEBUG )
    import sys
    load( sys.argv[1] )
#    import cProfile, sys
#    cProfile.runctx( "load(sys.argv[1])", globals(),locals(),'melialoader.profile' )
    
