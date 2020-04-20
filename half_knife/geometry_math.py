from bpy_extras import view3d_utils
import numpy as np

class GeometryMath:

    def __init__(self, context, object):
        self.context = context
        self.region = context.region
        self.rv3d = context.region_data
        self.matrix = object.matrix_world
        self.matrix_inv = self.matrix.inverted()

    def ray_cast_BVH(self, tree, bm, x, y):
        ray_origin_obj, ray_direction_obj = self.get_view_object_space(x, y)
        hit, normal, face_index, distance = tree.ray_cast(ray_origin_obj, ray_direction_obj)
        if not hit:
            return None, None
        return hit, bm.faces[face_index]

    def get_view_object_space(self, x, y):
        view_origin, view_vector = self.get_view_world_space(x, y)
        ray_target = view_origin + view_vector

        matrix_inv = self.matrix_inv
        ray_origin_obj = matrix_inv @ view_origin
        ray_target_obj = matrix_inv @ ray_target
        ray_direction_obj = ray_target_obj - ray_origin_obj

        return ray_origin_obj, ray_direction_obj

    def get_view_world_space(self, x, y):
        coord = x, y
        view_vector = view3d_utils.region_2d_to_vector_3d(self.region, self.rv3d, coord)
        view_origin = view3d_utils.region_2d_to_origin_3d(self.region, self.rv3d, coord)
        return view_origin, view_vector



    def location_3d_to_region_2d_object_space(self, v):
        return view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, self.matrix @ v)

    def distance_2d(self, v1, v2):
         pxv1 = self.location_3d_to_region_2d_object_space(v1)
         pxv2 = self.location_3d_to_region_2d_object_space(v2)
         return (pxv1 - pxv2).length

    def vertex_project(self, point, edge):
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
            projected, split_ratio = (edge.verts[0].co, 0) if d1 < d2 else (edge.verts[1].co, 1)

        return projected, split_ratio

    def distance_to_edge(self, point, edge):
        v1, v2 = [v.co for v in edge.verts]
        d1 = (point - v1).length
        d2 = (point - v2).length
        projected, split_ratio = self.vertex_project(point, edge)
        h = (point - projected).length
        # appriximately
        edge_pixel_distance = self.distance_2d(point, projected)
        # a = (v1 - v2).length
        # p = (a + d1 + d2) / 2
        # try:
        # h = (2 / a) * math.sqrt(abs(p * (p - a) * (p - d1) * (p - d2)))
        # except:
            # h = float("inf")
        vertex_distance, vertex_index, vertex_pixel_distance = (d1, 0, self.distance_2d(v1, point)) if d1 < d2 else (d2, 1, self.distance_2d(v2, point))
        edge_distance = min(h, d1, d2)

        return edge_distance, vertex_distance, vertex_index, edge_pixel_distance, vertex_pixel_distance, split_ratio, projected

    def find_closest(self, point, face):
        if not point:
            return None, None, None, None

        edge_dist = float("inf")
        edge_pixel_distance = float("inf")
        vertex_pixel_distance = float("inf")
        split_ratio = None
        edge = None
        vert = None
        projected = None
        for e in face.edges:
            dRes = self.distance_to_edge(point, e)
            if dRes[0] < edge_dist:
                edge_dist = dRes[0]
                edge = e
                vert = e.verts[dRes[2]]
                edge_pixel_distance = dRes[3]
                vertex_pixel_distance = dRes[4]
                split_ratio = dRes[5]
                projected = dRes[6]

        return vert, edge, vertex_pixel_distance, edge_pixel_distance, split_ratio, projected
