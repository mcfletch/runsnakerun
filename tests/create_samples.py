#! /usr/bin/env python
"""Creates hotshot and cProfile sample files"""
import time,cProfile,hotshot
from subpackage.timewaster import r

def x( ):
    print 'x'
    y()
    z()
    import big_import
    a()
    r()
def y( ):
    print 'y'
    for i in range( 2500 ):
        long(i) ** i
    time.sleep( 0.25 )
    z()
def z( ):
    print 'z'
    time.sleep( 0.1 )
    a()

def a( count=5 ):
    print 'a',count
    if count:
        time.sleep( 0.05 )
        return a( count - 1 )

if __name__ == "__main__":
    import pprint 
    command = '''x()'''
    profiler = hotshot.Profile( "hotshot.profile", lineevents=0 )
    profiler.runctx( command, globals(), locals())
    profiler.close()
    
    profiler = cProfile.Profile( subcalls=True )
    profiler.runctx( command, globals(), locals())
    stats = profiler.getstats()
    profiler.dump_stats( 'cprofile.profile' )
