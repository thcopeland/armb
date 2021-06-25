import time
from src.server.server import Server
from src.server.render_job import RenderJob
from src.shared.render_settings import RenderSettings

x = Server('', timeout=1)
x.add_worker("localhost", 7210)
x.start_job(RenderJob(1, 10, RenderSettings(100, 100, 100)))
t = 0
while True:
    x.update()
    time.sleep(0.1)
    t += 1
    print(".", end="", flush=True)
    
    if (t == 15):
        x.workers[0].status = 'READY'
    
    if (t == 20):
        x.stop_job()
        
    if t == 40:
        x.remove_worker(0)
