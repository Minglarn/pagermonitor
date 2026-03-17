import subprocess

multimon_cmd = [
    'multimon-ng', '-v', '1', '-C', 'SE', '-f', 'alpha', '-t', 'raw',
    '-a', 'POCSAG512', '-a', 'POCSAG1200', '-a', 'POCSAG2400', '-'
]

print("Executing:", " ".join(multimon_cmd))
try:
    p2 = subprocess.Popen(multimon_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    out, err = p2.communicate(timeout=2)
    print("STDOUT:", out)
    print("STDERR:", err)
    print("Return code:", p2.returncode)
except Exception as e:
    print("Exception:", e)
