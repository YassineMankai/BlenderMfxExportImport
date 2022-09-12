## here I suppose that the current geometry is always plugged to the first input and first output
# this part is hard coded TODO: find a better solution
import bpy
from  autoAlign import *


typeToSocketDict = {}
typeToSocketDict['GEOMETRY'] = 'NodeSocketGeometry'
typeToSocketDict['VALUE'] = 'NodeSocketFloat'
typeToSocketDict['INT'] = 'NodeSocketInt'
typeToSocketDict['BOOLEAN'] = 'NodeSocketBool'
typeToSocketDict['STRING'] = 'NodeSocketString'
typeToSocketDict['RGBA'] = 'NodeSocketColor'
typeToSocketDict['VALUE'] = 'NodeSocketFloat'
typeToSocketDict['OBJECT'] = 'NodeSocketObject'
typeToSocketDict['VECTOR'] = 'NodeSocketVector'
def typeToSocket(type):
    return typeToSocketDict[type]
def isDataFlowNode(node):
    for input in node.inputs:
        if input.type == 'GEOMETRY':
            return True
    for output in node.outputs:
        if output.type == 'GEOMETRY':
            return True
    return False
def isInputField(node):
    return node.rna_type.identifier in  ['GeometryNodeInputPosition', 
                                        'GeometryNodeInputNormal', 
                                        'GeometryNodeInputID', 
                                        'GeometryNodeInputIndex', 
                                        'GeometryNodeInputRadius',
                                        'GeometryNodeInputNamedAttribute']



### function used for the canonization
def getInputFieldName(node): #TODO: currently, only constant names are handled
    if node.rna_type.identifier == 'GeometryNodeInputNamedAttribute':
        return node.inputs['Name'].default_value
    return node.rna_type.identifier[17:].lower() 

def getSourceInputIndex(socket):
    socketIndex = int(socket.path_from_id()[:-1].split("[")[-1])
    if (socket.node.type == 'INSTANCE_ON_POINTS'):
        if socketIndex == 3 or socketIndex == 4:
            return 2
        else:
            return 0
    else: 
    # TODO: for now, we suppose requested attributes socket are listed directly after the corresponding geometry
        while(socketIndex >= 0 and socket.node.inputs[socketIndex].type != 'GEOMETRY'):
                socketIndex -= 1
        return socketIndex


### function used to JSONify a graph
def propertyIsHandled(node, prop): # skip property if it is declared as settings
    # TODO: expand this function to handle more cases
    if node.type in ['OPEN_MFX','GROUP', 'VECT_MATH']:
        return True
    return False

def getOperationInfo(operationNode):
    if operationNode.type == 'TEX_NOISE':
        return {'operation' : 'texture', 'info' : 'noise'} #TODO handle more noises
    elif operationNode.type == 'VECT_MATH':
        return {'operation' : operationNode.operation.lower(), 'info' : 'vector'} 
    elif operationNode.type == 'MATH':
        return {'operation' : operationNode.operation.lower(), 'info' : 'scalar'} 
    else:#TODO: add other nodes
        return 'add'

def getPluginName(openmfxNode):
    # TODO: switch system
    return openmfxNode.plugin_path.split('\\')[-1]

def stringToConstantValue(s):
    return {
        'case' : 'as_string',
        'as_bool': True,
        'as_int': 0,
        'as_float': 0.0,
        'as_vector': (0,0,0),
        'as_color': (0,0,0,0),
        'as_string': s
    } 
map = {
        'BOOLEAN': 'as_bool',
        'INT': 'as_int',
        'VALUE': 'as_float',
        'VECTOR': 'as_vector',
        'RGBA': 'as_color',
        'STRING': 'as_string',
    }
def getDefaultValue(input): 
    def_val = {
        'case' : map[input.type],
        'as_bool': True,
        'as_int': 0,
        'as_float': 0.0,
        'as_vector': (0,0,0),
        'as_color': (0,0,0,0),
        'as_string': ''
    }   
    
    if input.type in ['STRING', 'BOOLEAN', 'INT', 'VALUE']:
        def_val[map[input.type]] =  input.default_value
    elif input.type == 'VECTOR':
        def_val[map[input.type]] = (input.default_value[0], input.default_value[1], input.default_value[2])
    elif input.type == 'RGBA':
        def_val[map[input.type]] = (input.default_value[0], input.default_value[1], input.default_value[2], input.default_value[3]) 
    return  def_val

def isAttributeOperationNode(node): #make sure this is sufficient
    return not isDataFlowNode(node) and not isInputField(node)

#Todo: get default values from blender (for the moment they are hard coded)
def isDefault(input, def_val):
    val = def_val[map[input.type]]
    if input.node.type == 'TEX_NOISE':
        if input.name == 'Scale':
            return val == 5.0
        elif input.name == 'Detail':
            return val == 2.0 
        elif input.name == 'Roughness':
            return val == 0.5 
        elif input.name == 'Distortion':
            return val == 0.0 
        return True
    elif input.type == 'STRING':
        return val == ''
    elif input.name == 'Scale':
        if hasattr(input.node, 'operation') and (input.node.operation != 'SCALE' or val == 1.0):
            return True
    elif input.type == 'BOOLEAN':
        return val if input.name == 'Selection' else not val
    else:
        return val == 0 or val == (0,0,0) or val == (0,0,0,0)



