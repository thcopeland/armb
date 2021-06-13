import socket, re
from ..shared.render_settings import RenderSettings

def identity():
    return bytes(f"IDENTITY {socket.gethostname()}".encode())

def parse_identity(message):
    match = re.match("\AIDENTITY ([a-zA-Z0-9\-_.]+)\Z", message)
    
    if match:
        return match.group(1)

def synchronize_settings(settings):
    return (bytes("SYNCHRONIZE".encode()), bytes(settings.serialize().encode()))

def synchronize_acknowledged():
    return bytes("CONFIRM SYNCHRONIZE".encode())

def request_render_frame(frame):
    return bytes(f"RENDER {frame}".encode())
