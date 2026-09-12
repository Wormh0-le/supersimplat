#!/usr/bin/env python3
"""Build source-RGB/mask bundle, never renderer-aligned or User Confirmed by fiat."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil

from PIL import Image, ImageDraw

SPEC = Path(__file__).resolve().parents[1] / 'benchmarks' / 'teatime'


def read_verified(root: Path, relative: str, expected: str) -> bytes:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Asset path escapes preparation directory')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'Asset SHA mismatch: {relative}')
    return data


def binary_mask(path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as source:
        if source.size != size or source.mode not in ('1', 'L'):
            raise ValueError(f'Mask dimension/mode mismatch: {path}')
        mask = source.convert('L')
        if not set(mask.tobytes()) <= {0, 255}:
            raise ValueError(f'Mask is not binary: {path}')
        if mask.getbbox() is None:
            raise ValueError(f'Empty mask: {path}')
        return mask


def build(prepared: Path, out: Path, spec_dir: Path = SPEC) -> dict:
    repo = Path(__file__).resolve().parents[1]
    if out.resolve().is_relative_to(repo) or out.exists():
        raise ValueError('Use a new external output directory')
    spec = json.loads((spec_dir / 'benchmark.json').read_text())
    draft = json.loads((spec_dir / 'C.annotations.json').read_text())
    if [v['role'] for v in spec['views'] if v['fusionInput']] != ['A', 'B']:
        raise ValueError('Only A/B may be fusion inputs')
    if draft['status'] != 'assistant-draft-not-human-confirmed':
        raise ValueError('Draft provenance changed')
    for name, digest_key in (('cameras.bin', 'camerasSHA256'), ('images.bin', 'imagesSHA256')):
        read_verified(prepared, spec['calibrationSource']['path'] + '/' + name, spec['calibrationSource'][digest_key])
    for view in spec['views']:
        image = view['sourceRGB']
        read_verified(prepared, image['path'], image['sha256'])
        for mask in view['annotations']:
            if mask['provenance'] == 'publisher-test-mask':
                read_verified(prepared, mask['sourcePath'], mask['sha256'])
    out.mkdir(parents=True)
    records = []
    for view in spec['views']:
        role = view['role']
        rgb_path = out / f'{role}.rgb.jpg'
        shutil.copyfile(prepared / view['sourceRGB']['path'], rgb_path)
        with Image.open(rgb_path) as source:
            rgb = source.convert('RGB')
        if rgb.size != (view['camera']['width'], view['camera']['height']):
            raise ValueError('RGB/calibration dimensions differ')
        for annotation in view['annotations']:
            task = annotation['taskId']
            path = out / f'{role}.{task}.mask.png'
            if role != 'C':
                shutil.copyfile(prepared / annotation['sourcePath'], path)
            else:
                if (draft['width'], draft['height']) != rgb.size:
                    raise ValueError('C draft dimension mismatch')
                region = draft['tasks'][task]
                for polygon in [region['outer'], *region['holes']]:
                    if len(polygon) < 3 or any(len(p) != 2 or not all(math.isfinite(v) for v in p) or not (0 <= p[0] < rgb.width and 0 <= p[1] < rgb.height) for p in polygon):
                        raise ValueError('Invalid C draft polygon')
                mask = Image.new('L', rgb.size, 0)
                painter = ImageDraw.Draw(mask)
                painter.polygon([tuple(p) for p in region['outer']], fill=255)
                for hole in region['holes']:
                    painter.polygon([tuple(p) for p in hole], fill=0)
                mask.save(path)
            mask = binary_mask(path, rgb.size)
            overlay = rgb.copy()
            overlay.paste(Image.blend(rgb, Image.new('RGB', rgb.size, (0, 220, 170)), 0.4), mask=mask)
            overlay.save(out / f'{role}.{task}.overlay.png')
            records.append({'role': role, 'task': task, 'path': path.name,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'provenance': annotation['provenance'], 'userConfirmed': False,
                            'fusionEligibleForSourceOracle': role != 'C',
                            'currentRendererAligned': False})
    shutil.copyfile(spec_dir / 'benchmark.json', out / 'benchmark.json')
    report = {'status': 'source-reference-only', 'masks': records,
              'gpuValidation': 'not-performed', 'notes': 'A/B publisher masks; C assistant drafts. No resize. No automatic promotion to renderer Stable Masks.'}
    (out / 'bundle-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.prepared, args.out)
