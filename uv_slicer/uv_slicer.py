bl_info = {
    "name": "UV Slicer",
    "author": "Igrom",
    "description": "Режет геометрию по краям UDIM-квадратов и собирает их в (0;1)",
    "blender": (4, 5, 0),
    "location": "UV Editor > Sidebar",
    "warning": "",
    "category": "UV"
}

import bpy
import bmesh
import math

def is_uv_on_border(uv):
    return abs(.5 - uv % 1) >= 0.499999

class OpCutToUvRects(bpy.types.Operator):
    bl_idname = "uvs.cut_to_uv_rects"
    bl_label = "Разрезать по UV-тайлам"
    bl_description = "Разрезает геометрию по границам UDIM-тайлов. Все острова UV должны быть выпуклыми."
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if bpy.context.object and bpy.context.object.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

            print("Начат процесс разрезки UV!")

        for obj in objects:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            uv_lay = bm.loops.layers.uv.active
            iter = 1

            while (iter < 1000):
                print("Итерация: ", iter)
                iter += 1
                border_axis = -1
                border_value = -9999999
                border_face = None

                for axis in range(2):
                    for face in bm.faces:
                        min_maxes = []
                        for loop in face.loops:
                            uv = loop[uv_lay].uv[axis]
                            for min_max in min_maxes:
                                if uv < min_max[0] or uv > min_max[1]:
                                    border_face = face
                                    border_axis = axis
                                    border_value = min_max[0] if uv < min_max[0] else min_max[1]
                                    break
                            if border_face:
                                break
                            if is_uv_on_border(uv):
                                min_maxes.append((round(uv-1), round(uv+1)))
                            else:
                                min_maxes.append((math.floor(uv), math.ceil(uv)))
                        if border_face:
                            break

                if not border_face:
                    bm.to_mesh(obj.data)
                    bm.free()
                    break

                verts_to_connect = []
                edges = {}
                for edge in border_face.edges:
                    relevant_loops = []
                    for vert in edge.verts:
                        for loop in vert.link_loops:
                            if loop.face != border_face:
                                continue
                            relevant_loops.append(loop)

                    uvs = (relevant_loops[0][uv_lay].uv[border_axis],
                           relevant_loops[1][uv_lay].uv[border_axis])
                    
                    if uvs[0] == border_value:
                        if edge.verts[0] not in verts_to_connect:
                            verts_to_connect.append(edge.verts[0])
                        continue
                    elif uvs[1] == border_value:
                        if edge.verts[1] not in verts_to_connect:
                            verts_to_connect.append(edge.verts[1])
                        continue
                    elif uvs[0] < border_value and uvs[1] > border_value:
                        subdivision_value = abs((border_value-uvs[1])/(uvs[0]-uvs[1]))
                    elif uvs[1] < border_value and uvs[0] > border_value:
                        subdivision_value = abs((border_value-uvs[1])/(uvs[0]-uvs[1]))
                    else:
                        continue
                    edges[edge] = [vert, subdivision_value]

                for edge, values in edges.items():
                    edge_vert_pair = bmesh.utils.edge_split(edge, values[0], values[1])
                    verts_to_connect.append(edge_vert_pair[1])

                if len(verts_to_connect) >= 2:
                    bmesh.ops.connect_verts(bm, verts=verts_to_connect)
            # end while
        return {'FINISHED'}

class OpAssembleUvRects(bpy.types.Operator):
    bl_idname = "uvs.assemble_uv_rects"
    bl_label = "Собрать оверлапы"
    bl_description = "Собирает все UV из UDIM-тайлов в пространство 0-1 (для атласа)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

        for obj in objects:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            uv_lay = bm.loops.layers.uv.active

            for axis in range(2):
                for face in bm.faces:
                    rect_min = -9999999
                    rect_max = 9999999
                    for loop in face.loops:
                        uv = loop[uv_lay].uv[axis]
                        if is_uv_on_border(uv):
                            loop_min = round(uv-1)
                            loop_max = round(uv+1)
                        else:
                            loop_min = math.floor(uv)
                            loop_max = math.ceil(uv)
                        rect_min = max(rect_min, loop_min)
                        rect_max = min(rect_max, loop_max)
                    movement = -rect_min
                    if (rect_max - rect_min > 1.000001):
                        print("Предупреждение: странное лицо с областью > 1 в UV")
                    for loop in face.loops:
                        loop[uv_lay].uv[axis] += movement
            bm.to_mesh(obj.data)
            bm.free()

        # Обновление редактора
        for area in context.window.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.tag_redraw()
        return {'FINISHED'}

class UVS_PT_Panel(bpy.types.Panel):
    bl_label = "UV Нарезка"
    bl_idname = "UVS_PT_panel"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "UV Нарезка"

    def draw(self, context):
        layout = self.layout
        layout.operator("uvs.cut_to_uv_rects", text="Разрезать по UV-тайлам", icon='SCULPTMODE_HLT')
        layout.operator("uvs.assemble_uv_rects", text="Собрать оверлапы", icon='UV_DATA')


# Регистрация классов
classes = [
    OpCutToUvRects,
    OpAssembleUvRects,
    UVS_PT_Panel
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
