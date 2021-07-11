import select, glob, os

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
