import unittest
from runsnakerun import meliaeloader

class MeliaTests( unittest.TestCase ):
    def test_reduce_core( self ):
        records = [
            {'size': 10,'type':'str','address':1,'refs':[]},
            {'size': 1,'type':'moo','address':2,'refs':[1]},
            {'size': 1,'type':'moo','address':3,'refs':[1]},
        ]
        index = dict([
            (x['address'],x)
            for x in records 
        ])
        shared = {1:[2,3]}
        meliaeloader.simplify_core( index, shared )
        assert index == {
            2:{'size': 6,'type':'moo','address':2,'refs':[]},
            3:{'size': 6,'type':'moo','address':3,'refs':[]},
        }, index
    
    
