import socket, threading
from ..protocol.connection import ARMBConnection
from ..protocol import armb

class WorkerView:
    STATUS_INITIALIZING = 'INITIALIZING'
    STATUS_SYNCHRONIZING = 'SYNCHRONIZING'
    STATUS_RENDERING = 'RENDERING'
    STATUS_UPLOADING = 'UPLOADING'
    STATUS_READY = 'READY'
    STATUS_ERROR = 'ERROR'
    
    def __init__(self, host, port, timeout):
        self.status = WorkerView.STATUS_INITIALIZING
        self.identity = None
        self.settings_id = -1
        
        self.err = None
        self.timeout = timeout
        self.address = (host, port)
        self.socket = None
        self.connection = None
        
    def verified(self):
        return not self.identity is None
    
    def connected(self):
        return not self.connection is None
    
    def ok(self):
        return self.error() is None
    
    def error(self):
        if self.err:
            return self.err
        elif self.connection and self.connection.error:
            return self.connection.error
    
    def start(self, block=False):
        def establish_connection():
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect(self.address)
                self.socket.setblocking(False)
                self.connection = ARMBConnection(self.socket, self.timeout)
                self.connection.send(armb.identity())
            except OSError as e:
                self.err = e
        
        if block:
            establish_connection()
        else:
            threading.Thread(target=establish_connection).start()
    
    def stop(self):
        if self.connection:
            self.connection.close()
    
    def update_connection(self, read, write):
        if self.connected():
            self.connection.update(read, write)
    
            if read and not self.connection.receiving():
                self.connection.receive()
        
        if self.error():
            self.status = WorkerView.STATUS_ERROR
