bl_info = {
    "name" : "ARMB Network Render",
    "author" : "Tom Copeland",
    "description" : "Render animations over a network",
    "version" : (0, 1, 0),
    "blender" : (2, 90, 0),
    "warning" : "May be unstable",
    "wiki_url" : "https://www.github.com/thcopeland/armb",
    "location" : "Render > ARMB Network Render",
    "support" : "COMMUNITY",
    "category" : "Render"
}

import bpy
from .src.worker.worker import Worker
from .src.supervisor.supervisor import Supervisor, WorkerView
from .src.blender.blender import create_render_job

class ARMBController:
    def __init__(self):
        self.node_type = None # SUPERVISOR, WORKER
        self.worker = None
        self.supervisor = None

    def started(self):
        return self.node_type is not None

    def is_worker(self):
        return self.node_type == 'WORKER'

    def is_supervisor(self):
        return self.node_type == 'SUPERVISOR'

    def worker_start(self, output_dir, port):
        self.worker = Worker(bpy.path.abspath(output_dir), port, timeout=5)
        self.worker.start()
        self.node_type = 'WORKER'

    def worker_stop(self):
        self.worker.stop()
        self.node_type = None

    def supervisor_start(self, output_dir):
        self.supervisor = Supervisor(bpy.path.abspath(output_dir), timeout=5)
        self.node_type = 'SUPERVISOR'
        bpy.context.window_manager.armb.worker_list.clear()
        bpy.context.window_manager.armb.worker_index = 0

    def supervisor_stop(self):
        self.supervisor.remove_all_workers()
        self.node_type = None

    def supervisor_add_worker(self, host, port):
        self.supervisor.add_worker(host, port)

    def supervisor_remove_worker(self, index):
        self.supervisor.remove_worker(index)

    def supervisor_working(self):
        return self.supervisor.job and not self.supervisor.job.uploading_complete()

    def supervisor_finished_job(self):
        return self.supervisor.job and self.supervisor.job.uploading_complete()

    def supervisor_clean_workers(self):
        self.supervisor.clean_workers()

    def supervisor_start_render(self):
        self.supervisor.start_job(create_render_job(display_mode=bpy.context.window_manager.armb.render_display_mode))

    def supervisor_cancel_render(self):
        self.supervisor.stop_job()

    def supervisor_update_supervisor_rendering(self, val):
        if self.is_supervisor():
            if val:
                self.supervisor.enable_supervisor_rendering()
            else:
                self.supervisor.disable_supervisor_rendering()

    def update(self):
        if self.is_worker():
            if self.worker.closed and not self.worker.error():
                self.worker.restart()
            elif self.worker.ok():
                self.worker.update()
        elif self.is_supervisor():
            self.supervisor.update()

            if self.supervisor_working():
                bpy.context.window_manager.armb.progress_indicator = round(self.supervisor.job_progress()*100)

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

def update_supervisor_rendering(prop, context):
    ARMB.supervisor_update_supervisor_rendering(context.window_manager.armb.render_on_supervisor)

class ARMBSettings(bpy.types.PropertyGroup):
    render_display_mode: bpy.props.EnumProperty(name="Render display mode", description="How to display an in-progress render", default='AREA', items=render_display_values)
    render_on_supervisor: bpy.props.BoolProperty(name="Render on supervisor", description="Use the supervisor computer as another rendering worker", default=True, update=update_supervisor_rendering)
    output_dir: bpy.props.StringProperty(name="Output Path", description="The directory in which to store rendered frames", subtype='DIR_PATH', default="//armb/")
    worker_list: bpy.props.CollectionProperty(type=ARMBWorkerListItem)
    worker_index: bpy.props.IntProperty(name="Active Worker Index", default=0)
    progress_indicator: bpy.props.FloatProperty(name="Progress", subtype='PERCENTAGE', min=0, max=100, precision=0, default=30)

class ARMB_UL_WorkerList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        worker = ARMB.supervisor.workers[index]

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
            ARMB.supervisor_add_worker(self.worker_ip, port)

            new_item = context.window_manager.armb.worker_list.add()
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
        return 0 <= context.window_manager.armb.worker_index < len(context.window_manager.armb.worker_list)

    def execute(self, context):
        ARMB.supervisor_remove_worker(context.window_manager.armb.worker_index)
        context.window_manager.armb.worker_list.remove(context.window_manager.armb.worker_index)
        return {'FINISHED'}

class ARMB_OT_StartWorker(bpy.types.Operator):
    bl_idname = "wm.start_armb_worker"
    bl_label = "Start Worker"
    bl_description = "Start an ARMB worker"

    port: bpy.props.StringProperty(name="Worker Port", description="The port to run on", default="7210")

    def execute(self, context):
        try:
            port = int(self.port)
            ARMB.worker_start(context.window_manager.armb.output_dir, port)
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
    bl_description = "Cancel active render and disconnect from supervisor"

    def execute(self, context):
        ARMB.worker_stop()
        self.report({'INFO'}, "Successfully stopped worker")
        return {'FINISHED'}

class ARMB_OT_StartSupervisor(bpy.types.Operator):
    bl_idname = "wm.start_armb_supervisor"
    bl_label = "Start Supervisor"
    bl_description = "Start an ARMB supervisor"

    def execute(self, context):
        ARMB.supervisor_start(context.window_manager.armb.output_dir)
        bpy.ops.wm.armb_update_timer()
        self.report({'INFO'}, 'Successfully started supervisor')
        return {'FINISHED'}

