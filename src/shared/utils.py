import socket, select, glob, os, math

def socket_status(socket):
    read, write, err = select.select([socket], [socket], [], 0)
    return (socket in read, socket in write)

class BadMessageError(Exception):
    def __init__(self, description, message):
        self.message = description
        self.message_data = message

def delete_rendered_images(path, extension):
    # removes all files starting with a number, ending with the extension
    for file in glob.glob(f"{path}[0-9]*{extension}"):
        os.remove(file)

    directory, prefix = os.path.split(path)
    if not os.listdir(directory):
        os.rmdir(directory)

def get_local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip = None

    try:
        sock.connect(('10.255.255.255', 1))
        ip = sock.getsockname()[0]
    finally:
        sock.close()

    return ip

def filename_for_frame(frame, max_frame, extension, directory):
    digits_necessary = int(math.log10(abs(max_frame)))+1
    return f"{directory}{str(frame).rjust(digits_necessary, '0')}{extension}"
