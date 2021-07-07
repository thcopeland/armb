bl_info = {
    "name" : "ARMB Network Render",
    "author" : "Tom Copeland",
    "description" : "Render animations over a network",
    "version" : (0, 0, 0),
    "blender" : (2, 90, 0),
    "warning" : "May be unstable",
    "wiki_url" : "https://www.github.com/thcopeland/armb",
    "location" : "Render > ARMB Network Render",
    "support" : "COMMUNITY",
    "category" : "Render"
}

import bpy
from .src.worker.worker import Worker
from .src.server.server import Server, WorkerView
from .src.blender.blender import create_render_job

class ARMBController:
    def __init__(self):
        self.node_type = None # SERVER, WORKER
        self.worker = None
        self.server = None

    def started(self):
        return self.node_type is not None

    def is_worker(self):
        return self.node_type == 'WORKER'

    def is_server(self):
        return self.node_type == 'SERVER'

    def worker_start(self, output_dir, port):
        self.worker = Worker(bpy.path.abspath(output_dir), port, timeout=5)
        self.worker.start()
        self.node_type = 'WORKER'

    def worker_stop(self):
        self.worker.stop()
        self.node_type = None

    def server_start(self, output_dir):
        self.server = Server(bpy.path.abspath(output_dir), timeout=5)
        self.node_type = 'SERVER'
        bpy.context.scene.armb.worker_list.clear()
        bpy.context.scene.armb.worker_index = 0

    def server_stop(self):
        self.server.remove_all_workers()
        self.node_type = None

    def server_add_worker(self, host, port):
        self.server.add_worker(host, port)

    def server_remove_worker(self, index):
        self.server.remove_worker(index)

    def server_working(self):
        return self.server.job and not self.server.job.uploading_complete()

    def server_finished_job(self):
        return self.server.job and self.server.job.uploading_complete()

    def server_clean_workers(self):
        self.server.clean_workers()

    def server_start_render(self):
        self.server.start_job(create_render_job(display_mode=bpy.context.scene.armb.render_display_mode))

    def server_cancel_render(self):
        self.server.stop_job()

    def update(self):
        if self.is_worker():
            if self.worker.closed and not self.worker.error():
                self.worker.restart()
            elif self.worker.ok():
                self.worker.update()
        elif self.is_server():
            self.server.update()
            if self.server_working():
                bpy.context.scene.armb.progress_indicator = round(self.server.job_progress()*100)

ARMB = ARMBController()

class ARMBWorkerListItem(bpy.types.PropertyGroup):
    temp_name: bpy.props.StringProperty(name="Name", description="A temporary name for this worker")
    host: bpy.props.StringProperty(name="Host IP", description="The IP address of the worker computer")
    port: bpy.props.StringProperty(name="Port", description="The port the worker process is running on")

render_display_values = (
    ('WINDOW', "New Window", "Render in a separate window"),
    ('NONE', "Keep User Interface", "Show only the progress of the render"),
    ('SCREEN', "Maximized Area", "Show the in-progress render fullscreen"),
    ('AREA', "Image Editor", "Show the in-progress render in the image viewer"),
    ('PREFERENCES', "User Preferences", "Use the value in User Preferences (Interface > Temporary Editors > Render In)")
)

class ARMBSettings(bpy.types.PropertyGroup):
    render_display_mode: bpy.props.EnumProperty(name="Render display mode", description="How to display an in-progress render", default='AREA', items=render_display_values)
    render_on_server: bpy.props.BoolProperty(name="Render on server", description="Use the server computer as another rendering worker", default=True)
    output_dir: bpy.props.StringProperty(name="Output Path", description="The directory in which to store rendered frames", subtype='DIR_PATH', default="//armb/")
    worker_list: bpy.props.CollectionProperty(type=ARMBWorkerListItem)
    worker_index: bpy.props.IntProperty(name="Active Worker Index", default=0)
    progress_indicator: bpy.props.FloatProperty(name="Progress", subtype='PERCENTAGE', min=0, max=100, precision=0, default=30)

class ARMB_UL_WorkerList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        worker = ARMB.server.workers[index]

        if worker.ok() and not worker.connected() or worker.status == WorkerView.STATUS_INITIALIZING:
            status_icon = 'LAYER_USED'
        elif worker.status == WorkerView.STATUS_READY:
            status_icon = 'LAYER_ACTIVE'
        elif worker.status == WorkerView.STATUS_SYNCHRONIZING:
            status_icon = 'FILE_REFRESH'
        elif worker.status == WorkerView.STATUS_RENDERING:
            status_icon = 'VIEW_CAMERA'
        elif worker.status == WorkerView.STATUS_UPLOADING:
            status_icon = 'EXPORT'
        else:
            status_icon = 'ERROR'

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if not worker.connected() or not worker.ok():
                layout.enabled = False

            layout.label(text=(worker.identity or item.temp_name), icon=status_icon)

            if worker.error():
                layout.label(text=worker.error_description())
            elif not worker.connected():
                layout.label(text="Disconnected")

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon=status_icon)

