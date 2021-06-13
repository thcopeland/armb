import socket
from ..protocol.connection import ARMBConnection, ARMBMessageTimeoutError, ARMBMessageFormatError
from ..protocol import armb
from ..shared.render_settings import RenderSettings
from .server_view import ServerView
from .. import utils

class Worker:
    def __init__(self, port, timeout=10):
        self.port = port
        self.timeout = timeout
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection = None
        self.server = None
        
        self.task = None
    
    def connected(self):
        return self.connection and self.connection.ok()
    
    def start(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(False)
        self.socket.bind(("", self.port))
        self.socket.listen()

    def stop(self):
        if self.connection:
            self.connection.close()
        self.socket.close()
    
    def update(self):
        if not self.connected():
            readable, writeable = utils.socket_status(self.socket)

            if readable:
                self.accept_connection()
        else:
            readable, writeable = utils.socket_status(self.connection.socket)
            self.connection.update(readable, writeable)
            
            if not self.connection.ok():
                raise self.connection.error
            
            if self.connection.finished_receiving():
                self.handle_message(self.connection.receive())
    
    def accept_connection(self):
        sock, addr = self.socket.accept()
        sock.setblocking(False)
        self.connection = ARMBConnection(sock, self.timeout)
        self.server = ServerView()
        self.connection.send(armb.identity())
        self.update()
    
    def handle_message(self, message):
        msg_str = message.message.tobytes().decode()

        if msg_str.startswith("IDENTITY"):
            self.handle_identity_message(message, msg_str)
        elif msg_str.startswith("SYNCHRONIZE"):
            self.handle_synchronize_message(message)
        else:
            raise utils.BadMessageError("Unable to parse unknown message", message)
    
    def handle_identity_message(self, message, msg_str):
        id = armb.parse_identity(msg_str)
        if id:
            self.server.identity = id
        else:
            raise utils.BadMessageError("Unable to parse IDENTITY message", message)
    
    def handle_synchronize_message(self, message):
        data = message.data.tobytes().decode()
        settings = RenderSettings.deserialize(data)
        
        print(f"Received: resolution ({settings.resolution_x}, {settings.resolution_y}) {settings.percentage}%")
