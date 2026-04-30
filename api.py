from itertools import cycle
import threading
import time
import os
 
api_keys = [
    "6aa784ef049697c8d1801ce03dd5b1344908",
    "99a5eb22f29477dc1049ad12fd597780d608",
    "00467ee59fa0c04894a15ab97c75ec6b5f09",
    "c90890031a8a16e49fe34ff07a793f5aff08"
]
 
physical_cores = os.cpu_count() or 4
num_threads = min(len(api_keys), max(1, int(physical_cores * 3 / 4)))

thread_key_lists = {}
for i, key in enumerate(api_keys):
    thread_key_lists.setdefault(i % num_threads, []).append(key)

thread_key_cycles = {idx: cycle(keys) for idx, keys in thread_key_lists.items()}

wait = 0.1

thread_local = threading.local()

def get_thread_key():
    if not hasattr(thread_local, "cycle"):
        try:
            idx = int(threading.current_thread().name.split("_")[-1]) % num_threads
        except ValueError:
            idx = 0
        keys = thread_key_lists[idx]
        thread_local.cycle = cycle(keys)
        thread_local.wait = 0.1 / len(keys)
        time.sleep(idx * 0.1)
    return next(thread_local.cycle), thread_local.wait