import socket, threading
from ..protocol.connection import ARMBConnection
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
            self.err = utils.BadMessageError("Unable to parse REJECT message", message)
        elif job:
            job.unassign_frame(int(frame))
    
    def handle_confirm_cancel_message(self):
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
            self.connection.send(armb.request_upload_frame(frame))
            self.status = WorkerView.STATUS_UPLOADING
    
    def cancel_task(self):
        self.connection.send(armb.new_cancel_task_message())
