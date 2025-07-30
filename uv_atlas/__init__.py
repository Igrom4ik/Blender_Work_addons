bl_info = {
    "name": "UV Atlas",
    "author": "Igrom",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "3D View > Sidebar > UV Atlas",
    "description": "UV Atlas tools",
    "category": "UV"
}

from .uv_atlas import register, unregister

if __name__ == "__main__":
    register()
