import bpy
from  autoAlign import *
from  helpers import *
import json

PLUGIN_FOLDER_PATH = 'C:\\Users\\yassi\\Desktop\\Projects\\OpenMFX\\MfxTutorial\\build\\Debug\\'


def importGraphDescitptionFromJSON(graphName = 'test1'):
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
            socket = addSocket(node_group.inputs, attribute['type'], attribute['name']) 
            data_type = attribute['default_value']['case']
            socket.default_value = attribute['default_value'][data_type]
    for parameter in data['parameters']:
        socket = addSocket(node_group.inputs, parameter['type'], parameter['name'])
        data_type = parameter['default_value']['case']
        socket.default_value = parameter['default_value'][data_type]

    
    handledTypes = ['group', 'math', 'blender', 'openmfx', 'mesh_primitive',  'save_named_attribute']
    skipSettings = ['group', 'math', 'openmfx', 'save_named_attribute', 'input_object', 'multiplexer']
    for nodeData in data['nodes']:
        nodeName = nodeData['name']
        if nodeName == 'InputNode' or nodeName == 'OutputNode':
            continue        
        # add node according to type, apply settings and affect constant values to sockets
        nodeSettings = {}
        for setting in nodeData['settings']:
            nodeSettings[setting['property']] = setting['value']
        match nodeData['type']:
            case 'group':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeGroup')
                graphName = nodeSettings['graph']
                if (bpy.data.node_groups.find(graphName+'Imported') == -1):
                    importFromJSON(graphName)
                geomNodesGraph[nodeName].node_tree = bpy.data.node_groups[graphName+'Imported']
            case 'math':
                geomNodesGraph[nodeName] = addOperationNode(nodes, nodeSettings['operation'])
            case 'join':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeJoinGeometry')
            case 'blender':
                geomNodesGraph[nodeName] = nodes.new(nodeSettings['geo_node'])
            case 'input_object':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeObjectInfo')
                geomNodesGraph[nodeName].transform_space = nodeSettings["transform_space"]
                link(geomNodesGraph['InputNode'].outputs[nodeSettings['objectID']], geomNodesGraph[nodeName].inputs[0])
            case 'save_named_attribute':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeStoreNamedAttribute')
                geomNodesGraph[nodeName].data_type = nodeSettings['data_type']
                geomNodesGraph[nodeName].domain = nodeSettings['domain']
            case 'mesh_primitive':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeMesh' + nodeSettings['shape'].capitalize())
            case 'openmfx':
                geomNodesGraph[nodeName] = nodes.new('GeometryNodeOpenMfx')
                # TODO: use a database
                geomNodesGraph[nodeName].plugin_path = PLUGIN_FOLDER_PATH + nodeSettings['plugin']
                geomNodesGraph[nodeName].effect_enum = nodeSettings['effect']      
        
        geomNodesGraph[nodeName].name = nodeName

        if nodeData['type'] in handledTypes:
            for constant in nodeData['constants']:
                dataType = constant['data']['case']
                socketIndex = getSocketIndexFromComposedKey(constant['socket'])
                if (constant['type'] == 'value'):
                    geomNodesGraph[nodeName].inputs[socketIndex].default_value = constant['data'][dataType]
                elif (constant['type'] == 'parameter'):
                    link(geomNodesGraph['InputNode'].outputs[constant['data'][dataType]], geomNodesGraph[nodeName].inputs[socketIndex])
        
        if nodeData['type'] not in skipSettings:
            for prop in geomNodesGraph[nodeName].bl_rna.properties:
                prop_id = prop.identifier
                if prop_id in geomNodesGraph[nodeName].bl_rna.base.properties or prop.is_readonly:
                    continue
                setattr(geomNodesGraph[nodeName], prop_id, nodeSettings[prop_id])  
    
    inputNodesForMultiplexers = {}

    for nodeData in data['nodes']:
        nodeName = nodeData['name']
        for input in nodeData['inputs']:
            for connection in input['connections']:  
                sourceSocketIndex = getSocketIndexFromComposedKey(connection['from'])
                sourceNodeName = input['sourceNodeName']
                sourceNodeOutputCount = len(geomNodesGraph[sourceNodeName].outputs)
                if sourceNodeName == 'InputNode':
                    sourceNodeOutputCount -= 1
                
                targetSocket = geomNodesGraph['OutputNode'].inputs[-1] if nodeData['type'] == 'output' else geomNodesGraph[nodeName].inputs[getSocketIndexFromComposedKey(connection['to'])]
                sourceSocket = None
                if sourceSocketIndex >= sourceNodeOutputCount: # is multiplexed attribute -> need inputNode
                    multiplexerKey = (sourceNodeName, sourceSocketIndex) 
                    if not inputNodesForMultiplexers.get(multiplexerKey):
                        attributeData = {'attributeName' : getSocketNameFromComposedKey(connection['from']), 'type': targetSocket.type}
                        inputNodesForMultiplexers[multiplexerKey] = addNewInputNode(nodes, attributeData)
                    inputFieldOutputIndex = 0 if inputNodesForMultiplexers[multiplexerKey].type != 'INPUT_ATTRIBUTE' else ['FLOAT_VECTOR', 'FLOAT', 'FLOAT_COLOR', 'BOOLEAN', 'INT'].index(inputNodesForMultiplexers[multiplexerKey].data_type)
                    sourceSocket = inputNodesForMultiplexers[multiplexerKey].outputs[inputFieldOutputIndex]
                else:
                    sourceSocket = geomNodesGraph[input['sourceNodeName']].outputs[sourceSocketIndex] 
                
                link(sourceSocket, targetSocket)
            

    autoAlignNodes(geomNodesGraph['OutputNode'])
    f.close()
    return node_group

def importMeshEffectFromJson(settingsFile, object):
    f = open(settingsFile + '.json')
    data = json.load(f)

    bpy.context.view_layer.objects.active = object
    object.select_set(True)
    ao = bpy.context.active_object
    modifier = object.modifiers.new(data['effectName'], "NODES")
    modifier.node_group = importGraphDescitptionFromJSON(data['graphName'])
    
    for parameterData in data['parameters']:
        inputSocket = modifier.node_group.inputs[parameterData['name']]
        if parameterData['type'] == 'constant':
            modifier[inputSocket.identifier] = parameterData['data'][parameterData['data']['case']]
        else:
            modifier[inputSocket.identifier + '_use_attribute'] = True
            modifier[inputSocket.identifier + '_attribute_name'] = parameterData['data']['as_string']

    for objectInput in data['objectInputs']:
        inputSocket = modifier.node_group.inputs[objectInput['name']]
        modifier[inputSocket.identifier] = bpy.data.objects[objectInput['object']]

    f.close()
    return 0