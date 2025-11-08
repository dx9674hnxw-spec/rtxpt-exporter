RTXPT Project Exporter for Blender
Author: XyloN
Version: 1.2.0
Category: Import-Export
Compatibility: Blender 2.80+ (also tested with 3.x, 4.x)

Overview
RTXPT Project Exporter is a Blender add-on for exporting projects to the RTXPT engine.
It automatically generates glTF models for each subcollection inside a root collection called EXPORT_TEST, and builds a dedicated .scene.json project file in your RTXPT Assets folder with organized references and updated scene graph data.
Models are saved in Assets/Models/<Project>/<Collection>/<Collection>.gltf and the add-on can automatically launch the RTXPT executable after export.

Features
Per-collection glTF export (GLTF_SEPARATE format)

Automatic directory management, avoiding duplicates and updating project JSON

Appends or updates entries in both the "models" and "graph" sections of the scene file

Adds default lights and cameras sections if missing

RTXPT executable path is configurable (in Add-on Preferences)

Single-click export via a custom sidebar panel ("RTXPT")

Optional automatic launch of RTXPT.exe with the exported scene

Usage
Install the add-on in Blender via Preferences > Add-ons > Install.

In the RTXPT sidebar panel:

Set your Assets folder path

Set your project name

In Blender Add-on preferences, set the path to your RTXPT.exe.

Create a collection named EXPORT_TEST with each subcollection containing objects you want to export.

Click "Export RTXPT Project" in the sidebar.

Your glTF models will be in Assets/Models/<Project>/<Collection>/ and your .scene.json will be in Assets/<Project>.scene.json.

Requirements
Blender 2.80+ (works with latest stable builds)

RTXPT graphics engine, compatible with .scene.json and glTF

Installation
Download this repository.

Install in Blender: Edit > Preferences > Add-ons > Install...

Select RTXPT_Project_Exporter.py and activate the add-on.

Support
Issue Tracker / Feature Requests

Documentation, wiki, and further support: (to be linked/documented)

License
GPL v3
