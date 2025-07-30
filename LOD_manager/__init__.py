bl_info = {
    "name": "LOD Manager",
    "author": "Igrom",
    "version": (3, 5),
    "blender": (4, 0, 0),
    "location": "3D View > Sidebar > LOD",
    "description": "LOD UI with Ctrl/Shift multi-selection and camera-based auto-switching",
    "category": "Object",
    "doc_url": "https://github.com/Igrom/LODManager/wiki",
    "tracker_url": "https://github.com/Igrom/LODManager/issues"
}

from .LOD_manager import register, unregister

if __name__ == "__main__":
    register()
