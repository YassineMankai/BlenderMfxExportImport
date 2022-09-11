graphName = 'test1'
graph = D.node_groups[graphName]
import sys, os
os.chdir('D:/BlenderMfxExportImport/')
sys.path.append('D:/BlenderMfxExportImport/')

from  geometryNodeToJSON import *
exportToJSON(graph)

from  JSONToGeometryNode import *
importFromJSON(graphName)