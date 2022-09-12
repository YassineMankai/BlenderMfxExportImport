#Export
graphName = 'test1'
objectName = 'Test1'
path = 'C:/Users/yassi/Desktop/Projects/OpenMFX/BlenderMfxExportImport/'

import sys, os
os.chdir(path)
sys.path.append(path)

from  geometryNodeToJSON import *
graph = D.node_groups[graphName]
objTest = D.objects[objectName]
exportGraphAndSettingsToJSON(objTest, graph)



#Import
path = 'C:/Users/yassi/Desktop/Projects/OpenMFX/BlenderMfxExportImport/'

import sys, os
os.chdir(path)
sys.path.append(path)

from  JSONToGeometryNode import *
objectName = 'Test2'
settingFile = 'Test1_settings'
objTest = D.objects[objectName]
importMeshEffectFromJson(settingFile, objTest)