bl_info = {
    "name": "RTXPT Live Link",
    "author": "XyloN",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > RTXPT",
    "description": ("Live-links Blender's viewport (or scene camera) to a running RTXPT "
                    "instance over a local TCP connection, and can trigger a full scene "
                    "re-export + hot-reload via the RTXPT Exporter add-on. See Docs/LiveLink.md "
                    "in the RTXPT repository for the wire protocol."),
    "warning": "",
    "wiki_url": "https://github.com/dx9674hnxw-spec/rtxpt-exporter",
    "tracker_url": "https://github.com/dx9674hnxw-spec/rtxpt-exporter/issues",
    "category": "Import-Export",
    "support": "COMMUNITY",
    "doc_url": "https://github.com/dx9674hnxw-spec/rtxpt-exporter/blob/main/README.md"
}

# RTXPT Live Link
# ----------------
# Companion add-on to "RTXPT Scene Exporter" (RTXPT_OT_project_export). Where the
# exporter writes glTF + .scene.json files to disk, this add-on talks live to a running
# RTXPT.exe over a small local TCP connection (see Docs/LiveLink.md in the RTXPT
# repository for the exact protocol):
#   - streams the Blender viewport (or scene) camera to RTXPT's free-fly camera in
#     real time while connected, so navigating in Blender navigates in RTXPT too;
#   - "Sync Full Scene" re-runs the RTXPT Exporter (if installed) and asks RTXPT to
#     hot-reload the resulting .scene.json, without restarting the executable.
#
# This add-on works standalone (camera live link only) or alongside "RTXPT Scene
# Exporter" (adds full-scene sync). Networking uses only Python's standard library.

import bpy
import math
import queue
import socket
import threading
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty


# ---------------------------------------------------------------------------
# 1. TCP client
# ---------------------------------------------------------------------------
# All socket I/O runs on a small background thread; outgoing lines are handed to it
# via a thread-safe queue. Connection state (connected/connecting/last_error) is read
# from the main thread by the UI panel - plain attribute reads/writes are used rather
# than a lock, which is fine for these coarse status flags under the GIL.

class _LiveLinkClient:
    def __init__(self):
        self.sock = None
        self.connected = False
        self.connecting = False
        self.last_error = ""
        self._send_queue = queue.Queue()
        self._stop_flag = threading.Event()
        self._thread = None

    def connect(self, host, port):
        if self.connected or self.connecting:
            return
        self.last_error = ""
        self.connecting = True
        self._stop_flag.clear()
        # drop any stale queued lines from a previous session
        while not self._send_queue.empty():
            try:
                self._send_queue.get_nowait()
            except queue.Empty:
                break
        self._thread = threading.Thread(target=self._run, args=(host, port), daemon=True)
        self._thread.start()

    def disconnect(self):
        self._stop_flag.set()
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        self.sock = None
        self.connected = False
        self.connecting = False

    def send(self, line):
        """Thread-safe: queue a line to be sent by the background thread."""
        self._send_queue.put(line)

    def _run(self, host, port):
        try:
            sock = socket.create_connection((host, port), timeout=3.0)
        except OSError as e:
            self.connecting = False
            self.connected = False
            self.last_error = str(e)
            return

        sock.settimeout(0.02)
        self.sock = sock
        self.connected = True
        self.connecting = False
        self.send("HELLO Blender %s / RTXPT Live Link %s" % (
            bpy.app.version_string, ".".join(str(n) for n in bl_info["version"])))

        buffer = b""
        while not self._stop_flag.is_set():
            # flush anything queued for sending
            try:
                while True:
                    line = self._send_queue.get_nowait()
                    try:
                        sock.sendall((line + "\n").encode("utf-8"))
                    except OSError as e:
                        self.last_error = str(e)
                        self._stop_flag.set()
                        break
            except queue.Empty:
                pass

            if self._stop_flag.is_set():
                break

            try:
                data = sock.recv(4096)
                if not data:
                    break  # server closed the connection
                buffer += data
                while b"\n" in buffer:
                    _line, buffer = buffer.split(b"\n", 1)
                    # Replies (OK/ERR/PONG/HELLO_OK) are currently only used for
                    # diagnostics; nothing in the UI depends on parsing them yet.
            except socket.timeout:
                continue
            except OSError:
                break

        try:
            sock.close()
        except OSError:
            pass
        self.sock = None
        self.connected = False


_client = _LiveLinkClient()


# ---------------------------------------------------------------------------
# 2. Camera sampling + axis conversion (Blender Z-up -> RTXPT/glTF Y-up)
# ---------------------------------------------------------------------------

def _to_rtxpt(v):
    """Blender (Z-up) -> glTF/RTXPT (Y-up), matching the glTF exporter convention."""
    return (v.x, v.z, -v.y)


def _find_view3d(context):
    """Returns (SpaceView3D, RegionView3D) for the first perspective/user 3D viewport
    found, or (None, None) if none is visible (e.g. RTXPT would keep its last pose)."""
    wm = context.window_manager
    for window in wm.windows:
        screen = window.screen
        if not screen:
            continue
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    rv3d = space.region_3d
                    if rv3d is not None and rv3d.view_perspective in {'PERSP', 'CAMERA'}:
                        return space, rv3d
    return None, None


