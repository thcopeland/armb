import socket, os.path, shutil
from ..protocol.connection import ARMBConnection, ARMBMessageTimeoutError, ARMBMessageFormatError
from ..protocol import armb
from ..shared.render_settings import RenderSettings
from ..blender import blender
from ..shared import utils
from .server_view import ServerView
from .task import RenderTask

class Worker:
    def __init__(self, output_dir, port, timeout=10):
        self.output_dir = output_dir
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.connection = None
        self.server = None
        self.err = None

        self.render_settings = None
        self.original_render_settings = blender.create_render_settings()
        self.task = None
        self.closed = False

    def connected(self):
        return self.connection and self.connection.ok() and not self.closed

    def ok(self):
        return self.error() is None

    def error(self):
        if self.err:
            return self.err
        elif self.connection and self.connection.error:
            return self.connection.error

    def status_message(self):
        error = self.error()

        if error:
            if isinstance(error, ConnectionRefusedError):
                return "Unable to connect"
            elif isinstance(error, ConnectionError):
                return "Connection lost or rejected"
            elif isinstance(error, ARMBMessageFormatError):
                return "Received an invalid message (is this an ARMB server?)"
            elif isinstance(error, ARMBMessageTimeoutError):
                return "Connection timed out"
            elif isinstance(error, utils.BadMessageError):
                return "Received an unknown message (check version)"
            else:
                return f"Internal Error: {error}"
        elif self.task:
            return f"Rendering frame {self.task.frame}"
        elif self.connected():
            return f"Ready on port {self.port}"
        else:
            return f"Waiting on port {self.port}"

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
        self.err = None

    def stop(self):
        self.closed = True
        blender.clear_render_callbacks()
        blender.apply_render_settings(self.original_render_settings)
        if self.connection:
            self.connection.close()
        self.socket.close()

    def update(self):
        if self.ok():
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

                if self.task and not self.task.started:
                    if 'CANCELLED' not in blender.render_frame(self.task.frame, self.output_dir):
                        self.task.started = True
                        blender.apply_render_settings(self.render_settings)
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
        elif msg_str.startswith("UPLOAD "):
            self.handle_upload_message(message, msg_str)
        elif msg_str.startswith("CANCEL"):
            self.handle_cancel_message()
        elif msg_str.startswith("CLEANUP"):
            self.handle_cleanup_message()
        else:
            self.err = utils.BadMessageError("Unable to parse unknown message", message)

    def handle_identity_message(self, message, msg_str):
        id = armb.parse_identity_message(msg_str)
        if id:
            self.server.identity = id
        else:
            self.err = utils.BadMessageError("Unable to parse IDENTITY message", message)

    def handle_synchronize_message(self, message, msg_str):
        id = armb.parse_sync_message(msg_str) or 0
        data = message.data.tobytes().decode()
        self.render_settings = RenderSettings.deserialize(data)
        self.connection.send(armb.new_confirm_sync_message(id))

    def handle_render_message(self, message, msg_str):
        try:
            frame = int(armb.parse_request_render_message(msg_str))

            if not self.server.verified() or self.task:
                self.connection.send(armb.new_reject_render_message(frame))
            else:
                self.task = RenderTask(frame)
        except ValueError as e:
            print(e)
            self.err = utils.BadMessageError("Unable to parse RENDER message", message)

    def handle_upload_message(self, message, msg_str):
        try:
            frame = int(armb.parse_request_upload_message(msg_str))
            filepath = blender.rendered_frame_path(frame, self.output_dir)

            if not self.server.verified():
                self.connection.send(armb.new_reject_upload_message(frame))
            else:
                try:
                    with open(filepath, "rb") as f:
                        self.connection.send(armb.new_complete_upload_message(frame, os.path.basename(filepath)), f.read())
                except FileNotFoundError:
                    print("Unable to open", filepath)
                    self.connection.send(armb.new_reject_upload_message(frame))
        except ValueError as e:
            print(e)
            self.err = utils.BadMessageError("Unable to parse UPLOAD message", message)

    def handle_cancel_message(self):
        if self.task:
            self.task.remote_cancelled = True
        else:
            self.connection.send(armb.new_confirm_cancelled_message())

    def handle_render_complete(self, scene, bpy_context):
        if self.task.remote_cancelled:
            self.connection.send(armb.new_confirm_cancelled_message())
        else:
            self.connection.send(armb.new_render_complete_message(self.task.frame))

        blender.apply_render_settings(self.original_render_settings)
        self.task = None

    def handle_render_cancel(self, scene, bpy_context):
        if self.task.remote_cancelled:
            self.connection.send(armb.new_confirm_cancelled_message())
            self.task = None
        else:
            self.task.started = False
            self.task.record_failed_attempt()
            if self.task.failed():
                self.connection.send(armb.new_reject_render_message(self.task.frame))
                self.task = None

        blender.apply_render_settings(self.original_render_settings)

    def handle_cleanup_message(self):
        shutil.rmtree(self.output_dir)
