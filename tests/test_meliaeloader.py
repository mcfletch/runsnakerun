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
    def test_reduce_core( self ):
        """Do we share core-objects properly into parents"""
        records = [
            {'size': 10,'type':'str','address':1,'refs':[]},
            {'size': 1,'type':'moo','address':2,'refs':[1]},
            {'size': 1,'type':'moo','address':3,'refs':[1]},
        ]
        index,shared = records_as_index( records )
        meliaeloader.simplify_core( index, shared )
        assert index == {
            2:{'size': 6,'type':'moo','address':2,'refs':[]},
            3:{'size': 6,'type':'moo','address':3,'refs':[]},
        }, index
    
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
    
