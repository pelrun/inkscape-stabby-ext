#!/usr/bin/env python

import sys
import inkex
from inkex import NSS, addNS, etree, errormsg, Transform, Path

camera_offset=[11.3,-3.8]

zmax=-15
zmin=-35
travel_speed=20000
plunge_speed=10

debug_enabled=False

def debug(str):
    if debug_enabled:
        print(str)

class StabbyOutput(inkex.OutputExtension):
    """Save as Stabby Output"""

    def header(self, node: inkex.elements._svg.SvgDocumentElement):
        """Calculate the header and global orientation"""

        # Compose the transformations
        if node.tag == addNS("svg", "svg") and node.get("viewBox"):
            vx, vy, vw, vh = node.get_viewbox()
            dw = node.uutounit(node.get("width", vw), "mm")
            dh = node.uutounit(node.get("height", vh), "mm")
            vx = vx+(dw/2)
            vy = vy+(dh/2)
            rotate = 0
            portrait = True if (dh>dw) else False
            papersize = 3 if (dw>300 or dh>300) else 4
            self.output("(dw:{0:f} dh:{1:f} portrait:{2} papersize:A{3})\n".format(dw,dh,portrait,papersize))
            if (papersize == 4 and portrait) or (papersize == 3 and not portrait):
                # ensure we're in portrait orientation for A4/A5
                # and landscape for A3
                self.output("(rotated)\n")
                rotate=90
            if papersize == 4:
                self.coordinate_system = "G54 (A4 centre reference)\n"
            else:
                self.coordinate_system = "G57 (A3 centre reference)\n"
            t = "scale(1,-1) rotate({4:f}) translate({0:f}, {1:f}) scale({2:f},{3:f})".format(-vx, -vy, dw/vw, dh/vh, rotate)
            return Transform(t)

    def process_path(self, path: inkex.PathElement, transform):
        return 'path'

    def process_circle(self, circle: inkex.Circle, transform: inkex.Transform):
        absolute_tfm = transform * circle.composed_transform()
        position = absolute_tfm.apply_to_point(circle.center)
        if circle.get_id() == 'origin':
            self.origin = position
        return position

    def process_group(self, group, transform):
        """flatten layers and groups to avoid recursion"""
        result = []
        for child in group:
            if not isinstance(child, inkex.ShapeElement):
                continue
            if child.is_visible():
                if isinstance(child, inkex.Group):
                    result += self.process_group(child, transform)
                elif self.useNodes and isinstance(child, inkex.PathElement):
                    result.append(self.process_path(child, transform))
                elif self.useCircles:
                    if (isinstance(child, inkex.Circle) and child.radius < 6) or (isinstance(child, inkex.Ellipse) and child.radius.x < 6):
                        result.append(self.process_circle(child, transform))
                # else:
                #     # This only works for shape elements (not text yet!)
                #     new_elem = child.replace_with(child.to_path_element())
                #     # Element is given composed transform b/c it's not added back to doc
                #     new_elem.transform = child.composed_transform()
                #     self.process_path(new_elem, transform)
        return result

    def add_arguments(self, pars):
        #pars.add_argument('--useNodes')
        pass

    def output(self, text: str):
        self.stream.write(text.encode("ascii"))

    def save(self, stream):
        self.options.debug = False
        self.useCircles = True
        self.useNodes = False
        self.stream = stream
        self.origin = None
        self.coordinate_system="G54 (A4 centre reference)\n"

        svg = self.document.getroot()
        output_transform = self.header(svg)

        points=self.process_group(svg, output_transform)

        self.output("(Number of points:{})\n".format(len(points)))

        if self.origin == None:
            self.output(self.coordinate_system)
        else:
            self.output('G10 P6 L20 X{2:.2f} Y{3:.2f} (origin X{0:.2f} Y{1:.2f} offset X{4:.2f} Y{5:.2f})\n'.format(self.origin.x,self.origin.y, self.origin.x+camera_offset[0],self.origin.y+camera_offset[1], camera_offset[0], camera_offset[1]))
            self.output('G59 (custom origin)\n')

        self.output("G17 (XY plane)\n")
        self.output("G21 (millimetres)\n")
        self.output('\n')
        self.output("G0 Z0 F20000\n")
        self.output("G0 X0 Y0 F20000\n")
        self.output('\n')

        completed = set()
        for point in points:
            if point not in completed:
                debug("({})".format(point))
                self.output('G0 X{0:.2f} Y{1:.2f}\n'.format(point.x,point.y))
                self.output('G1 Z{0}\n'.format(zmin))
                self.output('G0 Z{0}\n'.format(zmax))
                self.output('\n')
                completed.add(point)
            else:
                self.output("(dropped duplicate)\n")

        self.output('G0 Z0\n')
        self.output('G53 X-5 Y-5 (return to home)\n')

if __name__ == '__main__':
    StabbyOutput().run()

