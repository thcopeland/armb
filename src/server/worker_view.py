import socket, threading
from ..protocol.connection import ARMBConnection, ARMBMessageTimeoutError, ARMBMessageFormatError
from ..protocol import armb

class WorkerView:
    STATUS_INITIALIZING = 'INITIALIZING'
    STATUS_SYNCHRONIZING = 'SYNCHRONIZING'
    STATUS_RENDERING = 'RENDERING'
    STATUS_UPLOADING = 'UPLOADING'
    STATUS_READY = 'READY'
    STATUS_ERROR = 'ERROR'
    
    def __init__(self, host, port, timeout):
        self.status = WorkerView.STATUS_INITIALIZING
        self.identity = None
        self.settings_id = -1
        
        self.err = None
        self.timeout = timeout
        self.address = (host, port)
        self.socket = None
        self.connection = None
        
    def verified(self):
        return not self.identity is None
    
    def connected(self):
        return self.connection is not None and self.connection.ok()
    
    def ok(self):
        return self.error() is None and (self.connection is None or self.connection.ok())
    
    def error(self):
        if self.err:
            self.status = WorkerView.STATUS_ERROR
            return self.err
        elif self.connection and self.connection.error:
            self.status = WorkerView.STATUS_ERROR
            return self.connection.error
    
    def error_description(self):
        error = self.error()
        
        if error:
            if isinstance(error, ConnectionRefusedError):
                return "Unable to connect"
            elif isinstance(error, ConnectionError):
                return "Connection lost or rejected"
            elif isinstance(error, ARMBMessageFormatError):
                return "Received an invalid message (check ARMB versions)"
            elif isinstance(error, ARMBMessageTimeoutError):
                return "Connection timed out"
            elif isinstance(error, utils.BadMessageError):
                return "Received an unknown message (is this an ARMB worker?)"
            else:
                return "Internal Error: " + str(error)
    
    def start(self, block=False):
        def establish_connection():
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(self.timeout)
                self.socket.connect(self.address)
                self.socket.setblocking(False)
                self.connection = ARMBConnection(self.socket, self.timeout)
                self.connection.send(armb.new_identity_message())
            except (OSError, socket.timeout) as e:
                self.err = e
                self.status = WorkerView.STATUS_ERROR
        
        if block:
            establish_connection()
        else:
            threading.Thread(target=establish_connection).start()
    
    def stop(self):
        if self.connection and not self.connection.closed:
            self.connection.close()
    
    def update_connection(self, read, write):
        if self.connected():
            self.connection.update(read, write)
    
    def handle_identity_message(self, message, msg_str):
        self.identity = armb.parse_identity_message(msg_str)
        if self.identity is None:
            self.err = utils.BadMessageError("Unable to parse IDENTITY message", message)
        else:
            self.status = WorkerView.STATUS_READY
    
    def handle_confirm_sync_message(self, message, msg_str):
        sync_id = armb.parse_confirm_sync_message(msg_str)
        
        if sync_id is None:
            self.err = utils.BadMessageError("Unable to parse CONFIRM SYNCHRONIZE message", message)
        else:
            self.settings_id = int(sync_id)
            self.status = WorkerView.STATUS_READY
    
    def handle_reject_render_message(self, job, message, msg_str):
        frame = armb.parse_reject_render_message(msg_str)
        
        if frame is None:
            self.err = utils.BadMessageError("Unable to parse REJECT RENDER message", message)
        elif job:
            job.unassign_frame(int(frame))
    
    def handle_confirm_cancel_message(self):
        self.status = WorkerView.STATUS_READY
    
    def handle_render_complete_message(self, job, message, msg_str):
        try:
            frame = int(armb.parse_render_complete_message(msg_str))
        except ValueError as e:
            print(e)
            self.err = utils.BadMessageError("Unable to parse COMPLETE RENDER message", message)
            return
        
        if job:
            job.mark_rendered(frame)
            self.status = WorkerView.STATUS_READY
    
    def handle_reject_upload_message(self, job, message, msg_str):
        try:
            frame = int(armb.parse_reject_upload_message(msg_str))
        except ValueError as e:
            print(e)
            self.err = utils.BadMessageError("Unable to parse RJECT UPLOAD message", message)
            return
        
        if job:
            job.mark_irretrievable(frame)
            self.status = WorkerView.STATUS_READY
    
    def handle_upload_complete_message(self, output_dir, job, message, msg_str):
        try:
            frame_str, filename = armb.parse_complete_upload_message(msg_str)
            frame = int(frame_str)
        except (ValueError, TypeError) as e:
            print(e)
            self.err = utils.BadMessageError("Unable to parse COMPLETE UPLOAD message", message)
            return
        
        if job:
            job.mark_uploaded(frame)
            job.write_frame(filename, output_dir, message.data)
            self.status = WorkerView.STATUS_READY
    
    def request_render_frame(self, job):
        if self.settings_id == job.settings.synchronization_id:
            frame = job.assign_next_frame(self)
            if frame:
                self.connection.send(armb.new_request_render_message(frame))
                self.status = WorkerView.STATUS_RENDERING
        else:
            self.connection.send(*armb.new_sync_message(job.settings))
            self.status = WorkerView.STATUS_SYNCHRONIZING
    
    def request_upload_frame(self, job):
        frame = job.next_for_uploading(self)
        
        if frame:
            self.connection.send(armb.new_request_upload_message(frame))
            self.status = WorkerView.STATUS_UPLOADING
    
    def cancel_task(self):
        self.connection.send(armb.new_cancel_task_message())
