"""测试 MAUD Java 调用"""
import subprocess
import os
import sys

JAVA_EXE = r"D:\00xXRD\Mand-2.99993\jdk\bin\java.exe"
MAUD_JAR = r"D:\00xXRD\Mand-2.99993\lib\Maud.jar"
INS_FILE = r"D:\00xXRD\maud-cli-dev\test_run\test.ins"

# Get all jars in lib directory
lib_dir = os.path.dirname(MAUD_JAR)
jars = [MAUD_JAR] + [
    os.path.join(lib_dir, f)
    for f in os.listdir(lib_dir)
    if f.endswith(".jar")
]
classpath = ";".join(jars)

print(f"CLASSPATH: {classpath[:200]}...")
print(f"INS_FILE: {INS_FILE}")

cmd = [
    JAVA_EXE,
    "-Xmx512m",
    "-cp", classpath,
    "com.radiographema.MaudText",
    "-f", INS_FILE
]

print(f"CMD: {' '.join(cmd[:4])} ...")

proc = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=30
)

print("STDOUT:")
print(proc.stdout[-2000:] if len(proc.stdout) > 2000 else proc.stdout)
print("\nSTDERR:")
print(proc.stderr[-1000:] if len(proc.stderr) > 1000 else proc.stderr)
print(f"\nReturn code: {proc.returncode}")