from pathlib import Path
from urllib.parse import unquote, urlparse, urlunparse

import ujson as json

YOLO_EXPORTS_WITH_IMAGES = {'YOLO_WITH_IMAGES', 'YOLO_OBB_WITH_IMAGES'}


def normalize_yolo_export_artifacts(output_dir, export_type):
    export_type_name = getattr(export_type, 'name', export_type)
    if export_type_name not in YOLO_EXPORTS_WITH_IMAGES:
        return

    output_root = Path(output_dir)
    images_dir = output_root / 'images'
    labels_dir = output_root / 'labels'

    if not images_dir.exists() or not labels_dir.exists():
        return

    image_stem_map = _decode_image_filenames(images_dir)
    _decode_label_filenames(labels_dir, image_stem_map)
    _remove_orphan_labels(images_dir, labels_dir)
    _remove_empty_directories(labels_dir)


def normalize_tasks_for_converter(tasks):
    return _normalize_value(tasks)


def normalize_export_file_for_converter(file_path):
    file_path = Path(file_path)

    with file_path.open(encoding='utf-8') as input_file:
        payload = json.load(input_file)

    normalized_payload = normalize_tasks_for_converter(payload)
    if normalized_payload == payload:
        return

    with file_path.open('w', encoding='utf-8') as output_file:
        json.dump(normalized_payload, output_file, ensure_ascii=False)


def _decode_image_filenames(images_dir):
    image_stem_map = {}

    for file_path in sorted(path for path in images_dir.rglob('*') if path.is_file()):
        decoded_name = unquote(file_path.name)
        target_path = _rename_with_unique_name(file_path, decoded_name)
        image_stem_map[file_path.stem] = target_path.stem

    return image_stem_map


def _decode_label_filenames(labels_dir, image_stem_map):
    for file_path in sorted(path for path in labels_dir.rglob('*') if path.is_file()):
        suffix = ''.join(file_path.suffixes) or '.txt'
        target_stem = image_stem_map.get(file_path.stem, unquote(file_path.stem))
        _rename_with_unique_name(file_path, f'{target_stem}{suffix}')


def _remove_orphan_labels(images_dir, labels_dir):
    image_stems = {path.stem for path in images_dir.rglob('*') if path.is_file()}

    for file_path in labels_dir.rglob('*.txt'):
        if file_path.stem not in image_stems:
            file_path.unlink()


def _remove_empty_directories(root_dir):
    for dir_path in sorted((path for path in root_dir.rglob('*') if path.is_dir()), reverse=True):
        if not any(dir_path.iterdir()):
            dir_path.rmdir()


def _rename_with_unique_name(file_path, target_name):
    target_path = file_path.with_name(target_name)
    if target_path == file_path:
        return file_path

    suffix = ''.join(target_path.suffixes)
    stem = target_path.name[: -len(suffix)] if suffix else target_path.name
    candidate_path = target_path
    index = 1

    while candidate_path.exists():
        candidate_name = f'{stem}_{index}{suffix}'
        candidate_path = file_path.with_name(candidate_name)
        index += 1

    file_path.rename(candidate_path)
    return candidate_path


def _normalize_value(value):
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, str):
        return _normalize_uploaded_url(value)
    return value


def _normalize_uploaded_url(value):
    if '/data/upload/' not in value:
        return value

    parsed = urlparse(value)
    path = parsed.path or value
    if '/data/upload/' not in path or '%' not in path:
        return value

    normalized_path = unquote(path)

    if parsed.scheme or parsed.netloc:
        return urlunparse(parsed._replace(path=normalized_path))

    if parsed.query or parsed.fragment or parsed.params:
        return urlunparse(parsed._replace(path=normalized_path))

    return normalized_path