class ARMB_OT_DisconnectSupervisor(bpy.types.Operator):
    bl_idname = "wm.disconnect_armb_supervisor"
    bl_label = "Disconnect"
    bl_description = "Cancel active render and disconnect from workers"

    def execute(self, context):
        ARMB.supervisor_stop()
        self.report({'INFO'}, "Successfully stopped supervisor")
        return {'FINISHED'}

    def draw(self, context):
        self.layout.label(text="Not all frames have been uploaded yet. Are you sure?")

    def invoke(self, context, event):
        if ARMB.supervisor_working():
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

class ARMB_OT_StartRender(bpy.types.Operator):
    bl_idname = "wm.start_armb_render"
    bl_label = "Render"
    bl_description = "Start rendering active scene on workers"

    @classmethod
    def poll(cls, context):
        return not ARMB.supervisor_working()

    def execute(self, context):
        ARMB.supervisor_start_render()
        return {'FINISHED'}

class ARMB_OT_CancelRender(bpy.types.Operator):
    bl_idname = "wm.cancel_armb_render"
    bl_label = "Cancel"
    bl_description = "Cancel the current render"

    @classmethod
    def poll(cls, context):
        return ARMB.supervisor_working()

    def execute(self, context):
        ARMB.supervisor_cancel_render()
        return {'FINISHED'}

class ARMB_OT_CleanWorkers(bpy.types.Operator):
    bl_idname = "wm.clean_armb_workers"
    bl_label = "Clean Workers"
    bl_description = "Delete rendered frames on workers"

    def execute(self, context):
        ARMB.supervisor_clean_workers()
        ARMB.supervisor_cancel_render()
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
        return ARMB.supervisor_finished_job()

    def execute(self, context):
        ARMB.supervisor_cancel_render()
        return {'FINISHED'}

class ARMB_OT_ShowRenderStats(bpy.types.Operator):
    bl_idname = "wm.show_armb_render_stats"
    bl_label = "Statistics"
    bl_description = "Show worker render statistics"

    @classmethod
    def poll(cls, context):
        return ARMB.supervisor.job is not None

    def draw(self, context):
        stats = ARMB.supervisor.job.worker_statistics()

        row = self.layout.row()
        split = row.split(factor=0.5)
        col = split.column()
        col.label(text="Name")
        if ARMB.supervisor.supervisor_worker in stats:
            col.label(text="Supervisor")
        for worker in ARMB.supervisor.workers:
            if worker.identity:
                col.label(text=worker.identity)
            else:
                col.label(text=f"{worker.address[0]}:{worker.address[1]}")

        col = split.column()
        col.label(text="Number")
        if ARMB.supervisor.supervisor_worker in stats:
            col.label(text=str(stats[ARMB.supervisor.supervisor_worker][0]))
        for worker in ARMB.supervisor.workers:
            if worker in stats:
                col.label(text=str(stats[worker][0]))
            else:
                col.label(text='0')

        col = split.column()
        col.label(text="Average Time")
        if ARMB.supervisor.supervisor_worker in stats:
            col.label(text=self.time_string(stats[ARMB.supervisor.supervisor_worker][1]))
        for worker in ARMB.supervisor.workers:
            if worker in stats:
                col.label(text=self.time_string(stats[worker][1]))
            else:
                col.label(text='-')

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def time_string(self, secs):
        mins = int(secs/60)
        hours = int(mins/60)
        return f"{(hours%60):02}:{(mins%60):02}:{(secs%60):05.02f}"

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
        wm = context.window_manager

        if not ARMB.started():
            row = layout.row()
            row.scale_y = 1.5
            row.operator("wm.start_armb_worker")

            row = layout.row()
            row.scale_y = 1.5
            row.operator("wm.start_armb_supervisor")

            layout.separator()
            layout.prop(wm.armb, "output_dir")
        elif ARMB.node_type == 'SUPERVISOR':
            row = layout.row()
            row.operator("wm.start_armb_render", icon='RENDER_ANIMATION')
            row.operator("wm.cancel_armb_render", icon='CANCEL')

            layout.template_list("ARMB_UL_WorkerList", "", wm.armb, "worker_list", wm.armb, "worker_index")

            row = layout.row()
            row.operator("wm.add_armb_worker", icon='ADD')
            row.operator("wm.remove_armb_worker", icon='REMOVE')

            layout.separator()

            row = layout.row()
            row.label(text="Render display mode: ")
            row.prop(wm.armb, "render_display_mode", text="")

            layout.prop(wm.armb, "render_on_supervisor")

            layout.separator()

            if ARMB.supervisor_working() or ARMB.supervisor_finished_job():
                box = layout.box()
                if ARMB.supervisor_working():
                    row = box.row()
                    row.label(text="Render in progress...")
                    row.operator("wm.show_armb_render_stats")
                else:
                    row = box.row()
                    row.label(text="Render complete!")
                    row = row.row()
                    row.alignment = 'RIGHT'
                    row.operator("wm.show_armb_render_stats")
                    row.operator("wm.close_armb_render_summary", text="",  icon='X')

                row = box.row()
                row.label(text=f"{ARMB.supervisor.job.frames_rendered}/{ARMB.supervisor.job.frame_count} frames rendered")
                row.label(text=f"{ARMB.supervisor.job.frames_uploaded}/{ARMB.supervisor.job.frame_count} frames uploaded")

                if ARMB.supervisor_working():
                    box.prop(wm.armb, "progress_indicator", slider=True)
                else:
                    box.operator("wm.clean_armb_workers")

                layout.separator()

            layout.operator("wm.disconnect_armb_supervisor")
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
    ARMB_OT_StartSupervisor,
    ARMB_OT_DisconnectSupervisor,
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

    bpy.types.WindowManager.armb = bpy.props.PointerProperty(type=ARMBSettings)

def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)

    del bpy.types.WindowManager.armb