def _format_cam_line(pos, forward, up, vfov, znear):
    p = _to_rtxpt(pos)
    d = _to_rtxpt(forward)
    u = _to_rtxpt(up)
    return "CAM %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f" % (
        p[0], p[1], p[2], d[0], d[1], d[2], u[0], u[1], u[2], vfov, znear)


def _build_cam_line_from_viewport(context):
    space, rv3d = _find_view3d(context)
    if rv3d is None:
        return None

    cam_to_world = rv3d.view_matrix.inverted()
    pos = cam_to_world.translation
    forward = -cam_to_world.col[2].xyz   # Blender cameras look down local -Z
    up = cam_to_world.col[1].xyz

    # Exact vertical FOV from the viewport's own projection matrix, rather than trying
    # to reverse-engineer it from lens/sensor settings (which vary with sensor fit).
    proj = rv3d.window_matrix
    try:
        vfov = 2.0 * math.atan(1.0 / proj[1][1])
    except ZeroDivisionError:
        vfov = 0.0

    znear = space.clip_start if space else 0.001
    return _format_cam_line(pos, forward, up, vfov, znear)


def _build_cam_line_from_scene_camera(context):
    cam_obj = context.scene.camera
    if cam_obj is None or cam_obj.type != 'CAMERA':
        return None
    cam_data = cam_obj.data
    if cam_data.type != 'PERSP':
        return None  # orthographic scene cameras have no RTXPT free-camera equivalent

    mat = cam_obj.matrix_world
    pos = mat.translation
    forward = -mat.col[2].xyz
    up = mat.col[1].xyz
    vfov = cam_data.angle_y  # accounts for render resolution / sensor fit
    znear = cam_data.clip_start
    return _format_cam_line(pos, forward, up, vfov, znear)


def _camera_sync_tick():
    context = bpy.context
    scene = context.scene
    props = getattr(scene, "rtxpt_livelink_props", None)
    interval = 1.0 / max(props.sync_rate, 1.0) if props else 0.2

    if _client.connected and props is not None:
        if props.sync_source == 'VIEWPORT':
            line = _build_cam_line_from_viewport(context)
        else:
            line = _build_cam_line_from_scene_camera(context)
        if line:
            _client.send(line)

        # keep the status panel (Connected/Disconnected/error) fresh even though it's
        # driven by a background thread the UI redraw system doesn't know about
        wm = context.window_manager
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

    return interval


def _ensure_timer_registered():
    if not bpy.app.timers.is_registered(_camera_sync_tick):
        bpy.app.timers.register(_camera_sync_tick, first_interval=0.05, persistent=True)


def _ensure_timer_unregistered():
    if bpy.app.timers.is_registered(_camera_sync_tick):
        bpy.app.timers.unregister(_camera_sync_tick)


# ---------------------------------------------------------------------------
# 3. Preferences, scene properties
# ---------------------------------------------------------------------------

class RTXPTLiveLink_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    host: StringProperty(name="Host", default="127.0.0.1")
    port: IntProperty(name="Port", default=42042, min=1, max=65535)

    def draw(self, context):
        layout = self.layout
        layout.label(text="RTXPT Live Link Server (see Docs/LiveLink.md)")
        row = layout.row(align=True)
        row.prop(self, "host")
        row.prop(self, "port")


def _get_prefs(context=None):
    context = context or bpy.context
    return context.preferences.addons[__name__].preferences


class RTXPT_LiveLink_Props(bpy.types.PropertyGroup):
    sync_source: EnumProperty(
        name="Sync Source",
        description="Which Blender camera drives RTXPT's free-fly camera",
        items=[
            ('VIEWPORT', "Active Viewport", "Mirror the 3D viewport's navigation camera - move/fly in Blender to move in RTXPT"),
            ('SCENE_CAMERA', "Scene Camera", "Mirror the scene's active Camera object"),
        ],
        default='VIEWPORT',
    )
    sync_rate: FloatProperty(
        name="Sync Rate (Hz)", default=20.0, min=1.0, max=60.0,
        description="How often the camera pose is sent to RTXPT while connected",
    )
    # Fallback project/asset settings, only shown when the RTXPT Exporter add-on
    # (which already exposes these on scene.rtxpt_proj_props) isn't installed/enabled.
    project_name: StringProperty(name="Project Name", default="TestProject")


# ---------------------------------------------------------------------------
# 4. Operators
# ---------------------------------------------------------------------------

class RTXPT_OT_LiveLinkConnect(bpy.types.Operator):
    bl_idname = "rtxpt.livelink_connect"
    bl_label = "Connect"
    bl_description = "Open a Live Link connection to a running RTXPT instance (started with --liveLink)"

    def execute(self, context):
        prefs = _get_prefs(context)
        _client.connect(prefs.host, prefs.port)
        _ensure_timer_registered()
        self.report({'INFO'}, f"Connecting to RTXPT Live Link at {prefs.host}:{prefs.port}...")
        return {'FINISHED'}


