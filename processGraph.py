from numpy import true_divide
import bpy
from  helpers import *

def exploreFieldExtent(node, visitedNodes, duplicateList, toDelete, geometryToInputField):
    visitedNodes[node.name] = 1
    nodes = node.id_data.nodes
    for output in node.outputs:
        for link in output.links:
            nextNode = link.to_node
            #TODO: check for multiple input geometries if needed
            if isDataFlowNode(nextNode):
                sourceInputIndex = getSourceInputIndex(link.to_socket)
                sourceNode = nextNode.inputs[sourceInputIndex].links[0].from_node
                sourceSocketIndex = nextNode.inputs[sourceInputIndex].links[0].from_socket.path_from_id()[:-1].split("[")[-1]
                sourceGeometry = (sourceNode.name, sourceSocketIndex)
                if not duplicateList.get(sourceGeometry):
                    duplicateList[sourceGeometry] = {}
                for nodeName in visitedNodes.keys():
                    currentNode = nodes[nodeName]
                    if isInputField(currentNode):
                        if not geometryToInputField.get(sourceGeometry[0]):
                            geometryToInputField[sourceGeometry[0]] = {}
                        fieldSocketIdentifier = getInputFieldName(currentNode)
                        if not geometryToInputField[sourceGeometry[0]].get(fieldSocketIdentifier):
                            geometryToInputField[sourceGeometry[0]][fieldSocketIdentifier] = duplicate_node(currentNode)
                        toDelete.append(nodeName)
                        duplicateList[sourceGeometry][nodeName] = geometryToInputField[sourceGeometry[0]][fieldSocketIdentifier]
                    elif not duplicateList[sourceGeometry].get(nodeName):
                        toDelete.append(nodeName)
                        duplicateList[sourceGeometry][nodeName] = duplicate_node(nodes[nodeName])
            else:
                exploreFieldExtent(nextNode, visitedNodes, duplicateList, toDelete, geometryToInputField)
    visitedNodes.pop(node.name)

def handleFieldInputs(node, geometryToConnect, duplicateList):
    nodeGenenrateGeometry = len([inp for inp in node.inputs if inp.type == 'GEOMETRY']) == 0
    for input in node.inputs:
        if len(input.links) == 0:
            continue
        if isDataFlowNode(node) and not nodeGenenrateGeometry:
            targetGeometrySocket = node.inputs[getSourceInputIndex(input)]
            sourceNodeName = targetGeometrySocket.links[0].from_node.name
            sourceSocketIndex = targetGeometrySocket.links[0].from_socket.path_from_id()[:-1].split("[")[-1]
            geometryToConnect = (sourceNodeName, sourceSocketIndex)
        
        for link in input.links:
            handleFieldInputs(link.from_node, geometryToConnect, duplicateList)
            sourceNode_cpy = link.from_node
            if duplicateList.get(geometryToConnect):
                if duplicateList[geometryToConnect].get(link.from_node.name):
                    sourceNode_cpy = duplicateList[geometryToConnect][link.from_node.name]
            sourceSocketIndex = int(link.from_socket.path_from_id()[:-1].split("[")[-1])

            toNode_cpy = node
            if duplicateList.get(geometryToConnect):
                if duplicateList[geometryToConnect].get(node.name):
                    toNode_cpy = duplicateList[geometryToConnect][node.name]
            targetSocketIndex = int(input.path_from_id()[:-1].split("[")[-1])

            node.id_data.links.new(sourceNode_cpy.outputs[sourceSocketIndex], toNode_cpy.inputs[targetSocketIndex])

