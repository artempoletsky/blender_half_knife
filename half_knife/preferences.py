# ##### BEGIN GPL LICENSE BLOCK #####
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

import bpy, _thread, time
import rna_keymap_ui
from bpy.app.translations import contexts as i18n_contexts
from bpy.app.handlers import persistent


class HalfKnifePreferencesAddKeymapOperator(bpy.types.Operator):
    """Add key map item"""
    bl_idname = "half_knife_preferences.keyitem_add"
    bl_label = "Add Key Map Item"

    def execute(self, context):
        km = context.keymap

        kmi = km.keymap_items.new("mesh.half_knife_operator", 'K', 'PRESS')
        context.preferences.is_dirty = True
        return {'FINISHED'}



user_prefs = bpy.context.preferences.themes[0].view_3d

class HalfKnifePreferencesDefaults():
    snap_vertex_distance = 20
    snap_edge_distance = 15

    cutting_edge = tuple(user_prefs.nurb_vline) + (1,)
    vertex = tuple(user_prefs.handle_sel_vect) + (1,)
    vertex_snap = tuple(user_prefs.handle_sel_auto) + (1,)
    edge_snap = tuple(user_prefs.handle_sel_auto) + (1,)

    angle_constraint_active_face =   tuple(user_prefs.handle_sel_auto) + (.4,)
    angle_constraint_axis = (1, 1, 1, 1)

    disable_knife_icon = False


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

    disable_knife_icon : bpy.props.BoolProperty(name = "Disable knife mouse cursor icon", default = defaults.disable_knife_icon)

    is_installed : bpy.props.BoolProperty(name = "Disable knife mouse cursor icon", default = False)

    use_edge_autofix : bpy.props.BoolProperty(name = "Use broken edge autofix", default = True)

    edge_autofix_distance : bpy.props.FloatProperty(name = "Edge autofix merge distance", default = 0.001)

    snap_vertex_distance : bpy.props.IntProperty(name = "Vertex snap distance (pixels)", default = defaults.snap_vertex_distance)
    snap_edge_distance : bpy.props.IntProperty(name = "Edge snap distance (pixels)", default = defaults.snap_edge_distance)

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

    angle_constraint_active_face : bpy.props.FloatVectorProperty(name="Angle constraint active face",
        default=defaults.angle_constraint_active_face,
        size=4,
        subtype="COLOR",
        min=0,
        max=1)

    angle_constraint_axis : bpy.props.FloatVectorProperty(name="Angle constraint axis",
        default=defaults.angle_constraint_axis,
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
            self.draw_keymaps(box)

    def draw_general(self, layout):
        row = layout.row()
        col = row.column()

        col.label(text="Snap settings:")
        col.prop(self, "snap_vertex_distance")
        col.prop(self, "snap_edge_distance")

        col.separator()
        col.prop(self, "disable_knife_icon")

        col.separator()
        col.prop(self, "use_edge_autofix")
        col.prop(self, "edge_autofix_distance")

    def draw_colors(self, layout):
        layout.use_property_split = True
        flow = layout.grid_flow(row_major=False, columns=0, even_columns=True, even_rows=False, align=False)

        flow.prop(self, "cutting_edge")
        flow.prop(self, "vertex")
        flow.prop(self, "vertex_snap")
        flow.prop(self, "edge_snap")
        flow.prop(self, "angle_constraint_active_face")
        flow.prop(self, "angle_constraint_axis")

    def draw_keymaps(self, layout):
        row = layout.row()
        col = row.column()

        col.label(text="Keymap settings:")

        wm = bpy.context.window_manager
        kc = wm.keyconfigs.user
        km = kc.keymaps['Mesh']
        col.context_pointer_set("keymap", km)
        for kmi in km.keymap_items:
            if is_addon_keymap(kmi):
                rna_keymap_ui.draw_kmi(["ADDON", "USER", "DEFAULT"], kc, km, kmi, col, 0)
        subcol = col.split(factor=0.2).column()
        subcol.operator(HalfKnifePreferencesAddKeymapOperator.bl_idname, text="Add New", text_ctxt=i18n_contexts.id_windowmanager, icon='ADD')

from bl_keymap_utils.io import keyconfig_init_from_data


def get_addon_prefs():
    addons_prefs = bpy.context.preferences.addons
    id = 'half_knife'
    return addons_prefs[id].preferences if id in addons_prefs else None

def is_addon_keymap(kmi):
    return kmi.idname in {'mesh.half_knife_operator', 'mesh.knife_tool'}

@persistent
def on_load():
    # print('on_load')
    keyconfigs = bpy.context.window_manager.keyconfigs
    kmis = keyconfigs.default.keymaps['Mesh'].keymap_items
    i = 0
    while not 'mesh.knife_tool' in kmis and i < 100:
        time.sleep(.1)
        i += 1
    # print(i)
    kmis['mesh.knife_tool'].alt = True

def load_handler(arg):
    _thread.start_new_thread(on_load,())
    # print('item count:',len(km.keymap_items))



def register_keymaps():

    keyconfigs = bpy.context.window_manager.keyconfigs
    # kc_defaultconf = keyconfigs.default
    kc_addonconf = keyconfigs.addon

    keyconfig_init_from_data(kc_addonconf, [
         (
            "Mesh",
            {"space_type": 'EMPTY', "region_type": 'WINDOW'},
            {"items": [
                ("mesh.half_knife_operator", {"type": 'K', "value": 'PRESS'},
                 {"properties": [("altitude_mode", False), ("auto_cut", False), ("snap_to_center", False), ("snap_to_center_alternate", False), ("cut_through", False), ("turn_off_snapping", False)],
                  "active":True}),
                ("mesh.half_knife_operator", {"type": 'K', "value": 'PRESS', "shift": True},
                 {"properties": [("altitude_mode", False), ("auto_cut", True), ("snap_to_center", False), ("snap_to_center_alternate", False), ("cut_through", False), ("turn_off_snapping", False)],
                  "active":True}),
            ]},
        ),
    ])
    kmis = keyconfigs.default.keymaps['Mesh'].keymap_items
    if 'mesh.knife_tool' in kmis:
        kmis['mesh.knife_tool'].alt = True
    else:
        _thread.start_new_thread(on_load,())
        # bpy.app.handlers.load_post.append(load_handler)
    prefs = get_addon_prefs()
    # print(prefs)
    if prefs and prefs.is_installed:
        # print('addon is installed')
        return
    # print('addon is installing')
    # kmi = keyconfigs.user.keymaps['Mesh'].keymap_items['mesh.knife_tool']
    # kmi.alt = True

    # bpy.context.preferences.is_dirty = True


    if prefs:
        prefs.is_installed = True

    #

def unregister_keymaps():
    keyconfigs = bpy.context.window_manager.keyconfigs
    kc_addonconf = keyconfigs.addon

    km = kc_addonconf.keymaps['Mesh']

    for kmi in km.keymap_items:
        if kmi.idname in {'mesh.half_knife_operator'} :
            km.keymap_items.remove(kmi)

    kc = keyconfigs.default
    km = kc.keymaps['Mesh']
    km.keymap_items['mesh.knife_tool'].alt = False
    return
