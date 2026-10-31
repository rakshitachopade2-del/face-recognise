import io
import os
import uuid
import warnings
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps
from PIL import __version__ as pillow_version
from pillow_heif import __version__ as heif_version
from pillow_heif import register_heif_opener

register_heif_opener()
PREPARATION_VERSION = f"exif-srgb-v2:pillow-{pillow_version}:heif-{heif_version}"


class MediaError(ValueError):
    pass


def decode(data, max_bytes, max_pixels):
    if len(data) > max_bytes:
        raise MediaError("file_too_large")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as im:
                fmt = im.format
                if fmt not in {"JPEG", "PNG", "HEIF"}:
                    raise MediaError("unsupported_format")
                if im.width * im.height > max_pixels or im.width < 1 or im.height < 1:
                    raise MediaError("pixel_limit")
                orientation = int(im.getexif().get(274, 1))
                oriented = ImageOps.exif_transpose(im)
                if im.info.get("icc_profile"):
                    try:
                        oriented = ImageCms.profileToProfile(oriented,
                            ImageCms.ImageCmsProfile(io.BytesIO(im.info["icc_profile"])),
                            ImageCms.createProfile("sRGB"), outputMode="RGB")
                    except (ValueError, OSError, ImageCms.PyCMSError) as exc:
                        raise MediaError("invalid_or_unsupported_color_profile") from exc
                else:
                    oriented = oriented.convert("RGB")  # Untagged images are explicitly treated as sRGB.
                oriented.load()
                rgb = np.asarray(oriented).copy()
                output = io.BytesIO()
                oriented.save(output, "PNG")
        return rgb, output.getvalue(), fmt, orientation
    except MediaError:
        raise
    except Exception as exc:
        raise MediaError("corrupt_or_unsupported_image") from exc


def safe_path(root: Path, key: str):
    path = (root / key).resolve()
    if root.resolve() not in path.parents:
        raise MediaError("unsafe_path")
    return path


def atomic_write(root: Path, key: str, data: bytes):
    target = safe_path(root, key)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_name(uuid.uuid4().hex + ".tmp")
    try:
        with open(temporary, "xb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
