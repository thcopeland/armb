import socket, selectors
from ..protocol.connection import ARMBConnection, ARMBMessageTimeoutError, ARMBMessageFormatError
from ..protocol import armb
from .worker_view import WorkerView
from .. import utils

class Server:
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.workers = []
        self.job = None
    
    def add_worker(self, host, port):
        worker = WorkerView(host, port, self.timeout)
        worker.start()
        self.workers.append(worker)
    
    def remove_worker(self, index):
        self.workers.pop(index).stop()
    
    def start_job(self, job):
        if self.job and not self.job.uploading_complete():
            self.stop_job()
        else:
            self.job = job
        
    def stop_job(self):
        pass # todo
    
    def update(self):
        for worker in self.workers:
            if worker.ok() and worker.connected():
                readable, writeable = utils.socket_status(worker.socket)
                worker.update_connection(readable, writeable)
                
                if worker.connection.finished_receiving():
                    self.handle_message(worker, worker.connection.receive())
                
                if not worker.connection.sending():
                    self.send_message(worker)

    def handle_message(self, worker, message):
        msg_str = message.message.tobytes().decode()
        
        if msg_str.startswith("IDENTITY"):
            self.handle_identity_message(worker, message, msg_str)
        else:
            worker.error = utils.BadMessageError("Unable to parse unknown message", message)
    
    def handle_identity_message(self, worker, message, msg_str):
        worker.identity = armb.parse_identity(msg_str)
        if worker.identity is None:
            raise utils.BadMessageError("Unable to parse IDENTITY message", message)
        worker.status = WorkerView.STATUS_READY
    
    def send_message(self, worker):
        print(worker.status)
        if worker.status == WorkerView.STATUS_READY:
            if self.job:
                if not self.job.rendering_complete():
                    self.request_render_frame(worker)
                elif not self.job.uploading_complete():
                    self.request_upload_frame(worker)
    
    def request_render_frame(self, worker):
        if worker.settings_id == self.job.settings.synchronization_id:
            frame = self.job.assign_next_frame(worker)
            if frame:
                worker.connection.send(armb.request_render_frame(frame))
                worker.status = WorkerView.STATUS_RENDERING
        else:
            worker.connection.send(*armb.synchronize_settings(self.job.settings))
            worker.status = WorkerView.STATUS_SYNCHRONIZING
    
    def request_upload_frame(self, worker):
        frame = self.job.next_for_uploading(worker)
        
        if frame:
            worker.connection.send(arb.request_upload_frame(frame))
            worker.status = WorkerView.STATUS_UPLOADING
