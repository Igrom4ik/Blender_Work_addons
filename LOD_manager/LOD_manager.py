bl_info = {
    "name": "LOD Manager",
    "author": "Igrom",
    "version": (3, 27),
    "blender": (4, 5, 0),
    "location": "3D View > Sidebar > LOD",
    "description": "LOD UI with dynamic percentage-based thresholds, Ctrl/Shift multi-selection, Ctrl+Mouse Wheel group switching, and camera-based auto-switching",
    "category": "Object",
    "doc_url": "https://github.com/Igrom/LODManager/wiki",
    "tracker_url": "https://github.com/Igrom/LODManager/issues"
}

import bpy
import re
import json
import math
import numpy as np
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

# Global cache for LOD groups and color state
LOD_GROUPS_CACHE = []
COLORING_ENABLED_LAST = False

# Translation dictionary (for UI localization)
TRANSLATIONS = {
    "ru": {
        "addon_name": "LOD Manager",
        "description_tab": "Описание",
        "description_label": "Инструкция по использованию LOD Manager:",
        "desc_refresh": "• Обновить группы LOD — сканирует сцену и находит объекты с суффиксом '_LOD0', '_LOD1' и т.п.",
        "desc_select": "• Клик по имени LOD — выбирает одну группу (изоляция остальных LOD-объектов).",
        "desc_ctrl": "• Ctrl + Клик — добавляет/удаляет LOD из текущего выбора.",
        "desc_shift": "• Shift + Клик — выбирает диапазон LOD-групп.",
        "desc_ctrl_wheel": "• Ctrl + Колесо мыши — переключает активную LOD-группу (вверх/вниз).",
        "desc_polycount": "• Поликаунт — отображает общее и видимое количество полигонов для LOD-объектов.",
        "desc_colors": "• Цвета — задают отображаемый цвет для LOD-объектов по группам.",
        "desc_auto_lod": "• Авто LOD — переключает LODы автоматически по процентным диапазонам расстояний до камеры.",
        "desc_restrict": "• Ограничить камерой — LOD-объекты управляются только для рендера, в 3D-вьюпорте видны по ручному выбору, если камера не активна.",
        "desc_warning": "⚠ Для корректной работы LOD-объекты должны называться как 'Name_LOD0', 'Name_LOD1', и т.п.",
        "refresh_groups": "Обновить группы LOD",
        "select_item": "Выделить LOD-группу",
        "scroll_lod_group": "Переключить LOD-группу",
        "set_active_lod": "Установить активную LOD-группу",
        "enable_color": "Включить цвета",
        "show_polycount": "Показать поликаунт",
        "auto_lod_enabled": "Включить авто LOD",
        "restrict_to_camera": "Ограничить камерой",
        "camera": "Камера",
        "threshold": "Порог для LOD{0} (%)",
        "lod_color": "LOD{0} Цвет",
        "total_polycount": "Общий поликаунт: {0}",
        "visible_polycount": "Видимый поликаунт: {0}",
        "total_visible_polycount": "Общий видимый поликаунт: {0}",
        "error_polycount": "Ошибка чтения данных",
        "language": "Язык",
        "language_ru": "Русский",
        "language_en": "English",
        "no_lod_objects": "LOD-объекты не найдены",
        "update_manually": "Обновить вручную",
        "base_distance": "Базовое расстояние",
        "auto_calculate_base": "Автоматически вычислить базовое расстояние",
    },
    "en": {
        "addon_name": "LOD Manager",
        "description_tab": "Description",
        "description_label": "Instructions for using LOD Manager:",
        "desc_refresh": "• Refresh LOD Groups — scans the scene for objects with '_LOD0', '_LOD1', etc. suffixes.",
        "desc_select": "• Click on LOD name — selects one group (isolates other LOD objects).",
        "desc_ctrl": "• Ctrl + Click — adds/removes LOD from current selection.",
        "desc_shift": "• Shift + Click — selects a range of LOD groups.",
        "desc_ctrl_wheel": "• Ctrl + Mouse Wheel — switches active LOD group (up/down).",
        "desc_polycount": "• Polycount — displays total and visible polygon counts for LOD objects.",
        "desc_colors": "• Colors — set display colors for LOD objects by group.",
        "desc_auto_lod": "• Auto LOD — switches LODs automatically based on percentage distance ranges to camera.",
        "desc_restrict": "• Restrict to Camera — LOD objects are managed only for render, visible in 3D viewport by manual selection if camera is not active.",
        "desc_warning": "⚠ For proper operation, LOD objects must be named like 'Name_LOD0', 'Name_LOD1', etc.",
        "refresh_groups": "Refresh LOD Groups",
        "select_item": "Select LOD Group",
        "scroll_lod_group": "Switch LOD Group",
        "set_active_lod": "Set Active LOD Group",
        "enable_color": "Enable Colors",
        "show_polycount": "Show Polycount",
        "auto_lod_enabled": "Enable Auto LOD",
        "restrict_to_camera": "Restrict to Camera",
        "camera": "Camera",
        "threshold": "Threshold for LOD{0} (%)",
        "lod_color": "LOD{0} Color",
        "total_polycount": "Total polycount: {0}",
        "visible_polycount": "Visible polycount: {0}",
        "total_visible_polycount": "Total visible polycount: {0}",
        "error_polycount": "Error reading polycount data",
        "language": "Language",
        "language_ru": "Русский",
        "language_en": "English",
        "no_lod_objects": "No LOD objects found",
        "update_manually": "Update Manually",
        "base_distance": "Base Distance",
        "auto_calculate_base": "Auto Calculate Base Distance",
    }
}

