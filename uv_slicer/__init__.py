bl_info = {
    "name": "UV Slicer",
    "author": "Igrom",
    "version": (1, 0),
    "blender": (4, 5, 0),
    "location": "3D View > Sidebar > UV Slicer",
    "description": "UV Slicer tools",
    "category": "UV"
}

from .uv_slicer import register, unregister

if __name__ == "__main__":
    register()
