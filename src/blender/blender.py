from ..shared.render_settings import RenderSettings
from ..supervisor.render_job import RenderJob

bpy = None

try:
    import bpy
except ImportError:
    print('WARINING: unable to import bpy')

def create_render_settings():
    if bpy:
        props = bpy.context.scene.render
        prefs = bpy.context.preferences
        return RenderSettings(props.resolution_x, props.resolution_y, props.resolution_percentage, prefs.view.render_display_type)
    return RenderSettings(1920, 1280, 100)

def apply_render_settings(settings):
    if bpy and settings is not None:
        props = bpy.context.scene.render
        prefs = bpy.context.preferences

        props.resolution_x = settings.resolution_x
        props.resolution_y = settings.resolution_y
        props.resolution_percentage = settings.percentage

        if settings.display_mode in {'SCREEN', 'AREA', 'WINDOW', 'NONE'}:
            prefs.view.render_display_type = settings.display_mode

def create_render_job(display_mode=None):
    if bpy:
        scene = bpy.context.scene
        settings = create_render_settings()
        if display_mode is not None:
            settings.display_mode = display_mode
        return RenderJob(scene.frame_start, scene.frame_end, settings, create_render_settings())
    return RenderJob(1, 250, create_render_settings())

def set_render_callbacks(finished_callback, cancelled_callback):
    if bpy:
        bpy.app.handlers.render_complete.append(finished_callback)
        bpy.app.handlers.render_cancel.append(cancelled_callback)

def clear_render_callbacks():
    if bpy:
        bpy.app.handlers.render_complete.clear()
        bpy.app.handlers.render_cancel.clear()

def render_frame(frame, root_path, generate=True):
    if bpy:
        bpy.context.scene.render.filepath = f"{root_path}{frame}" if generate else root_path
        bpy.context.scene.frame_set(frame)
        return bpy.ops.render.render('INVOKE_DEFAULT', write_still=True)
    return {'RUNNING_MODAL'}

def filename_extension():
    return bpy.context.scene.render.file_extension or ""

def rendered_filename(frame):
    if bpy:
        return bpy.path.abspath(f"{frame}{filename_extension()}")
    return f"{frame}.png"

def rendered_frame_path(frame, root_path):
    return root_path + rendered_filename(frame)
