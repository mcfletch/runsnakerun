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

class MeliaTests( unittest.TestCase ):
    def test_simplify_index( self ):
        """Do we remove __dict__ items properly?"""
        records = [
            {'size': 10,'type':'moo','address':1,'refs':[]},
            {'size': 1,'type':'dict','address':2,'refs':[1]},
            {'size': 1,'type':'module','address':3,'refs':[2]},
        ]
        index,shared = records_as_index( records )
        meliaeloader.simplify_index( index, shared )
        assert index == {
            3:{'size': 2,'type':'module','address':3,'refs':[1], 'parents':[]},
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
            {'size': 1,'type':'dict','address':2,'refs':[1]},
            {'size': 1,'type':'module','address':3,'refs':[2]},
        ]
        index,shared = records_as_index( records )
        meliaeloader.bind_parents( index, shared )
        meliaeloader.recurse_module( 
            index[3], 
            index, 
            shared,
        )
        assert index[3]['totsize'] == 22, index[3]['totsize']
    def test_recursive_shared( self ):
        """Do we account for recursive structures shared across modules properly?"""
        records = [
            {'size': 10,'type':'moo','address':1,'refs':[4]},
            {'size': 10,'type':'moo','address':4,'refs':[1]},
            {'size': 1,'type':'dict','address':2,'refs':[1]},
            {'size': 1,'type':'module','address':3,'refs':[2]},
            {'size': 1,'type':'dict','address':5,'refs':[4]},
            {'size': 1,'type':'module','address':6,'refs':[5]},
        ]
        index,shared = records_as_index( records )
        meliaeloader.bind_parents( index, shared )
        
        loops = list( meliaeloader.find_loops( index[6], index ) )
        assert len(loops) == 1, loops 
        loop = loops[0]
        assert set(loop) == set([1,4]), loop
        
        for module in [3,6]:
            meliaeloader.recurse_module( 
                index[module], 
                index, 
                shared,
            )
            assert index[module]['totsize'] == 12, index[module]['totsize']
        
