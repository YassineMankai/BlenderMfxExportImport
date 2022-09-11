####### writing a graph
import bpy, os
from  processGraph import *
from helpers import *
import json

blenderToOpenMfxMap = {} # 'TODO: blendernode -> openmfxNode'

# currently: blender node are not exported exactly like the standard (we export other data and treat the node as a special case) TODO: generalize thos

def typeIsHandled(type): # TODO: in these cases replace the node with an OpenMfx One
    if type.startswith('MESH_PRIMITIVE'):
        return True
    return type in ['OPEN_MFX', 'GROUP', 'MESH_PRIMITIVE', 'OBJECT_INFO', 'JOIN', 'JOIN_GEOMETRY', 'VECT_MATH', 'TEX_NOISE', 'INSTANCE_ON_POINTS', 'SET_POSITION']
def CustomMessage(type):  # here we can add a message to the user to replace the node with something else
    return ''

def exportNodes(nodes, dictionary):
    nodeList = dictionary['nodes']
    for node in nodes:
        if node.type != 'GROUP_OUTPUT' and node.type != 'GROUP_INPUT':
            '''if not typeIsHandled(node.type):
                print('Graph contains a node that is not handled in the OpenMfx standard yet')
                nodeData = {'name': node.name, 'type': node.type}
                print(nodeData)
                print(CustomMessage(node.type))
                return -1
        '''

            isMultiplexer = node.label == 'multiplexer'
            
            if isMultiplexer:
                continue

            isOperation = isAttributeOperationNode(node)
            nodeList[node.name]= {'type': '', 'inputs': {}, 'settings': {}, 'constants':{}} 
            
            # export properties
            for prop in node.bl_rna.properties:
                prop_id = prop.identifier
                if prop_id in node.bl_rna.base.properties or prop.is_readonly or propertyIsHandled(node, prop):
                    continue
                nodeList[node.name]['settings'][prop_id] = getattr(node, prop_id)
            
            # export attributes set to default
            for inputIndex in range(len(node.inputs)):
                input = node.inputs[inputIndex]
                if not input.is_linked:
                    def_val = getDefaultValue(input)      
                    if not isDefault(input, def_val):
                        nodeList[node.name]['constants'][input.name + ' (' + str(inputIndex) + ')'] = {'type' : 'value', 'data' : def_val}
            
            # set node type and settings
            if node.type == 'GROUP':
                exportToJSON(node.node_tree)
                nodeList[node.name]['type'] = 'group'
                nodeList[node.name]['settings']["graph"] = node.node_tree.name
            elif node.type == 'OPEN_MFX':
                nodeList[node.name]['type'] = 'openmfx'
                nodeList[node.name]['settings']["plugin"] = getPluginName(node)
                nodeList[node.name]['settings']["effect"] = node.effect_enum
            elif node.type.startswith('MESH_PRIMITIVE'):
                nodeList[node.name]['type'] = 'mesh_primitive'
                nodeList[node.name]['settings']["shape"] = node.type.split('_')[-1].lower()
            elif node.type == 'OBJECT_INFO':
                nodeList[node.name]['type'] = 'input_object'
            elif node.type == 'STORE_NAMED_ATTRIBUTE':
                nodeList[node.name]['type'] = 'save_named_attribute'
            elif node.type == 'JOIN_GEOMETRY':
                nodeList[node.name]['type'] = 'join'
                nodeList[node.name]['settings']["nbInputs"] = len(node.inputs[0].links)
            elif isOperation:
                nodeList[node.name]['type'] = 'math'
                nodeList[node.name]['settings']["operation"] = getOperationInfo(node)
            else: # normal blender effect node
                nodeList[node.name]['type'] = 'blender'
                nodeList[node.name]['settings']["geo_node"] = node.bl_idname
    return 1

def getSourceIndex(sourceSocket, inputMap):
    val = int(sourceSocket.path_from_id()[:-1].split("[")[-1])
    if sourceSocket.node.type != 'GROUP_INPUT':
        return val
    else:
        return inputMap[val]

