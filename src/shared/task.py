class RenderTask:
    def __init__(self, frame, max_frame):
        self.frame = frame
        self.max_frame = max_frame
        self.started = False
        self.remote_cancelled = False
        self.attempts = 0

    def record_failed_attempt(self):
        self.attempts += 1

    def failed(self):
        return self.attempts >= 3
