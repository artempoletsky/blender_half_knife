bl_info = {
    "name": "Half knife",
    "author": "Artem Poletsky",
    "version": (1, 0, 1),
    "blender": (2, 82, 0),
    # "location": "",
    "description": "Optimized for fast workflow knife tool",
    "warning": "",
    "wiki_url": "",
    "category": "Mesh",
}

if "bpy" in locals():
    import importlib
    importlib.reload(draw)
    Draw = draw.Draw
    importlib.reload(geometry_math)
    GeometryMath = geometry_math.GeometryMath
    importlib.reload(preferences)

else:
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
            return None
        vert = self.get_new_vert()
        if self.snap_mode == 'FACE':
            dissolved_edges = vert.link_edges[slice(len(vert.link_edges) - 2)]
            bmesh.ops.dissolve_edges(self.bmesh, edges = dissolved_edges, use_verts = False, use_face_split = False)
        bmesh.update_edit_mesh(self.object.data, True)
        vert.select_set(True)
        self.bmesh.select_history.add(vert)
        return vert

    def get_drawing_edges(self, hit):
        return [{"verts": [{"co": v.co},
        {"co": hit}]
        } for v in self.initial_vertices]

    def snap_vert_preivew(self, vert):
        self.snap_mode = 'VERT'
        self.vert = vert
        self.snapped_hit = vert.co
        return {
            'edge': [(self.get_drawing_edges(vert.co), self.prefs.cutting_edge)],
            'vert': [([vert.co], self.prefs.vertex_snap)]
        }

    def snap_face_preivew(self, hit, face):
        self.snap_mode = 'FACE'
        self.face = face
        self.snapped_hit = hit
        return {
            # 'face': [(face, (1, 0, 0, .5))],
            'edge': [(self.get_drawing_edges(hit), self.prefs.cutting_edge)],
            'vert': [([hit], self.prefs.vertex)]
        }

    def snap_edge_preivew(self, hit, edge, projected, split_ratio):
        self.snap_mode = 'EDGE'
        self.split_ratio = split_ratio
        self.edge = edge
        # if no need to create new vertex
        if split_ratio in [0, 1]:
            projected = projected.co
        self.snapped_hit = projected
        return {
            'edge': [(self.get_drawing_edges(projected), self.prefs.cutting_edge), ([edge_to_dict(edge)], self.prefs.edge_snap)],
            'vert': [([projected], self.prefs.vertex)]
        }

    def create_cut_obj(self, initial_vertices, new_vertex_co):
        # Make a new BMesh
        bm = bmesh.new()


        px = self.util.location_3d_to_region_2d_object_space(new_vertex_co)
        view_origin, view_vector = self.util.get_view_world_space(px.x, px.y)
        v0 = bm.verts.new(view_origin + view_vector)
        for v in initial_vertices:
            # v.select_set(False)
            px = self.util.location_3d_to_region_2d_object_space(v.co)
            view_origin, view_vector = self.util.get_view_world_space(px.x, px.y)
            v1 = bm.verts.new(view_origin + view_vector)
            edge = bm.edges.new((v0, v1))

        me = bpy.data.meshes.new("Mesh")
        bm.to_mesh(me)
        bm.free()


        # Add the mesh to the scene
        obj = bpy.data.objects.new("Object", me)
        bpy.context.collection.objects.link(obj)

        # bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        self.cut_obj = obj

    def delete_cut_obj(self):
        bpy.ops.object.editmode_toggle()
        bpy.ops.object.delete({"selected_objects": [self.cut_obj]})
        bpy.ops.object.editmode_toggle()

    def run_cut(self, context, event):
#        v = self.bmesh.verts.new()
#        v.co = self.new_vert
        if not self.hit:
            return
        bm = self.bmesh
        self.create_cut_obj(self.initial_vertices, self.snapped_hit)
        bpy.ops.mesh.knife_project()
        bpy.ops.mesh.select_mode(use_extend = False, use_expand = False, type = 'VERT')
        self.delete_cut_obj()
        # bpy.ops.mesh.select_all(action = 'DESELECT')
        select_location = self.util.location_3d_to_region_2d_object_space(self.snapped_hit)
        bpy.ops.view3d.select(location = (int(select_location.x), int(select_location.y)))


    def select_only(self, bmesh_geom):
        bpy.ops.mesh.select_all(action = 'DESELECT')
        for e in bmesh_geom:
            e.select_set(True)

    def calc_hit(self, context, event):
        batch = None
        # try:
        hit, face = self.util.ray_cast_BVH(self.tree, self.bmesh, event.mouse_region_x, event.mouse_region_y)
        # except:
            # hit = None
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

        id = 'half_knife'
        self.prefs = addons_prefs[id].preferences if id in addons_prefs else preferences.HalfKnifePreferencesDefaults()

        self.bmesh = bmesh.from_edit_mesh(self.object.data)

        self.initial_vertices = [v for v in self.bmesh.verts if v.select]
        vert_len = len(self.initial_vertices)
        if vert_len > 10:
            self.report({'ERROR'}, 'Too many vertices selected! Canceling.')
            return {'CANCELLED'}

        self.tree = BVHTree.FromBMesh(self.bmesh)
        self.util = GeometryMath(context, self.object)

        if vert_len == 0:
            vert = self.addVert(context, event)
            if not vert or self.auto_cut:
                return {'FINISHED'}
            self.initial_vertices = [vert]

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

    preferences.register_keymaps()


def unregister():
    preferences.unregister_keymaps()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