### function used to import a JSON as a graph
def addNewInputNode(nodes, attribute):
    if attribute['attributeName'] == 'id':
        return nodes.new('GeometryNodeInputID')
    elif attribute['attributeName'] in  ['position', 'normal', 'index', 'radius']:
        return nodes.new('GeometryNodeInput' + attribute['attributeName'].capitalize())
    else:
        n = nodes.new('GeometryNodeInputNamedAttribute')
        if attribute['attributeName'] != '':
            n.inputs['Name'].default_value = attribute['attributeName']
        if attribute['type'] == 'VECTOR' or attribute['type'] == 'COLOR':
            n.data_type = 'FLOAT_' + attribute['type']
        elif attribute['type'] == 'VALUE':
            n.data_type = 'FLOAT'
        else:
            n.data_type = attribute['type']
        return n

def addSocket(interface, type, name):
    return interface.new(typeToSocket(type), name)

def getSocketIndexFromComposedKey(key):
    return int(key[:-1].split('(')[-1])

def getSocketNameFromComposedKey(key):
    i = -1
    while key[i] != '(':
        i -= 1
    return key[:i-1]

def getBlenderOperation(operation):
    return operation.upper()

def addOperationNode(nodes, operationInfo):
    if operationInfo['info'] == 'noise':
        return nodes.new('ShaderNodeTexNoise') #TODO handle more noises
    elif operationInfo['info'] == 'vector':
        n = nodes.new('ShaderNodeVectorMath')
        n.operation = getBlenderOperation(operationInfo['operation'])
        return n
    elif operationInfo['info'] == 'scalar':
        n = nodes.new('ShaderNodeMath')
        n.operation = getBlenderOperation(operationInfo['operation'])
        return n
    else:
        return nodes.new('ShaderNodeVectorMath')


### Duplication functions
# source gist github elie
def duplicate_node(n1, node_group=None, duplicate_links=False):
    """
    Duplicate a node (without duplicating its links)
    @param n1 The node to duplicate
    @param node_group (optional) Group in which the node must be duplicated
    @param duplicate_links Whether to keep input links or not
    @return the new duplicate node
    """
    if node_group is None:
        node_group = n1.id_data
    n2 = node_group.nodes.new(type=n1.rna_type.identifier)
    for prop in n1.bl_rna.properties:
        prop_id = prop.identifier
        if prop_id in n1.bl_rna.base.properties or prop.is_readonly:
            continue
        value = getattr(n1, prop_id)
        setattr(n2, prop_id, value)
    for in1, in2 in zip(n1.inputs, n2.inputs):
        if hasattr(in1, 'default_value'):
            in2.default_value = in1.default_value
        if duplicate_links:
            for link in in1.links:
                node_group.links.new(input=link.from_socket, output=in2)
    for out1, out2 in zip(n1.outputs, n2.outputs):
        if hasattr(out1, 'default_value'):
            out2.default_value = out1.default_value
    if (n1.id_data == n2.id_data):
        n2.name = n1.name+'_cpy'
    else:
        n2.name = n1.name
    return n2
# duplicate graph and conncet input to default field inputs, returns the total nubmer of links connected to the output of each node
def isDefaultPositionInput(input):
    return not(input.is_linked) and ((input.node.type[:3] == 'TEX' and input.name == 'Vector') or \
        (input.node.type == 'SET_POSITION' and input.name == 'Position'))
def duplicateGraphAndEnsureConnections(node_group, newName = ''):
    graphName = node_group.name
    nodes = node_group.nodes
    links = node_group.links
    if newName == '':
        node_group_cpy = bpy.data.node_groups.new(type='GeometryNodeTree', name=graphName+'_cpy')  
    else:
        node_group_cpy = bpy.data.node_groups.new(type='GeometryNodeTree', name=newName)  
    nodes_cpy = node_group_cpy.nodes  
    links_cpy = node_group_cpy.links
    for input in node_group.inputs:
        test_input = node_group_cpy.inputs.new(input.bl_socket_idname, input.name)
        if hasattr(input, 'default_value'):
            test_input.default_value = input.default_value
    for output in node_group.outputs:
        node_group_cpy.outputs.new(output.bl_socket_idname, output.name)
    
    for node in nodes:
        if len(node.inputs) > 0 and node.inputs[0].type == 'GEOMETRY' and len(node.inputs[0].links) == 0:
            print("error: not connected geometry input on: " + node.name)
            return None
        
        duplicate_node(node, node_group_cpy)

        for i in range(len(node.inputs)):
            input = node.inputs[i]
            if isDefaultPositionInput(input):
                new_posNode = nodes_cpy.new('GeometryNodeInputPosition')
                new_posNode.name = 'Position '+node.name
                links_cpy.new(new_posNode.outputs[0], node_group_cpy.nodes[node.name].inputs[i])
    for link in links:
        source_socket = nodes_cpy[link.from_node.name].outputs[int(link.from_socket.path_from_id()[:-1].split("[")[-1])]
        target_socket = nodes_cpy[link.to_node.name].inputs[int(link.to_socket.path_from_id()[:-1].split("[")[-1])]
        links_cpy.new(source_socket, target_socket)

    return  node_group_cpy
