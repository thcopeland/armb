import os, math

class FrameAssignment:
    def __init__(self, frame_num):
        self.frame_number = frame_num
        self.assignee = None
        self.rendered = False
        self.uploaded = False
        self.irretrievable = False

    def assign(self, worker):
        self.assignee = worker
        self.rendered = False
        self.uploaded = False

    def unassign(self):
        self.assignee = None

    def assigned(self):
        return not self.assignee is None

class RenderJob:
    def __init__(self, frame_start, frame_end, settings):
        self.frame_start = frame_start
        self.frame_end = frame_end
        self.frame_count = frame_end - frame_start + 1
        self.frames_rendered = 0
        self.frames_uploaded = 0
        self.frames_irretrievable = 0
        self.frame_assignments = [ FrameAssignment(n) for n in range(frame_start, frame_end+1) ]
        self.settings = settings

    def progress(self):
        if not self.rendering_complete():
            return self.frames_rendered / self.frame_count
        return self.frames_uploaded / self.frame_count

    def rendering_complete(self):
        return self.frames_rendered == self.frame_count

    def uploading_complete(self):
        return (self.frames_uploaded + self.frames_irretrievable) == self.frame_count

    def assign_next_frame(self, worker):
        for frame in self.frame_assignments:
            if self.available(frame):
                frame.assign(worker)
                return frame.frame_number

    def unassign_frame(self, fnum):
        if self.frame_start <= fnum <= self.frame_end:
            frame = self.frame_assignments[fnum - self.frame_start]

            if not frame.rendered:
                frame.unassign()

    def next_for_uploading(self, worker):
        for frame in self.frame_assignments:
            if frame.assignee is worker and not (frame.uploaded or frame.irretrievable):
                return frame.frame_number

    def mark_rendered(self, fnum):
        if self.frame_start <= fnum <= self.frame_end:
            frame = self.frame_assignments[fnum - self.frame_start]

            if not frame.rendered:
                self.frames_rendered += 1
                frame.rendered = True

    def mark_irretrievable(self, fnum):
        if self.frame_start <= fnum <= self.frame_end:
            frame = self.frame_assignments[fnum - self.frame_start]

            if not frame.irretrievable:
                self.frames_irretrievable += 1
                frame.irretrievable = True

    def mark_uploaded(self, fnum):
        if self.frame_start <= fnum <= self.frame_end:
            frame = self.frame_assignments[fnum - self.frame_start]

            if not frame.uploaded:
                self.frames_uploaded += 1
                frame.uploaded = True

    def available(self, frame):
        return not frame.assigned() or not frame.assignee.ok()

    def write_frame(self, frame, extension, directory, data):
        if not os.path.exists(directory):
            os.makedirs(directory)

        digits_necessary = math.ceil(math.log10(self.frame_end))
        filename = f"{directory}{str(frame).rjust(digits_necessary, '0')}{extension}"
        with open(filename, 'wb') as f:
            f.write(data)