def get_translation(context, key, *args):
    """Get a translated string based on current language setting."""
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
        for key in ["desc_refresh", "desc_select", "desc_ctrl", "desc_shift", "desc_ctrl_wheel",
                    "desc_polycount", "desc_colors", "desc_auto_lod", "desc_restrict"]:
            col.label(text=get_translation(context, key))
        col.separator()
        col.label(text=get_translation(context, "desc_warning"))

class LODListItem(bpy.types.PropertyGroup):
    name: StringProperty()
    selected: BoolProperty(default=False)

class ThresholdItem(bpy.types.PropertyGroup):
    value: FloatProperty(
        name="Percentage",
        description="Percentage of base distance for LOD switch",
        min=0.0,
        max=100.0,
        default=50.0,
        update=lambda self, ctx: update_lod_selection(ctx.scene)
    )

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
    """Convert HSV to RGB color tuple."""
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
    """Generate a distinct color for an LOD group level."""
    hue = (index / total) % 1.0
    saturation = uniform(0.7, 1.0)
    value = uniform(0.7, 1.0)
    return hsv_to_rgb(hue, saturation, value)

def update_lod_selection(scene):
    props = scene.lod_tool_props
    global COLORING_ENABLED_LAST, LOD_GROUPS_CACHE
    print("=== Updating LOD selection ===")
    if not props.has_lod_objects:
        print("No LOD objects detected.")
        return

    # Automatic LOD mode
    if props.auto_lod_enabled:
        if not props.camera:
            print("Auto LOD enabled but no camera selected.")
            return
        camera_loc = props.camera.matrix_world.translation
        # Rebuild valid groups to avoid ReferenceError
        valid_groups = []
        for group in LOD_GROUPS_CACHE:
            if not group['lods']:
                continue
            base_obj = group['lods'][0][1]
            if base_obj and base_obj.name in scene.objects:
                valid_groups.append(group)
            else:
                print(f"Object {base_obj.name if base_obj else 'None'} removed, skipping group.")
        LOD_GROUPS_CACHE = valid_groups
        if not LOD_GROUPS_CACHE:
            return

        # Dynamically calculate base_distance as max distance to LOD objects
        max_distance = 0.0
        for group in LOD_GROUPS_CACHE:
            base_obj = group['lods'][0][1]
            distance = (base_obj.matrix_world.translation - camera_loc).length
            max_distance = max(max_distance, distance)
        base_distance = max(max_distance, 1.0) if max_distance > 0.0 else props.base_distance
        print(f"Dynamic base_distance: {base_distance} units")

        # Prepare sorted threshold distances (as percentages of base_distance)
        thr_values = sorted([t.value / 100.0 * base_distance for t in props.thresholds])
        print(f"Threshold values (absolute): {thr_values}")

        # Initialize polycount
        visible_polycount = 0  # Сбрасываем перед подсчётом

        # Optional: prepare color map for levels
        color_map = {}
        if props.enable_color:
            for idx, item in enumerate(props.lod_list):
                try:
                    lvl = int(item.name[3:])
                    color_map[lvl] = props.lod_colors[idx].color
                except:
                    continue

        # Apply LOD visibility and colors per group individually
        for group_entry in LOD_GROUPS_CACHE:
            if not group_entry['lods']:
                continue
            base_obj = group_entry['lods'][0][1]
            if not base_obj or base_obj.name not in scene.objects:
                continue
            distance = (base_obj.matrix_world.translation - camera_loc).length
            print(f"Group {group_entry['base_name']}, Distance: {distance}")

            # Determine LOD index for this group
            lod_index = 0
            for i, thr in enumerate(thr_values):
                if distance >= thr:
                    lod_index = i + 1
                else:
                    break
            lod_index = min(lod_index, group_entry['max_index'])
            print(f"Group {group_entry['base_name']}, LOD index: {lod_index}")

            is_camera_active = (scene.camera == props.camera)
            for i, (lod_num, lod_obj) in enumerate(group_entry['lods']):
                if lod_obj and lod_obj.name in scene.objects:
                    is_visible = (i == lod_index)
                    lod_obj.hide_render = not is_visible
                    if not (is_camera_active and props.restrict_to_camera):
                        lod_obj.hide_viewport = not is_visible
                    # Assign color if enabled
                    if props.enable_color:
                        lod_obj.color = color_map.get(lod_num, (1.0, 1.0, 1.0, 1.0))
                    elif COLORING_ENABLED_LAST:
                        lod_obj.color = (1.0, 1.0, 1.0, 1.0)
                    # Count polygons only for visible LOD objects
                    if is_visible and lod_obj.type == 'MESH' and lod_obj.data:
                        visible_polycount += len(lod_obj.data.polygons)
                else:
                    print(f"Object {lod_obj.name if lod_obj else 'None'} removed, skipping.")

        # Save polycount to cache
        props.polycount_cache = json.dumps({"mode": "auto", "visible_polycount": int(visible_polycount)})
        print(f"Visible polycount in auto mode: {visible_polycount}")

        # Hide all non-LOD objects (in auto LOD mode)
        lod_objs_set = {lod_obj for group in LOD_GROUPS_CACHE for (_, lod_obj) in group['lods'] if lod_obj and lod_obj.name in scene.objects}
        is_camera_active = (scene.camera == props.camera)
        for obj in scene.objects:
            if obj.type == 'MESH' and obj not in lod_objs_set:
                obj.hide_render = True
                if not (is_camera_active and props.restrict_to_camera):
                    obj.hide_viewport = True

    else:
        # Manual LOD mode (оставляем без изменений, так как проблема только в авто-режиме)
        selected_levels = [int(item.name[3:]) for item in props.lod_list if item.selected]
        print(f"Manual mode selected LOD levels: {selected_levels}")
        show_all = (len(selected_levels) == 0)
        poly_data = {}
        color_map = {}
        if props.enable_color:
            for idx, item in enumerate(props.lod_list):
                try:
                    lvl = int(item.name[3:])
                    color_map[lvl] = props.lod_colors[idx].color
                except:
                    continue
        visible_polycount_total = 0
        for group_entry in LOD_GROUPS_CACHE:
            for lod_num, lod_obj in group_entry['lods']:
                if lod_obj and lod_obj.name in scene.objects:
                    # Determine visibility based on selection
                    if show_all or lod_num in selected_levels:
                        lod_obj.hide_render = False
                        lod_obj.hide_viewport = False
                        visible = True
                    else:
                        lod_obj.hide_render = True
                        lod_obj.hide_viewport = True
                        visible = False
                    if props.enable_color:
                        lod_obj.color = color_map.get(lod_num, (1.0, 1.0, 1.0, 1.0))
                    elif COLORING_ENABLED_LAST:
                        lod_obj.color = (1.0, 1.0, 1.0, 1.0)
                    # Count polygons for polycount stats
                    if lod_obj.type == 'MESH' and lod_obj.data:
                        polycount = len(lod_obj.data.polygons)
                    else:
                        polycount = 0
                    key = str(lod_num)
                    if key not in poly_data:
                        poly_data[key] = {"total": 0, "visible": 0}
                    poly_data[key]["total"] += polycount
                    if visible:
                        poly_data[key]["visible"] += polycount
                        visible_polycount_total += polycount
                else:
                    print(f"Object {lod_obj.name if lod_obj else 'None'} removed, skipping.")
        props.polycount_cache = json.dumps({"mode": "manual", "data": poly_data})

    COLORING_ENABLED_LAST = props.enable_color
    print("=== Update complete ===")

