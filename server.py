import time
from src.server.server import Server
from src.server.render_job import RenderJob
from src.shared.render_settings import RenderSettings

x = Server()
x.add_worker("localhost", 7210)
x.start_job(RenderJob(1, 10, RenderSettings(100, 100, 100), 10))
while True:
    x.update()
    time.sleep(0.1)
    print(".", end="", flush=True)
