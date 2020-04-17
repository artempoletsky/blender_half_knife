
import bpy

class HalfKnifePreferencesDefaults():
    snap_vertex_distance = 20
    snap_edge_distance = 15

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
        row = layout.row()
        col = row.column()

        col.label(text="Color settings:")

    def draw_keymaps(self, context, layout):
        row = layout.row()
        col = row.column()

        col.label(text="Keymap settings:")