class LOD_UL_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        row.active = item.selected
        op = row.operator("lod.select_item", text=item.name, emboss=False,
                          icon='LAYER_USED' if item.selected else 'LAYER_ACTIVE')
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
        for key in ["desc_refresh", "desc_select", "desc_ctrl", "desc_shift", "desc_ctrl_wheel",
                    "desc_polycount", "desc_colors", "desc_auto_lod", "desc_restrict"]:
            col.label(text=get_translation(context, key))
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
        layout.prop(props, "language")  # Язык
        layout.operator("lod.refresh_groups", text=get_translation(context, "refresh_groups"), icon='FILE_REFRESH')  # Обновление групп
        if not props.has_lod_objects:
            layout.label(text=get_translation(context, "no_lod_objects"), icon='INFO')
            return
        layout.template_list("LOD_UL_items", "", props, "lod_list", props, "lod_active_index",
                             rows=max(1, min(len(props.lod_list), 8)))  # Список LOD
        layout.separator()
        layout.prop(props, "enable_color", text=get_translation(context, "enable_color"), icon='COLOR')  # Цвета
        if props.enable_color:
            for i, color_item in enumerate(props.lod_colors):
                layout.prop(color_item, "color", text=get_translation(context, "lod_color", i))
        layout.separator()
        layout.prop(props, "auto_lod_enabled", text=get_translation(context, "auto_lod_enabled"), icon='AUTO')  # Авто-режим
        if props.auto_lod_enabled:
            layout.prop(props, "restrict_to_camera", text=get_translation(context, "restrict_to_camera"), icon='RENDER_STILL')  # Ограничение камерой
            layout.prop(props, "camera", text=get_translation(context, "camera"), icon='CAMERA_DATA')  # Выбор камеры
            layout.prop(props, "base_distance", text=get_translation(context, "base_distance"), icon='EMPTY_AXIS')  # Базовое расстояние
            layout.operator("lod.auto_calculate_base", text=get_translation(context, "auto_calculate_base"), icon='ZOOM_SELECTED')  # Авто-расчёт
            for i, threshold in enumerate(props.thresholds):
                label = get_translation(context, "threshold", i + 1)
                layout.prop(threshold, "value", text=label, slider=True)  # Пороги
            layout.operator("lod.update_manually", text=get_translation(context, "update_manually"), icon='FILE_REFRESH')  # Ручное обновление
        layout.separator()
        row = layout.row()
        row.prop(props, "show_polycount", text=get_translation(context, "show_polycount"),
                 icon="TRIA_DOWN" if props.show_polycount else "TRIA_RIGHT", emboss=False)  # Поликаунт
        if props.show_polycount and props.polycount_cache:
            try:
                cache = json.loads(props.polycount_cache)
                if cache.get("mode") == "manual":
                    layout.label(text=get_translation(context, "total_polycount"))
                    for lod_key in sorted(cache["data"].keys(), key=int):
                        data = cache["data"][lod_key]
                        box = layout.box()
                        box.label(text=f"LOD{lod_key}:")
                        box.label(text=get_translation(context, "total_polycount", data['total']))
                        box.label(text=get_translation(context, "visible_polycount", data['visible']))
                elif cache.get("mode") == "auto":
                    layout.label(text=get_translation(context, "total_visible_polycount", cache['visible_polycount']))
            except Exception as e:
                print(f"Error parsing polycount cache: {e}")
                layout.label(text=get_translation(context, "error_polycount"))

