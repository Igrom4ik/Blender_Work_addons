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

import bpy
import re
import json
import math
from bpy.props import (
    CollectionProperty,
    StringProperty,
    PointerProperty,
    IntProperty,
    BoolProperty,
    FloatVectorProperty,
    FloatProperty,
    EnumProperty,
)
from random import uniform

LOD_PATTERN = re.compile(r".*_LOD(\d+)$", re.IGNORECASE)

# Словарь переводов
TRANSLATIONS = {
    "ru": {
        "addon_name": "LOD Manager",
        "description_tab": "Описание",
        "description_label": "Инструкция по использованию LOD Manager:",
        "desc_refresh": "• Обновить группы LOD — сканирует сцену и находит объекты с суффиксом '_LOD0', '_LOD1' и т.п.",
        "desc_select": "• Клик по имени LOD — выбирает одну группу (изоляция остальных).",
        "desc_ctrl": "• Ctrl + Клик — добавляет/удаляет LOD из текущего выбора.",
        "desc_shift": "• Shift + Клик — выбирает диапазон LOD-групп.",
        "desc_polycount": "• Поликаунт — отображает общее и видимое количество полигонов.",
        "desc_colors": "• Цвета — задают отображаемый цвет объекта по LOD-группе.",
        "desc_auto_lod": "• Авто LOD — переключает LODы автоматически по расстоянию до камеры.",
        "desc_warning": "⚠ Для корректной работы объекты должны называться как 'Name_LOD0', 'Name_LOD1', и т.п.",
        "refresh_groups": "Обновить группы LOD",
        "select_item": "Выделить LOD-группу",
        "enable_color": "Включить цвета",
        "show_polycount": "Показать поликаунт",
        "auto_lod_enabled": "Включить авто LOD",
        "camera": "Камера",
        "threshold": "Порог до LOD{0}",
        "lod_color": "LOD{0} Цвет",
        "total_polycount": "Общий polycount: {0}",
        "visible_polycount": "Видимый polycount: {0}",
        "total_visible_polycount": "Общий видимый polycount: {0}",
        "error_polycount": "Ошибка чтения данных",
        "language": "Язык",
        "language_ru": "Русский",
        "language_en": "English",
    },
    "en": {
        "addon_name": "LOD Manager",
        "description_tab": "Description",
        "description_label": "Instructions for using LOD Manager:",
        "desc_refresh": "• Refresh LOD Groups — scans the scene for objects with '_LOD0', '_LOD1', etc. suffixes.",
        "desc_select": "• Click on LOD name — selects one group (isolates others).",
        "desc_ctrl": "• Ctrl + Click — adds/removes LOD from current selection.",
        "desc_shift": "• Shift + Click — selects a range of LOD groups.",
        "desc_polycount": "• Polycount — displays total and visible polygon counts.",
        "desc_colors": "• Colors — set display colors for objects by LOD group.",
        "desc_auto_lod": "• Auto LOD — switches LODs automatically based on camera distance.",
        "desc_warning": "⚠ For proper operation, objects must be named like 'Name_LOD0', 'Name_LOD1', etc.",
        "refresh_groups": "Refresh LOD Groups",
        "select_item": "Select LOD Group",
        "enable_color": "Enable Colors",
        "show_polycount": "Show Polycount",
        "auto_lod_enabled": "Enable Auto LOD",
        "camera": "Camera",
        "threshold": "Threshold to LOD{0}",
        "lod_color": "LOD{0} Color",
        "total_polycount": "Total polycount: {0}",
        "visible_polycount": "Visible polycount: {0}",
        "total_visible_polycount": "Total visible polycount: {0}",
        "error_polycount": "Error reading polycount data",
        "language": "Language",
        "language_ru": "Русский",
        "language_en": "English",
    }
}

def get_translation(context, key, *args):
    """Получение переведенной строки с учетом текущего языка."""
    props = context.scene.lod_tool_props
    lang = props.language if hasattr(props, "language") else "en"
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    return text.format(*args) if args else text

class LODManagerPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text=get_translation(context, "description_label"))
        col = box.column(align=True)
        col.label(text=get_translation(context, "desc_refresh"))
        col.label(text=get_translation(context, "desc_select"))
        col.label(text=get_translation(context, "desc_ctrl"))
        col.label(text=get_translation(context, "desc_shift"))
        col.label(text=get_translation(context, "desc_polycount"))
        col.label(text=get_translation(context, "desc_colors"))
        col.label(text=get_translation(context, "desc_auto_lod"))
        col.separator()
        col.label(text=get_translation(context, "desc_warning"))

class LODListItem(bpy.types.PropertyGroup):
    name: StringProperty()
    selected: BoolProperty(default=False)

class ThresholdItem(bpy.types.PropertyGroup):
    value: FloatProperty(name="Distance", min=0, default=10)

class LODColorItem(bpy.types.PropertyGroup):
    color: FloatVectorProperty(
        name="LOD Color",
        subtype='COLOR',
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0
    )

