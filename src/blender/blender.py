from ..shared.render_settings import RenderSettings
from ..server.render_job import RenderJob

bpy = None

try:
    import bpy
except ImportError:
    print('WARINING: unable to import bpy')

def create_render_settings():
    if bpy:
        props = bpy.context.scene.render
        return RenderSettings(props.resolution_x, props.resolution_y, props.resolution_percentage)
    return RenderSettings(1920, 1280, 100)

def apply_render_settings(settings):
    if bpy:
        props = bpy.context.scene.render
        
        props.resolution_x = settings.resolution_x
        props.resolution_y = settings.resolution_y
        props.resolution_percentage = settings.percentage
    else:
        print(f"Render Settings: {settings.resolution_x}x{settings.resolution_y} at {settings.percentage}%")

def create_render_job():
    if bpy:
        scene = bpy.context.scene
        return RenderJob(scene.frame_start, scene.frame_end, create_render_settings())
    return RenderJob(1, 250, create_render_settings())
