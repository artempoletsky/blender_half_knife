
import bpy

class HalfKnifePreferencesDefaults():
    snap_vertex_distance = 20
    snap_edge_distance = 15

defaults = HalfKnifePreferencesDefaults()

class HalfKnifePreferences(bpy.types.AddonPreferences, HalfKnifePreferencesBase):
    bl_idname = 'HalfKnife'

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
            self.draw_snap_utilities_colors(box)

        elif self.tabs == "KEYMAPS":
            self.draw_snap_utilities_keymaps(context, box)

    def draw_general(box):
        row = layout.row()
        col = row.column()

        col.label(text="Snap Properties:")
        col.prop(self, "snap_vertex_distance")
        col.prop(self, "snap_edge_distance")
