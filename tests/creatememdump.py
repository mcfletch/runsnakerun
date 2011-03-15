import sys,httplib

from meliae import scanner
filename = 'dump.memory'
fh = open( filename, 'wb' )
scanner.dump_all_objects( fh )
fh.close()
print 'saved memory dump to: %r'%( filename, )
