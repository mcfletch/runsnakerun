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
from gettext import gettext as _
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
            for child in children( record, index, stop_types=stop_types ):
                if child['address'] in already_seen:
                    # break the loop, and charge parents full-rate
                    child['parents'].remove( record['address'] )
                    child.setdefault( 'recursive_parents',[]).append( record['address'] )
                else:
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

def children_types( record, index, key='refs', stop_types=None ):
    """Produce dictionary mapping type-key to instances for all children"""
    types = {}
    for child in children( record, index, key, stop_types=stop_types ):
        types.setdefault(child['type'],[]).append( child )
    return types
        

#def remove_unreachable( modules, index, stop_types, already_seen=None, min_size=0 ):
#    reachable = set()
#    for module in modules:
#        for record in recurse( 
#            module, index, 
#            stop_types=stop_types, 
#            already_seen=already_seen, 
#            type_group=True,
#        ):
#            reachable.add( record['address'] )
#    for value in index.values():
#        value['parents']
    

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

def simple( child, shared, parent ):
    """Return sub-set of children who are "simple" in the sense of group_children"""
    return (
        not child.get('refs',())
        and (
            not shared.get(child['address'])
        or 
            shared.get(child['address']) == [parent['address']]
        )
    )

def group_children( index, shared, min_kids=10, stop_types=None, delete_children=True ):
    """Collect like-type children into sub-groups of objects for objects with long children-lists
    
    Only group if:
    
        * there are more than X children of type Y
        * children are "simple"
            * individual children have no children themselves
            * individual children have no other parents...
    """
    to_compress = []
    
    for to_simplify in list(iterindex( index )):
        if not isinstance( to_simplify, dict ):
            continue
        for typ,kids in children_types( to_simplify, index, stop_types=stop_types ).items():
            kids = [k for k in kids if k and simple(k,shared, to_simplify)]
            if len(kids) >= min_kids:
                # we can group and compress out...
                to_compress.append( (to_simplify,typ,kids))
    
    for to_simplify,typ,kids in to_compress:
        typ_address = new_address(index)
        kid_addresses = [k['address'] for k in kids]
        index[typ_address] = {
            'address': typ_address,
            'type': _('<many>'),
            'name': typ,
            'size': sum( [k.get('size',0) for k in kids], 0),
        }
        
        shared[typ_address] = [to_simplify['address']]
        to_simplify['refs'][:] = [typ_address]
        
        if delete_children:
            for address in kid_addresses:
                del index[address]
                del shared[address]
            index[typ_address]['refs'] = []
        else:
            index[typ_address]['refs'] = kid_addresses

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
                if parents and len(parents) == len(raw_parents):
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

def find_reachable( modules, index, shared, stop_types=None ):
    """Find the set of all reachable objects from given root nodes (modules)"""
    reachable = set()
    for module in modules:
        for child in recurse( module, index, stop_types=stop_types):
            reachable.add( child['address'] )
    return reachable

def deparent_unreachable( reachable, shared ):
    """Eliminate all parent-links from unreachable objects from reachable objects
    """
    for id,shares in shared.iteritems():
        if id in reachable: # child is reachable
            filtered = [
                x 
                for x in shares 
                if x in reachable # only those parents which are reachable
            ]
            if len(filtered) != len(shares):
                shares[:] = filtered

class _syntheticaddress( object ):
    current = -1
    def __call__( self, target ):
        while self.current in target:
            self.current -= 1
        target[self.current] = True
        return self.current 
new_address = _syntheticaddress()

def index_size( index ):
    return sum([
        v.get('size',0)
        for v in iterindex( index )
    ],0)

def iterindex( index ):
    for (k,v) in index.iteritems():
        if (
            isinstance(v,dict) and 
            isinstance(k,(int,long))
        ):
            yield v

def bind_parents( index, shared ):
    """Set parents on all items in index"""
    for v in iterindex( index ):
        v['parents'] = shared.get( v['address'], [] )

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
    
    stop_types = set([
        'module',
    ])
    
    modules = [index[addr] for addr in modules]
    
    
    initial = index_size( index )
    
    reachable = find_reachable( modules, index, shared, stop_types=stop_types )
    deparent_unreachable( reachable, shared )
    
    new = index_size( index )
    assert initial == new, (initial,new)
    
    unreachable = sum([
        v.get( 'size' )
        for v in iterindex( index )
        if v['address'] not in reachable
    ], 0 )
    print '%s bytes are unreachable from modules'%( unreachable )

    simplify_index( index,shared )

    new = index_size( index )
    assert initial == new, (initial,new)

    group_children( index, shared, min_kids=10, stop_types=stop_types )

    new = index_size( index )
    assert initial == new, (initial,new)

    records = []
    for m in modules:
        recurse_module(
            m, index, shared, stop_types=stop_types
        )
        new = index_size( index )
        assert initial == new, (initial,new)
        
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
    
    assert all_modules + unreachable == initial, (all_modules, unreachable, initial, unreachable+initial )

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
    
