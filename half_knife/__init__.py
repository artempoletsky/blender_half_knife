bl_info = {
    "name": "Half knife",
    "author": "Artem Poletsky",
    "version": (1, 1, 0),
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

def calc_edge_center(edge):
    return (edge.verts[0].co + edge.verts[1].co) / 2

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
    snap_to_center: bpy.props.BoolProperty(name="Snap to center", default=False)
    cut_through: bpy.props.BoolProperty(name="Cut through", default=False)
    turn_off_snapping: bpy.props.BoolProperty(name="Turn off snapping", default=False)

    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'VIEW_3D'
            and len(context.selected_objects) > 0
            and context.object.mode == 'EDIT')

    def get_new_vert(self):
        if self.snap_mode == 'VERT':
            return self.vert, self.vert.co
        elif self.snap_mode == 'EDGE':
            center = calc_edge_center(self.edge)
            split_ratio = self.util.get_split_ratio(self.snapped_hit, self.edge)
            edge, vert = bmesh.utils.edge_split(self.edge, self.edge.verts[0], split_ratio)
            return vert, center
        else:
            center = self.face.calc_center_median()
            vert = bmesh.ops.poke(self.bmesh, faces=[self.face])['verts'][0]
            vert.co = self.snapped_hit
            return vert, center

    def addVert(self, context, event):
        self.calc_hit(context, event)
        if self.snap_mode == 'VOID':
            co = self.util.get_viewport_point_object_space(event.mouse_region_x, event.mouse_region_y)
            vert = self.bmesh.verts.new()
            vert.co = co
            self.virtual_start = vert
            return vert, co
        vert, center = self.get_new_vert()
        if self.snap_mode == 'FACE':
            dissolved_edges = vert.link_edges[slice(len(vert.link_edges) - 2)]
            bmesh.ops.dissolve_edges(self.bmesh, edges = dissolved_edges, use_verts = False, use_face_split = False)

        if self.snap_mode == 'FACE':
            self.face = vert.link_faces[0]
        vert.select_set(True)
        self.bmesh.select_history.add(vert)
        self.update_geom()
        return vert, center

    def update_geom(self):
        bmesh.update_edit_mesh(self.object.data, True)
        self.tree = BVHTree.FromBMesh(self.bmesh)
        self.bmesh.faces.ensure_lookup_table()

    def get_drawing_edges(self, hit):
        return [{"verts": [{"co": v.co},
        {"co": hit}]
        } for v in self.initial_vertices]

    def snap_void_preivew(self, hit):
        self.snap_mode = 'VOID'
        self.snapped_hit = hit
        return {
            'edge': [(self.get_drawing_edges(hit), self.prefs.cutting_edge)],
            'vert': [([hit], self.prefs.vertex)]
        }

    def snap_vert_preivew(self, vert):
        self.snap_mode = 'VERT'
        self.snapped_hit = vert.co
        return {
            'edge': [(self.get_drawing_edges(vert.co), self.prefs.cutting_edge)],
            'vert': [([vert.co], self.prefs.vertex_snap)]
        }

    def update_snap_axises(self):
        vert = self.initial_vertices[0]
        v_edges = vert.link_edges
        result = []
        def createLine(vert_co, vector, face):
            v = vector * 20
            return self.util.project_point_on_view(vert_co), self.util.project_point_on_view(vert_co + vector), face, vert_co - v, vert_co + v
        for face in vert.link_faces:
            edges = []
            for e in v_edges:
                if e in face.edges:
                    edges.append(e)
            # print(edges)
            v1 = edges[0].other_vert(vert).co - vert.co
            v1.normalize()
            v2 = edges[1].other_vert(vert).co - vert.co
            v2.normalize()
            v = (v1 + v2) / 2
            # print(v.length)
            if v.length < 0.001:
                v = mathutils.Vector(np.cross(face.normal, v2))
                v.normalize()

            n45 = (v1 + v) / 2
            p45 = (v2 + v) / 2
            result.append(createLine(vert.co, n45, face))
            result.append(createLine(vert.co, v, face))
            result.append(createLine(vert.co, p45, face))
        if not self.last_hited_face:
            self.last_hited_face = vert.link_faces[0]
        self.snap_axises = result

    def get_drawing_axis(self):
        # vert = self.initial_vertices[0].co
        # vert = self.util.project_point_on_view(vert)
        # face = self.initial_face
        # edge = self.initial_edge
        # v1, v2 = [v.co for v in edge.verts]
        a = self.active_axis
        axises = []
        # for v, face in vertices:
        axises.append({
            "verts": [{"co": a[0]}, {"co": a[1]}]
        })
        return (axises, self.prefs.angle_constraint_axis)

    def snap_to_axis(self, hit):
        res_d = float("inf")
        res_p = None
        # start = self.util.project_point_on_view(self.initial_vertices[0].co)
        axises = self.snap_axises
        res_axis = None
        for start, end, face, draw_start, draw_end in axises:
            if face != self.last_hited_face:
                continue
            p = self.util.vertex_project(hit, start, end)
            d = (hit - p).length
            if d < res_d:
                res_d = d
                res_p = p
                res_axis = (draw_start, draw_end)
        return res_p, res_axis

    def snap_face_preivew(self, hit, face):
        self.snap_mode = 'FACE'
        if self._snap_to_center and not self._turn_off_snapping:
            self.snapped_hit = face.calc_center_median()
        else:
            self.snapped_hit = hit
        return {
            # 'face': [(face, (1, 0, 0, .5))],
            'edge': [(self.get_drawing_edges(self.snapped_hit), self.prefs.cutting_edge)],
            'vert': [([self.snapped_hit], self.prefs.vertex)]
        }

    def snap_edge_preivew(self, hit, edge, projected):
        self.snap_mode = 'EDGE'
        if self._snap_to_center and not self._turn_off_snapping:
            projected = calc_edge_center(edge)
        self.snapped_hit = projected
        return {
            'edge': [(self.get_drawing_edges(projected), self.prefs.cutting_edge), ([edge_to_dict(edge)], self.prefs.edge_snap)],
            'vert': [([projected], self.prefs.vertex)]
        }

    def select_path(self, exclude_ends):
        for start, end in self.selection_path:
            se = end - start
            l = int(se.length / 4)
            range_start = 0
            range_end = l + 1
            if exclude_ends:
                range_start = 1
                range_end = l
            for i in range(range_start, range_end):
                p = start + (i / l) * se
                bpy.ops.view3d.select_circle(x = int(p.x), y = int(p.y), radius = 2, wait_for_input = False, mode = 'ADD')

    def create_cut_obj(self, initial_vertices, new_vertex_co):
        # Make a new BMesh
        bm = bmesh.new()

        self.selection_path = []
        end_px = self.util.location_3d_to_region_2d_object_space(new_vertex_co)
        view_origin, view_vector = self.util.get_view_world_space(end_px.x, end_px.y)
        v0 = bm.verts.new(view_origin + view_vector)
        # v0.select_set(True)
        for v in initial_vertices:
            # v.select_set(False)
            px = self.util.location_3d_to_region_2d_object_space(v.co)
            view_origin, view_vector = self.util.get_view_world_space(px.x, px.y)
            v1 = bm.verts.new(view_origin + view_vector)
            # v1.select_set(True)
            edge = bm.edges.new((v0, v1))
            self.selection_path.append((px, end_px))

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

    def delete_vitrual_vertex(self):
        if self.virtual_start:
            bmesh.ops.delete(self.bmesh, geom = [self.virtual_start], context = 'VERTS')
            self.update_geom()

    def run_cut(self):
