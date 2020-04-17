
from bpy_extras import view3d_utils
from mathutils import Vector

def BVH_ray_cast(context, event, tree, bmesh, object):
    ray_origin_obj, ray_direction_obj = get_view_object_space(context, event, object)
    hit, normal, face_index, distance = tree.ray_cast(ray_origin_obj, ray_direction_obj)
    print(hit)
    if not hit:
        return None, None
    return hit, bmesh.faces[face_index]

def get_view_object_space(context, event, object):
    region = context.region
    rv3d = context.region_data
    coord = event.mouse_region_x, event.mouse_region_y
    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    ray_target = ray_origin + view_vector

    matrix_inv = object.matrix_world.inverted()
    ray_origin_obj = matrix_inv @ ray_origin
    ray_target_obj = matrix_inv @ ray_target
    ray_direction_obj = ray_target_obj - ray_origin_obj

    return ray_origin_obj, ray_direction_obj
