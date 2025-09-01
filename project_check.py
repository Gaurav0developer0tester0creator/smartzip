import subprocess

tests = [
    ("Compressors", "import compressors; print('OK compressors:', dir(compressors))"),
    ("Benchmark", "benchmark.py"),
    ("Adaptive", "smartzip_adaptive.py"),
    ("Catalog", "catalog_test.py"),
]

for name, cmd in tests:
    print(f"\n=== {name} Test ===")
    if cmd.endswith(".py"):
        res = subprocess.run(["python", cmd], capture_output=True, text=True)
    else:
        res = subprocess.run(["python", "-c", cmd], capture_output=True, text=True)
    print(res.stdout or res.stderr)
