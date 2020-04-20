import bpy
import gpu
from gpu_extras.batch import batch_for_shader
#import time
import mathutils
import bgl

class Draw:

    def __init__(self, context, matrix):
        self.matrix = matrix
        self.context = context
        self.shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        self.batches = []

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
        return batch_for_shader(self.shader, 'LINES', {"pos": coords})

    def draw_start(self):
#        args = (self, context)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_VIEW')
        self.redraw = self.context.area.tag_redraw

    def draw_end(self):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        self.redraw()

    def clear(self):
        self.batches = []

    # def map_to_color(self, elems):
    #     colors = []
    #     result = []
    #     color_index = 0
    #     for e, color in val:
    #         if color in colors:
    #             color_index = colors.index(color)
    #             result[i].append(e)
    #         else:
    #             color_index = len(colors)
    #             colors.append(color)
    #             result.append([e])
    #     return colors, result

    def batch(self, dict):
        self.batches = []
        for key, val in dict.items():
            if key == 'face':
                for t in val:
                    self.batches.append((self.batch_polygon(t[0]), t[1]))
            elif key == 'edge':
                for t in val:
                    self.batches.append((self.batch_edges(t[0]), t[1]))
            elif key == 'vert':
                for t in val:
                    self.batches.append((self.batch_vertices(t[0]), t[1]))

    def _draw(self):
#        if not self.batch:
#            return
        self.shader.bind()
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glLineWidth(3)
        bgl.glPointSize(12)
        for b, color in self.batches:
            self.shader.uniform_float("color", color)
            b.draw(self.shader)