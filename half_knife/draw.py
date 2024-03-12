# ##### BEGIN GPL LICENSE BLOCK #####
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
#import time
import mathutils
from functools import cmp_to_key

class Draw:

    def __init__(self, context, matrix):
        self.matrix = matrix
        self.context = context
        self.shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        self.edge_shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')

        region = bpy.context.region
        self.edge_shader.uniform_float("viewportSize", (region.width, region.height))
        self.edge_shader.uniform_float("lineWidth", 3.0)

        self.batches = []
        gpu.state.blend_set("ALPHA")

    def batch_polygon(self, face):
        vertices = [self.matrix @ v.co for v in face.verts] if face else []
        indices = mathutils.geometry.tessellate_polygon((vertices,))
        return batch_for_shader(
            self.shader, 'TRIS',
            {"pos": vertices},
            indices=indices,
        )

    def batch_vertices(self, vertices):
        vertices = [self.matrix @ v for v in vertices]
        return batch_for_shader(self.shader, 'POINTS', {"pos": vertices})

    def batch_edges(self, edges):
#       vertex coordinates in edges
        coords = [self.matrix @ v['co'] for e in edges for v in e['verts']]

#        shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        return batch_for_shader(self.edge_shader, 'LINES', {"pos": coords})

    def draw_start(self):
#        args = (self, context)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_VIEW')
        self.redraw = self.context.area.tag_redraw

    def draw_end(self):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        self.redraw()

    def clear(self):
        self.batches = []

    def batch(self, dict):
        self.batches = []
        for key, val in dict.items():
            if key == 'face':
                for t in val:
                    self.batches.append((self.batch_polygon(t[0]), t[1], 'face'))
            elif key == 'edge':
                for t in val:
                    self.batches.append((self.batch_edges(t[0]), t[1], 'edge'))
            elif key == 'vert':
                for t in val:
                    self.batches.append((self.batch_vertices(t[0]), t[1], 'vert'))


    def _draw(self):
#        if not self.batch:
#            return
        self.shader.bind()
        self.edge_shader.bind()
        
        # face < edge < vert
        def comparator(t1, t2):
            if t1[2] == t2[2]:
                return 0
            elif t1[2] == 'vert' or t1[2] == 'edge' and t2[2] == 'face':
                return 1
            else:
                return -1
            
        batches = sorted(self.batches, key = cmp_to_key(comparator), reverse = False)
        for b, color, batchType in batches:
            shader = self.edge_shader if batchType == "edge" else self.shader
            shader.uniform_float("color", color)
            b.draw(shader)
        
                