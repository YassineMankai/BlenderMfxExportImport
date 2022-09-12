graphName = 'test1'
path = 'C:/Users/yassi/Desktop/Projects/OpenMFX/BlenderMfxExportImport/'

import sys, os
os.chdir(path)
sys.path.append(path)

from  geometryNodeToJSON import *
graph = D.node_groups[graphName]
exportToJSON(graph)

from  JSONToGeometryNode import *
importFromJSON(graphName)