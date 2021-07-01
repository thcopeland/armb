import socket, re
from ..shared.render_settings import RenderSettings

def first_match_group(rexp, str):
    match = re.match(rexp, str)

    if match:
        return match.group(1)

def new_identity_message():
    return bytes(f"IDENTITY {socket.gethostname()}".encode())

def parse_identity_message(message):
    return first_match_group("\AIDENTITY ([\w\-.]+)\Z", message)

def new_sync_message(settings):
    return (bytes(f"SYNCHRONIZE {settings.synchronization_id}".encode()), bytes(settings.serialize().encode()))

def parse_sync_message(message):
    return first_match_group("\ASYNCHRONIZE (\d+)\Z", message)

def new_confirm_sync_message(id):
    return bytes(f"CONFIRM SYNCHRONIZE {id}".encode())

def parse_confirm_sync_message(message):
    return first_match_group("\ACONFIRM SYNCHRONIZE (\d+)\Z", message)

def new_request_render_message(frame):
    return bytes(f"RENDER {frame}".encode())

def parse_request_render_message(message):
    return first_match_group("RENDER (-?\d+)", message)

def new_reject_render_message(frame):
    return bytes(f"REJECT RENDER {frame}".encode())

def parse_reject_render_message(message):
    return first_match_group("REJECT RENDER (-?\d+)", message)

def new_render_complete_message(frame):
    return bytes(f"COMPLETE RENDER {frame}".encode())

def parse_render_complete_message(message):
    return first_match_group("COMPLETE RENDER (-?\d+)", message)

def new_cancel_task_message():
    return bytes("CANCEL".encode())

def new_confirm_cancelled_message():
    return bytes("CONFIRM CANCEL".encode())

def new_request_upload_message(frame):
    return bytes(f"UPLOAD {frame}".encode())

def parse_request_upload_message(message):
    return first_match_group("UPLOAD (-?\d+)", message)

def new_reject_upload_message(frame):
    return bytes(f"REJECT UPLOAD {frame}".encode())

def parse_reject_upload_message(message):
    return first_match_group("REJECT UPLOAD (-?\d+)", message)

def new_complete_upload_message(frame, filename):
    return bytes(f"COMPLETE UPLOAD {frame} {filename}".encode())

def parse_complete_upload_message(message):
    match = re.match("COMPLETE UPLOAD (-?\d+) (\S+)", message) # generated filenames contain no whitespace

    if match:
        return match.groups()
