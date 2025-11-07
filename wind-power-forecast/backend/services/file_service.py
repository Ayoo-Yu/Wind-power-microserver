import os
from pathlib import Path
from typing import Iterable, Optional, Union

from werkzeug.utils import secure_filename

from windpower_core.storage import ensure_local_subdir, normalize_wind_farm_code, sanitize_filename


def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def save_uploaded_file(
    file,
    file_id: str,
    upload_folder: Union[str, Path],
    *,
    wind_farm_code: Optional[str] = None,
    default_wind_farm_code: str = "default-farm",
    subdirs: Optional[Iterable[str]] = None,
) -> Path:
    sanitized_name = sanitize_filename(file.filename, fallback="upload")
    filename_wo_ext, ext = os.path.splitext(secure_filename(sanitized_name))
    new_upload_filename = f"{filename_wo_ext}_{file_id}{ext or '.dat'}"

    base_dir = Path(upload_folder)
    target_dir = base_dir
    if wind_farm_code:
        normalized = normalize_wind_farm_code(wind_farm_code, default_wind_farm_code)
        target_dir = ensure_local_subdir(base_dir, normalized, *(subdirs or ()))
    else:
        target_dir.mkdir(parents=True, exist_ok=True)

    upload_path = target_dir / new_upload_filename
    file.save(upload_path)
    return upload_path


def find_file_by_id(file_id, upload_folder):
    base_dir = Path(upload_folder)
    if not base_dir.exists():
        return None

    for root, _, files in os.walk(base_dir):
        for name in files:
            if file_id in name:
                return str(Path(root) / name)
    return None
