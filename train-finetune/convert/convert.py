"""Convert safetensors to GGUF for Ollama.

Usage:
    python convert.py <model_dir> [--llama-cpp <path>] [--outtype f16]

Steps:
    1. Fix config.json vocab_size to match tokenizer
    2. Pad embedding weights if needed
    3. Convert to GGUF using llama.cpp convert_hf_to_gguf.py
    4. Create Ollama Modelfile and register model

Requirements:
    - gguf Python package (pip install gguf)
    - llama.cpp cloned locally (for convert_hf_to_gguf.py)
    - safetensors, torch, transformers, sentencepiece
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_LLAMA_CPP = str(Path(__file__).parent.parent.parent / "llama.cpp")
GGUF_NAME = "functiongemma-finetuned.gguf"
MODLEFILE_NAME = "Modelfile"


def fix_vocab_size(model_dir: Path) -> int:
    """Fix config.json vocab_size to match the tokenizer's max token ID + 1.

    Gemma3 tokenizer has vocab_size 262144 but max token ID 262145,
    so config needs vocab_size = 262146.

    Returns the new vocab_size.
    """
    config_path = model_dir / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    old_vocab = config.get("vocab_size", 0)
    new_vocab = old_vocab + 2  # max_token_id + 1

    if old_vocab == new_vocab:
        print(f"  vocab_size already correct: {old_vocab}")
        return old_vocab

    config["vocab_size"] = new_vocab
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print(f"  Fixed vocab_size: {old_vocab} -> {new_vocab}")
    return new_vocab


def pad_embeddings(model_dir: Path, target_vocab: int) -> bool:
    """Pad embedding matrix to match vocab_size.

    The model may have fewer embedding rows than vocab_size.
    This pads with zeros so the GGUF converter doesn't error.

    Returns True if padding was applied.
    """
    from safetensors.torch import load_file, save_file
    import torch

    safetensor_files = list(model_dir.glob("*.safetensors"))
    if not safetensor_files:
        print("  No safetensors found, skipping padding")
        return False

    modified = False
    for st_path in safetensor_files:
        tensors = load_file(str(st_path))

        for key in tensors:
            if "embed_tokens" in key or "token_embd" in key:
                current_rows = tensors[key].shape[0]
                if current_rows >= target_vocab:
                    print(f"  {key}: {current_rows} rows, no padding needed")
                    continue

                pad_size = target_vocab - current_rows
                hidden = tensors[key].shape[1]
                padding = torch.zeros(pad_size, hidden, dtype=tensors[key].dtype)
                tensors[key] = torch.cat([tensors[key], padding], dim=0)
                print(f"  Padded {key}: {current_rows} -> {target_vocab} ({pad_size} rows)")
                modified = True

        if modified:
            save_file(tensors, str(st_path))

    return modified


def convert_to_gguf(model_dir: Path, llama_cpp: Path, outtype: str) -> Path:
    """Run llama.cpp convert_hf_to_gguf.py to produce GGUF file.

    Returns the path to the generated GGUF file.
    """
    convert_script = llama_cpp / "convert_hf_to_gguf.py"
    if not convert_script.exists():
        print(f"ERROR: {convert_script} not found")
        print(f"Clone llama.cpp first: git clone https://github.com/ggml-org/llama.cpp")
        sys.exit(1)

    output_path = Path.cwd() / GGUF_NAME
    cmd = [
        sys.executable,
        str(convert_script),
        str(model_dir),
        "--outfile", str(output_path),
        "--outtype", outtype,
    ]

    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)

    print(f"  Output: {output_path} ({output_path.stat().st_size / 1e6:.1f} MB)")
    return output_path


def create_ollama_model(gguf_path: Path, model_name: str = "functiongemma-finetuned"):
    """Create Ollama Modelfile and register the model."""
    modelfile_path = gguf_path.parent / MODLEFILE_NAME
    modelfile_path.write_text(
        f"FROM {gguf_path.resolve()}\n",
        encoding="utf-8",
    )
    print(f"  Created {MODLEFILE_NAME}")

    # Stop ollama if running
    subprocess.run(["ollama", "stop", model_name], capture_output=True)

    # Create model
    result = subprocess.run(
        ["ollama", "create", model_name, "-f", str(modelfile_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"WARNING: ollama create failed: {result.stderr}")
    else:
        print(f"  Ollama model '{model_name}' created")


def main():
    parser = argparse.ArgumentParser(description="Convert safetensors to GGUF")
    parser.add_argument("model_dir", help="Path to HuggingFace model directory")
    parser.add_argument(
        "--llama-cpp",
        default=DEFAULT_LLAMA_CPP,
        help=f"Path to llama.cpp (default: {DEFAULT_LLAMA_CPP})",
    )
    parser.add_argument(
        "--outtype",
        default="f16",
        choices=["f32", "f16", "q8_0", "q4_0"],
        help="Output quantization type (default: f16)",
    )
    parser.add_argument(
        "--ollama",
        action="store_true",
        help="Also create Ollama model after conversion",
    )
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    if not model_dir.exists():
        print(f"ERROR: {model_dir} does not exist")
        sys.exit(1)

    print(f"Model: {model_dir.resolve()}")
    print()

    # Step 1: Fix vocab size
    print("[1/3] Fixing vocab_size...")
    vocab_size = fix_vocab_size(model_dir)
    print()

    # Step 2: Pad embeddings
    print("[2/3] Padding embeddings...")
    pad_embeddings(model_dir, vocab_size)
    print()

    # Step 3: Convert to GGUF
    print("[3/3] Converting to GGUF...")
    gguf_path = convert_to_gguf(model_dir, Path(args.llama_cpp), args.outtype)
    print()

    # Optional: Create Ollama model
    if args.ollama:
        print("Creating Ollama model...")
        create_ollama_model(gguf_path)
        print()

    print("Done!")


if __name__ == "__main__":
    main()