def hsv_to_rgb(h, s, v):
    """Преобразование HSV в RGB."""
    h = h % 1.0
    h *= 360
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c

    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    return (r + m, g + m, b + m, 1.0)

def generate_distinct_color(index, total):
    """Генерирует визуально различимый цвет для LOD-группы."""
    hue = (index / total) % 1.0
    saturation = uniform(0.7, 1.0)
    value = uniform(0.7, 1.0)
    return hsv_to_rgb(hue, saturation, value)

def update_lod_selection(scene):
    props = scene.lod_tool_props
    if props.auto_lod_enabled and props.camera:
        # Автоматический режим LOD
        camera = props.camera
        lod_groups = {}
        
        for obj in scene.objects:
            match = LOD_PATTERN.match(obj.name)
            if match:
                base_name = re.sub(r"_LOD\d+$", "", obj.name)
                lod_num = match.group(1)
                if base_name not in lod_groups:
                    lod_groups[base_name] = []
                lod_groups[base_name].append((int(lod_num), obj))
        
        visible_polycount = 0
        for base_name, group in lod_groups.items():
            group.sort(key=lambda x: x[0])
            if group:
                obj = group[0][1]
                distance = (obj.location - camera.location).length
                num_exceeded = sum(1 for t in props.thresholds if distance >= t.value)
                lod_to_show = min(num_exceeded, len(group) - 1)
                for i, (lod_num, lod_obj) in enumerate(group):
                    lod_obj.hide_set(i != lod_to_show)
                    if i == lod_to_show and lod_obj.type == 'MESH' and lod_obj.data:
                        visible_polycount += len(lod_obj.data.polygons)
        
        props.polycount_cache = json.dumps({"mode": "auto", "visible_polycount": visible_polycount})
    else:
        # Ручной режим
        selected_lods = {item.name.replace("LOD", "") for item in props.lod_list if item.selected}
        polycount_data = {}
        
        for obj in scene.objects:
            match = LOD_PATTERN.match(obj.name)
            is_lod = bool(match)
            obj.hide_set(True)
            
            if is_lod and obj.type == 'MESH' and obj.data:
                lod_num = match.group(1)
                if lod_num not in polycount_data:
                    polycount_data[lod_num] = {'total': 0, 'visible': 0}
                polycount_data[lod_num]['total'] += len(obj.data.polygons)
                if lod_num in selected_lods:
                    obj.hide_set(False)
                    polycount_data[lod_num]['visible'] += len(obj.data.polygons)
        
        props.polycount_cache = json.dumps({"mode": "manual", "data": polycount_data})
    
    # Применение цветов
    if props.enable_color:
        for obj in scene.objects:
            match = LOD_PATTERN.match(obj.name)
            if match:
                lod_num = int(match.group(1))
                if lod_num < len(props.lod_colors):
                    obj.color = props.lod_colors[lod_num].color
                else:
                    obj.color = (1, 1, 1, 1)
            else:
                obj.color = (1, 1, 1, 1)
    else:
        # Сброс цветов при отключении
        for obj in scene.objects:
            obj.color = (1, 1, 1, 1)

class LOD_UL_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        row.active = item.selected
        op = row.operator("lod.select_item", text=item.name, emboss=False, icon='LAYER_USED' if item.selected else 'LAYER_ACTIVE')
        op.index = index

class LOD_PT_description(bpy.types.Panel):
    bl_label = "Description"
    bl_idname = "LOD_PT_description"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'LOD'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text=get_translation(context, "description_label"))
        col = box.column(align=True)
        col.label(text=get_translation(context, "desc_refresh"))
        col.label(text=get_translation(context, "desc_select"))
        col.label(text=get_translation(context, "desc_ctrl"))
        col.label(text=get_translation(context, "desc_shift"))
        col.label(text=get_translation(context, "desc_polycount"))
        col.label(text=get_translation(context, "desc_colors"))
        col.label(text=get_translation(context, "desc_auto_lod"))
        col.separator()
        col.label(text=get_translation(context, "desc_warning"))

class LOD_PT_panel(bpy.types.Panel):
    bl_label = "LOD Manager"
    bl_idname = "LOD_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'LOD'

    def draw(self, context):
        layout = self.layout
        props = context.scene.lod_tool_props

        layout.prop(props, "language")
        layout.operator("lod.refresh_groups", text=get_translation(context, "refresh_groups"), icon='FILE_REFRESH')
        row_count = max(1, min(len(props.lod_list), 8))
        layout.template_list("LOD_UL_items", "", props, "lod_list", props, "lod_active_index", rows=row_count)

        layout.separator()
        layout.prop(props, "enable_color", text=get_translation(context, "enable_color"))
        if props.enable_color:
            for i, color_item in enumerate(props.lod_colors):
                layout.prop(color_item, "color", text=get_translation(context, "lod_color", i))

        layout.separator()
        layout.prop(props, "auto_lod_enabled", text=get_translation(context, "auto_lod_enabled"))
        if props.auto_lod_enabled:
            layout.prop(props, "camera", text=get_translation(context, "camera"))
            for i, threshold in enumerate(props.thresholds):
                layout.prop(threshold, "value", text=get_translation(context, "threshold", i + 1))

        layout.separator()
        row = layout.row()
        row.prop(props, "show_polycount", text=get_translation(context, "show_polycount"), icon="TRIA_DOWN" if props.show_polycount else "TRIA_RIGHT", emboss=False)

        if props.show_polycount and props.polycount_cache:
            try:
                cache = json.loads(props.polycount_cache)
                if cache["mode"] == "manual":
                    layout.label(text=get_translation(context, "total_polycount"))
                    for lod in sorted(cache["data"].keys(), key=lambda k: int(k)):
                        data = cache["data"][lod]
                        box = layout.box()
                        box.label(text=f"LOD{lod}:")
                        box.label(text=get_translation(context, "total_polycount", data['total']))
                        box.label(text=get_translation(context, "visible_polycount", data['visible']))
                elif cache["mode"] == "auto":
                    layout.label(text=get_translation(context, "total_visible_polycount", cache['visible_polycount']))
            except:
                layout.label(text=get_translation(context, "error_polycount"))

