graphName = 'test1'
path = ''
graph = D.node_groups[graphName]
import sys, os
os.chdir('C:/Users/yassi/Desktop/Projects/OpenMFX/BlenderMfxExportImport/')
sys.path.append('C:/Users/yassi/Desktop/Projects/OpenMFX/BlenderMfxExportImport/')

from  geometryNodeToJSON import *
exportToJSON(graph)

from  JSONToGeometryNode import *
importFromJSON(graphName)