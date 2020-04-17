bl_info = {
    "name": "Half knife",
    "author": "Artem Poletsky",
    "version": (1, 0, 0),
    "blender": (2, 82, 0),
    # "location": "",
    "description": "Optimized for fast workflow knife tool",
    "warning": "",
    "wiki_url": "",
    "category": "Mesh",
}

if "bpy" in locals():
    import importlib
    importlib.reload(ray_cast)
    importlib.reload(draw)
    Draw = draw.Draw
    importlib.reload(geometry_math)
    GeometryMath = geometry_math.GeometryMath
    importlib.reload(preferences)

else:
    from . import ray_cast
    from .draw import Draw
    from .geometry_math import GeometryMath
    from . import preferences

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

def edge_to_dict(edge):
    return {"verts": [{"co": edge.verts[0].co}, {"co": edge.verts[1].co}]}

def find_shared_edge(v1, v2):
    e1 = list(v1.link_edges)
    e2 = list(v2.link_edges)
    for e in e1:
        if e in e2:
            return e
    return None

def find_shared_face(v1, v2):
    e1 = list(v1.link_faces)
    e2 = list(v2.link_faces)
    for e in e1:
        if e in e2:
            return e
    return None

def is_backfacing(face, view_vector):
    normal = face.normal
    return np.dot(view_vector, normal) > 0


class HalfKnifeOperator(bpy.types.Operator):
    """Run half knife"""
    bl_idname = "mesh.half_knife_operator"
    bl_label = "Half knife"
    bl_options = {'REGISTER', 'UNDO'}

    auto_cut: bpy.props.BoolProperty(name="Cut without preview", default=False)

    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'VIEW_3D'
            and len(context.selected_objects) > 0
            and context.object.mode == 'EDIT')

    def get_new_vert(self):
        if self.snap_mode == 'VERT':
            return self.vert
        elif self.snap_mode == 'EDGE':
            edge, vert = bmesh.utils.edge_split(self.edge, self.edge.verts[0], self.split_ratio)
            return vert
        else:
            vert = bmesh.ops.poke(self.bmesh, faces=[self.face])['verts'][0]
            vert.co = self.hit
            return vert

    def addVert(self, context, event):
        if not self.calc_hit(context, event):
            return
        vert = self.get_new_vert()
        if self.snap_mode == 'FACE':
            dissolved_edges = vert.link_edges[slice(2)]
            bmesh.ops.dissolve_edges(self.bmesh, edges = dissolved_edges, use_verts = False, use_face_split = False)
        bmesh.update_edit_mesh(self.object.data, True)
        vert.select_set(True)
        self.bmesh.select_history.add(vert)

    def get_drawing_edges(self, hit):
        return [{"verts": [{"co": v.co},
        {"co": hit}]
        } for v in self.initial_vertices]

    def snap_vert_preivew(self, vert):
        self.snap_mode = 'VERT'
        self.vert = vert
        return {
            'edge': [(self.get_drawing_edges(vert.co), COLORS['cutting_edge'])],
            'vert': [([vert.co], COLORS['vertex_snap'])]
        }

    def snap_face_preivew(self, hit, face):
        self.snap_mode = 'FACE'
        self.face = face
        return {
            # 'face': [(face, (1, 0, 0, .5))],
            'edge': [(self.get_drawing_edges(hit), COLORS['cutting_edge'])],
            'vert': [([hit], COLORS['vertex'])]
        }

    def snap_edge_preivew(self, hit, edge, projected, split_ratio):
        self.snap_mode = 'EDGE'
        self.split_ratio = split_ratio
        self.edge = edge
        # if no need to create new vertex
        if split_ratio in [0, 1]:
            projected = projected.co
        return {
            'edge': [(self.get_drawing_edges(projected), COLORS['cutting_edge']), ([edge_to_dict(edge)], COLORS['edge_snap'])],
            'vert': [([projected], COLORS['vertex'])]
        }



    def run_cut(self, context, event):
