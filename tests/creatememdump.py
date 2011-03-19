#! /usr/bin/env python
import sys,httplib

class Test( object ):
    def __init__( self, size=1024 ):
        self.data = 'a'*size

# set up some reference loops
t = Test()
t2 = Test()
t3 = Test()
t2.first = t
t3.first = t
t.second = t 
t.third = t3

big_list = [ Test(i) for i in range(256) ]
big_list.append( big_list )

def main():

    from meliae import scanner
    filename = 'dump.memory'
    fh = open( filename, 'wb' )
    scanner.dump_all_objects( fh )
    fh.close()
    print 'saved memory dump to: %r'%( filename, )

if __name__ == "__main__":
    main()
