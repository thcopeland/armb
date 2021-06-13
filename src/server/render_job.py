import time

class FrameAssignment:
    def __init__(self, frame_num):
        self.assignment_time = 0
        self.frame_number = frame_num
        self.assignee = None
        self.confirmed = False
        self.rendered = False
        self.uploaded = False
    
    def assign(self, worker):
        self.assignee = worker
        self.assignment_time = time.time()
        self.confirmed = False
        self.rendered = False
        self.uploaded = False
    
    def assigned(self):
        return not self.assignee is None

class RenderJob:
    STATUS_RENDERING = 'RENDERING'
    STATUS_UPLOADING = 'UPLOADING'
    
    def __init__(self, frame_start, frame_end, settings, confirmation_timeout):
        self.status = RenderJob.STATUS_RENDERING
        self.frame_start = frame_start
        self.frame_end = frame_end
        self.frame_count = frame_end - frame_start + 1
        self.frames_rendered = 0
        self.frames_uploaded = 0
        self.frame_assignments = [ FrameAssignment(n) for n in range(frame_start, frame_end+1) ]
        self.confirmation_timeout = confirmation_timeout
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
    
    def next_for_uploading(self, worker):
        for frame in self.frame_assignments:
            if frame.assignee is worker and not frame.uploaded:
                return frame.frame_number
        
    def mark_confirmed(self, frame):
        self.frame_assignments[frame].confirmed = True
    
    def mark_rendered(self, frame):
        if not self.frame_assignments[frame].rendered:
            self.frames_rendered += 1
            self.frame_assignments[frame].rendered = True
        
    def mark_uploaded(self, frame):
        if not self.frame_assignments[frame].uploaded:
            self.frames_uploaded += 1
            self.frame_assignments[frame].uploaded = True
                
    def available(self, frame):
        unassigned = not frame.assigned()
        unconfirmed = not frame.confirmed and time.time() - frame.assignment_time > self.confirmation_timeout
        assignee_died = frame.assigned() and not frame.assignee.ok()
        
        return unassigned or unconfirmed or assignee_died
