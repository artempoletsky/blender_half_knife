
import bpy

user_prefs = bpy.context.preferences.themes[0].view_3d

class HalfKnifePreferencesDefaults():
    snap_vertex_distance = 20
    snap_edge_distance = 15

    cutting_edge = tuple(user_prefs.nurb_vline) + (1,)
    vertex = tuple(user_prefs.handle_sel_vect) + (1,)
    vertex_snap = tuple(user_prefs.handle_sel_auto) + (1,)
    edge_snap = tuple(user_prefs.handle_sel_auto) + (1,)


    # cutting_edge = (0.603827, 0.000000, 0.318547, 1.000000)
    # vertex = (0.051269, 0.527115, 0.029557, 1.000000)
    # vertex_snap = (0.871367, 1.000000, 0.051269, 1.000000)
    # edge_snap = (0.871367, 1.000000, 0.051269, 1.000000)


defaults = HalfKnifePreferencesDefaults()

class HalfKnifePreferences(bpy.types.AddonPreferences):
    bl_idname = 'half_knife'

    tabs : bpy.props.EnumProperty(name="Tabs",
        items = [("GENERAL", "General", ""),
            ("KEYMAPS", "Keymaps", ""),
            ("COLORS", "Colors", ""),],
        default="GENERAL")

    snap_vertex_distance : bpy.props.IntProperty(name = "Vertex snap distance", default = defaults.snap_vertex_distance)
    snap_edge_distance : bpy.props.IntProperty(name = "Edge snap distance", default = defaults.snap_edge_distance)

    cutting_edge : bpy.props.FloatVectorProperty(name="Cutting edge",
        default=defaults.cutting_edge,
        size=4,
        subtype="COLOR",
        min=0,
        max=1)

    vertex : bpy.props.FloatVectorProperty(name="Vertex",
        default=defaults.vertex,
        size=4,
        subtype="COLOR",
        min=0,
        max=1)

    vertex_snap : bpy.props.FloatVectorProperty(name="Vertex snap to",
        default=defaults.vertex_snap,
        size=4,
        subtype="COLOR",
        min=0,
        max=1)

    edge_snap : bpy.props.FloatVectorProperty(name="Edge snap to",
        default=defaults.edge_snap,
        size=4,
        subtype="COLOR",
        min=0,
        max=1)

    def draw(self, context):
        layout = self.layout

        # TAB BAR
        row = layout.row()
        row.prop(self, "tabs", expand=True)

        box = layout.box()

        if self.tabs == "GENERAL":
            self.draw_general(box)

        elif self.tabs == "COLORS":
            self.draw_colors(box)

        elif self.tabs == "KEYMAPS":
            self.draw_keymaps(context, box)

    def draw_general(self, layout):
        row = layout.row()
        col = row.column()

        col.label(text="Snap settings:")
        col.prop(self, "snap_vertex_distance")
        col.prop(self, "snap_edge_distance")

    def draw_colors(self, layout):
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=False, columns=0, even_columns=True, even_rows=False, align=False)

        flow.prop(self, "cutting_edge")
        flow.prop(self, "vertex")
        flow.prop(self, "vertex_snap")
        flow.prop(self, "edge_snap")

    def draw_keymaps(self, context, layout):
        row = layout.row()
        col = row.column()

        col.label(text="Keymap settings:")
