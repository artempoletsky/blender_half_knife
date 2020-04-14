if "bpy" in locals():
    import importlib
    importlib.reload(ray_cast)
    importlib.reload(draw)
else:
    from . import ray_cast
    from . import draw

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

def vertex_project(point, edge):
    v1, v2 = [v.co for v in edge.verts]
    ap = point - v1
    ab = v2 - v1
    temp = ab * (np.dot(ap,ab) / np.dot(ab,ab))
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
    # try:
    h = (2 / a) * math.sqrt(abs(p * (p - a) * (p - d1) * (p - d2)))
    # except:
        # h = float("inf")
    d, index = (d1, 0) if d1 < d2 else (d2, 1)
    return min(h, d1, d2), d, index

def find_closest(point, face):
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

class ViewOperatorRayCast(bpy.types.Operator):
    """Run half knife"""
    bl_idname = "view3d.half_knife_operator"
    bl_label = "Half knife"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'VIEW_3D'
            and len(context.selected_objects) > 0
            and context.object.mode == 'EDIT')

    def get_drawing_edges(self, hit):
        return [{"verts": [{"co": v.co},
        {"co": hit}]
        } for v in self.initial_vertices]

    def snap_vert_preivew(self, vert):
        self.cut_mode = 'VERT'
        self.vert = vert
        return {
            'edge': self.get_drawing_edges(vert.co),
            'vert': [vert.co]
        }

    def snap_face_preivew(self, hit, face):
        self.cut_mode = 'FACE'
        return {
            'edge': self.get_drawing_edges(hit),
            'vert': [hit]
        }

    def snap_edge_preivew(self, hit, edge):
        self.cut_mode = 'EDGE'
        new_vert, split_ratio = vertex_project(hit, edge)
        self.split_ratio = split_ratio
        self.edge = edge
        # if no need to create new vertex
        if split_ratio in [0, 1]:
            new_vert = new_vert.co
        return {
            'edge': self.get_drawing_edges(new_vert),
            'vert': [new_vert]
        }



    def run_cut(self):
#        v = self.bmesh.verts.new()
#        v.co = self.new_vert
        if self.cut_mode == 'VERT':
            vert = self.vert
        elif self.cut_mode == 'EDGE':
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
            try:
                hit, face = ray_cast.BVH_ray_cast(context, event, self.tree, self.bmesh)
            except:
                hit = None

            if hit:
                vert, edge, edge_dist, vert_dist = find_closest(hit, face)
                snap_distance = 0.3
                if vert_dist < snap_distance:
                    batch = self.snap_vert_preivew(vert)
                elif edge_dist < snap_distance:
                    batch = self.snap_edge_preivew(hit, edge)
                else:
                    batch = self.snap_face_preivew(hit, face)

                self.draw.batch(batch)
            else:
                self.draw.clear()
            self.draw.redraw()
            return {'RUNNING_MODAL'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.draw.draw_end()
            return {'CANCELLED'}
        elif event.type in {'LEFTMOUSE'}:
            self.draw.draw_end()
            self.run_cut()
            return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.context = context
        self.object = context.edit_object

        self.bmesh = bmesh.from_edit_mesh(self.object.data)
        self.tree = BVHTree.FromBMesh(self.bmesh)
        self.initial_vertices = [v for v in self.bmesh.verts if v.select]
        self.draw = draw.Draw(context, context.object.matrix_world)
        context.window_manager.modal_handler_add(self)
        self.draw.draw_start()
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(ViewOperatorRayCast)


def unregister():
    bpy.utils.unregister_class(ViewOperatorRayCast)


if __name__ == "__main__":
    register()