#        v = self.bmesh.verts.new()
#        v.co = self.new_vert
        if not self.hit:
            return
        for v in self.initial_vertices:
            v.select_set(False)

        bm = self.bmesh

        if self.snap_mode == 'VERT':
            vert = self.vert
        elif self.snap_mode == 'EDGE':
            edge, vert = bmesh.utils.edge_split(self.edge, self.edge.verts[0], self.split_ratio)

        else:
            vert = bmesh.ops.poke(bm, faces=[self.face])['verts'][0]
            vert.co = self.hit
            edges = list(vert.link_edges)

        view_origin, view_vector = ray_cast.get_view_object_space(context, event, self.object)

        pairs = []
        all_dissolved_edges = []
        for v in self.initial_vertices:
            shared_face = find_shared_face(v, vert)
            if shared_face:
                bmesh.ops.connect_vert_pair(self.bmesh, verts = (v, vert))
                continue

            normal = mathutils.geometry.normal([v.co, vert.co, view_origin])
            bm.verts.ensure_lookup_table()

            hidden_faces = []
            for f in bm.faces:
                if is_backfacing(f, view_vector):
                    hidden_faces.append(f)
                    f.hide_set(True)

            visible_geom = [g for g in bm.faces[:]
                            + bm.verts[:] + bm.edges[:] if not g.hide]

            bisect_result = bmesh.ops.bisect_plane(bm, geom = visible_geom, dist = 0.0001, plane_co = v.co, plane_no = normal, use_snap_center = False, clear_outer = False, clear_inner = False)

            bisect_edges = list(filter(lambda g: type(g) == bmesh.types.BMEdge, bisect_result['geom_cut']))

            for e in bisect_edges:
                e.select_set(True)
            bpy.ops.mesh.hide(unselected = True)
            bpy.ops.mesh.select_all(action = 'DESELECT')

            v.select_set(True)
            vert.select_set(True)

            bpy.ops.mesh.shortest_path_select(edge_mode = 'SELECT')
            dissolved_edges = list(filter(lambda e: not e.select and not e in visible_geom, bisect_edges))

            bpy.ops.mesh.reveal()

            all_dissolved_edges += dissolved_edges

        bmesh.ops.dissolve_edges(bm, edges = all_dissolved_edges, use_verts = True, use_face_split = False)
        if self.snap_mode == 'FACE':
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
        # self.select_only(all_dissolved_edges)
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
            hit, face = ray_cast.BVH_ray_cast(context, event, self.tree, self.bmesh, self.object)
        except:
            hit = None
        self.hit = hit
        if hit:
            vert, edge, vertex_pixel_distance, edge_pixel_distance, split_ratio, projected = self.util.find_closest(hit, face)

            if vertex_pixel_distance < self.prefs.snap_vertex_distance:
                batch = self.snap_vert_preivew(vert)
            elif edge_pixel_distance < self.prefs.snap_edge_distance:
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
            self.run_cut(context, event)
            return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.context = context
        self.object = context.edit_object
        addons_prefs = context.preferences.addons
        # print(addons_prefs)
        id = 'half_knife'
        self.prefs = addons_prefs[id].preferences if id in addons_prefs else preferences.HalfKnifePreferencesDefaults()

        self.bmesh = bmesh.from_edit_mesh(self.object.data)

        self.initial_vertices = [v for v in self.bmesh.verts if v.select]
        vert_len = len(self.initial_vertices)
        if vert_len > 10:
            self.report({'ERROR'}, 'Too many vertices selected! Canceling.')
            return {'CANCELLED'}

        self.tree = BVHTree.FromBMesh(self.bmesh)
        self.util = GeometryMath(context)

        if vert_len == 0:
            self.addVert(context, event)
            return {'FINISHED'}

        if self.auto_cut:
            if self.calc_hit(context, event):
                self.run_cut(context, event)
            return {'FINISHED'}


        self.draw = Draw(context, context.object.matrix_world)
        context.window_manager.modal_handler_add(self)
        self.draw.draw_start()

        return {'RUNNING_MODAL'}

classes = (
    preferences.HalfKnifePreferences,
    HalfKnifeOperator
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # register_keymaps()


def unregister():
    # unregister_keymaps()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
