import socket, selectors
from ..protocol.connection import ARMBConnection, ARMBMessageTimeoutError, ARMBMessageFormatError
from ..protocol import armb
from .worker_view import WorkerView
from ..shared import utils

class Server:
    def __init__(self, output_dir, timeout=10):
        self.output_dir = output_dir
        self.timeout = timeout
        self.workers = []
        self.job = None

    def add_worker(self, host, port):
        worker = WorkerView(host, port, self.timeout)
        worker.start()
        self.workers.append(worker)

    def remove_worker(self, index):
        self.workers.pop(index).stop()

    def remove_all_workers(self):
        for worker in self.workers:
            worker.stop()
        self.workers.clear()

    def start_job(self, job):
        if not self.job or self.job.uploading_complete():
            self.job = job

    def stop_job(self):
        if self.job:
            self.job = None
            for worker in self.workers:
                if worker.ok() and worker.status in { WorkerView.STATUS_RENDERING, WorkerView.STATUS_UPLOADING }:
                    worker.cancel_task()

    def job_progress(self):
        if self.job:
            return self.job.progress()

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
            worker.handle_identity_message(message, msg_str)
        elif msg_str.startswith("CONFIRM SYNCHRONIZE "):
            worker.handle_confirm_sync_message(message, msg_str)
        elif msg_str.startswith("REJECT RENDER "):
            worker.handle_reject_render_message(self.job, message, msg_str)
        elif msg_str.startswith("CONFIRM CANCEL"):
            worker.handle_confirm_cancel_message()
        elif msg_str.startswith("COMPLETE RENDER "):
            worker.handle_render_complete_message(self.job, message, msg_str)
        elif msg_str.startswith("REJECT UPLOAD "):
            worker.handle_reject_upload_message(self.job, message, msg_str)
        elif msg_str.startswith("COMPLETE UPLOAD "):
            worker.handle_upload_complete_message(self.output_dir, self.job, message, msg_str)
        else:
            worker.err = utils.BadMessageError("Unable to parse unknown message", message)

    def send_message(self, worker):
        print(worker.status)
        if worker.status == WorkerView.STATUS_READY:
            if self.job:
                if not self.job.rendering_complete():
                    worker.request_render_frame(self.job)
                elif not self.job.uploading_complete():
                    worker.request_upload_frame(self.job)
