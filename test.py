graphName = 'test1'
path = 'C:/Users/yassi/Desktop/Projects/OpenMFX/BlenderMfxExportImport/'
graph = D.node_groups[graphName]
import sys, os
os.chdir(path)
sys.path.append(path)

from  geometryNodeToJSON import *
exportToJSON(graph)

from  JSONToGeometryNode import *
importFromJSON(graphName)