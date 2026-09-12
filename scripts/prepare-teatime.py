#!/usr/bin/env python3
"""Prepare pinned LERF-Mask assets externally; no rendering or GPU qualification."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import urllib.request
import zipfile

from PIL import Image

SOURCES = {
    "data": ("87eaf79de186f3c717b872846f277d39e16dca07", "data/lerf_mask/teatime.zip", "8e1ac21925d0eb5f4a0a41a71404f73a78f1dcd84bdc046049b6b3e723952ca1"),
    "model": ("34cbf65561144792d7a1861b38274bd7be18c8bc", "checkpoint/lerf_mask/teatime.zip", "d93f1f907197a8cfb807c7b44c180d787eb0fedb1361837fa239de1bde4fa67e"),
}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch(name: str, out: Path) -> Path:
    revision, relative, expected = SOURCES[name]
    destination = out / f"{name}.zip"
    if destination.exists():
        if sha256(destination) != expected:
            raise ValueError(f"Existing {name} archive has wrong SHA-256")
        return destination
    url = f"https://huggingface.co/mqye/Gaussian-Grouping/resolve/{revision}/{relative}?download=true"
    part = destination.with_suffix(".partial")
    try:
        with urllib.request.urlopen(url, timeout=180) as response, part.open("wb") as stream:
            shutil.copyfileobj(response, stream, length=1024 * 1024)
        if sha256(part) != expected:
            raise ValueError(f"Downloaded {name} archive has wrong SHA-256")
        part.replace(destination)
    finally:
        part.unlink(missing_ok=True)
    return destination


def member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"Unsafe archive path: {name}")
    return path


def put(root: Path, relative: str, data: bytes) -> dict:
    path = root.joinpath(*member_path(relative).parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def prepare(out: Path, with_model: bool) -> dict:
    repo = Path(__file__).resolve().parents[1]
    if out.resolve().is_relative_to(repo):
        raise ValueError("Use an external --out directory, not a path inside the repository")
    out.mkdir(parents=True, exist_ok=True)
    result = out / "prepared"
    if result.exists():
        raise ValueError("prepared/ already exists; choose a fresh output directory")
    result.mkdir()
    report = {"kind": "lerf-teatime-asset-inventory/v1", "status": "source-annotations-only", "rendererValidated": False,
              "humanConfirmedForCurrentRenderer": False, "sources": SOURCES, "masks": [], "views": [], "model": None}
    with zipfile.ZipFile(fetch("data", out)) as archive:
        names = sorted(n for n in archive.namelist() if not n.endswith("/"))
        for name in names:
            member_path(name)
        put(result, "data-members.json", (json.dumps(names, indent=2) + "\n").encode())
        images = {PurePosixPath(n).name: n for n in names if "/images/" in n and PurePosixPath(n).suffix.lower() in (".jpg", ".jpeg", ".png")}
        train = {PurePosixPath(n).stem for n in names if "/images_train/" in n}
        tests = sorted(n for n in images if PurePosixPath(n).stem not in train) if train else []
        report["imageCount"] = len(images)
        report["trainImageCount"] = len(train)
        report["testImageNames"] = tests
        for idx, name in enumerate(tests):
            data = archive.read(images[name])
            record = put(result, f"reference/rgb/{name}", data)
            with Image.open(io.BytesIO(data)) as image:
                record.update({"testIndex": idx, "sourceMember": images[name], "width": image.width, "height": image.height, "mode": image.mode})
            report["views"].append(record)
        for name in names:
            path = PurePosixPath(name)
            if "test_mask" in path.parts and path.suffix.lower() == ".png":
                suffix = path.parts[path.parts.index("test_mask") + 1:]
                data = archive.read(name)
                record = put(result, "reference/test_mask/" + "/".join(suffix), data)
                with Image.open(io.BytesIO(data)) as image:
                    colors = image.convert("L").getcolors(maxcolors=257)
                    record.update({"sourceMember": name, "sourceView": suffix[0], "prompt": path.stem,
                                   "width": image.width, "height": image.height, "mode": image.mode,
                                   "grayCounts": colors})
                report["masks"].append(record)
            if path.name in ("cameras.bin", "images.bin", "cameras.txt", "images.txt") and "sparse" in path.parts:
                put(result, "calibration/" + "/".join(path.parts), archive.read(name))
    if not report["masks"]:
        raise ValueError("No source test masks: cannot manufacture annotations")
    if with_model:
        with zipfile.ZipFile(fetch("model", out)) as archive:
            names = sorted(n for n in archive.namelist() if not n.endswith("/"))
            for name in names:
                member_path(name)
            put(result, "model-members.json", (json.dumps(names, indent=2) + "\n").encode())
            for name in names:
                if PurePosixPath(name).name in ("cameras.json", "cfg_args"):
                    put(result, "model-metadata/" + name, archive.read(name))
            plys = [n for n in names if n.endswith("/iteration_30000/point_cloud.ply")]
            if len(plys) != 1:
                raise ValueError(f"Expected one 30k Gaussian PLY, got {plys}")
            # Never execute cfg_args or unpickle identity/classifier tensors.
            target = out / "point_cloud.ply"
            with archive.open(plys[0]) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            header = []
            with target.open("rb") as stream:
                for _ in range(1024):
                    line = stream.readline(4096).decode("ascii").strip()
                    header.append(line)
                    if line == "end_header":
                        break
                else:
                    raise ValueError("Invalid/oversized PLY header")
            report["model"] = {"sourceMember": plys[0], "sha256": sha256(target), "bytes": target.stat().st_size, "header": header,
                               "semanticTraining": "Gaussian Grouping checkpoint; identity features must not be selection input; not claimed vanilla RGB-only trained baseline"}
    put(result, "inventory.json", (json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--with-model", action="store_true")
    args = parser.parse_args()
    prepare(args.out, args.with_model)
