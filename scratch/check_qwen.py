from huggingface_hub import HfApi, snapshot_download
import sys

api = HfApi()
print("Checking model info...", flush=True)
info = api.model_info("Qwen/Qwen3-ASR-0.6B")
print(f"Pipeline: {info.pipeline_tag}", flush=True)
print(f"Private: {info.private}", flush=True)
print(f"Downloads: {info.downloads}", flush=True)

print("\nDownloading model...", flush=True)
snapshot_download("Qwen/Qwen3-ASR-0.6B", local_dir_use_symlinks=False)
print("Done!", flush=True)