class LOD_Tool_Props(bpy.types.PropertyGroup):
    lod_list: CollectionProperty(type=LODListItem)
    lod_active_index: IntProperty(default=-1)
    polycount_cache: StringProperty(default="")
    show_polycount: BoolProperty(default=False)
    enable_color: BoolProperty(default=False, update=lambda self, ctx: update_lod_selection(ctx.scene))
    auto_lod_enabled: BoolProperty(default=False, update=lambda self, ctx: update_lod_selection(ctx.scene))
    restrict_to_camera: BoolProperty(
        default=False,
        update=lambda self, ctx: update_lod_selection(ctx.scene),
        description="Restrict LOD visibility to render, leaving 3D viewport unaffected unless camera is not active"
    )
    camera: PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'CAMERA',
        update=lambda self, ctx: update_lod_selection(ctx.scene)
    )
    base_distance: FloatProperty(
        name="Base Distance",
        description="Reference distance for percentage-based thresholds (manual override)",
        default=100.0,
        min=0.0,
        subtype='DISTANCE',
        unit='LENGTH'
    )
    thresholds: CollectionProperty(type=ThresholdItem)
    lod_colors: CollectionProperty(type=LODColorItem)
    language: EnumProperty(
        items=[("ru", "Русский", ""), ("en", "English", "")],
        default="en"
    )
    has_lod_objects: BoolProperty(default=False)