class ARMB_OT_AddWorker(bpy.types.Operator):
    bl_idname = "wm.add_armb_worker"
    bl_label = "Add worker"
    bl_description = "Connect to an ARMB worker"

    worker_ip: bpy.props.StringProperty(name="IP Address", description="The IP address of the computer the worker is running on, e.g. 10.0.0.50")
    worker_port: bpy.props.StringProperty(name="Port", description="The port the worker is running on", default="7210")

    def execute(self, context):
        try:
            port = int(self.worker_port)
            ARMB.server_add_worker(self.worker_ip, port)

            new_item = context.scene.armb.worker_list.add()
            new_item.temp_name = f"{self.worker_ip}:{self.worker_port}"
            new_item.host = self.worker_ip
            new_item.port = self.worker_port

            self.report({'INFO'}, f"Connecting to worker at {self.worker_ip}:{self.worker_port}")
        except ValueError:
            self.report({'WARNING'}, f"{new_item.port} is not a valid port number")

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class ARMB_OT_RemoveWorker(bpy.types.Operator):
    bl_idname = "wm.remove_armb_worker"
    bl_label = "Remove worker"
    bl_description = "Disconnect from an ARMB worker"

    @classmethod
    def poll(cls, context):
        return 0 <= context.scene.armb.worker_index < len(context.scene.armb.worker_list)

    def execute(self, context):
        ARMB.server_remove_worker(context.scene.armb.worker_index)
        context.scene.armb.worker_list.remove(context.scene.armb.worker_index)
        return {'FINISHED'}

class ARMB_OT_StartWorker(bpy.types.Operator):
    bl_idname = "wm.start_armb_worker"
    bl_label = "Start Worker"
    bl_description = "Start an ARMB worker"

    port: bpy.props.StringProperty(name="Worker Port", description="The port to run on", default="7210")

    def execute(self, context):
        try:
            port = int(self.port)
            ARMB.worker_start(context.scene.armb.output_dir, port)
            bpy.ops.wm.armb_update_timer()
            self.report({'INFO'}, f"Successfully started worker on port {self.port}")
        except ValueError as e:
            self.report({'WARNING'}, f"{self.port} is not a valid port number")
        except OSError as e:
            self.report({'WARNING'}, f"Unable to start worker on port {self.port}")

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class ARMB_OT_DisconnectWorker(bpy.types.Operator):
    bl_idname = "wm.disconnect_armb_worker"
    bl_label = "Disconnect"
    bl_description = "Cancel active render and disconnect from server"

    def execute(self, context):
        ARMB.worker_stop()
        self.report({'INFO'}, "Successfully stopped worker")
        return {'FINISHED'}

class ARMB_OT_StartServer(bpy.types.Operator):
    bl_idname = "wm.start_armb_server"
    bl_label = "Start Server"
    bl_description = "Start an ARMB server"

    def execute(self, context):
        ARMB.server_start(context.scene.armb.output_dir)
        bpy.ops.wm.armb_update_timer()
        self.report({'INFO'}, 'Successfully started server')
        return {'FINISHED'}

class ARMB_OT_DisconnectServer(bpy.types.Operator):
    bl_idname = "wm.disconnect_armb_server"
    bl_label = "Disconnect"
    bl_description = "Cancel active render and disconnect from workers"

    def execute(self, context):
        ARMB.server_stop()
        self.report({'INFO'}, "Successfully stopped server")
        return {'FINISHED'}

class ARMB_OT_StartRender(bpy.types.Operator):
    bl_idname = "wm.start_armb_render"
    bl_label = "Render"
    bl_description = "Start rendering active scene on workers"

    @classmethod
    def poll(cls, context):
        return not ARMB.server_working()

    def execute(self, context):
        ARMB.server_start_render()
        return {'FINISHED'}

class ARMB_OT_CancelRender(bpy.types.Operator):
    bl_idname = "wm.cancel_armb_render"
    bl_label = "Cancel"
    bl_description = "Cancel the current render"

    @classmethod
    def poll(cls, context):
        return ARMB.server_working()

    def execute(self, context):
        ARMB.server_cancel_render()
        return {'FINISHED'}

class ARMB_OT_CleanWorkers(bpy.types.Operator):
    bl_idname = "wm.clean_armb_workers"
    bl_label = "Clean Workers"
    bl_description = "Delete rendered frames on workers"

    def execute(self, context):
        ARMB.server_clean_workers()
        ARMB.server_cancel_render()
        return {'FINISHED'}

    def draw(self, context):
        self.layout.label(text="This will delete all frames from all workers.", icon='ERROR')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class ARMB_OT_CloseRenderSummary(bpy.types.Operator):
    bl_idname = "wm.close_armb_render_summary"
    bl_label = "Close"
    bl_description = "Close the render summary"

    @classmethod
    def poll(cls, context):
        return ARMB.server_finished_job()

    def execute(self, context):
        ARMB.server_cancel_render()
        return {'FINISHED'}

