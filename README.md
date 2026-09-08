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

---

# RTXPT Live Link

`RTXPT Live Link.py` is a companion add-on to the exporter above. Where the exporter
writes glTF + `.scene.json` files to disk, Live Link talks *live* to a running RTXPT
instance over a small local TCP connection, so you can navigate the RTXPT viewport by
navigating Blender's, and push scene changes without restarting `RTXPT.exe` every time.

It requires an RTXPT build with the `--liveLink` Live Link server (see
[`Docs/LiveLink.md`](https://github.com/dx9674hnxw-spec/RTXPT/blob/main/Docs/LiveLink.md)
in the RTXPT repository for the wire protocol and current limitations). It works
standalone for camera live link; installing the RTXPT Exporter add-on alongside it
additionally enables one-click full scene sync.

## Features

- **Live camera sync** - while connected, streams either the active 3D viewport camera
  (fly/orbit in Blender and RTXPT follows) or the scene's Camera object, at a
  configurable rate (default 20 Hz).
- **Sync Full Scene** - re-runs the RTXPT Exporter's export operator and asks RTXPT to
  hot-reload the resulting `.scene.json`, in one click.
- Connection status, host/port and a `Ping` diagnostic button live in the same `RTXPT`
  sidebar tab as the exporter panel.

## Usage

1. Install `RTXPT Live Link.py` the same way as the exporter: **Edit > Preferences >
   Add-ons > Install...**, select the file, enable the add-on.
2. Launch RTXPT with Live Link enabled: `Rtxpt.exe --scene YourProject.scene.json --liveLink`
   (add `--liveLinkPort` if you changed the port in the add-on preferences; default is
   `42042` on both sides).
3. In Blender's `RTXPT` sidebar tab, open the **RTXPT Live Link** panel and click
   **Connect**.
4. Move around the 3D viewport - RTXPT's camera follows in real time.
5. After editing the scene, click **Sync Full Scene** to re-export and hot-reload it in
   RTXPT (requires the RTXPT Exporter add-on to also be installed and enabled, and a
   project name set in its panel).

## Requirements

- Blender 2.80+ (same compatibility range as the exporter)
- An RTXPT build that includes the Live Link server (`--liveLink` command line option);
  see the [RTXPT repository](https://github.com/dx9674hnxw-spec/RTXPT)
- Blender and RTXPT running on the same machine (the server only binds to
  `127.0.0.1` by design)

## License

GPL v3, same as the exporter add-on.
