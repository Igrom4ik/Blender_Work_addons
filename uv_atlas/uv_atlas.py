bl_info = {
    "name": "uv_atlas_tool",
    "author": "Igor Unguryznov aka Igron",
    "version": (1, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > UV Atlas",
    "description": "Инструменты для паковки UV на основе JSON спрайт-атласа",
    "warning": "",
    "doc_url": "",
    "category": "UV",
}
import bpy
import os
import json
import re
import numpy as np

# --- Утилиты ---------------------------------------------------------------

def normalize_name(name):
    name = name.lower()
    name = os.path.basename(name)
    name = re.sub(r'\.\d{3}$', '', name)  # Удаляем Blender-суффиксы вроде .001, .002 перед расширением
    name = re.sub(r'\.\w+$', '', name)   # Удаляем расширение (например, .tga)
    name = re.sub(r'-', '_', name)       # Замена дефиса на подчёркивание для совпадения с JSON
    name = re.sub(r'^t_', '', name)
    name = re.sub(r'_(albedo|basecolor)$', '', name)
    name = re.sub(r'_lod\d+$', '', name)
    # Убрано re.sub(r'_[a-z0-9]+$', '', name) — оно ломало имена вроде '_atlas'
    return name

def get_texture_name_from_material(mat):
    if not mat or not mat.use_nodes:
        return None
    tree = mat.node_tree
    principled = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not principled:
        return None
    base_color_input = principled.inputs.get('Base Color')
    if not base_color_input or not base_color_input.is_linked:
        return None
    linked_node = base_color_input.links[0].from_node
    if linked_node.type == 'TEX_IMAGE' and linked_node.image:
        return os.path.basename(linked_node.image.name or linked_node.image.filepath)
    return None

def load_sprite_bounds(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    bounds = {}
    width = data['atlas']['width']
    height = data['atlas']['height']
    for sprite_name, sprite_data in data['frames'].items():
        frame = sprite_data['frame']
        x, y, w, h = frame['x'], frame['y'], frame['width'], frame['height']
        y = height - (y + h)  # Коррекция Y для UV (инверсия)
        u_min = x / width
        u_max = (x + w) / width
        v_min = y / height
        v_max = (y + h) / height
        key_name = normalize_name(sprite_name)
        bounds[key_name] = {
            'original_name': sprite_name,  # сохраняем оригинальное имя при желании
            'uv_bounds': ((u_min, u_max), (v_min, v_max)),
            'rotated': sprite_data['rotated'],
            'size_px': (w, h)
        }
    return bounds, width, height  # Возвращаем также width/height

# --- Кастомный PropertyGroup для элементов списка включений ---------------

class IncludeUVItem(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        cls.name = bpy.props.StringProperty(name="UV Channel Name")
        cls.include = bpy.props.BoolProperty(name="Include", default=False)

    @classmethod
    def unregister(cls):
        if hasattr(cls, "name"):
            del cls.name
        if hasattr(cls, "include"):
            del cls.include

# --- Оператор для сканирования и обновления списка UV-каналов ---------------

class UV_OT_RefreshUVList(bpy.types.Operator):
    bl_idname = "object.refresh_uv_list"
    bl_label = "Refresh UV List"
    bl_description = "Сканирует выделенные объекты и обновляет список уникальных UV-каналов"

    def execute(self, context):
        unique_uvs = set()
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj.data.uv_layers:
                for uv in obj.data.uv_layers:
                    unique_uvs.add(uv.name)
        
        scene = context.scene
        scene.uv_include_items.clear()
        for uv_name in sorted(unique_uvs):
            item = scene.uv_include_items.add()
            item.name = uv_name
            item.include = False
        
        self.report({'INFO'}, f"Обновлено: {len(unique_uvs)} уникальных UV-каналов из выделенных объектов")
        return {'FINISHED'}

# --- Оператор 1: просто находит совпадения ----------------------------------

class UV_OT_ApplySpriteAtlas(bpy.types.Operator):
    bl_idname = "object.apply_sprite_atlas_uv"
    bl_label = "Apply UV Remap"
    bl_description = "Сопоставляет UV по совпадению имён текстур с JSON (без трансформации)"

    def execute(self, context):
        json_path = context.scene.uv_atlas_json_path
        if not os.path.isfile(json_path):
            self.report({'ERROR'}, f"JSON не найден: {json_path}")
            return {'CANCELLED'}

        try:
            sprite_bounds, _, _ = load_sprite_bounds(json_path)
            print("[DEBUG] Ключи в JSON после нормализации:", list(sprite_bounds.keys()))
        except Exception as e:
            self.report({'ERROR'}, f"Ошибка при загрузке JSON: {e}")
            return {'CANCELLED'}

        count = 0
        for obj in context.selected_objects:  # Только выделенные
            if obj.type != 'MESH':
                continue
            for mat_slot in obj.material_slots:
                mat = mat_slot.material
                tex_name_raw = get_texture_name_from_material(mat)
                if not tex_name_raw:
                    continue
                tex_name = normalize_name(tex_name_raw)
                if tex_name in sprite_bounds:
                    count += 1

        self.report({'INFO'}, f"🔍 Объектов с совпадением имён текстур: {count}")
        return {'FINISHED'}

# --- Оператор 2: переатласовка UV -------------------------------------------

class UV_OT_PackToSpriteAtlas(bpy.types.Operator):
    bl_idname = "object.pack_sprite_uv"
    bl_label = "Pack UVs to Sprite Atlas"
    bl_description = "Масштабирует и переносит UV в границы спрайта (атласа)"

    def execute(self, context):
        json_path = context.scene.uv_atlas_json_path
        if not os.path.isfile(json_path):
            self.report({'ERROR'}, f"JSON не найден: {json_path}")
            return {'CANCELLED'}

        try:
            sprite_bounds_all, atlas_width, atlas_height = load_sprite_bounds(json_path)
            print("[DEBUG] Ключи в JSON после нормализации:", list(sprite_bounds_all.keys()))
        except Exception as e:
            self.report({'ERROR'}, f"Ошибка при загрузке JSON: {e}")
            return {'CANCELLED'}

        included_uvs = [item.name for item in context.scene.uv_include_items if item.include]
        if not included_uvs:
            all_uvs = set()
            for obj in context.selected_objects:
                if obj.type == 'MESH' and obj.data.uv_layers:
                    for uv in obj.data.uv_layers:
                        all_uvs.add(uv.name)
            included_uvs = sorted(all_uvs)

        assign_mat = context.scene.uv_atlas_material
        padding = context.scene.uv_padding

        # Предупреждение: проверяем наличие и имена текстур (только для выделенных)
        scene_textures = set()
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            for mat_slot in obj.material_slots:
                mat = mat_slot.material
                tex_name_raw = get_texture_name_from_material(mat)
                if tex_name_raw:
                    tex_name = normalize_name(tex_name_raw)
                    scene_textures.add(tex_name)
        atlas_keys = set(sprite_bounds_all.keys())
        missing_in_atlas = scene_textures - atlas_keys
        missing_in_scene = atlas_keys - scene_textures
        if missing_in_atlas:
            warn_msg = f"⚠️ Текстуры в сцене без совпадения в JSON: {', '.join(missing_in_atlas)}. Проверьте имена или наличие в атласе."
            print(warn_msg)
            self.report({'WARNING'}, warn_msg)
        if missing_in_scene:
            warn_msg = f"⚠️ Текстуры в JSON без использования в сцене: {', '.join(missing_in_scene)}. Возможно, не критичны, но проверьте."
            print(warn_msg)
            self.report({'WARNING'}, warn_msg)

        total_packed = 0
        total_assigned = 0
        for uv_name in included_uvs:
            # Группируем выделенные объекты по нормализованной текстуре
            texture_to_objs = {}
            for obj in context.selected_objects:
                if obj.type != 'MESH':
                    continue
                mesh = obj.data
                if not mesh.uv_layers or uv_name not in mesh.uv_layers:
                    continue
                tex_name = None
                for mat_slot in obj.material_slots:
                    mat = mat_slot.material
                    tex_name_raw = get_texture_name_from_material(mat)
                    if tex_name_raw:
                        tex_name = normalize_name(tex_name_raw)
                        if tex_name in sprite_bounds_all:
                            break
                if tex_name and tex_name in sprite_bounds_all:
                    texture_to_objs.setdefault(tex_name, []).append(obj)

            # Для каждой группы: собираем все UV для общего расчёта, затем применяем
            for tex_name, objs in texture_to_objs.items():
                all_uvs = []
                uv_layers = []
                meshes = []
                for obj in objs:
                    uv_layer = obj.data.uv_layers[uv_name]
                    uvs = [[loop.uv.x, loop.uv.y] for loop in uv_layer.data]
                    if uvs:
                        all_uvs.extend(uvs)
                        uv_layers.append(uv_layer)
                        meshes.append(obj.data)
                if not all_uvs:
                    continue
                arr = np.array(all_uvs)
                if arr.ndim != 2 or arr.shape[1] != 2:
                    continue
                # Центр массы (centroid) всех UV точек
                src_center = np.mean(arr, axis=0)
                sprite_data = sprite_bounds_all[tex_name]
                bounds = sprite_data['uv_bounds']
                rotated = sprite_data['rotated']
                # Без паддинга: используем полные границы
                dst_u_min = bounds[0][0]
                dst_u_max = bounds[0][1]
                dst_v_min = bounds[1][0]
                dst_v_max = bounds[1][1]
                dst_center = np.array([(dst_u_min + dst_u_max) / 2, (dst_v_min + dst_v_max) / 2])
                # Поворот всех относительных UV одновременно относительно центра
                rel = arr - src_center
                if rotated:
                    rel_rot = np.column_stack((rel[:, 1], -rel[:, 0]))
                else:
                    rel_rot = rel
                # Расчёт bounding box и scale на повернутых координатах
                rot_u_min, rot_u_max = rel_rot[:, 0].min(), rel_rot[:, 0].max()
                rot_v_min, rot_v_max = rel_rot[:, 1].min(), rel_rot[:, 1].max()
                src_width = rot_u_max - rot_u_min if rot_u_max > rot_u_min else 1
                src_height = rot_v_max - rot_v_min if rot_v_max > rot_v_min else 1
                dst_width = dst_u_max - dst_u_min
                dst_height = dst_v_max - dst_v_min
                scale_u = dst_width / src_width
                scale_v = dst_height / src_height
                scale = min(scale_u, scale_v)
                # Применяем масштаб и сдвиг к повернутым координатам
                # После масштабирования, bounding box может не совпадать с dst_center — нужно сдвинуть в границы
                rel_rot_scaled = rel_rot * scale
                # bounding box после масштабирования
                rot_u_min_s, rot_u_max_s = rel_rot_scaled[:, 0].min(), rel_rot_scaled[:, 0].max()
                rot_v_min_s, rot_v_max_s = rel_rot_scaled[:, 1].min(), rel_rot_scaled[:, 1].max()
                # Центр bounding box после масштабирования
                bbox_center = np.array([
                    (rot_u_min_s + rot_u_max_s) / 2,
                    (rot_v_min_s + rot_v_max_s) / 2
                ])
                # Центр целевого контейнера
                target_center = np.array([
                    (dst_u_min + dst_u_max) / 2,
                    (dst_v_min + dst_v_max) / 2
                ])
                # Сдвиг, чтобы центр совпал с центром контейнера
                offset = target_center - bbox_center
                rel_rot_scaled_offset = rel_rot_scaled + offset
                idx = 0
                packed_objs = 0
                for uv_layer, mesh in zip(uv_layers, meshes):
                    num_loops = len(uv_layer.data)
                    rel_rot_obj = rel_rot_scaled_offset[idx:idx + num_loops]
                    for i, loop in enumerate(uv_layer.data):
                        uv_scaled = rel_rot_obj[i]
                        loop.uv = uv_scaled.tolist()
                    mesh.update()
                    packed_objs += 1
                    idx += num_loops
                
                # Дополнительный равномерный скейл для padding в конце (относительно центра)
                if padding > 0:
                    sprite_w, sprite_h = sprite_data['size_px']
                    if sprite_w <= 2 * padding or sprite_h <= 2 * padding:
                        print(f"[WARN] Пропуск padding для '{tex_name}': размер спрайта слишком мал ({sprite_w}x{sprite_h})")
                        scale_factor = 1.0
                    else:
                        scale_u_pad = (sprite_w - 2 * padding) / sprite_w
                        scale_v_pad = (sprite_h - 2 * padding) / sprite_h
                        scale_factor = min(scale_u_pad, scale_v_pad)
                    if scale_factor < 1.0:
                        for uv_layer, mesh in zip(uv_layers, meshes):
                            for loop in uv_layer.data:
                                uv = np.array([loop.uv.x, loop.uv.y])
                                rel = uv - dst_center
                                rel_scaled = rel * scale_factor
                                new_uv = rel_scaled + dst_center
                                loop.uv = new_uv.tolist()
                            mesh.update()
                        print(f"[INFO] Применён padding-скейл {scale_factor:.3f} для '{tex_name}'")
                
                # Назначаем материал группе объектов, если выбран
                if assign_mat:
                    for obj in objs:
                        for slot in obj.material_slots:
                            slot.material = assign_mat
                    total_assigned += len(objs)
                rot_info = " (с поворотом)" if rotated else ""
                print(f"[INFO] Группа текстуры '{tex_name}', канал '{uv_name}': упаковано {packed_objs} объектов{rot_info}")
                total_packed += packed_objs

        msg = f"✅ Упаковано объектов: {total_packed}"
        if total_assigned > 0:
            msg += f" | Назначено материала: {total_assigned} объектам"
        self.report({'INFO'}, msg)
        return {'FINISHED'}

# --- Общая панель интерфейса -----------------------------------------------

class UV_PT_SpriteAtlasPanel(bpy.types.Panel):
    bl_label = "Sprite Atlas UV Tools"
    bl_idname = "OBJECT_PT_sprite_uv_remap"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'UV Atlas'

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "uv_atlas_json_path")
        
        layout.operator("object.refresh_uv_list", icon="FILE_REFRESH")
        
        box = layout.box()
        box.label(text="Включить UV-каналы для packing:")
        if not context.scene.uv_include_items:
            box.label(text="Список пуст - пакуем все. Нажмите Refresh.")
        else:
            for item in context.scene.uv_include_items:
                row = box.row()
                row.prop(item, "include", text="")
                row.label(text=item.name)
        
        layout.prop(context.scene, "uv_atlas_material")  # Выбор материала
        layout.prop(context.scene, "uv_padding")  # Параметр padding
        
        layout.operator("object.pack_sprite_uv", icon="MOD_UVPROJECT")
        layout.operator("object.apply_sprite_atlas_uv", icon="UV")

# --- Дублирующая панель в UV Editor ----------------------------------------

class UV_PT_SpriteAtlasPanel_UVEditor(UV_PT_SpriteAtlasPanel):
    bl_space_type = 'IMAGE_EDITOR'
    bl_idname = "IMAGE_PT_sprite_uv_remap"

# --- Регистрация -----------------------------------------------------------

classes = [
    IncludeUVItem,
    UV_OT_RefreshUVList,
    UV_OT_ApplySpriteAtlas,
    UV_OT_PackToSpriteAtlas,
    UV_PT_SpriteAtlasPanel,
    UV_PT_SpriteAtlasPanel_UVEditor,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.uv_atlas_json_path = bpy.props.StringProperty(
        name="Atlas JSON Path",
        description="Путь к JSON-файлу спрайт-атласа",
        subtype='FILE_PATH'
    )
    bpy.types.Scene.uv_include_items = bpy.props.CollectionProperty(type=IncludeUVItem)
    bpy.types.Scene.uv_atlas_material = bpy.props.PointerProperty(
        type=bpy.types.Material,
        name="Assign Material",
        description="Материал для назначения после packing"
    )
    bpy.types.Scene.uv_padding = bpy.props.IntProperty(
        name="Padding (px)",
        description="Отступ в пикселях с каждой стороны для равномерного скейла островов",
        default=0,
        min=0
    )

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.uv_atlas_json_path
    del bpy.types.Scene.uv_include_items
    del bpy.types.Scene.uv_atlas_material
    del bpy.types.Scene.uv_padding

if __name__ == "__main__":
    register()