class ARMB_OT_ShowRenderStats(bpy.types.Operator):
    bl_idname = "wm.show_armb_render_stats"
    bl_label = "Statistics"
    bl_description = "Show worker render statistics"

    @classmethod
    def poll(cls, context):
        return ARMB.server_finished_job()

    def draw(self, context):
        stats = ARMB.server.job.worker_statistics()

        row = self.layout.row()
        split = row.split(factor=0.5)
        col = split.column()
        col.label(text="Name")
        for worker in ARMB.server.workers:
            if worker.identity:
                col.label(text=worker.identity)
            else:
                col.label(text=f"{worker.address[0]}:{worker.address[1]}")

        col = split.column()
        col.label(text="Number")
        for worker in ARMB.server.workers:
            if worker in stats:
                col.label(text=str(stats[worker][0]))
            else:
                col.label(text='0')

        col = split.column()
        col.label(text="Average Time")
        for worker in ARMB.server.workers:
            if worker in stats:
                secs = stats[worker][1]
                mins = int(secs/60)
                hours = int(mins/60)
                col.label(text=f"{(hours%60):02}:{(mins%60):02}:{secs:04.02}")
            else:
                col.label(text='-')

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class ARMB_OT_UpdateTimer(bpy.types.Operator):
    bl_idname = "wm.armb_update_timer"
    bl_label = "ARMB Update Timer"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'

    _timer = None

    def modal(self, context, event):
        if event.type == 'TIMER':
            if context.region:
                context.region.tag_redraw()
            ARMB.update()

        return {'PASS_THROUGH'}

    def execute(self, context):
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        context.window_manager.event_timer_remove(self._timer)

class ARMB_PT_UI(bpy.types.Panel):
    bl_label = "ARMB Network Render"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'render'
    bl_order = 15

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        if not ARMB.started():
            row = layout.row()
            row.scale_y = 1.5
            row.operator("wm.start_armb_worker")

            row = layout.row()
            row.scale_y = 1.5
            row.operator("wm.start_armb_server")

            layout.separator()
            layout.prop(scene.armb, "output_dir")
        elif ARMB.node_type == 'SERVER':
            row = layout.row()
            row.operator("wm.start_armb_render", icon='RENDER_ANIMATION')
            row.operator("wm.cancel_armb_render", icon='CANCEL')

            layout.template_list("ARMB_UL_WorkerList", "", bpy.context.scene.armb, "worker_list", bpy.context.scene.armb, "worker_index")

            row = layout.row()
            row.operator("wm.add_armb_worker", icon='ADD')
            row.operator("wm.remove_armb_worker", icon='REMOVE')

            layout.separator()

            row = layout.row()
            row.label(text="Render display mode: ")
            row.prop(scene.armb, "render_display_mode", text="")

            layout.prop(scene.armb, "render_on_server")

            layout.separator()

            if ARMB.server_working() or ARMB.server_finished_job():
                box = layout.box()
                if ARMB.server_working():
                    box.label(text="Render in progress...")
                else:
                    row = box.row()
                    row.label(text="Render complete!")
                    row = row.row()
                    row.alignment = 'RIGHT'
                    row.operator("wm.show_armb_render_stats")
                    row.operator("wm.close_armb_render_summary", text="",  icon='X')

                row = box.row()
                row.label(text=f"{ARMB.server.job.frames_rendered}/{ARMB.server.job.frame_count} frames rendered")
                row.label(text=f"{ARMB.server.job.frames_uploaded}/{ARMB.server.job.frame_count} frames uploaded")

                if ARMB.server_working():
                    box.prop(scene.armb, "progress_indicator", slider=True)
                else:
                    box.operator("wm.clean_armb_workers")

                layout.separator()

            layout.operator("wm.disconnect_armb_server")
        else:
            if ARMB.worker.ok():
                layout.label(text=ARMB.worker.status_message())
            else:
                layout.label(text=ARMB.worker.status_message(), icon='ERROR')

            layout.operator("wm.disconnect_armb_worker", text="Disconnect")

classes = [
    ARMBWorkerListItem,
    ARMBSettings,
    ARMB_UL_WorkerList,
    ARMB_OT_StartWorker,
    ARMB_OT_DisconnectWorker,
    ARMB_OT_StartServer,
    ARMB_OT_DisconnectServer,
    ARMB_OT_StartRender,
    ARMB_OT_CancelRender,
    ARMB_OT_CleanWorkers,
    ARMB_OT_CloseRenderSummary,
    ARMB_OT_ShowRenderStats,
    ARMB_OT_AddWorker,
    ARMB_OT_RemoveWorker,
    ARMB_OT_UpdateTimer,
    ARMB_PT_UI
]

def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.armb = bpy.props.PointerProperty(type=ARMBSettings)

def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)

    del bpy.types.Scene.armb


if __name__ == "__main__":
    register()

    bpy.context.scene.armb.worker_list.clear()
