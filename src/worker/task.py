class RenderTask:
    def __init__(self, frame):
        self.frame = frame
        self.started = False
        self.remote_cancelled = False
        # self.attempts = 0
    
class UploadTask:
    def __init__(self, frame):
        self.frame = frame
    
