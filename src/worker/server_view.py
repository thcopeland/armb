class ServerView:
    def __init__(self):
        self.identity = None

    def verified(self):
        return not self.identity is None
