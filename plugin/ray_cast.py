
from bpy_extras import view3d_utils
from mathutils import Vector

def BVH_ray_cast(context, event, tree, bmesh):
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

def get_view_vector(context, event):
    region = context.region
    rv3d = context.region_data
    coord = event.mouse_region_x, event.mouse_region_y
    return view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)

def get_view_origin(context, event):
    region = context.region
    rv3d = context.region_data
    coord = event.mouse_region_x, event.mouse_region_y
    return view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
