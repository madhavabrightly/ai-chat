"""
Memory Twin AI — Dataset Download Script
Downloads datasets from ModelScope for optional reference/style use.

Datasets are NOT used to train the model.
They are stored in the datasets/ directory for:
  - Reference persona/dialogue style guidance
  - Optional RAG retrieval testing
  - Future fine-tuning (out of scope for MVP)

Usage:
    python -m backend.scripts.download_datasets
"""
import logging
import os
import subprocess
import sys

_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _proj not in sys.path:
    sys.path.insert(0, _proj)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.config import DATASETS_DIR

DATASETS = [
    # { "name": "Display name", "dataset": "org/dataset", "size": "X MB" }
    {
        "name": "Synthetic Persona Chat",
        "dataset": "google/Synthetic-Persona-Chat",
        "size": "38.38 MB",
    },
    {
        "name": "Nemotron Personas",
        "dataset": "nv-community/Nemotron-Personas",
        "size": "2.69 GB",
    },
    {
        "name": "Multi-Round Interpersonal Dialogues",
        "dataset": "DatatangBeijing/830276groups-Multi_RoundInterpersonalDialoguesTextData",
        "size": "321.26 KB",
    },
    {
        "name": "SoulChat Corpus",
        "dataset": "YIRONGCHEN/SoulChatCorpus",
        "size": "900 MB",
    },
    {
        "name": "Multi-Emotion Dialogue Dataset",
        "dataset": "zhangzhihao/Simplified_Chinese_Multi-Emotion_Dialogue_Dataset",
        "size": "unknown",
    },
    {
        "name": "RAG System Model Training",
        "dataset": "TaitaiPhu/RAG-System-Model-Training",
        "size": "2.31 GB",
    },
]


def download_dataset(info: dict):
    """Download a single dataset using modelscope CLI."""
    dataset_name = info["dataset"]
    dest_dir = os.path.join(DATASETS_DIR, dataset_name.replace("/", "_"))
    os.makedirs(dest_dir, exist_ok=True)

    logger.info(f"\n{'=' * 46}")
    logger.info(f"Downloading: {info['name']} ({info['size']})")
    logger.info(f"Dataset: {dataset_name}")
    logger.info(f"Destination: {dest_dir}")
    logger.info(f"{'=' * 46}")

    try:
        subprocess.run(
            ["modelscope", "download", "--dataset", dataset_name, "--local_dir", dest_dir],
            check=True,
            timeout=3600,
        )
        logger.info(f"✓ {info['name']} downloaded successfully.")
    except subprocess.CalledProcessError as e:
        logger.warning(f"✗ Failed to download {info['name']}: {e}")
    except subprocess.TimeoutExpired:
        logger.warning(f"✗ Timeout downloading {info['name']} (skipping)")


if __name__ == "__main__":
    logger.info("\n" + "=" * 46)
    logger.info("Memory Twin AI — Dataset Downloader")
    logger.info(f"Datasets directory: {DATASETS_DIR}")
    logger.info("=" * 46)
    logger.info("\nNOTE: These datasets are for reference only.")
    logger.info("They are NOT used to train or fine-tune the model.")
    logger.info("The pre-trained LLM and embedding model are used as-is.\n")

    for ds in DATASETS:
        download_dataset(ds)

    logger.info("\nAll dataset downloads complete.")
    logger.info(f"Datasets stored in: {DATASETS_DIR}")
