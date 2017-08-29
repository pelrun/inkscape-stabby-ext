#!/usr/bin/env python

import sys
import inkex
from inkex import NSS, addNS, etree, errormsg
import simplepath, simpletransform

zmax=-15
zmin=-35
travel_speed=20000
plunge_speed=10

def get_dimension(s="1024"):
    """Convert an SVG length string from arbitrary units to mm"""
    if s == "":
        return 0
    try:
        last = int(s[-1])
    except:
        last = None

    if type(last) == int:
        return float(s)
    elif s[-1] == "%":
        return 1024
    elif s[-2:] == "px":
        return float(s[:-2])/3.54
    elif s[-2:] == "pt":
        return float(s[:-2])*1.25/3.54
    elif s[-2:] == "em":
        return float(s[:-2])*16/3.54
    elif s[-2:] == "mm":
        return float(s[:-2])*3.54/3.54
    elif s[-2:] == "pc":
        return float(s[:-2])*15/3.54
    elif s[-2:] == "cm":
        return float(s[:-2])*35.43/3.54
    elif s[-2:] == "in":
        return float(s[:-2])*90/3.54
    else:
        return 1024

def propagate_transform(node, parent_transform=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]):
    """Propagate transform to remove inheritance"""

    # Don't enter non-graphical portions of the document
    if (node.tag == addNS("namedview", "sodipodi")
        or node.tag == addNS("defs", "svg")
        or node.tag == addNS("metadata", "svg")
        or node.tag == addNS("foreignObject", "svg")):
        return

    # Compose the transformations
    if node.tag == addNS("svg", "svg") and node.get("viewBox"):
        vx, vy, vw, vh = [get_dimension(x) for x in node.get("viewBox").split()]
        dw = get_dimension(node.get("width", vw))
        dh = get_dimension(node.get("height", vh))
        vx = vx+(dw/2)
        vy = vy+(dh/2)
        rotate = 0
        portrait = True if (dh>dw) else False
        papersize = 3 if (dw>300 or dh>300) else 4
        print "(dw:{0:f} dh:{1:f} portrait:{2} papersize:A{3})".format(dw,dh,portrait,papersize)
        if (papersize == 4 and portrait) or (papersize == 3 and not portrait):
            # ensure we're in portrait orientation for A4/A5
            # and landscape for A3
            print "(rotated)"
            rotate=90
        if papersize == 4:
            print "G54 (A4 centre reference)"
        else:
            print "G57 (A3 centre reference)"
        t = "rotate({4:f}) translate({0:f}, {1:f}) scale({2:f},{3:f})".format(-vx, -vy, dw/vw, dh/vh, rotate)
        this_transform = simpletransform.parseTransform(t, parent_transform)
        this_transform = simpletransform.parseTransform(node.get("transform"), this_transform)
        del node.attrib["viewBox"]
    else:
        this_transform = simpletransform.parseTransform(node.get("transform"), parent_transform)

    if (node.tag == addNS("svg", "svg")
        or node.tag == addNS("g", "svg")
        or node.tag == addNS("a", "svg")
        or node.tag == addNS("switch", "svg")):

        # Remove the transform attribute
        if "transform" in node.keys():
            del node.attrib["transform"]

        # Continue propagating on subelements
        for c in node.iterchildren():
            propagate_transform(c, this_transform)
    else:
        # This element is not a container
        node.set("transform", simpletransform.formatTransform(this_transform))

def path_to_points(path_d, mtx=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]):

    # Exit on empty paths
    if not path_d:
        return []

    # Parse the path
    path = simplepath.parsePath(path_d)

    points = []

    for s in path:
        cmd, params = s
        if cmd not in ['Z','H','V']:
            points.append(params[-2:])

    # Apply the transformation
    if mtx != [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]:
        for pt in points:
            simpletransform.applyTransformToPoint(mtx, pt)

    return points
        
class StabbyEffect(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)
        self.useCircles = True
        self.useNodes = False
        
    def effect(self):
        svg = self.document.getroot()
        propagate_transform(svg)

        # Again, there are two ways to get the attibutes:
        width  = self.unittouu(svg.get('width'))
        height = self.unittouu(svg.get('height'))
        centre = (width/2, height/2)
        
        points = []
        for node in svg.iterchildren():
            points += self.convert_node(node)
        
        print "G17 (XY plane)"
        print "G21 (millimetres)"
        print ''
        print "G0 Z0 F20000"
        print "G0 X0 Y0"
        print ''

        for point in points:
            print 'G0 X{0:.2f} Y{1:.2f}'.format(point[0],-point[1])
            print 'G1 Z{0}'.format(zmin)
            print 'G0 Z{0}'.format(zmax)
            print ''

        print 'G0 Z0'
        print 'G53 X-5 Y-5 (return to home)'


    def convert_node(self, node):
    
        # Parse tags that don't draw any layers
        if node.tag == addNS("namedview", "sodipodi"):
            return []
        elif node.tag == addNS("defs", "svg"):
            return []
        elif node.tag == addNS("metadata", "svg"):
            return []
        elif node.tag not in [
            addNS("g", "svg"),
            addNS("a", "svg"),
            addNS("switch", "svg"),
            addNS("path", "svg"),
            addNS("circle", "svg")]:
            # An unsupported element
            return []

        points = []
        if node.tag == addNS("g", "svg"):
            for subnode in node:
                points += self.convert_node(subnode)

        elif (node.tag == addNS("a", "svg")
              or node.tag == addNS("switch", "svg")):
            # Treat anchor and switch as a group
            for subnode in node:
                points += self.convert_node(subnode)
        elif self.useNodes and node.tag == addNS("path", "svg"):
            points = self.convert_path(node)
        elif self.useCircles and node.tag == addNS("circle", "svg"):
            points = self.convert_circle(node)

        return points

    def convert_circle(self, node):
        if float(node.get('r'))>6:
            return []
        pt = [float(node.get('cx')),float(node.get('cy'))] 
        mtx = simpletransform.parseTransform(node.get("transform"))
        simpletransform.applyTransformToPoint(mtx, pt)
        return [pt]

    def convert_path(self, node):
    
        mtx = simpletransform.parseTransform(node.get("transform"))

        return path_to_points(node.get("d"), mtx)

if __name__ == '__main__':
    e = StabbyEffect()
    e.affect(output=False)
