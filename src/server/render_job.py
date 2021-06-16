class FrameAssignment:
    def __init__(self, frame_num):
        self.frame_number = frame_num
        self.assignee = None
        self.rendered = False
        self.uploaded = False
    
    def assign(self, worker):
        self.assignee = worker
        self.rendered = False
        self.uploaded = False
    
    def unassign(self):
        self.assignee = None
    
    def assigned(self):
        return not self.assignee is None

class RenderJob:
    STATUS_RENDERING = 'RENDERING'
    STATUS_UPLOADING = 'UPLOADING'
    
    def __init__(self, frame_start, frame_end, settings):
        self.status = RenderJob.STATUS_RENDERING
        self.frame_start = frame_start
        self.frame_end = frame_end
        self.frame_count = frame_end - frame_start + 1
        self.frames_rendered = 0
        self.frames_uploaded = 0
        self.frame_assignments = [ FrameAssignment(n) for n in range(frame_start, frame_end+1) ]
        self.settings = settings
        
    def progress(self):
        if self.status == RenderJob.STATUS_RENDERING:
            return self.frames_rendered / self.frame_count
        return self.frames_uploaded / self.frame_count
    
    def rendering_complete(self):
        return self.frames_rendered == self.frame_count
    
    def uploading_complete(self):
        return self.frames_uploaded == self.frame_count
    
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
            if frame.assignee is worker and not frame.uploaded:
                return frame.frame_number
    
    def mark_rendered(self, fnum):
        if self.frame_start <= fnum <= self.frame_end:
            frame = self.frame_assignments[fnum - self.frame_start]
            
            if not frame.rendered:
                self.frames_rendered += 1
                frame.rendered = True
    
    def mark_uploaded(self, fnum):
        if self.frame_start <= fnum <= self.frame_end:
            frame = self.frame_assignments[fnum - self.frame_start]
            
            if not frame.uploaded:
                self.frames_uploaded += 1
                frame.uploaded = True
    
    def available(self, frame):
        return not frame.assigned() or not frame.assignee.ok()
