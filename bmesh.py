# This example assumes we have a mesh object in edit-mode

import bpy
import bmesh
import gpu
import numpy as np
from random import random
from gpu_extras.batch import batch_for_shader
import time
import mathutils

# Get the active mesh
obj = bpy.context.edit_object
me = obj.data


# Get a BMesh representation
bm = bmesh.from_edit_mesh(me)

bm.faces.active = None

me.calc_loop_triangles()


face = bm.faces[0]

shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
def batch_polygon(face):

    vertices = [v.co for v in face.verts]
    indices = mathutils.geometry.tessellate_polygon((vertices,))
    return batch_for_shader(
        shader, 'TRIS',
        {"pos": vertices},
        indices=indices,
    )

batch = batch_polygon(face)

def draw():
    shader.bind()
    shader.uniform_float("color", (1, 0, 0, 1))
    batch.draw(shader)

bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_VIEW')
