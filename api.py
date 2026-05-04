from itertools import cycle
import threading
import time
import sys
import os


def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

os.chdir(get_base_path())

def load_keys(filepath = ("api.env")):
    keys = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and "=" in line:
                keys.append(line.split("=", 1)[1])
    return keys

api_keys = load_keys()
 

physical_cores = os.cpu_count() or 4
num_threads = min(len(api_keys), max(1, int(physical_cores * 3 / 4)))

thread_key_lists = {}
for i, key in enumerate(api_keys):
    thread_key_lists.setdefault(i % num_threads, []).append(key)

thread_key_cycles = {idx: cycle(keys) for idx, keys in thread_key_lists.items()}

default_wait = 0.11

thread_local = threading.local()


def get_thread_key():
    if not hasattr(thread_local, "cycle"):
        try:
            idx = int(threading.current_thread().name.split("_")[-1]) % num_threads
        except ValueError:
            idx = 0
        keys = thread_key_lists[idx]
        thread_local.cycle = cycle(keys)
        thread_local.wait = default_wait / len(keys)
        time.sleep(idx * default_wait)
    return next(thread_local.cycle), thread_local.wait