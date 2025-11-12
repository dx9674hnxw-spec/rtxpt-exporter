bl_info = {
    "name": "RTXPT Exporter",
    "author": "XyloN",
    "version": (1, 2, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > RTXPT",
    "description": ("Permet l'export des sous-collections de 'EXPORT_TEST' en modèles glTF "
                    "et JSON de scène compatible RTXPT, avec mise à jour et gestion des doublons. "
                    "Chemin RTXPT.exe configurable dans les préférences de l'addon."),
    "warning": "",
    "wiki_url": "https://github.com/dx9674hnxw-spec/rtxpt-exporter",
    "tracker_url": "https://github.com/dx9674hnxw-spec/rtxpt-exporter/issues",
    "category": "Import-Export",
    "support": "COMMUNITY",
    "doc_url": "https://github.com/dx9674hnxw-spec/rtxpt-exporter/blob/main/README.md"
}

# 1. Imports & Tools Utilitaires

import bpy
import os
import json
from bpy.props import StringProperty, FloatVectorProperty, FloatProperty, BoolProperty, EnumProperty, PointerProperty

def safe_color(val, default=(1.0, 1.0, 1.0)):
    try:
        if hasattr(val, "__iter__"):
            return [float(x) for x in val[:3]]
        return [float(val)]*3
    except Exception:
        return list(default)

def get_collections_enum(self, context):
    root_collection = bpy.data.collections.get("EXPORT_TEST")
    items = []
    if root_collection:
        for col in root_collection.children:
            items.append((col.name, col.name, ""))
    if not items:
        items.append(("NONE", "None", "No collections found"))
    return items

# 2. Préférences d'addon

class RTXPT_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    rtxpt_exe: StringProperty(
        name="RTXPT.exe Path",
        subtype='FILE_PATH',
        default=""
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Global RTXPT Settings")
        layout.prop(self, "rtxpt_exe")

# 3. Propriétés de projet et caméra

class RTXPT_Proj_Props(bpy.types.PropertyGroup):
    assets_root: StringProperty(
        name="RTXPT 'Assets' Folder",
        subtype='DIR_PATH',
        default="//rtxpt_v.1.7.0_binaries/Assets"
    )
    project_name: StringProperty(
        name="Project Name",
        default="TestProject"
    )
    selected_node: EnumProperty(
        name="Selected Node",
        description="Select collection node to modify",
        items=get_collections_enum
    )
    node_translation: FloatVectorProperty(
        name = "Translation",
        subtype = 'TRANSLATION',
        size=3,
        default=(0.0, 0.0, 0.0)
    )
    node_scale: FloatProperty(
        name="Scale",
        default=1.0,
        min=0.0
    )

class RTXPT_Camera_Props(bpy.types.PropertyGroup):
    translation: FloatVectorProperty(
        name="Translation",
        subtype='TRANSLATION',
        size=3,
        default=(-20.0, 1.8, 12.0)
    )
    rotation: FloatVectorProperty(
        name="Rotation (Quaternion)",
        size=4,
        default=(0.0, -0.7071068, 0.0, 0.7071068)
    )
    vertical_fov: FloatProperty(
        name="Vertical FOV",
        default=1.04,
        min=0.0
    )
    z_near: FloatProperty(
        name="Z Near",
        default=0.001,
        min=0.0
    )
    exposure_value: FloatProperty(
        name="Exposure Value",
        default=-1.0
    )
    enable_auto_exposure: BoolProperty(
        name="Enable Auto Exposure",
        default=True
    )
    exposure_compensation: FloatProperty(
        name="Exposure Compensation",
        default=0.8
    )
    exposure_value_min: FloatProperty(
        name="Exposure Value Min",
        default=-4.0
    )
    exposure_value_max: FloatProperty(
        name="Exposure Value Max",
        default=6.0
    )

# 4. Panel UI main exporter + camera + material edit

class RTXPT_PT_ExportPanel(bpy.types.Panel):
    bl_label = "RTXPT Project Exporter"
    bl_idname = "RTXPT_PT_proj_export_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RTXPT"

    def draw(self, context):
        scene = context.scene
        props = scene.rtxpt_proj_props
        layout = self.layout
        layout.prop(props, "assets_root")
        layout.prop(props, "project_name")

        root_collection = bpy.data.collections.get("EXPORT_TEST")
        if root_collection:
            layout.label(text="Select node to modify:")
            layout.prop(props, "selected_node", text="Node")

            selected_name = props.selected_node
            col = root_collection.children.get(selected_name)
            if col:
                layout.label(text=f"Edit properties for {selected_name}:")
                layout.prop(props, "node_translation", text="Translation")
                layout.prop(props, "node_scale", text="Scale")

        layout.operator("rtxpt.project_export", icon="EXPORT")

class RTXPT_PT_CameraPanel(bpy.types.Panel):
    bl_label = "RTXPT Camera Settings"
    bl_idname = "RTXPT_PT_camera_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RTXPT"

    def draw(self, context):
        cam_props = context.scene.rtxpt_camera_props
        layout = self.layout

        layout.prop(cam_props, "translation")
        layout.prop(cam_props, "rotation")
        layout.prop(cam_props, "vertical_fov")
        layout.prop(cam_props, "z_near")
        layout.prop(cam_props, "exposure_value")
        layout.prop(cam_props, "enable_auto_exposure")
        layout.prop(cam_props, "exposure_compensation")
        layout.prop(cam_props, "exposure_value_min")
        layout.prop(cam_props, "exposure_value_max")

class RTXPT_PT_MaterialEditPanel(bpy.types.Panel):
    bl_label = "Edit ExcludeFromNEE Material"
    bl_idname = "RTXPT_PT_material_edit_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RTXPT"

    def draw(self, context):
        layout = self.layout
        props = context.scene.rtxpt_material_edit_props

        layout.prop(props, "material_name")
        layout.prop(props, "exclude_from_nee")

        row = layout.row()
        row.operator("rtxpt.material_edit_load", text="Load Material JSON")
        row.operator("rtxpt.material_edit_save", text="Save Material JSON")

# 5. Exporteur principal et opérateurs edits matière

class RTXPT_OT_ProjectExport(bpy.types.Operator):
    bl_idname = "rtxpt.project_export"
    bl_label = "Export RTXPT Project"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.rtxpt_proj_props
        cam_props = context.scene.rtxpt_camera_props
        addon_prefs = context.preferences.addons[__name__].preferences

        project = props.project_name.strip()
        if not project:
            self.report({"ERROR"}, "Please enter a valid project name.")
            return {"CANCELLED"}

        assets_root = bpy.path.abspath(props.assets_root)
        model_root = os.path.join(assets_root, "Models", project)
        os.makedirs(model_root, exist_ok=True)
        json_path = os.path.join(assets_root, f"{project}.scene.json")

        root_collection = bpy.data.collections.get("EXPORT_TEST")
        if not root_collection:
            self.report({"ERROR"}, "❌ Collection 'EXPORT_TEST' not found in the Blender scene.")
            return {"CANCELLED"}

        warning_objs = []
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "models" not in data:
                        data["models"] = []
                    if "graph" not in data:
                        data["graph"] = []
            except Exception as e:
                self.report({"WARNING"}, f"Failed to load existing JSON, creating new one: {e}")
                data = {"models": [], "graph": []}
        else:
            data = {"models": [], "graph": []}

        new_models = []
        new_graph = []

        selected_node_name = props.selected_node
        for i, collection in enumerate(root_collection.children):
            if len(collection.objects) == 0:
                continue

            gltf_name = f"{collection.name}.gltf"
            gltf_folder = os.path.join(model_root, collection.name)
            os.makedirs(gltf_folder, exist_ok=True)
            gltf_path = os.path.join(gltf_folder, gltf_name)

            bpy.ops.object.select_all(action='DESELECT')
            for obj in collection.objects:
                obj.select_set(True)
                if obj.type == 'MESH':
                    has_mat = False
                    if hasattr(obj, 'material_slots') and len(obj.material_slots) > 0:
                        has_mat = any(slot.material is not None for slot in obj.material_slots)
                    if not has_mat:
                        warning_objs.append(obj.name)

            bpy.ops.export_scene.gltf(
                filepath=gltf_path,
                use_selection=True,
                export_format='GLTF_SEPARATE',
                export_apply=True
            )

            if collection.objects:
                locs = [o.location for o in collection.objects]
                mean_loc = [sum(coord[i] for coord in locs) / len(locs) for i in range(3)]
            else:
                mean_loc = [0.0, 0.0, 0.0]

            rel_model_path = f"Models/{project}/{collection.name}/{gltf_name}"
            if rel_model_path not in data["models"]:
                new_models.append(rel_model_path)

            material_props = {}
            for obj in collection.objects:
                if hasattr(obj, 'material_slots'):
                    for slot in obj.material_slots:
                        if slot.material is not None:
                            mat = slot.material
                            if "ignore_neeshadowray" in mat:
                                material_props["ignore_neeshadowray"] = bool(mat["ignore_neeshadowray"])
                            if "exclude_from_nee" in mat and bool(mat["exclude_from_nee"]):
                                material_props["ExcludeFromNEE"] = True

            if collection.name == selected_node_name:
                translation = list(props.node_translation)
                scale = props.node_scale
            else:
                translation = [round(mean_loc[0], 3), round(mean_loc[1], 3), round(mean_loc[2], 3)]
                scale = 1.0

            node_info = {
                "name": collection.name,
                "model": i,
                "translation": translation,
                "scaling": scale
            }
            if material_props:
                node_info["material_properties"] = material_props

            existing_node = next((n for n in data["graph"] if n.get("name") == collection.name), None)
            if existing_node:
                existing_node.update(node_info)
            else:
                new_graph.append(node_info)

        data["models"].extend(new_models)
        data["graph"].extend(new_graph)

        if not any(n.get("name") == "Lights" for n in data["graph"]):
            data["graph"].append({
                "name": "Lights",
                "children": [{
                    "name": "Sky",
                    "type": "EnvironmentLight",
                    "radianceScale": [1, 1, 1],
                    "textureIndex": [0],
                    "rotation": [0],
                    "path": "==PROCEDURAL_SKY=="
                }]
            })

        if not any(n.get("name") == "Cameras" for n in data["graph"]):
            data["graph"].append({
                "name": "Cameras",
                "children": [{
                    "name": "Outside",
                    "type": "PerspectiveCamera",
                    "translation": list(cam_props.translation),
                    "rotation": list(cam_props.rotation),
                    "verticalFov": cam_props.vertical_fov,
                    "zNear": cam_props.z_near,
                    "exposureValue": cam_props.exposure_value,
                    "enableAutoExposure": cam_props.enable_auto_exposure,
                    "exposureCompensation": cam_props.exposure_compensation,
                    "exposureValueMin": cam_props.exposure_value_min,
                    "exposureValueMax": cam_props.exposure_value_max
                }]
            })

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.report({"ERROR"}, f"Error writing JSON: {e}")
            return {"CANCELLED"}

        materials_folder = os.path.join(assets_root, "Materials")
        os.makedirs(materials_folder, exist_ok=True)
        unique_materials = set()
        for collection in root_collection.children:
            for obj in collection.objects:
                if hasattr(obj, 'material_slots'):
                    for slot in obj.material_slots:
                        if slot.material is not None:
                            unique_materials.add(slot.material)

        for mat in unique_materials:
            mat_json = {
                "AlphaCutoff": getattr(mat, "alpha_threshold", 0.5),
                "BaseOrDiffuseColor": safe_color(getattr(mat, "diffuse_color", (1.0, 1.0, 1.0))),
                "DiffuseTransmissionFactor": getattr(mat, "diffuse_transmission_factor", 0.0),
                "EmissiveColor": safe_color(getattr(mat, "emissive_color", (0.0, 0.0, 0.0))),
                "EmissiveIntensity": getattr(mat, "emissive_intensity", 1.0),
                "EnableAlphaTesting": False,
                "EnableAsAnalyticLightProxy": False,
                "EnableBaseTexture": True,
                "EnableEmissiveTexture": True,
                "EnableNormalTexture": True,
                "EnableOcclusionRoughnessMetallicTexture": True,
                "EnableTransmission": True,
                "EnableTransmissionTexture": True,
                "ExcludeFromNEE": ("exclude_from_nee" in mat and bool(mat["exclude_from_nee"])),
                "IoR": getattr(mat, "ior", 2.0),
                "Metalness": getattr(mat, "metallic", 0.0),
                "MetalnessInRedChannel": False,
                "NestedPriority": getattr(mat, "nested_priority", 14),
                "NormalTextureScale": getattr(mat, "normal_scale", 0.0),
                "Opacity": getattr(mat, "opacity", 1.0),
                "PSDDominantDeltaLobe": 0,
                "PSDExclude": False,
                "Roughness": getattr(mat, "roughness", 0.0),
                "ShadowNoLFadeout": 0.0,
                "SpecularColor": safe_color(getattr(mat, "specular_color", (0.0, 0.0, 0.0))),
                "ThinSurface": getattr(mat, "thin_surface", False),
                "TransmissionFactor": getattr(mat, "transmission_factor", 1.0),
                "UseSpecularGlossModel": False,
                "VolumeAttenuationColor": [1.0, 1.0, 1.0],
                "VolumeAttenuationDistance": 3.4028234663852886e+38,
                "version": 1,
            }
            mat_path = os.path.join(materials_folder, f"{mat.name}.material.json")
            with open(mat_path, "w", encoding="utf-8") as f:
                json.dump(mat_json, f, indent=2)

        exe_path = addon_prefs.rtxpt_exe
        if exe_path and os.path.isfile(bpy.path.abspath(exe_path)):
            import subprocess
            try:
                subprocess.Popen([bpy.path.abspath(exe_path), "--scene", json_path])
                self.report({"INFO"}, f"RTXPT launched from: {exe_path}")
            except Exception as e:
                self.report({"WARNING"}, f"Failed to launch RTXPT.exe: {e}")

        if warning_objs:
            unique_objs = ', '.join(set(warning_objs))
            self.report({'WARNING'}, f"Warning: The following objects have no material and may cause RTXPT render crash: {unique_objs}")

        self.report({"INFO"}, f"Project export completed: {json_path}")
        return {"FINISHED"}

class RTXPT_MaterialEdit_Props(bpy.types.PropertyGroup):
    material_name: StringProperty(name="Material Name")
    exclude_from_nee: BoolProperty(name="Exclude From NEE", default=False)

class RTXPT_OT_MaterialEditLoad(bpy.types.Operator):
    bl_idname = "rtxpt.material_edit_load"
    bl_label = "Load Material JSON"

    def execute(self, context):
        props = context.scene.rtxpt_material_edit_props
        assets_root = bpy.path.abspath(props.assets_root) if hasattr(props, "assets_root") else bpy.path.abspath("//rtxpt_v.1.7.0_binaries/Assets")
        materials_folder = os.path.join(assets_root, "Materials")
        mat_filename = f"{props.material_name}.material.json"
        mat_path = os.path.join(materials_folder, mat_filename)
        if not os.path.exists(mat_path):
            self.report({"ERROR"}, f"Material file not found: {mat_path}")
            return {"CANCELLED"}

        with open(mat_path, "r", encoding="utf-8") as f:
            mat_json = json.load(f)

        props.exclude_from_nee = mat_json.get("ExcludeFromNEE", False)
        self.report({"INFO"}, f"Material data loaded for {props.material_name}")
        return {"FINISHED"}

class RTXPT_OT_MaterialEditSave(bpy.types.Operator):
    bl_idname = "rtxpt.material_edit_save"
    bl_label = "Save Material JSON"

    def execute(self, context):
        props = context.scene.rtxpt_material_edit_props
        assets_root = bpy.path.abspath(props.assets_root) if hasattr(props, "assets_root") else bpy.path.abspath("//rtxpt_v.1.7.0_binaries/Assets")
        materials_folder = os.path.join(assets_root, "Materials")
        mat_filename = f"{props.material_name}.material.json"
        mat_path = os.path.join(materials_folder, mat_filename)

        if not os.path.exists(mat_path):
            self.report({"ERROR"}, f"Material file not found: {mat_path}")
            return {"CANCELLED"}

        with open(mat_path, "r", encoding="utf-8") as f:
            mat_json = json.load(f)

        mat_json["ExcludeFromNEE"] = props.exclude_from_nee

        with open(mat_path, "w", encoding="utf-8") as f:
            json.dump(mat_json, f, indent=2)

        self.report({"INFO"}, f"Material file saved: {mat_path}")
        return {"FINISHED"}

# Register/Unregister

def register():
    bpy.utils.register_class(RTXPT_AddonPreferences)
    bpy.utils.register_class(RTXPT_OT_ProjectExport)
    bpy.utils.register_class(RTXPT_Proj_Props)
    bpy.utils.register_class(RTXPT_PT_ExportPanel)
    bpy.utils.register_class(RTXPT_Camera_Props)
    bpy.utils.register_class(RTXPT_PT_CameraPanel)
    bpy.utils.register_class(RTXPT_MaterialEdit_Props)
    bpy.utils.register_class(RTXPT_PT_MaterialEditPanel)
    bpy.utils.register_class(RTXPT_OT_MaterialEditLoad)
    bpy.utils.register_class(RTXPT_OT_MaterialEditSave)

    bpy.types.Scene.rtxpt_proj_props = bpy.props.PointerProperty(type=RTXPT_Proj_Props)
    bpy.types.Scene.rtxpt_camera_props = bpy.props.PointerProperty(type=RTXPT_Camera_Props)
    bpy.types.Scene.rtxpt_material_edit_props = bpy.props.PointerProperty(type=RTXPT_MaterialEdit_Props)

def unregister():
    del bpy.types.Scene.rtxpt_proj_props
    del bpy.types.Scene.rtxpt_camera_props
    del bpy.types.Scene.rtxpt_material_edit_props

    bpy.utils.unregister_class(RTXPT_OT_MaterialEditSave)
    bpy.utils.unregister_class(RTXPT_OT_MaterialEditLoad)
    bpy.utils.unregister_class(RTXPT_PT_MaterialEditPanel)
    bpy.utils.unregister_class(RTXPT_MaterialEdit_Props)
    bpy.utils.unregister_class(RTXPT_PT_CameraPanel)
    bpy.utils.unregister_class(RTXPT_Camera_Props)
    bpy.utils.unregister_class(RTXPT_PT_ExportPanel)
    bpy.utils.unregister_class(RTXPT_Proj_Props)
    bpy.utils.unregister_class(RTXPT_OT_ProjectExport)
    bpy.utils.unregister_class(RTXPT_AddonPreferences)

if __name__ == "__main__":
    register()
