"""Module to load cProfile/profile records as a tree of records"""
import pstats, os

class PStatsLoader( object ):
    """Load profiler statistic from """
    def __init__( self, filename ):
        self.filename = filename 
        self.rows = {}
        self.stats = pstats.Stats( filename )
        self.tree = self.load( self.stats.stats )
    def load( self, stats ):
        """Build a squaremap-compatible model from a pstats class"""
        rows = self.rows
        for func, raw in stats.iteritems():
            rows[func] =  PStatRow( func,raw )
        for row in rows.itervalues():
            row.weave( rows )
        for key,value in rows.items():
            if not value.parents:
                return value
        raise RuntimeError( 'No top-level function???' )

class PStatRow( object ):
    """Simulates a HotShot profiler record using PStats module"""
    def __init__( self, key, raw ):
        self.children = []
        self.parents = []
        file,line,func = self.key = key
        try:
            dirname,basename = os.path.dirname(file),os.path.basename(file)
        except ValueError, err:
            dirname = ''
            basename = file
        cc, nc, tt, ct, callers = raw
        (
            self.calls, self.recursive, self.local, self.localPer,
            self.cummulative, self.cummulativePer, self.directory,
            self.filename, self.name, self.lineno
        ) = (
            cc, 
            nc,
            tt,
            tt/nc,
            ct,
            ct/cc,
            dirname,
            basename,
            func,
            line,
        )
        self.callers = callers
    def __repr__( self ):
        return 'PStatRow( %r,%r,%r,%r, %s )'%(self.directory, self.filename, self.lineno, self.name, self.children)
    def add_child( self, child ):
        self.children.append( child )
    
    def weave( self, rows ):
        for caller,data in self.callers.iteritems():
            # data is (cc,nc,tt,ct)
            parent = rows.get( caller )
            if parent:
                self.parents.append( parent )
                parent.children.append( self )
    def child_cumulative_time( self, child ):
        total = self.cummulative
        if total:
            (cc,nc,tt,ct) = child.callers[ self.key ]
            return float(ct)/total
        return 0
    

if __name__ == "__main__":
    import sys
    p = PStatsLoader( sys.argv[1] )
    assert p.tree
    print p.tree
