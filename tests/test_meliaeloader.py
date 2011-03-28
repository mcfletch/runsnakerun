import unittest
from runsnakerun import meliaeloader

def records_as_index( records ):
    index = dict([
        (x['address'],x)
        for x in records 
    ])
    shared = {}
    for value in records:
        for ref in value['refs']:
            shared.setdefault( ref, [] ).append( value['address'] )
    return index, shared

class MeliaeTests( unittest.TestCase ):
    def test_simplify_dict( self ):
        """Do we remove __dict__ items properly?"""
        records = [
            {'size': 10,'type':'moo','address':1,'refs':[]},
            {'size': 1,'type':'dict','address':2,'refs':[1]},
            {'size': 1,'type':'module','address':3,'refs':[2]},
        ]
        index,shared = records_as_index( records )
        meliaeloader.bind_parents( index, shared )
        meliaeloader.simplify_dicts( index, shared )
        assert index == {
            3:{'size': 2,'type':'module','address':3,'refs':[1], 'parents':[],'compressed':True},
            1:{'size': 10,'type':'moo','address':1,'refs':[],'parents':[3]},
        }, index
    
    def test_group_children( self ):
        """Do we group large numbers of children properly?"""
        strings = [
            {'size':1,'type':'str','address': i+12,'refs':[]}
            for i in range( 10 )
        ]
        records = [
            {'size': 10,'type':'moo','address':1,'refs':[s['address'] for s in strings]},
            {'size': 1,'type':'dict','address':2,'refs':[1]},
            {'size': 1,'type':'module','address':3,'refs':[2]},
        ] + strings
        index,shared = records_as_index( records )
        meliaeloader.group_children( index, shared )
        assert len(index) == 4, index # module, dict, moo, collection-of-strings
        
        new = index[-1]
        assert len(new['refs']) == 0, new
        assert new['type'] == '<many>', new
        assert new['name'] == 'str', new
    
    def test_recursive( self ):
        """Do we account for recursive structures properly?"""
        records = [
            {'size': 10,'type':'moo','address':1,'refs':[4]},
            {'size': 10,'type':'moo','address':4,'refs':[1]},
            {'size': 0,'type':'moo','address':5,'refs':[1,4]},
            {'size': 1,'type':'dict','address':2,'refs':[5]},
            {'size': 1,'type':'module','address':3,'refs':[2]},
        ]
        index,shared = records_as_index( records )
        meliaeloader.bind_parents( index, shared )
        meliaeloader.simplify_dicts( index, shared )
        loops = list( meliaeloader.find_loops( index[3], index ) )
        assert loops
        meliaeloader.promote_loops( loops, index, shared )
        
        meliaeloader.recurse_module( 
            index[3], 
            index, 
            shared,
        )
        assert index[3]['totsize'] == 22, index
    
    def test_recursive_shared( self ):
        """Do we account for recursive structures shared across modules properly?
        
        Loops should become a single "thing" which has references and parents, but 
        also can be broken down to see what is in the loop...
        
        Loop totsize is the totsize of all components of the loop divided by the 
        number of references to the loop which are *not* from the loop itself...
        """
        records = [
            {'size': 10,'type':'moo','address':1,'refs':[4]},
            {'size': 10,'type':'moo','address':4,'refs':[1]},
            {'size': 0,'type':'moo','address':7,'refs':[1]},
            {'size': 1,'type':'dict','address':2,'refs':[7]},
            {'size': 1,'type':'module','address':3,'refs':[2]},
            
            {'size': 1,'type':'dict','address':5,'refs':[4,1]}, # should become a single ref to loop...
            {'size': 1,'type':'module','address':6,'refs':[5]},
        ]
        index,shared = records_as_index( records )
        meliaeloader.bind_parents( index, shared )
        meliaeloader.simplify_dicts( index, shared )
        
        loops = list( meliaeloader.find_loops( index[6], index ) )
        assert len(loops) == 1, loops 
        loop = loops[0]
        assert set(loop) == set([1,4]), loop
        
        meliaeloader.promote_loops( loops, index, shared )
        
        for module in [3,6]:
            meliaeloader.recurse_module( 
                index[module], 
                index=index, 
                shared=shared,
            )
            assert index[module]['totsize'] == 12, index[module]['totsize']

        loop = [x for x in index.values() if x['type'] == '<loop>'][0]
        assert set(loop['parents']) == set([6,7]), loop['parents']
    
