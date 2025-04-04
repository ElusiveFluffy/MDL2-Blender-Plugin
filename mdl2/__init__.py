
bl_info = {
        "name": "MDL2 Tools",
        "description": "Import and export MDL2s",
        "author": "Kana Miyoshi",
        "version": (1, 5),
        "blender": (3, 0, 0),
        "location": "View3D > Sidebar",
        "category": "Object"
        }

import bpy

from .importer import ImportMDL2
from .exporter import ExportMDL2
from . import collisionPanel

# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(ImportMDL2.bl_idname, text="MDL2 (.mdl)")

# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ExportMDL2.bl_idname, text="MDL2 (.mdl)")

def register():
    bpy.utils.register_class(ImportMDL2)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.utils.register_class(ExportMDL2)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    collisionPanel.register()


def unregister():
    bpy.utils.unregister_class(ImportMDL2)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(ExportMDL2)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    collisionPanel.unregister()


if __name__ == "__main__":
    register()