def getSourceData(sourceSocket, inputMap):
    sourceSocketIndex = getSourceIndex(sourceSocket, inputMap)
    if sourceSocket.node.label == 'multiplexer':
        multiplexer = sourceSocket.node
        if sourceSocketIndex < len(multiplexer.inputs):
            realLink = multiplexer.inputs[sourceSocketIndex].links[0]
            return getSourceData(realLink.from_socket, inputMap)
        else:
            realLink = multiplexer.inputs[0].links[0]
            return getSourceData(realLink.from_socket, inputMap)
    
    elif sourceSocket.type == 'GEOMETRY':
        return {'sourceNodeName': sourceSocket.node.name, 'socketIndex': sourceSocketIndex, 'connections' : {}}

    elif sourceSocket.display_shape == 'DIAMOND':
        if isAttributeOperationNode(sourceSocket.node):
            return {'sourceNodeName': sourceSocket.node.name, 'socketIndex': sourceSocketIndex, 'connections' : {}}
        else:
            while sourceSocket.node.outputs[sourceSocketIndex].type != 'GEOMETRY':
                sourceSocketIndex -= 1
            return {'sourceNodeName': sourceSocket.node.name, 'socketIndex': getSourceIndex(sourceSocket.node.outputs[sourceSocketIndex], inputMap), 'connections' : {}}

def addConnection(inputData, link, inputMap):
    sourceSocket = link.from_socket
    targetSocket = link.to_socket
    sourceSocketIndex = getSourceIndex(sourceSocket, inputMap)
    targetSocketIndex = targetSocket.path_from_id()[:-1].split("[")[-1]
       
    sourceKey = sourceSocket.name + ' (' + str(sourceSocketIndex) + ')'
    targetKey = targetSocket.name + ' (' + targetSocketIndex + ')'
    
    currentSoruceData = getSourceData(sourceSocket, inputMap)

    for key in list(inputData.keys()):
        if inputData[key]['sourceNodeName'] == currentSoruceData['sourceNodeName'] and inputData[key]['socketIndex'] == currentSoruceData['socketIndex']:
            inputData[key]['connections'][targetKey] = sourceKey
            return
    inputData['attributeExtraGeometry_' + targetSocketIndex] = currentSoruceData
    inputData['attributeExtraGeometry_' + targetSocketIndex]['connections'][targetKey]  = sourceKey

def exportLinks(nodes, dictionary, inputMap):
    nodeList = dictionary['nodes']

    for node in nodes:
        if node.label == 'multiplexer' or node.type == 'GROUP_INPUT':
            continue
        nodeData = nodeList[node.name]
        if node.type == 'INSTANCE_ON_POINTS':
            if node.inputs['Points'].is_linked:
                link = node.inputs['Points'].links[0]
                nodeData['inputs']['Points'] = getSourceData(link.from_socket, inputMap)
                addConnection(nodeData['inputs'], node.inputs['Points'].links[0], inputMap)
            if node.inputs['Instance'].is_linked:
                link = node.inputs['Instance'].links[0]
                nodeData['inputs']['Instance'] = getSourceData(link.from_socket, inputMap)
                addConnection(nodeData['inputs'], node.inputs['Instance'].links[0], inputMap)
            for socketPointsAttributeIndex in [1,5,6]:
                if node.inputs[socketPointsAttributeIndex].is_linked:
                    addConnection(nodeData['inputs'], node.inputs[socketPointsAttributeIndex].links[0], inputMap)
            for socketPointsAttributeIndex in [3,4]:
                if node.inputs[socketPointsAttributeIndex].is_linked:
                    addConnection(nodeData['inputs'], node.inputs[socketPointsAttributeIndex].links[0], inputMap)
        elif node.type == 'JOIN_GEOMETRY':
            i = 0
            for sourceGeometryLink in node.inputs['Geometry'].links:
                nodeData['inputs']['Geometry ' + '(' + str(i) + ')'] = getSourceData(sourceGeometryLink.from_socket, inputMap)
                addConnection(nodeData['inputs'], sourceGeometryLink, inputMap)
                i+=1
        else:
            linkedInputs = [inp for inp in node.inputs if inp.is_linked]
            # handle parameters and geometry links first
            for input in linkedInputs:
                sourceSocket = input.links[0].from_socket
                targetSocket = input
                sourceSocketIndex = sourceSocket.path_from_id()[:-1].split("[")[-1]
                targetSocketIndex = targetSocket.path_from_id()[:-1].split("[")[-1]
                if input.type == 'GEOMETRY':
                    link = input.links[0]
                    nodeData['inputs'][input.name] = getSourceData(link.from_socket, inputMap)
                    addConnection(nodeData['inputs'], link, inputMap)
                elif input.type == 'OBJECT':
                    nodeList[node.name]['settings']['objectID'] = inputMap[int(sourceSocketIndex)]
                elif input.display_shape == 'CIRCLE':
                    nodeList[node.name]['constants'][targetSocket.name + ' (' + targetSocketIndex + ')'] = {'type' : 'parameter', 'data' : sourceSocket.name}
                
            # handle attributes last
            for input in linkedInputs:
                if input.display_shape == 'DIAMOND':
                    addConnection(nodeData['inputs'], input.links[0], inputMap)

