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
from .src.server.render_job import RenderJob
from .src.shared.render_settings import RenderSettings

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
        self.worker = Worker(output_dir, port, timeout=5)
        self.worker.start()
        self.node_type = 'WORKER'
    
    def worker_stop(self):
        self.worker.stop()
        self.node_type = None
    
    def worker_status(self):
        if not self.worker.connected():
            return "WAITING"
        elif not self.worker.connection.ok():
            return "ERROR"
        elif self.worker.task:
            return "WORKING"
        else:
            return "READY"
    
    def server_start(self, output_dir):
        self.server = Server(output_dir, timeout=5)
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
    
    def update(self):
        if self.is_worker():
            if self.worker.closed:
                self.worker.restart()
            else:
                self.worker.update()
        elif self.is_server():
            self.server.update()
    
ARMB = ARMBController()

class ARMBWorkerListItem(bpy.types.PropertyGroup):
    host: bpy.props.StringProperty(name="Host IP", description="The IP address of the worker computer")
    port: bpy.props.StringProperty(name="Port", description="The port the worker process is running on")

class ARMBSettings(bpy.types.PropertyGroup):
    render_on_server: bpy.props.BoolProperty(name="Render on server", description="Use the server computer as another rendering worker", default=True)
    output_dir: bpy.props.StringProperty(name="Output Path", description="The directory in which to store rendered frames", subtype='DIR_PATH', default="//armb/")
    worker_list: bpy.props.CollectionProperty(type=ARMBWorkerListItem)
    worker_index: bpy.props.IntProperty(default=0)

class ARMB_UL_WorkerList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        worker = ARMB.server.workers[index]
        
        if not worker.connected():
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
                            
            layout.label(text=(worker.identity or 'New Worker'), icon=status_icon)

            if worker.error():
                layout.label(text=str(worker.error()))
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
            new_item.host = self.worker_ip
            new_item.port = self.worker_port
            
            self.report({'INFO'}, f"Connecting to worker at {self.worker_ip} {self.worker_port}")
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
        return len(context.scene.armb.worker_list) > 0
    
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
    
    def execute(self, context):
        return {'FINISHED'}

class ARMB_OT_CancelRender(bpy.types.Operator):
    bl_idname = "wm.cancel_armb_render"
    bl_label = "Cancel"
    bl_description = "Cancel the current render"
    
    def execute(self, context):
        return {'FINISHED'}

class ARMB_OT_UpdateTimer(bpy.types.Operator):
    bl_idname = "wm.armb_update_timer"
    bl_label = "ARMB Update Timer"

    _timer = None

    def modal(self, context, event):
        # if event.type in {'RIGHTMOUSE', 'ESC'}:
        #     self.cancel(context)
        #     return {'CANCELLED'}

        if event.type == 'TIMER':
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
            
            layout.template_list("ARMB_UL_WorkerList", "", bpy.context.scene.armb, "worker_list", bpy.context.scene.armb, "worker_index", item_dyntip_propname="name")
            
            row = layout.row()
            row.operator("wm.add_armb_worker", icon='ADD')
            row.operator("wm.remove_armb_worker", icon='REMOVE')
            
            row = layout.row()
            row.prop(scene.armb, "render_on_server")
            
            layout.separator()

            layout.operator("wm.disconnect_armb_server")
        else:
            row = layout.row()
            row.label(text=f"Running on port {ARMB.worker.port}")
            row.label(text=ARMB.worker_status())
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
        
