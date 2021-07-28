from ..blender import blender
from ..shared.task import RenderTask
from ..shared import utils

class SupervisorWorker:
    def __init__(self):
        self.identity = '__supervisor__'
        self.task = None
        self.enabled = True
        self.output_dir = None
        self.job = None

    def __eq__(self, other):
        return self.identity == other.identity

    def __hash__(self):
        return hash(self.identity)

    def ok(self):
        return True

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def synchronize(self, output_dir, job):
        self.output_dir = output_dir
        self.job = job

    def ready(self):
        return self.enabled and self.job and self.task is None

    def preparing(self):
        return self.enabled and self.job and self.task and not self.task.started

    def rendering(self):
        return self.enabled and self.task and self.task.started

    def cancel(self):
        if self.task:
            self.job = None
            self.task.remote_cancelled = True

    def update(self):
        if self.ready():
            frame = self.job.assign_next_frame(self)

            if frame:
                self.task = RenderTask(frame, self.job.frame_end)

        if self.preparing():
            path = utils.filename_for_frame(self.task.frame, self.task.max_frame, '', self.output_dir)
            blender.apply_render_settings(self.job.settings)
            if 'CANCELLED' not in blender.render_frame(self.task.frame, path):
                blender.set_render_callbacks(self.handle_render_complete, self.handle_render_cancel)
                self.task.started = True

    def handle_render_complete(self, scene, bpy_context):
        if self.job:
            self.job.mark_rendered(self.task.frame)
            self.job.mark_uploaded(self.task.frame)
            blender.clear_render_callbacks()
        self.task = None

    def handle_render_cancel(self, scene, bpy_context):
        if self.task.remote_cancelled:
            blender.apply_render_settings(self.job.original_settings)
            blender.clear_render_callbacks()
            self.task = None
        else:
            self.task.started = False
            self.task.record_failed_attempt()
            if self.task.failed():
                blender.apply_render_settings(self.job.original_settings)
                blender.clear_render_callbacks()
                self.job.unassign_frame(self.task.frame)
                self.task = None