def generateMultiplexerFromNode(node, inputFields):
    node_group = node.id_data
    nodes = node_group.nodes
    wrapperGroup = bpy.data.node_groups.new(type='GeometryNodeTree', name='multiplexer_' + node.name)

    inputFieldOutputIndex = 0

    nodeGroupInput = wrapperGroup.nodes.new('NodeGroupInput')
    nodeGroupOutput = wrapperGroup.nodes.new('NodeGroupOutput')

    for outputIndex in range(len(node.outputs)):
        output = node.outputs[outputIndex]
        if output.type == 'CUSTOM':
            continue
        wrapperGroup.outputs.new(type=output.bl_idname, name=output.name)
        wrapperGroup.inputs.new(type=output.bl_idname, name=output.name)
        wrapperGroup.links.new(nodeGroupInput.outputs[outputIndex], nodeGroupOutput.inputs[outputIndex])      
    for inputFieldName in inputFields.keys():
        inputField = inputFields[inputFieldName]
        inputField_cpy = duplicate_node(inputField, wrapperGroup)
        type = inputField_cpy.outputs[0].bl_idname
        if inputField_cpy.bl_idname == 'GeometryNodeInputNamedAttribute':
            inputFieldOutputIndex = ['FLOAT_VECTOR', 'FLOAT', 'FLOAT_COLOR', 'BOOLEAN', 'INT'].index(inputField_cpy.data_type)
            type = 'NodeSocket' + ['Vector', 'Float', 'Color', 'Bool', 'Int'][inputFieldOutputIndex]
        wrapperGroup.outputs.new(type=type, name=inputFieldName)
        wrapperGroup.links.new(inputField_cpy.outputs[inputFieldOutputIndex], nodeGroupOutput.inputs[-2])   
    autoAlignNodes(nodeGroupOutput)
    multiplexerNode = node_group.nodes.new('GeometryNodeGroup')
    multiplexerNode.node_tree = wrapperGroup
    multiplexerNode.name = 'multiplexer_' + node.name
    multiplexerNode.label = 'multiplexer'

    for outputIndex in range(len(node.outputs)):
        output = node.outputs[outputIndex]
        if output.type == 'CUSTOM':
            continue
        for link in node.outputs[outputIndex].links:
            to_socket = link.to_socket
            node_group.links.remove(link)
            node_group.links.new(multiplexerNode.outputs[outputIndex], to_socket)
        node_group.links.new(output, multiplexerNode.inputs[outputIndex])
            
    for inputFieldName in inputFields.keys():
        inputField = inputFields[inputFieldName]
        for link in inputField.outputs[inputFieldOutputIndex].links:
            node_group.links.new(multiplexerNode.outputs[inputFieldName], link.to_socket)
        if nodes.get(inputField.name):
            nodes.remove(inputField)    
    return wrapperGroup

def canonizeGraph(node_group):
    nodes = node_group.nodes
    duplicateList = {}
    geometryToInputField = {}
    toDelete = []
    multiplexers = []
    originalNames = [node.name for node in node_group.nodes] #To avoid handling newly created nodes
    for orginal_nodeName in originalNames:
        node = nodes[orginal_nodeName]
        if isInputField(node):
            visitedNodes = {}
            exploreFieldExtent(node, visitedNodes, duplicateList, toDelete, geometryToInputField)
    groupOutputNode = node_group.nodes['OutputNode']
    handleFieldInputs(groupOutputNode, (None, None), duplicateList)   
    for nodeName in toDelete:
        if nodes.get(nodeName):
            nodes.remove(nodes[nodeName]) 
    for nodeName in geometryToInputField.keys():
        multiplexers.append(generateMultiplexerFromNode(nodes[nodeName], geometryToInputField[nodeName]))  
    autoAlignNodes(groupOutputNode)
    return node_group, multiplexers

def preProcess(graph): 
    # keep one input node
    GroupInputNode = graph.nodes.new('NodeGroupInput')
    for node in graph.nodes:
        if node.bl_idname == 'NodeGroupInput':
            for outputIndex in range(len(node.outputs)):
                output = node.outputs[outputIndex]
                for edge in output.links:
                    graph.links.new(GroupInputNode.outputs[outputIndex], edge.to_socket)
    for node in graph.nodes:
        if node.bl_idname == 'NodeGroupInput' and node != GroupInputNode:
            graph.nodes.remove(node) 
    GroupInputNode.name = 'InputNode'

    # keep one output node
    GroupOutputNode = graph.nodes.new('NodeGroupOutput')
    for node in graph.nodes:
        if node.bl_idname == 'NodeGroupOutput':
            for inputIndex in range(len(node.inputs)):
                input = node.inputs[inputIndex]
                for edge in input.links:
                    graph.links.new(edge.from_socket, GroupOutputNode.inputs[inputIndex])
    for node in graph.nodes:
        if node.bl_idname == 'NodeGroupOutput' and node != GroupOutputNode:
            graph.nodes.remove(node) 
    GroupOutputNode.name = 'OutputNode'

    # make object info name attribute a graph parameter to avoid context dependant variables inside the graph
    for node in graph.nodes:
        if node.type == 'OBJECT_INFO':
            graph.links.new(GroupInputNode.outputs[-1], node.inputs['Object'])


