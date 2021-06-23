import socket
from ..protocol.connection import ARMBConnection, ARMBMessageTimeoutError, ARMBMessageFormatError
from ..protocol import armb
from ..shared.render_settings import RenderSettings
from ..blender import blender
from ..shared import utils
from .server_view import ServerView
from .task import RenderTask, UploadTask

class Worker:
    def __init__(self, output_dir, port, timeout=10):
        self.output_dir = output_dir
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.connection = None
        self.server = None

        self.task = None
        self.closed = False
    
    def connected(self):
        return self.connection and self.connection.ok() and not self.closed
    
    def start(self):
        blender.set_render_callbacks(self.handle_render_complete, self.handle_render_cancel)
        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(False)
        self.socket.bind(("", self.port))
        self.socket.listen()
    
    def restart(self):
        if self.closed:
            self.stop()
            self.start()
        elif self.connection and not self.connect.closed:
            self.connection.close()
        
        self.task = None
        self.server = None
        self.connection = None
        self.closed = False

    def stop(self):
        self.closed = True
        blender.clear_render_callbacks()
        if self.connection:
            self.connection.close()
        self.socket.close()
    
    def update(self):
        if not self.closed:
            readable, writeable = utils.socket_status(self.socket)
            if readable:
                if self.connected():
                    self.reject_connection()
                else:
                    self.accept_connection()
        
        if self.connected():
            readable, writeable = utils.socket_status(self.connection.socket)
            self.connection.update(readable, writeable)
            
            if self.connection.finished_receiving():
                self.handle_message(self.connection.receive())
                
            if self.task and isinstance(self.task, RenderTask) and not self.task.started:
                self.task.started = True
                blender.render_frame(self.task.frame, self.output_dir)
            
        elif self.connection and self.connection.closed:
            self.stop()
    
    def accept_connection(self):
        sock, addr = self.socket.accept()
        sock.setblocking(False)
        self.connection = ARMBConnection(sock, self.timeout)
        self.server = ServerView()
        self.connection.send(armb.new_identity_message())
        self.update()
        
    def reject_connection(self):
        sock, addr = self.socket.accept()
        sock.close()
    
    def handle_message(self, message):
        msg_str = message.message.tobytes().decode()

        if msg_str.startswith("IDENTITY "):
            self.handle_identity_message(message, msg_str)
        elif msg_str.startswith("SYNCHRONIZE "):
            self.handle_synchronize_message(message, msg_str)
        elif msg_str.startswith("RENDER "):
            self.handle_render_message(message, msg_str)
        elif msg_str.startswith("CANCEL"):
            self.handle_cancel_message()
        else:
            raise utils.BadMessageError("Unable to parse unknown message", message)
    
    def handle_identity_message(self, message, msg_str):
        id = armb.parse_identity_message(msg_str)
        if id:
            self.server.identity = id
        else:
            raise utils.BadMessageError("Unable to parse IDENTITY message", message)
    
    def handle_synchronize_message(self, message, msg_str):
        id = armb.parse_sync_message(msg_str) or 0
        data = message.data.tobytes().decode()
        
        blender.apply_render_settings(RenderSettings.deserialize(data))
        
        self.connection.send(armb.new_confirm_sync_message(id))
    
    def handle_render_message(self, message, msg_str):
        try:
            frame = int(armb.parse_request_render_message(msg_str))
        except ValueError:
            frame = None
        
        if not frame:
            raise utils.BadMessageError("Unable to parse RENDER message", message)
        elif not self.server.verified() or self.task:
            self.connection.send(armb.new_reject_render_message(frame))
        else:
            self.task = RenderTask(frame)
    
    def handle_cancel_message(self):
        if self.task:
            self.task.remote_cancelled = True
            # TODO trigger ESC or something
        else:
            self.connection.send(armb.new_confirm_cancelled_message())
    
    def handle_render_complete(self, scene, bpy_context):
        if self.task.remote_cancelled:
            self.connection.send(armb.new_confirm_cancelled_message())
        else:
            self.connection.send(armb.new_render_complete_message(self.task.frame))
        
        self.task = None
        
    def handle_render_cancel(self, scene, bpy_context):
        if self.task.remote_cancelled:
            self.connection.send(armb.new_confirm_cancelled_message())
        else:
            self.task.started = False
            # self.task.attempts += 1
