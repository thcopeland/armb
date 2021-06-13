import time
from src.worker.worker import Worker

x = Worker(7210)
x.start()

while True:
    x.update()
    time.sleep(0.1)
    print(".", end="", flush=True)