class LOD_OT_select_item(bpy.types.Operator):
    bl_idname = "lod.select_item"
    bl_label = "Select LOD Group"
    bl_options = {'INTERNAL'}
    index: IntProperty()
    def invoke(self, context, event):
        props = context.scene.lod_tool_props
        items = props.lod_list
        idx = self.index
        if not event.ctrl and not event.shift:
            for it in items:
                it.selected = False
            items[idx].selected = True
        elif event.ctrl:
            items[idx].selected = not items[idx].selected
        elif event.shift and props.lod_active_index >= 0:
            start, end = min(props.lod_active_index, idx), max(props.lod_active_index, idx)
            for i in range(start, end + 1):
                items[i].selected = True
        # Update active index for scroll operations
        if props.lod_active_index < 0 or not items[props.lod_active_index].selected:
            props.lod_active_index = idx
        update_lod_selection(context.scene)
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}

class LOD_OT_scroll_lod_group(bpy.types.Operator):
    bl_idname = "lod.scroll_lod_group"
    bl_label = "Switch LOD Group"
    bl_options = {'REGISTER', 'UNDO'}
    direction: StringProperty(default="UP")
    @classmethod
    def poll(cls, context):
        props = context.scene.lod_tool_props
        return props.has_lod_objects and not props.auto_lod_enabled and context.mode == 'OBJECT'
    def execute(self, context):
        props = context.scene.lod_tool_props
        items = props.lod_list
        if not items:
            return {'CANCELLED'}
        current_idx = max(0, props.lod_active_index)
        new_idx = (current_idx + (1 if self.direction == "UP" else -1)) % len(items)
        for item in items:
            item.selected = False
        items[new_idx].selected = True
        props.lod_active_index = new_idx
        update_lod_selection(context.scene)
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}

class LOD_OT_set_active_lod(bpy.types.Operator):
    bl_idname = "lod.set_active_lod"
    bl_label = "Set Active LOD Group"
    bl_options = {'REGISTER', 'UNDO'}
    index: IntProperty()
    @classmethod
    def poll(cls, context):
        props = context.scene.lod_tool_props
        return props.has_lod_objects and not props.auto_lod_enabled and context.mode == 'OBJECT'
    def execute(self, context):
        props = context.scene.lod_tool_props
        items = props.lod_list
        idx = self.index
        if not 0 <= idx < len(items):
            return {'CANCELLED'}
        for item in items:
            item.selected = False
        items[idx].selected = True
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
        props.thresholds.clear()
        props.has_lod_objects = False
        # Reset the cached groups
        global LOD_GROUPS_CACHE
        LOD_GROUPS_CACHE = []
        # Identify all LOD objects and group by base object name
        lod_names = set()
        lod_groups_temp = {}
        for obj in context.scene.objects:
            match = LOD_PATTERN.match(obj.name)
            if match:
                lod_num = match.group(1)
                base_name = obj.name.rsplit('_LOD', 1)[0]
                lod_names.add(lod_num)
                lod_groups_temp.setdefault(base_name, []).append((int(lod_num), obj))
        print(f"Found LOD levels: {lod_names}")
        if lod_groups_temp:
            props.has_lod_objects = True
            sorted_lod_levels = sorted({int(x) for x in lod_names})
            for lod in sorted_lod_levels:
                props.lod_list.add().name = f"LOD{lod}"
                props.lod_colors.add().color = generate_distinct_color(int(lod), len(sorted_lod_levels))
            if props.lod_list:
                props.lod_list[0].selected = True
                props.lod_active_index = 0
            # Create default thresholds (evenly spaced percentages)
            num_thresholds_needed = len(sorted_lod_levels) - 1
            for i in range(num_thresholds_needed):
                item = props.thresholds.add()
                item.value = (i + 1) * 100.0 / num_thresholds_needed
            print(f"Initialized {len(props.thresholds)} thresholds.")
            # Build the cached LOD groups list
            for base_name, lod_list in lod_groups_temp.items():
                lod_list.sort(key=lambda x: x[0])
                max_index = len(lod_list) - 1
                LOD_GROUPS_CACHE.append({
                    "base_name": base_name,
                    "lods": lod_list,
                    "max_index": max_index
                })
            # Immediately update LOD selection to apply current settings
            update_lod_selection(context.scene)
        props.polycount_cache = ""
        return {'FINISHED'}

