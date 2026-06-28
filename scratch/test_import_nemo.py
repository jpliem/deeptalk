import sys
import traceback

print("Starting import test...")
try:
    import nemo.collections.asr as nemo_asr
    print("ASR module imported successfully!")
except Exception as e:
    print("FAILED to import ASR module!")
    traceback.print_exc()
