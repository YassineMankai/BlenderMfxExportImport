import os
from collections import OrderedDict
from itertools import repeat

import bpy
from mathutils import Vector

def get_node_height(node):
    """Work around the fact that blender does not update
    dimensions.y for nodes that have just been created"""
    return 400 #node_height.get(node.type, node_height[...])

def nodes_arrange(nodelist, level, margin_x, margin_y, x_last):
    """Largely imported from NodeArrange add-on by JuhaW (GPL)
    https://github.com/JuhaW/NodeArrange"""
    parents = []
    for node in nodelist:
        parents.append(node.parent)
        node.parent = None

    widthmax = max([x.width for x in nodelist])
    xpos = x_last - (widthmax + margin_x) if level != 0 else 0
    
    y = 0

    for node in nodelist:

        if node.hide:
            hidey = (get_node_height(node) / 2) - 8
            y = y - hidey
        else:
            hidey = 0

        node.location.y = y
        y = y - margin_y - get_node_height(node) + hidey

        node.location.x = xpos

    y = y + margin_y

    for i, node in enumerate(nodelist):
        node.parent =  parents[i]

    return xpos

def autoAlignNodes2(root, margin_x=100, margin_y=20):
    a = []
    a.append([root])

    level = 0

    while a[level]:
        a.append([])

        for node in a[level]:
            inputlist = [i for i in node.inputs if i.is_linked]

            if inputlist:
                for input in inputlist:
                    for nlinks in input.links:
                        node1 = nlinks.from_node
                        a[level + 1].append(node1)

        level += 1

    del a[level]
    level -= 1

    #remove duplicate nodes at the same level, first wins
    for x, nodes in enumerate(a):
        a[x] = list(OrderedDict(zip(a[x], repeat(None))))

    #remove duplicate nodes in all levels, last wins
    top = level
    for row1 in range(top, 1, -1):
        for col1 in a[row1]:
            for row2 in range(row1-1, 0, -1):
                for col2 in a[row2]:
                    if col1 == col2:
                        a[row2].remove(col2)
                        break

    ########################################

    level_count = level + 1
    x_last = 0
    for level in range(level_count):
        x_last = nodes_arrange(a[level], level, margin_x, margin_y, x_last)  

def getNbOutputs(node_group):
    nodes = node_group.nodes
    nbOutputs = {}
    for node in nodes:
        nbOutputs[node.name] = 0
        for output in node.outputs:
            nbOutputs[node.name] += len(output.links)
    return nbOutputs

def getRelativeYposToParent(node_group):
    nodes = node_group.nodes
    relativeYposToParent = {}
    for node in nodes:
        relativeYposToParent[node.name] = {}
        index = -1
        for input in node.inputs:
            for link in input.links:
                sourceNode = link.from_node
                if relativeYposToParent[node.name].get(sourceNode.name) == None:
                    index += 1
                    relativeYposToParent[node.name][sourceNode.name] = index  
        offset = index / 2
        for sourceNodeName in relativeYposToParent[node.name].keys():
            relativeYposToParent[node.name][sourceNodeName] = (offset - relativeYposToParent[node.name][sourceNodeName])
    return relativeYposToParent

def autoAlignNodes(root, margin_x=250, margin_y=500):
    nodeQueue = [(root,0)]
    nbOutputs = getNbOutputs(root.id_data)
    nbOutputs[root.name] = 1
    relativeYposToParent = getRelativeYposToParent(root.id_data)
    grid = []
    while (nodeQueue):
        node, column = nodeQueue.pop(0)
        nbOutputs[node.name] -= 1
        if nbOutputs[node.name] == 0:
            node.location = (100, 100)
            
            if len(grid) == column:
                grid.append([])
            grid[column].append(node)
            for input in node.inputs:
                for link in input.links:
                    nodeQueue.append((link.from_node, column + 1))
            
            nbParents  = 0
            x,y = 0,0
            for output in node.outputs:
                for link in output.links:
                    nbParents += 1
                    parentNode = link.to_node
                    x = min(x, parentNode.location.x - margin_x)
                    y += parentNode.location.y + relativeYposToParent[link.to_node.name][node.name] * margin_y 
            if (nbParents > 0):
                y /= nbParents
            node.location = (x, y)
            
            if len(grid[column]) > 1:
                if (node.location - grid[column][-2].location).length < 350:
                    for neighborIndex in range(len(grid[column])-1):
                        grid[column][neighborIndex].location.y += 50
                    grid[column][-1].location.y -= 150
