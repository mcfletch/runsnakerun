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
    
