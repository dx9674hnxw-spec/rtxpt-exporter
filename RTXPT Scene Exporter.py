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

import bpy
import os
import json
from bpy.props import StringProperty

class RTXPT_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    rtxpt_exe: StringProperty(
        name="Chemin RTXPT.exe",
        subtype='FILE_PATH',
        default=""
    )
    def draw(self, context):
        layout = self.layout
        layout.label(text="Configuration globale RTXPT")
        layout.prop(self, "rtxpt_exe")

class RTXPT_OT_ProjectExport(bpy.types.Operator):
    bl_idname = "rtxpt.project_export"
    bl_label = "Exporter Projet RTXPT"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.rtxpt_proj_props
        addon_prefs = context.preferences.addons[__name__].preferences
        project = props.project_name.strip()
        if not project:
            self.report({"ERROR"}, "Indique un nom de projet valide.")
            return {"CANCELLED"}

        assets_root = bpy.path.abspath(props.assets_root)
        model_root = os.path.join(assets_root, "Models", project)
        os.makedirs(model_root, exist_ok=True)
        json_path = os.path.join(assets_root, f"{project}.scene.json")

        root_collection = bpy.data.collections.get("EXPORT_TEST")
        if not root_collection:
            self.report({"ERROR"}, "❌ La collection 'EXPORT_TEST' n'existe pas dans la scène Blender.")
            return {"CANCELLED"}

        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "models" not in data:
                        data["models"] = []
                    if "graph" not in data:
                        data["graph"] = []
            except Exception as e:
                self.report({"WARNING"}, f"Erreur lecture JSON existant, création d'un nouveau: {e}")
                data = {"models": [], "graph": []}
        else:
            data = {"models": [], "graph": []}

        new_models = []
        new_graph = []

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

            rel_model_path = os.path.relpath(
                os.path.join("Models", project, collection.name, gltf_name),
                start=assets_root
            ).replace("\\", "/")

            if rel_model_path not in data["models"]:
                new_models.append(rel_model_path)

            existing_node = next((n for n in data["graph"] if n.get("name") == collection.name), None)
            node_info = {
                "name": collection.name,
                "model": i,
                "translation": [round(mean_loc[0], 3), round(mean_loc[1], 3), round(mean_loc[2], 3)],
                "scaling": 1
            }
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
                    "translation": [-20, 1.8, 12],
                    "rotation": [0, -0.7071068, 0, 0.7071068],
                    "verticalFov": 1.04,
                    "zNear": 0.001,
                    "exposureValue": -1.0
                }]
            })

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.report({"ERROR"}, f"Erreur écriture JSON : {e}")
            return {"CANCELLED"}

        # Optionnel : Lancer RTXPT.exe si le chemin est défini dans les préférences
        exe_path = addon_prefs.rtxpt_exe
        if exe_path and os.path.isfile(bpy.path.abspath(exe_path)):
            import subprocess
            try:
                subprocess.Popen([bpy.path.abspath(exe_path), "--scene", json_path])
                self.report({"INFO"}, f"Lancement RTXPT : {exe_path}")
            except Exception as e:
                self.report({"WARNING"}, f"Impossible de lancer RTXPT.exe : {e}")

        self.report({"INFO"}, f"Export projet terminé : {json_path}")
        return {"FINISHED"}

class RTXPT_Proj_Props(bpy.types.PropertyGroup):
    assets_root: StringProperty(
        name="Dossier 'Assets' RTXPT",
        subtype='DIR_PATH',
        default="//rtxpt_v.1.7.0_binaries/Assets"
    )
    project_name: StringProperty(
        name="Nom du projet",
        default="TestProjet"
    )

class RTXPT_PT_ExportPanel(bpy.types.Panel):
    bl_label = "RTXPT Project Exporter"
    bl_idname = "RTXPT_PT_proj_export_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RTXPT"

    def draw(self, context):
        props = context.scene.rtxpt_proj_props
        layout = self.layout
        layout.prop(props, "assets_root")
        layout.prop(props, "project_name")
        layout.operator("rtxpt.project_export", icon="EXPORT")

def register():
    bpy.utils.register_class(RTXPT_AddonPreferences)
    bpy.utils.register_class(RTXPT_OT_ProjectExport)
    bpy.utils.register_class(RTXPT_Proj_Props)
    bpy.utils.register_class(RTXPT_PT_ExportPanel)
    bpy.types.Scene.rtxpt_proj_props = bpy.props.PointerProperty(type=RTXPT_Proj_Props)

def unregister():
    del bpy.types.Scene.rtxpt_proj_props
    bpy.utils.unregister_class(RTXPT_PT_ExportPanel)
    bpy.utils.unregister_class(RTXPT_Proj_Props)
    bpy.utils.unregister_class(RTXPT_OT_ProjectExport)
    bpy.utils.unregister_class(RTXPT_AddonPreferences)

if __name__ == "__main__":
    register()


