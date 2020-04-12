import bpy
from bpy_extras import view3d_utils
from mathutils.bvhtree import BVHTree
import bmesh
import gpu
#import numpy as np
#from random import random
from gpu_extras.batch import batch_for_shader
#import time
import mathutils

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

    def visible_objects_and_duplis():
        """Loop over (object, matrix) pairs (mesh only)"""

        depsgraph = context.evaluated_depsgraph_get()
        for dup in depsgraph.object_instances:
            if dup.is_instance:  # Real dupli instance
                obj = dup.instance_object
                yield (obj, dup.matrix_world.copy())
            else:  # Usual object
                obj = dup.object
                yield (obj, obj.matrix_world.copy())

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
        return None

    return bmesh.faces[face_index]

    # cast rays and find the closest object
    # best_length_squared = -1.0
    # best_obj = None

    # for obj, matrix in visible_objects_and_duplis():
    #     if obj.type == 'MESH':
    #         hit, normal, face_index = obj_ray_cast(obj, matrix)
    #         if hit is not None:
    #             hit_world = matrix @ hit
    #             scene.cursor.location = hit_world
    #             length_squared = (hit_world - ray_origin).length_squared
    #             if best_obj is None or length_squared < best_length_squared:
    #                 best_length_squared = length_squared
    #                 best_obj = obj

    # # now we have the object under the mouse cursor,
    # # we could do lots of stuff but for the example just select.
    # if best_obj is not None:
    #     # for selection etc. we need the original object,
    #     # evaluated objects are not in viewlayer
    #     best_original = best_obj.original
    #     best_original.select_set(True)
    #     context.view_layer.objects.active = best_original


class ViewOperatorRayCast(bpy.types.Operator):
    """Modal object selection with a ray cast"""
    bl_idname = "view3d.modal_operator_raycast"
    bl_label = "RayCast View Operator"

    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')


    def batch_polygon(self, face):


        vertices = [v.co for v in face.verts] if face else []
        indices = mathutils.geometry.tessellate_polygon((vertices,))
        return batch_for_shader(
            self.shader, 'TRIS',
            {"pos": vertices},
            indices=indices,
        )

    def _draw(self):
#        if not self.batch:
#            return

        self.shader.bind()
        self.shader.uniform_float("color", (1, 0, 0, 1))
        self.batch.draw(self.shader)

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            # allow navigation
            return {'PASS_THROUGH'}
        elif event.type == 'MOUSEMOVE':
            self.batch = self.batch_polygon(main(context, event, self.tree, self.bmesh))
            self.redraw()
            return {'RUNNING_MODAL'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.draw_end()
            return {'CANCELLED'}

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
            self.tree = BVHTree.FromObject(context.object, context.evaluated_depsgraph_get())
            self.bmesh = bmesh.from_edit_mesh(context.object.data)
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