#        v = self.bmesh.verts.new()
#        v.co = self.new_vert
        # if not self.hit:
            # return

        self.create_cut_obj(self.initial_vertices, self.snapped_hit)
        self.delete_vitrual_vertex()
        bpy.ops.mesh.knife_project(cut_through = self._cut_through)
        bpy.ops.mesh.select_mode(use_extend = False, use_expand = False, type = 'VERT')
        self.delete_cut_obj()
        # # bpy.ops.mesh.select_all(action = 'DESELECT')
        if self._snap_to_center:
            self.select_path(True)
            self.bmesh.free()
            bm = self.bmesh = bmesh.from_edit_mesh(self.object.data)
            for v in bm.verts:
                if v.select:
                    edges = []
                    for e in v.link_edges:
                        v0 = e.other_vert(v)
                        if not v0.select:
                            edges.append(e)
                    v1 = edges[0].other_vert(v)
                    v2 = edges[1].other_vert(v)
                    v.co = (v1.co + v2.co) / 2

        bmesh.update_edit_mesh(self.object.data, True)
        select_location = self.util.location_3d_to_region_2d_object_space(self.snapped_hit)
        bpy.ops.view3d.select(location = (int(select_location.x), int(select_location.y)))


    def select_only(self, bmesh_geom):
        bpy.ops.mesh.select_all(action = 'DESELECT')
        for e in bmesh_geom:
            e.select_set(True)

    def calc_hit(self, context, event):
        batch = None
        hit = None
        # try:
        if not self._angle_constraint:
            hit, face = self.util.ray_cast_BVH(self.tree, self.bmesh, event.mouse_region_x, event.mouse_region_y)
            # except:
                # hit = None
            self.hit = hit
        if hit:
            vert, edge, vertex_pixel_distance, edge_pixel_distance, projected = self.util.find_closest(hit, face)
            self.vert = vert
            self.edge = edge
            self.face = face
            if vertex_pixel_distance < self.prefs.snap_vertex_distance and not self._turn_off_snapping:
                batch = self.snap_vert_preivew(vert)
            elif edge_pixel_distance < self.prefs.snap_edge_distance and not self._turn_off_snapping:
                batch = self.snap_edge_preivew(hit, edge, projected)
            else:
                batch = self.snap_face_preivew(hit, face)
        else:
            hit = self.util.get_viewport_point_object_space(event.mouse_region_x, event.mouse_region_y)

            if self._angle_constraint:
                geometry_hit, face = self.util.ray_cast_BVH(self.tree, self.bmesh, event.mouse_region_x, event.mouse_region_y)
                vert = self.initial_vertices[0]
                if geometry_hit and face in vert.link_faces:
                    self.last_hited_face = face
                hit, active_axis = self.snap_to_axis(hit)
                self.active_axis = active_axis
            batch = self.snap_void_preivew(hit)
        return batch

    def draw_helper_text(self):
        shift = "On" if self._turn_off_snapping else "Off"
        snap_to_center = "On" if self._snap_to_center else "Off"
        angle_constraint = "On" if self._angle_constraint else "Off"
        angle_constraint_text = " C: angle_constraint (" + angle_constraint + ");"
        snap_to_center_text = " Ctrl: snap to center (" + snap_to_center + ");"
        if self.is_multiple_verts or self.virtual_start:
            angle_constraint_text = ""
            snap_to_center_text = ""

        cut_through = "On" if self._cut_through else "Off"
        self.context.area.header_text_set("Shift: turn off snapping(" + shift + ");" + snap_to_center_text + angle_constraint_text + " Z: cut_through: (" + cut_through + ")")

    def clear_helper_text(self):
        self.context.area.header_text_set(None)

    def update_initial_vertex_position(self):
        vert = self.initial_vertices[0]
        vert.co = self.inital_centered_hit if self._snap_to_center else self.initial_hit
        self.update_geom()
        # bmesh.update_edit_mesh(self.object.data, True)
        self.update_snap_axises()

    def redraw(self, context, event):
        batch = self.calc_hit(context, event)
        if batch:
            if self._angle_constraint:
                batch['edge'].insert(0, self.get_drawing_axis())
                batch['face'] = [(self.last_hited_face, self.prefs.angle_constraint_active_face)]
            self.draw.batch(batch)
        else:
            self.draw.clear()
        self.draw.redraw()

    def modal(self, context, event):
        # self._shift = event.shift
        # self._ctrl =  event.ctrl
        is_multiple_verts = self.is_multiple_verts
        is_virtual_start = bool(self.virtual_start)
        # self._turn_off_snapping = event.shift
        # self._snap_to_center = event.ctrl and not is_multiple_verts

        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            # allow navigation
            if not self._angle_constraint and not is_virtual_start:
                return {'PASS_THROUGH'}
        elif event.type == 'Z' and event.value == 'PRESS':
            self._cut_through = not self._cut_through
        elif event.type == 'C' and event.value == 'PRESS':
            if  is_multiple_verts or is_virtual_start:
                return {'RUNNING_MODAL'}
            self._angle_constraint = not self._angle_constraint
            self.update_snap_axises()
        elif event.type in {'LEFT_CTRL', 'RIGHT_CTRL'} and event.value == 'PRESS':
            if  is_multiple_verts or is_virtual_start:
                return {'RUNNING_MODAL'}
            self._snap_to_center = not self._snap_to_center
            # self._angle_constraint = False
            if self.is_cut_from_new_vertex:
                self.update_initial_vertex_position()
                self.redraw(context, event)
        elif event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT'} and event.value == 'PRESS':
            self._turn_off_snapping = not self._turn_off_snapping
        elif event.type == 'MOUSEMOVE':
            self.redraw(context, event)

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.draw.draw_end()
            self.clear_helper_text()
            self.delete_vitrual_vertex()
            if not self.prefs.disable_knife_icon:
                context.window.cursor_modal_restore()
            return {'CANCELLED'}
        elif event.type in {'LEFTMOUSE'}:
            self.calc_hit(context, event)
            self.draw.draw_end()
            self.run_cut()
            self.clear_helper_text()
            if not self.prefs.disable_knife_icon:
                context.window.cursor_modal_restore()
            return {'FINISHED'}

        self.draw_helper_text()
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self._cut_through = self.cut_through
        self._angle_constraint = False
        self._snap_to_center = self.snap_to_center
        self._turn_off_snapping = self.turn_off_snapping
        self.context = context
        self.object = context.edit_object
        addons_prefs = context.preferences.addons

        id = 'half_knife'
        self.prefs = addons_prefs[id].preferences if id in addons_prefs else preferences.HalfKnifePreferencesDefaults()

        self.bmesh = bmesh.from_edit_mesh(self.object.data)

        self.initial_vertices = [v for v in self.bmesh.verts if v.select]
        vert_len = len(self.initial_vertices)
        self.is_multiple_verts = vert_len > 1
        if vert_len > 10:
            self.report({'ERROR'}, 'Too many vertices selected! Canceling.')
            return {'CANCELLED'}

        self.tree = BVHTree.FromBMesh(self.bmesh)
        self.util = GeometryMath(context, self.object)

        self.is_cut_from_new_vertex = False
        self.virtual_start = None
        auto_cut = self.auto_cut
        if vert_len == 0:
            vert, center = self.addVert(context, event)

            if not vert:
                return {'FINISHED'}

            if auto_cut:
                # if self.virtual_start:
                    # return {'FINISHED'}
                if self._snap_to_center:
                    vert.co = center
                # return {'FINISHED'}
            #else snapped vertex is selected, not the new
            if self.snap_mode != 'VERT' and not self.virtual_start:
                self.is_cut_from_new_vertex = True
                self.inital_centered_hit = mathutils.Vector(center)
            if not self.virtual_start:
                self.initial_face = self.face
            # if self.snap_mode == 'EDGE':
            #
            #     self.initial_edge = self.edge

            self.initial_vertices = [vert]
            vert_len = 1


        if auto_cut and not self.virtual_start:
            self.calc_hit(context, event)
            if self.snap_mode != 'VOID':
                self.run_cut()
                return {'FINISHED'}


        if vert_len == 1:
            vert = self.initial_vertices[0]
            self.initial_hit = mathutils.Vector(vert.co)
            if not self.is_cut_from_new_vertex:
                self.inital_centered_hit = self.initial_hit


        self.last_hited_face = None

        if not self.prefs.disable_knife_icon:
            context.window.cursor_modal_set("KNIFE")
        self.draw = Draw(context, context.object.matrix_world)
        context.window_manager.modal_handler_add(self)
        self.draw.draw_start()

        return {'RUNNING_MODAL'}

classes = (
    preferences.HalfKnifePreferences,
    HalfKnifeOperator
)

def menu_func(self, context):
    layout = self.layout
    layout.separator()
    # print('menu')
    layout.operator_context = "INVOKE_REGION_WIN"
    layout.operator(HalfKnifeOperator.bl_idname, text = HalfKnifeOperator.bl_label)
# for i in dir(bpy.types):
    # if "snap" in i: print(i)
def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    preferences.register_keymaps()
    bpy.types.VIEW3D_MT_edit_mesh.append(menu_func)

def unregister():
    preferences.unregister_keymaps()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.types.VIEW3D_MT_edit_mesh.remove(menu_func)

if __name__ == "__main__":
    register()