class LOD_OT_auto_calculate_base(bpy.types.Operator):
    bl_idname = "lod.auto_calculate_base"
    bl_label = "Auto Calculate Base Distance"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        props = context.scene.lod_tool_props
        if not props.camera or not props.has_lod_objects:
            return {'CANCELLED'}
        camera_loc = props.camera.matrix_world.translation
        max_distance = 0.0
        for group in LOD_GROUPS_CACHE:
            if not group['lods']:
                continue
            base_obj = group['lods'][0][1]
            if base_obj and base_obj.name in context.scene.objects:
                distance = (base_obj.matrix_world.translation - camera_loc).length
                max_distance = max(max_distance, distance)
        props.base_distance = max(max_distance, 1.0) if max_distance > 0.0 else 100.0
        update_lod_selection(context.scene)
        return {'FINISHED'}

class LOD_OT_update_manually(bpy.types.Operator):
    bl_idname = "lod.update_manually"
    bl_label = "Update Manually"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        update_lod_selection(context.scene)
        return {'FINISHED'}

def lod_handler(scene, depsgraph):
    # Called on any dependency graph update (e.g. object moved)
    props = scene.lod_tool_props
    if props.has_lod_objects and bpy.context.mode == 'OBJECT' and not bpy.context.active_operator:
        update_lod_selection(scene)

def frame_handler(scene, depsgraph):
    # Called on frame change (for animations)
    props = scene.lod_tool_props
    if props.has_lod_objects and props.auto_lod_enabled and props.camera:
        update_lod_selection(scene)

classes = (
    LODListItem,
    ThresholdItem,
    LODColorItem,
    LOD_Tool_Props,
    LOD_UL_items,
    LOD_OT_select_item,
    LOD_OT_scroll_lod_group,
    LOD_OT_set_active_lod,
    LOD_OT_refresh_groups,
    LOD_OT_auto_calculate_base,
    LOD_OT_update_manually,
    LOD_PT_description,
    LOD_PT_panel,
    LODManagerPreferences,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.lod_tool_props = PointerProperty(type=LOD_Tool_Props)
    # Add keymaps for Ctrl + Mouse Wheel LOD cycling
    wm = bpy.context.window_manager
    if kc := wm.keyconfigs.addon:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        for direction, wheel in [("DOWN", 'WHEELUPMOUSE'), ("UP", 'WHEELDOWNMOUSE')]:
            kmi = km.keymap_items.new('lod.scroll_lod_group', wheel, 'PRESS', ctrl=True)
            kmi.properties.direction = direction
    bpy.app.handlers.depsgraph_update_post.append(lod_handler)
    bpy.app.handlers.frame_change_post.append(frame_handler)
    print("LOD Manager registered.")

def unregister():
    try:
        bpy.app.handlers.depsgraph_update_post.remove(lod_handler)
        bpy.app.handlers.frame_change_post.remove(frame_handler)
    except Exception:
        pass
    wm = bpy.context.window_manager
    if kc := wm.keyconfigs.addon:
        if km := kc.keymaps.get('3D View'):
            for kmi in [k for k in km.keymap_items if k.idname == 'lod.scroll_lod_group']:
                km.keymap_items.remove(kmi)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.lod_tool_props
    print("LOD Manager unregistered.")

if __name__ == "__main__":
    register()
    