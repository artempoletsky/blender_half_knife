if "bpy" in locals():
    import importlib
    importlib.reload(ray_cast)
else:
    from . import ray_cast

import bpy
from bpy_extras import view3d_utils
from mathutils.bvhtree import BVHTree
import bmesh
import gpu
import numpy as np
#from random import random
from gpu_extras.batch import batch_for_shader
#import time
import mathutils
import bgl
import math



def main(context, event, tree, bmesh):
    """Run this function on left mouse, execute the ray cast"""
    # get the context arguments
    scene = context.scene
    region = context.region
    rv3d = context.region_data
    coord = event.mouse_region_x, event.mouse_region_y

    # get the ray from the viewport and mouse
    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)

    ray_target = ray_origin + view_vector

    # my_tree0 = BVHTree.FromObject(context.object, context.evaluated_depsgraph_get())

    def obj_ray_cast(matrix):
        """Wrapper for ray casting that moves the ray into object space"""

        # get the ray relative to the object
        matrix_inv = matrix.inverted()
        ray_origin_obj = matrix_inv @ ray_origin
        ray_target_obj = matrix_inv @ ray_target
        ray_direction_obj = ray_target_obj - ray_origin_obj

        # cast the ray
#        success, location, normal, face_index = obj.ray_cast(ray_origin_obj, ray_direction_obj)
        location, normal, face_index, distance = tree.ray_cast(ray_origin_obj, ray_direction_obj)

#        print(face_index)
        if location:
            return location, normal, face_index
        else:
            return None, None, None

    matrix = context.object.matrix_world
    hit, normal, face_index = obj_ray_cast(matrix)
    if hit is None:
        return None, None

    return hit, bmesh.faces[face_index]

def vertex_project(point, edge):
    v1, v2 = [v.co for v in edge.verts]
    ap = point - v1
    ab = v2 - v1
    temp = ab * (np.dot(ap,ab) / np.dot(ab,ab))
    print(temp, v1, ab)
    projected = v1 + temp
    d1 = (v1 - projected).length
    d2 = (v2 - projected).length
    a = ab.length
    # projected = projected if abs(d1 + d2 - a) < 0.001 else edge.verts[0] if d1 < d2 else edge.verts[1]
    split_ratio = 0
    if (abs(d1 + d2 - a) < 0.001):
        split_ratio = d1 / a
    else:
        projected, split_ratio = (edge.verts[0], 0) if d1 < d2 else (edge.verts[1], 1)
    return projected, split_ratio

# returns distance_to_edge, distance_to_closest_vert, index_of_closest_vert
def distance_to_edge(point, edge):
    v1, v2 = [v.co for v in edge.verts]
    d1 = (point - v1).length
    d2 = (point - v2).length
    a = (v1 - v2).length
    p = (a + d1 + d2) / 2
    h = (2 / a) * math.sqrt(p * (p - a) * (p - d1) * (p - d2))
    d, index = (d1, 0) if d1 < d2 else (d2, 1)
    return min(h, d1, d2), d, index

class ViewOperatorRayCast(bpy.types.Operator):
    """Modal object selection with a ray cast"""
    bl_idname = "view3d.modal_operator_raycast"
    bl_label = "RayCast View Operator"
    bl_options = {'REGISTER', 'UNDO'}

    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')


    def batch_polygon(self, face):


        vertices = [v.co for v in face.verts] if face else []
        indices = mathutils.geometry.tessellate_polygon((vertices,))
        return batch_for_shader(
            self.shader, 'TRIS',
            {"pos": vertices},
            indices=indices,
        )


    def find_closest(self, point, face):
        if not point:
            return None, None, None, None

        edge_dist = float("inf")
        vert_dist = float("inf")
        edge = None
        vert = None
        for e in face.edges:
            d, vd, i = distance_to_edge(point, e)
            if d < edge_dist:
                edge_dist = d
                edge = e
                vert = e.verts[i]
                vert_dist = vd

        return vert, edge, edge_dist, vert_dist

    def batch_vertices(self, vertices):
        matrix = self.object.matrix_world
        vertices = [matrix @ v for v in vertices]
        return batch_for_shader(self.shader, 'POINTS', {"pos": vertices})

    def batch_edges(self, edges):
#       vertex coordinates in edges
        matrix = self.object.matrix_world
        coords = [matrix @ v['co'] for e in edges for v in e['verts']]

#        shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        return batch_for_shader(self.shader, 'LINES', {"pos": coords})

    def _draw(self):
#        if not self.batch:
#            return
        bgl.glLineWidth(3)

        self.shader.bind()
        self.shader.uniform_float("color", (1, 0, 0, 1))
#        bgl.glBegin(bgl.GL_POINTS)
        bgl.glPointSize(12)
        self.batch_new_vertices.draw(self.shader)
        self.shader.uniform_float("color", (0, 1, 0, 1))
        self.batch_new_edges.draw(self.shader)

    def run_cut(self):
#        v = self.bmesh.verts.new()
#        v.co = self.new_vert
        edge, vert = bmesh.utils.edge_split(self.edge, self.edge.verts[0], self.split_ratio)
        pairs = []
        for v in self.initial_vertices:
            v.select_set(False)
#        self.initial_vertices.append(vert)
            bmesh.ops.connect_vert_pair(self.bmesh, verts = (v, vert))
#            bmesh.ops.connect_verts(self.bmesh, verts = (v, vert))

        bmesh.update_edit_mesh(self.object.data, True)
        vert.select_set(True)
        self.bmesh.select_history.add(vert)

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            # allow navigation
            return {'PASS_THROUGH'}
        elif event.type == 'MOUSEMOVE':
            hit, face = ray_cast.BVH_ray_cast(context, event, self.tree, self.bmesh)
            if hit:
                vert, edge, edge_dist, vert_dist = self.find_closest(hit, face)
                new_vert, split_ratio = vertex_project(hit, edge)
                self.split_ratio = split_ratio
                self.edge = edge
                # if no need to create new vertex
                if split_ratio in [0, 1]:
                    new_vert = new_vert.co

                new_egdes = [{"verts": [{"co": v.co},
                {"co": new_vert}]
                } for v in self.initial_vertices]
                print(new_egdes)
#
#
#                    new_vert = v
                # self.new_vert = new_vert
                self.batch_new_vertices = self.batch_vertices([new_vert])
                self.batch_new_edges = self.batch_edges(new_egdes)
            else:
                self.batch_new_edges = self.batch_vertices([])
                self.batch_new_vertices = self.batch_vertices([])
            self.redraw()
            return {'RUNNING_MODAL'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.draw_end()
            return {'CANCELLED'}
        elif event.type in {'LEFTMOUSE'}:
            self.draw_end()
            self.run_cut()
            return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def draw_start(self, context):
#        args = (self, context)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_VIEW')
        self.redraw = context.area.tag_redraw

    def draw_end(self):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        self.redraw()

    def invoke(self, context, event):
        if context.space_data.type == 'VIEW_3D':
            self.object = context.object
            self.tree = BVHTree.FromObject(context.object, context.evaluated_depsgraph_get())
            self.bmesh = bmesh.from_edit_mesh(context.object.data)
            self.initial_vertices = [v for v in self.bmesh.verts if v.select]
            context.window_manager.modal_handler_add(self)
            self.draw_start(context)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}


def register():
    bpy.utils.register_class(ViewOperatorRayCast)


def unregister():
    bpy.utils.unregister_class(ViewOperatorRayCast)


if __name__ == "__main__":
    register()
