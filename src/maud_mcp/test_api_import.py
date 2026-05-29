"""Check import"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from maud_api import MaudAPI, MaudRunner, INSGenerator, DataConverter, RefinementConfig, RefinementResult

JAVA_HOME = r"D:\00xXRD\Mand-2.99993\jdk"
MAUD_JAR = r"D:\00xXRD\Mand-2.99993\lib\Maud.jar"
WORK_DIR = r"D:\00xXRD\maud-cli-dev\test_run"

api = MaudAPI(java_home=JAVA_HOME, maud_jar=MAUD_JAR)

config = RefinementConfig(
    template_par="default.par",
    iterations=3,
    data_files=["sample_data.xy"],
    cif_phases=["ZnO.cif"],
    output_dir=WORK_DIR,
    auto_background=True
)

result = api.runner.refine(config)
print(f"success={result.success}, rwp={result.rwp}, gof={result.gof}, wss={result.wss}")

# Show log excerpt
for line in result.log.split('\n'):
    if 'Rwp (%)' in line:
        print(f"RWP_LINE: {line}")
    if 'sig=' in line:
        print(f"SIG_LINE: {line}")
    if 'Starting refinement' in line:
        print(f"REFINE_START: {line}")