import socket, selectors
from ..protocol.connection import ARMBConnection, ARMBMessageTimeoutError, ARMBMessageFormatError
from ..protocol import armb
from .worker_view import WorkerView
from .supervisor_worker import SupervisorWorker
from ..shared import utils

class Supervisor:
    def __init__(self, output_dir, timeout=10):
        self.output_dir = output_dir
        self.timeout = timeout
        self.workers = []
        self.supervisor_worker = SupervisorWorker()
        self.job = None

        self.enable_supervisor_rendering()

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

    def enable_supervisor_rendering(self):
        self.supervisor_worker.enable()

    def disable_supervisor_rendering(self):
        self.supervisor_worker.disable()

    def start_job(self, job):
        if not self.job or self.job.uploading_complete():
            self.job = job
            self.supervisor_worker.synchronize(self.output_dir, self.job)

    def stop_job(self):
        if self.job:
            self.supervisor_worker.cancel()

            if not self.job.uploading_complete():
                for worker in self.workers:
                    if worker.ok() and worker.status in { WorkerView.STATUS_RENDERING, WorkerView.STATUS_UPLOADING }:
                        worker.cancel_task()
            self.job = None

    def job_progress(self):
        if self.job:
            return self.job.progress()

    def clean_workers(self):
        for worker in self.workers:
            if worker.ok() and worker.connected():
                worker.request_clean_frames()

    def update(self):
        self.supervisor_worker.update()

        for worker in self.workers:
            if worker.ok() and worker.connected():
                worker.update_connection()

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
        if worker.status == WorkerView.STATUS_READY:
            if self.job:
                if not self.job.rendering_complete():
                    worker.request_render_frame(self.job)
                elif not self.job.uploading_complete():
                    worker.request_upload_frame(self.job)
