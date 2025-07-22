import os
import json
import psutil

CONFIG_FILE = 'config.json'

# Detect system resources
def detect_resources():
    cpu_cores = os.cpu_count() or 1
    virtual_mem = psutil.virtual_memory()
    total_mem_gb = virtual_mem.total // (1024 ** 3)
    return cpu_cores, total_mem_gb

# Recommend concurrency settings
def recommend_settings(cpu_cores, total_mem_gb):
    # Conservative defaults, can be tuned
    max_threads = min(32, cpu_cores * 2)
    # Assume each thread/process needs at least 256MB
    max_processes = min(cpu_cores, max(1, total_mem_gb // 0.25))
    return {
        'cpu_cores': cpu_cores,
        'total_mem_gb': total_mem_gb,
        'max_threads': max_threads,
        'max_processes': max_processes
    }

def main():
    cpu_cores, total_mem_gb = detect_resources()
    settings = recommend_settings(cpu_cores, total_mem_gb)
    print(json.dumps(settings, indent=2))
    with open(CONFIG_FILE, 'w') as f:
        json.dump(settings, f, indent=2)
    print(f"Config written to {CONFIG_FILE}")

if __name__ == '__main__':
    main() 