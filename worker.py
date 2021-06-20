import time
from src.worker.worker import Worker

x = Worker('', 7210)
x.start()

t = 0
while True:
    x.update()
    time.sleep(0.1)
    t += 1
    # if t == 70:
    #     x.stop()
    #     print("Closing Time ♬ ♩")
    if x.closed:
        print("*", end="", flush=True)
    else:
        print("-", end="", flush=True)
