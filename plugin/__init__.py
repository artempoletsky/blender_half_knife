if "bpy" in locals():
    import importlib
    importlib.reload(ray_cast)
    importlib.reload(draw)
    Draw = draw.Draw
    importlib.reload(geometry_math)
    GeometryMath = geometry_math.GeometryMath
else:
    from . import ray_cast
    from .draw import Draw
    from .geometry_math import GeometryMath

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

user_prefs = bpy.context.preferences.themes[0].view_3d
COLORS = {
    "cutting_edge": tuple(user_prefs.nurb_vline) + (1,),
    "vertex": tuple(user_prefs.handle_sel_vect) + (1,),
    "vertex_snap": tuple(user_prefs.handle_sel_auto) + (1,),
    "edge_snap": tuple(user_prefs.handle_sel_auto) + (1,),
}

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

def edge_to_dict(edge):
    return {"verts": [{"co": edge.verts[0].co}, {"co": edge.verts[1].co}]}

def find_shared_edge(v1, v2):
    e1 = list(v1.link_edges)
    e2 = list(v2.link_edges)
    for e in e1:
        if e in e2:
            return e
    return None

class HalfKnifeOperator(bpy.types.Operator):
    """Run half knife"""
    bl_idname = "mesh.half_knife_operator"
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
            'edge': [(self.get_drawing_edges(vert.co), COLORS['cutting_edge'])],
            'vert': [([vert.co], COLORS['vertex_snap'])]
        }

    def snap_face_preivew(self, hit, face):
        self.cut_mode = 'FACE'
        self.face = face
        return {
            # 'face': [(face, (1, 0, 0, .5))],
            'edge': [(self.get_drawing_edges(hit), COLORS['cutting_edge'])],
            'vert': [([hit], COLORS['vertex'])]
        }

    def snap_edge_preivew(self, hit, edge, projected, split_ratio):
        self.cut_mode = 'EDGE'
        self.split_ratio = split_ratio
        self.edge = edge
        # if no need to create new vertex
        if split_ratio in [0, 1]:
            projected = projected.co
        return {
            'edge': [(self.get_drawing_edges(projected), COLORS['cutting_edge']), ([edge_to_dict(edge)], COLORS['edge_snap'])],
            'vert': [([projected], COLORS['vertex'])]
        }



    def run_cut(self):
#        v = self.bmesh.verts.new()
#        v.co = self.new_vert
        if not self.hit:
            return

        bm = self.bmesh

        if self.cut_mode == 'VERT':
            vert = self.vert
        elif self.cut_mode == 'EDGE':
            edge, vert = bmesh.utils.edge_split(self.edge, self.edge.verts[0], self.split_ratio)
        else:
            vert = bmesh.ops.poke(self.bmesh, faces=[self.face])['verts'][0]
            vert.co = self.hit
            edges = list(vert.link_edges)

        pairs = []
        for v in self.initial_vertices:
            v.select_set(False)
#        self.initial_vertices.append(vert)
            normal = mathutils.geometry.normal([v.co, vert.co, self.camera_origin])
            bm.verts.ensure_lookup_table()
            # plane_co = (v.co + vert.co) / 2
            # hidden_verts = []
            # for v1 in bm.verts:
            #     if (mathutils.geometry.distance_point_to_plane(v1.co, v.co, self.camera_origin) < -0.1 and
            #         mathutils.geometry.distance_point_to_plane(v1.co, vert.co, self.camera_origin) < -0.1):
            #         hidden_verts.append(v1)
            #         v1.hide_set(True)

            visible_geom = [g for g in bm.faces[:]
                            + bm.verts[:] + bm.edges[:] if not g.hide]


             # bmesh.ops.bisect_plane(bm, geom, dist, plane_co, plane_no, use_snap_center, clear_outer, clear_inner)
            bisect_result = bmesh.ops.bisect_plane(bm, geom = visible_geom, dist = 0.0001, plane_co = v.co, plane_no = normal, use_snap_center = False, clear_outer = False, clear_inner = False)


            # print(result['geom'])
            bisect_edges = list(filter(lambda g: type(g) == bmesh.types.BMEdge, bisect_result['geom_cut']))

            v.select_set(True)
            vert.select_set(True)
            bpy.ops.mesh.shortest_path_select(edge_mode = 'SELECT')
            dissolved_edges = list(filter(lambda e: not e.select and (not vert in e.verts or self.cut_mode != 'FACE'), bisect_edges))
            shared = find_shared_edge(v, vert)
            # self.select_only([shared])
            if shared:
                dissolved_edges.remove(shared)
            # self.select_only(dissolved_edges)
            bmesh.ops.dissolve_edges(bm, edges = dissolved_edges, use_verts = True, use_face_split = False)

            # for v1 in hidden_verts:
                # v1.hide_set(False)

        if self.cut_mode == 'FACE':
            edge_len = len(vert.link_edges)
            new_edges = vert.link_edges
            dissolved_edges = []
            for e in new_edges:
                if not (e.other_vert(vert) in self.initial_vertices) and edge_len > 2:
                    dissolved_edges.append(e)
                    edge_len -= 1

            bmesh.ops.dissolve_edges(bm, edges = dissolved_edges, use_verts = False, use_face_split = False)




        # bmesh.update_edit_mesh(self.object.data, True)
        # for v in self.initial_vertices:


        bmesh.update_edit_mesh(self.object.data, True)
        bpy.ops.mesh.select_all(action = 'DESELECT')
        vert.select_set(True)
        bm.select_history.add(vert)

    def select_only(self, bmesh_geom):
        bpy.ops.mesh.select_all(action = 'DESELECT')
        for e in bmesh_geom:
            e.select_set(True)

    def calc_hit(self, context, event):
        batch = None
        try:
            hit, face = ray_cast.BVH_ray_cast(context, event, self.tree, self.bmesh)
        except:
            hit = None
        self.hit = hit
        if hit:
            vert, edge, vertex_pixel_distance, edge_pixel_distance, split_ratio, projected = self.util.find_closest(hit, face)

            snap_distance = 15
            if vertex_pixel_distance < snap_distance:
                batch = self.snap_vert_preivew(vert)
            elif edge_pixel_distance < snap_distance:
                batch = self.snap_edge_preivew(hit, edge, projected, split_ratio)
            else:
                batch = self.snap_face_preivew(hit, face)

        return batch

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            # allow navigation
            return {'PASS_THROUGH'}
        elif event.type == 'MOUSEMOVE':

            batch = self.calc_hit(context, event)
            if batch:
                self.draw.batch(batch)
            else:
                self.draw.clear()
            self.draw.redraw()
            return {'RUNNING_MODAL'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.draw.draw_end()
            return {'CANCELLED'}
        elif event.type in {'LEFTMOUSE'}:
            self.calc_hit(context, event)
            self.draw.draw_end()
            self.camera_origin = self.util.get_camera_origin(event)
            self.run_cut()
            return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.context = context
        self.object = context.edit_object

        self.bmesh = bmesh.from_edit_mesh(self.object.data)
        self.tree = BVHTree.FromBMesh(self.bmesh)
        self.initial_vertices = [v for v in self.bmesh.verts if v.select]
        self.draw = Draw(context, context.object.matrix_world)
        context.window_manager.modal_handler_add(self)
        self.draw.draw_start()

        self.util = GeometryMath(context)
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(HalfKnifeOperator)


def unregister():
    bpy.utils.unregister_class(HalfKnifeOperator)


if __name__ == "__main__":
    register()