def exportToJSON(geomGraph):
    graphName = geomGraph.name  
    node_group = duplicateGraphAndEnsureConnections(geomGraph)
    preProcess(node_group)
    node_group, multiplexers = canonizeGraph(node_group)

    nodes = node_group.nodes

    # Data to be written
    dictionary = {}
    dictionary['name'] = graphName
    dictionary['inputs'] = []
    dictionary['parameters'] = {}
    dictionary['nodes'] = {}

    dictionary['nodes']['OutputNode'] = {'type': 'output', 'inputs': {}, 'settings': {}, 'constants': {}}
    dictionary['nodes']['InputNode'] = {'type': 'input', 'inputs': {}, 'settings': {}, 'constants': {}}

    GroupInputNode = nodes.get('InputNode')
    
    inputMap = {}
    inputSocketIndex = 0
    parameterSocketIndex = 0
    # Standard: First input should always be main geometry
    for i in range(len(GroupInputNode.outputs) - 1):
        input = GroupInputNode.outputs[i] # outputs of the geometry node are the inputs of the procedural graph effect
        if input.type == 'GEOMETRY':
            inputMap[i] = inputSocketIndex
            inputSocketIndex += 1
            dictionary['inputs'].append({
                'sourceType': 'geometry',
                'name': input.name,
                'attributes': []
            })
        elif input.type == 'OBJECT':
            inputMap[i] = inputSocketIndex
            inputSocketIndex += 1
            dictionary['inputs'].append({
                'sourceType': 'object',
                'name': input.name,
                'attributes': []
            })
        elif input.display_shape == 'CIRCLE':
            inputMap[i] = parameterSocketIndex
            parameterSocketIndex += 1
            dictionary['parameters'][input.name] = {
                'type': input.type, #TODO: use standarized types instead of blender specific ones
                'default_value': getDefaultValue(input)
            }
        else:
            inputMap[i] = inputSocketIndex
            inputSocketIndex += 1
            dictionary['inputs'][-1]['attributes'].append({
                'name': input.name,
                'type': input.type, #TODO: use standarized types instead of blender specific ones
                'default_value': getDefaultValue(input)
            })

            
    success = exportNodes(nodes, dictionary)
    if success == -1:
        return
    exportLinks(nodes, dictionary, inputMap)
    
    json_object = json.dumps(dictionary, indent=4)
    with open(graphName + ".json", "w") as outfile:
        outfile.write(json_object)
    
    bpy.data.node_groups.remove(node_group)
    for multiplexerGroup in multiplexers:
        bpy.data.node_groups.remove(multiplexerGroup)
    