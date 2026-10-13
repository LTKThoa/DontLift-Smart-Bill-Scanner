"""Reviewed dataset manifests and explicit split leakage checks."""

import hashlib
import json
import re
from pathlib import Path

from .domain import ValidationError, array, identifier, integer, obj


def manifest_hash(manifest: dict) -> str:
    """Order-independent identity; all manifest metadata remains significant."""
    canonical = dict(manifest)
    canonical['samples'] = sorted(manifest['samples'], key=lambda sample: sample['sampleId'])
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_manifest(value: object, base_dir: Path | None = None, verify_images: bool = False) -> dict:
    manifest = obj(value, 'manifest')
    if integer(manifest.get('schemaVersion'), 'schemaVersion', 1) != 1:
        raise ValidationError('unsupported manifest schemaVersion')
    identifier(manifest.get('datasetVersion'), 'datasetVersion')
    if type(manifest.get('synthetic')) is not bool:
        raise ValidationError('synthetic must be explicit boolean')
    samples = array(manifest.get('samples'), 'samples', True)
    sample_ids, hashes, groups = set(), set(), {}
    counts = {'train': 0, 'validation': 0, 'test': 0}
    verified = 0
    for raw in samples:
        sample = obj(raw, 'sample')
        sid = identifier(sample.get('sampleId'), 'sampleId')
        if sid in sample_ids:
            raise ValidationError('duplicate sampleId')
        sample_ids.add(sid)
        digest = sample.get('imageSha256')
        if not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest):
            raise ValidationError('imageSha256 must be lowercase SHA-256')
        if digest in hashes:
            raise ValidationError('duplicate image hash; deduplicate before splitting')
        hashes.add(digest)
        split = sample.get('split')
        if not isinstance(split, str) or split not in counts:
            raise ValidationError('split must be train, validation or test')
        counts[split] += 1
        for kind in ('merchantGroup', 'templateGroup', 'familyGroup'):
            group = identifier(sample.get(kind), kind)
            key = (kind, group)
            if key in groups and groups[key] != split:
                raise ValidationError(f'{kind} appears across splits')
            groups[key] = split
        identifier(sample.get('qualityGroup'), 'qualityGroup')
        identifier(sample.get('source'), 'source')
        identifier(sample.get('annotationVersion'), 'annotationVersion')
        if sample.get('rightsConfirmed') is not True or sample.get('reviewStatus') != 'REVIEWED':
            raise ValidationError('samples require confirmed rights and reviewed annotation')
        if verify_images:
            relative = Path(identifier(sample.get('imagePath'), 'imagePath'))
            root = (base_dir or Path.cwd()).resolve()
            path = (root / relative).resolve()
            if relative.is_absolute() or not path.is_relative_to(root):
                raise ValidationError('imagePath must remain inside dataset directory')
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValidationError('missing image or image hash mismatch')
            verified += 1
    return {'valid': True, 'datasetVersion': manifest['datasetVersion'],
            'manifestSha256': manifest_hash(manifest), 'synthetic': manifest['synthetic'],
            'sampleCount': len(samples), 'splitCounts': counts, 'imagesVerified': verified,
            'warnings': ['EMPTY_SPLITS'] if any(count == 0 for count in counts.values()) else []}