class LOD_Tool_Props(bpy.types.PropertyGroup):
    lod_list: CollectionProperty(type=LODListItem)
    lod_active_index: IntProperty(default=-1)
    polycount_cache: StringProperty(default="")
    show_polycount: BoolProperty(name="Show Polycount", default=False)
    enable_color: BoolProperty(
        name="Enable Colors",
        default=False,
        update=lambda self, ctx: update_lod_selection(ctx.scene)
    )
    auto_lod_enabled: BoolProperty(
        name="Enable Auto LOD",
        default=False,
        update=lambda self, ctx: update_lod_selection(ctx.scene)
    )
    camera: PointerProperty(type=bpy.types.Object, poll=lambda self, obj: obj.type == 'CAMERA')
    thresholds: CollectionProperty(type=ThresholdItem)
    lod_colors: CollectionProperty(type=LODColorItem)
    language: EnumProperty(
        name="Language",
        items=[
            ("ru", "Русский", "Russian language"),
            ("en", "English", "English language"),
        ],
        default="en",
        update=lambda self, ctx: update_lod_selection(ctx.scene)
    )

class LOD_OT_select_item(bpy.types.Operator):
    bl_idname = "lod.select_item"
    bl_label = "Select LOD Group"
    bl_options = {'INTERNAL'}

    index: IntProperty()

    def invoke(self, context, event):
        props = context.scene.lod_tool_props
        idx = self.index
        items = props.lod_list

        if not event.ctrl and not event.shift:
            for it in items:
                it.selected = False
            items[idx].selected = True
        elif event.ctrl:
            items[idx].selected = not items[idx].selected
        elif event.shift:
            last_idx = props.lod_active_index
            if last_idx < 0:
                for it in items:
                    it.selected = False
                items[idx].selected = True
            else:
                start = min(last_idx, idx)
                end = max(last_idx, idx)
                for i in range(start, end + 1):
                    items[i].selected = True

        props.lod_active_index = idx
        update_lod_selection(context.scene)
        return {'FINISHED'}

class LOD_OT_refresh_groups(bpy.types.Operator):
    bl_idname = "lod.refresh_groups"
    bl_label = "Refresh LOD Groups"

    def execute(self, context):
        props = context.scene.lod_tool_props
        props.lod_list.clear()
        props.lod_colors.clear()

        lod_names = set()
        for obj in context.scene.objects:
            match = LOD_PATTERN.match(obj.name)
            if match:
                lod = match.group(1)
                lod_names.add(lod)

        sorted_lods = sorted(lod_names, key=int)
        for lod in sorted_lods:
            item = props.lod_list.add()
            item.name = f"LOD{lod}"
            color_item = props.lod_colors.add()
            color_item.color = generate_distinct_color(int(lod), len(sorted_lods))

        if props.lod_list:
            props.lod_list[0].selected = True
            props.lod_active_index = 0
            update_lod_selection(context.scene)

        num_lods = len(props.lod_list)
        num_thresholds_needed = max(0, num_lods - 1)
        current_thresholds = [t.value for t in props.thresholds]
        props.thresholds.clear()
        for i in range(num_thresholds_needed):
            item = props.thresholds.add()
            if i < len(current_thresholds):
                item.value = current_thresholds[i]
            else:
                item.value = 10 * (i + 1)

        props.polycount_cache = ""
        return {'FINISHED'}

def lod_handler(scene, depsgraph):
    update_lod_selection(scene)

classes = (
    LODListItem,
    ThresholdItem,
    LODColorItem,
    LOD_Tool_Props,
    LOD_UL_items,
    LOD_OT_select_item,
    LOD_OT_refresh_groups,
    LOD_PT_description,
    LOD_PT_panel,
    LODManagerPreferences,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.lod_tool_props = PointerProperty(type=LOD_Tool_Props)
    bpy.app.handlers.depsgraph_update_post.append(lod_handler)

def unregister():
    try:
        bpy.app.handlers.depsgraph_update_post.remove(lod_handler)
    except:
        pass
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.lod_tool_props

if __name__ == "__main__":
    register()