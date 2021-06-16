import socket, selectors
from ..protocol.connection import ARMBConnection, ARMBMessageTimeoutError, ARMBMessageFormatError
from ..protocol import armb
from .worker_view import WorkerView
from ..shared import utils

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
        if self.job:
            self.job = None
            for worker in self.workers:
                if worker.ok() and worker.status in { WorkerView.STATUS_RENDERING, WorkerView.STATUS_UPLOADING }:
                    self.cancel_worker_task(worker)
    
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
        
        if msg_str.startswith("IDENTITY "):
            self.handle_identity_message(worker, message, msg_str)
        elif msg_str.startswith("CONFIRM SYNCHRONIZE "):
            self.handle_confirm_sync_message(worker, message, msg_str)
        elif msg_str.startswith("REJECT "):
            self.handle_reject_render_message(worker, message, msg_str)
        elif msg_str.startswith("CONFIRM CANCEL"):
            self.handle_confirm_cancel_message(worker)
        else:
            worker.err = utils.BadMessageError("Unable to parse unknown message", message)
    
    def handle_identity_message(self, worker, message, msg_str):
        worker.identity = armb.parse_identity_message(msg_str)
        if worker.identity is None:
            worker.err = utils.BadMessageError("Unable to parse IDENTITY message", message)
        else:
            worker.status = WorkerView.STATUS_READY
    
    def handle_confirm_sync_message(self, worker, message, msg_str):
        sync_id = armb.parse_confirm_sync_message(msg_str)
        
        if sync_id is None:
            worker.err = utils.BadMessageError("Unable to parse CONFIRM SYNCHRONIZE message", message)
        else:
            worker.settings_id = int(sync_id)
            worker.status = WorkerView.STATUS_READY
    
    def handle_reject_render_message(self, worker, message, msg_str):
        frame = armb.parse_reject_render_message(msg_str)
        
        if frame is None:
            worker.err = utils.BadMessageError("Unable to parse REJECT message", message)
        elif self.job:
            self.job.unassign_frame(int(frame))
    
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
                worker.connection.send(armb.new_request_render_message(frame))
                worker.status = WorkerView.STATUS_RENDERING
        else:
            worker.connection.send(*armb.new_sync_message(self.job.settings))
            worker.status = WorkerView.STATUS_SYNCHRONIZING
    
    def request_upload_frame(self, worker):
        frame = self.job.next_for_uploading(worker)
        
        if frame:
            worker.connection.send(armb.request_upload_frame(frame))
            worker.status = WorkerView.STATUS_UPLOADING
    
    def cancel_worker_task(self, worker):
        worker.connection.send(armb.new_cancel_task_message())
    
    def handle_confirm_cancel_message(self, worker):
        worker.status = WorkerView.STATUS_READY