class RTXPT_OT_LiveLinkDisconnect(bpy.types.Operator):
    bl_idname = "rtxpt.livelink_disconnect"
    bl_label = "Disconnect"
    bl_description = "Close the Live Link connection to RTXPT"

    def execute(self, context):
        _client.disconnect()
        return {'FINISHED'}


class RTXPT_OT_LiveLinkPing(bpy.types.Operator):
    bl_idname = "rtxpt.livelink_ping"
    bl_label = "Ping"
    bl_description = "Send a PING to RTXPT to check the connection is alive"

    @classmethod
    def poll(cls, context):
        return _client.connected

    def execute(self, context):
        _client.send("PING")
        self.report({'INFO'}, "Sent PING")
        return {'FINISHED'}


def _resolve_relative_scene_path(context):
    """Returns the .scene.json path relative to the Assets folder, matching what the
    RTXPT Exporter add-on writes to (Assets/<project>.scene.json), or None if no
    project name is configured anywhere."""
    scene = context.scene
    exporter_props = getattr(scene, "rtxpt_proj_props", None)
    if exporter_props is not None and exporter_props.project_name.strip():
        return f"{exporter_props.project_name.strip()}.scene.json"

    livelink_props = getattr(scene, "rtxpt_livelink_props", None)
    if livelink_props is not None and livelink_props.project_name.strip():
        return f"{livelink_props.project_name.strip()}.scene.json"

    return None


class RTXPT_OT_LiveLinkSyncNow(bpy.types.Operator):
    bl_idname = "rtxpt.livelink_sync_now"
    bl_label = "Sync Full Scene"
    bl_description = ("Re-export the scene via the RTXPT Exporter add-on, then ask "
                       "RTXPT to hot-reload it (requires the RTXPT Exporter add-on)")

    @classmethod
    def poll(cls, context):
        return hasattr(bpy.types, "RTXPT_OT_project_export")

    def execute(self, context):
        try:
            result = bpy.ops.rtxpt.project_export()
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}
        if 'FINISHED' not in result:
            return {'CANCELLED'}

        relative_scene = _resolve_relative_scene_path(context)
        if not relative_scene:
            self.report({'ERROR'}, "Set a project name (RTXPT Exporter panel) before syncing.")
            return {'CANCELLED'}

        if not _client.connected:
            self.report({'WARNING'}, "Exported scene, but not connected to RTXPT - could not send RELOAD.")
            return {'FINISHED'}

        _client.send(f"RELOAD {relative_scene}")
        self.report({'INFO'}, f"Exported and asked RTXPT to reload {relative_scene}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# 5. UI panel
# ---------------------------------------------------------------------------

class RTXPT_PT_LiveLinkPanel(bpy.types.Panel):
    bl_label = "RTXPT Live Link"
    bl_idname = "RTXPT_PT_livelink_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RTXPT"

    def draw(self, context):
        layout = self.layout
        prefs = _get_prefs(context)
        props = context.scene.rtxpt_livelink_props

        if _client.connected:
            status, icon = "Connected", 'LINKED'
        elif _client.connecting:
            status, icon = "Connecting...", 'SORTTIME'
        else:
            status, icon = "Disconnected", 'UNLINKED'
        layout.label(text=f"Status: {status}", icon=icon)
        if _client.last_error and not _client.connected and not _client.connecting:
            layout.label(text=_client.last_error[:60], icon='ERROR')

        col = layout.column(align=True)
        col.prop(prefs, "host")
        col.prop(prefs, "port")

        row = layout.row(align=True)
        if _client.connected or _client.connecting:
            row.operator("rtxpt.livelink_disconnect", icon='UNLINKED')
        else:
            row.operator("rtxpt.livelink_connect", icon='LINKED')
        row.operator("rtxpt.livelink_ping", icon='FILE_REFRESH', text="")

        layout.separator()
        layout.label(text="Live Camera Sync")
        layout.prop(props, "sync_source", text="Source")
        layout.prop(props, "sync_rate")

        layout.separator()
        layout.label(text="Full Scene Sync")
        if not hasattr(bpy.types, "RTXPT_OT_project_export"):
            layout.label(text="Install 'RTXPT Exporter' add-on for this", icon='INFO')
            if not hasattr(context.scene, "rtxpt_proj_props"):
                layout.prop(props, "project_name")
        layout.operator("rtxpt.livelink_sync_now", icon='FILE_REFRESH')


# ---------------------------------------------------------------------------
# 6. Register / unregister
# ---------------------------------------------------------------------------

_classes = (
    RTXPTLiveLink_AddonPreferences,
    RTXPT_LiveLink_Props,
    RTXPT_OT_LiveLinkConnect,
    RTXPT_OT_LiveLinkDisconnect,
    RTXPT_OT_LiveLinkPing,
    RTXPT_OT_LiveLinkSyncNow,
    RTXPT_PT_LiveLinkPanel,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rtxpt_livelink_props = bpy.props.PointerProperty(type=RTXPT_LiveLink_Props)
    _ensure_timer_registered()


def unregister():
    _ensure_timer_unregistered()
    _client.disconnect()

    del bpy.types.Scene.rtxpt_livelink_props
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
