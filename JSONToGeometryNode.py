import bpy
from  autoAlign import *
from  helpers import *
import json

def importFromJSON(graphName = 'test1'):
    f = open(graphName + '.json')
    data = json.load(f)
    
    bpy.ops.node.new_node_tree(type='GeometryNodeTree', name=graphName+'Imported') 
    node_group = bpy.data.node_groups[graphName+'Imported']
    nodes = node_group.nodes

    node_group.inputs.clear()
    node_group.outputs.clear()
    nodes.clear()

    link = node_group.links.new

    geomNodesGraph = {} 
    geomNodesGraph['InputNode'] = nodes.new('NodeGroupInput')
    geomNodesGraph['InputNode'].name = 'InputNode'

    geomNodesGraph['OutputNode'] = nodes.new('NodeGroupOutput')
    geomNodesGraph['OutputNode'].name = 'OutputNode'

    # declare inputs and parameters
    for input in data['inputs']:
        if input['sourceType'] == 'geometry':
            addSocket(node_group.inputs, 'GEOMETRY', input['name'])
        elif input['sourceType'] == 'object':
            addSocket(node_group.inputs, 'OBJECT', input['name'])
        for attribute in input['attributes']:
            addSocket(node_group.inputs, attribute['type'], attribute['name']) 
    for parameterName in data['parameters'].keys():
        addSocket(node_group.inputs, data['parameters'][parameterName]['type'], parameterName)

    
    handledTypes = ['group', 'math', 'blender', 'openmfx', 'mesh_primitive',  'save_named_attribute']
    skipSettings = ['group', 'math', 'openmfx', 'save_named_attribute', 'input_object', 'multiplexer']
    for nodeName in list(data['nodes'].keys()):
        if nodeName == 'InputNode' or nodeName == 'OutputNode':
            continue
        nodeData = data['nodes'][nodeName]
        
        # add node according to type, apply settings and affect constant values to sockets
        match nodeData['type']:
            case 'group':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeGroup')
                graphName = nodeData['settings']['graph']
                if (bpy.data.node_groups.find(graphName+'Imported') == -1):
                    importFromJSON(graphName)
                geomNodesGraph[nodeName].node_tree = bpy.data.node_groups[graphName+'Imported']
            case 'math':
                geomNodesGraph[nodeName] = addOperationNode(nodes, nodeData['settings']['operation'])
            case 'join':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeJoinGeometry')
            case 'blender':
                geomNodesGraph[nodeName] = nodes.new(nodeData['settings']['geo_node'])
            case 'input_object':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeObjectInfo')
                geomNodesGraph[nodeName].transform_space = nodeData['settings']["transform_space"]
                link(geomNodesGraph['InputNode'].outputs[nodeData['settings']['objectID']], geomNodesGraph[nodeName].inputs[0])
            case 'save_named_attribute':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeStoreNamedAttribute')
                geomNodesGraph[nodeName].data_type = nodeData['settings']['data_type']
                geomNodesGraph[nodeName].domain = nodeData['settings']['domain']
            case 'mesh_primitive':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeMesh' + nodeData['settings']['shape'].capitalize())
            case 'openmfx':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeOpenMfx')
                # TODO: use a database
                geomNodesGraph[nodeName].plugin_path = 'C:\\Users\\yassi\\Desktop\\Projects\\OpenMFX\\MfxTutorial\\build\\Debug\\' + nodeData['settings']['plugin']
                geomNodesGraph[nodeName].effect_enum = nodeData['settings']['effect']      
        
        geomNodesGraph[nodeName].name = nodeName

        if nodeData['type'] in handledTypes:
            for constantkey in nodeData['constants'].keys():
                socketIndex = getSocketIndexFromComposedKey(constantkey)
                if (nodeData['constants'][constantkey]['type'] == 'value'):
                    geomNodesGraph[nodeName].inputs[socketIndex].default_value = nodeData['constants'][constantkey]['data']
                elif (nodeData['constants'][constantkey]['type'] == 'parameter'):
                    link(geomNodesGraph['InputNode'].outputs[nodeData['constants'][constantkey]['data']], geomNodesGraph[nodeName].inputs[socketIndex])
        
        if nodeData['type'] not in skipSettings:
            for prop in geomNodesGraph[nodeName].bl_rna.properties:
                prop_id = prop.identifier
                if prop_id in geomNodesGraph[nodeName].bl_rna.base.properties or prop.is_readonly:
                    continue
                setattr(geomNodesGraph[nodeName], prop_id, nodeData['settings'][prop_id])  
    
    inputNodesForMultiplexers = {}

    for nodeName in list(data['nodes'].keys()):
        nodeData = data['nodes'][nodeName]
        for inputKey in nodeData['inputs'].keys():
            input = nodeData['inputs'][inputKey]
            connectionList = list(input['connections'].items())
            for connection in connectionList:  
                sourceSocketIndex = getSocketIndexFromComposedKey(connection[1])
                sourceNodeName = input['sourceNodeName']
                sourceNodeOutputCount = len(geomNodesGraph[sourceNodeName].outputs)
                if sourceNodeName == 'InputNode':
                    sourceNodeOutputCount -= 1
                
                sourceSocket = None
                if sourceSocketIndex >= sourceNodeOutputCount: # is multiplexed attribute -> need inputNode
                    multiplexerKey = (sourceNodeName, sourceSocketIndex) 
                    if not inputNodesForMultiplexers.get(multiplexerKey):
                        attributeData = {'attributeName' : getSocketNameFromComposedKey(connection[1]), 'type': targetSocket.type}
                        inputNodesForMultiplexers[multiplexerKey] = addNewInputNode(nodes, attributeData)
                    sourceSocket = inputNodesForMultiplexers[multiplexerKey].outputs[0]
                else:
                    sourceSocket = geomNodesGraph[input['sourceNodeName']].outputs[sourceSocketIndex] 
                targetSocket = geomNodesGraph['OutputNode'].inputs[-1] if nodeData['type'] == 'output' else geomNodesGraph[nodeName].inputs[getSocketIndexFromComposedKey(connection[0])]
                link(sourceSocket, targetSocket)
            

    autoAlignNodes(geomNodesGraph['OutputNode'])
    f.close()