"""Shared validation and digesting for editor-owned AI CameraBindings."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping


def _nonnegative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f"AI Select Anchor {field_name} must be a non-negative integer"
        )
    return value


def _positive_integer(value: object, field_name: str) -> int:
    integer = _nonnegative_integer(value, field_name)
    if integer <= 0:
        raise ValueError(f"AI Select Anchor {field_name} must be greater than zero")
    return integer


def _finite_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"AI Select Anchor {field_name} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(
            f"AI Select Anchor {field_name} must be a finite number"
        ) from error
    if not math.isfinite(number):
        raise ValueError(f"AI Select Anchor {field_name} must be a finite number")
    return number


def _number_sequence(value: object, length: int, field_name: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(
            f"AI Select Anchor {field_name} must contain {length} finite numbers"
        )
    return tuple(
        _finite_number(item, f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def _javascript_json_number(value: float) -> str:
    """Encode one finite float with the browser's JSON.stringify convention."""

    if value == 0:
        return "0"
    rendered = repr(value)
    if "e" not in rendered and "E" not in rendered:
        return rendered.removesuffix(".0")
    mantissa, exponent_text = rendered.lower().split("e", maxsplit=1)
    exponent = int(exponent_text)
    if -6 <= exponent < 21:
        sign = ""
        if mantissa.startswith("-"):
            sign = "-"
            mantissa = mantissa[1:]
        whole, _, fraction = mantissa.partition(".")
        digits = (whole + fraction).rstrip("0") or "0"
        decimal_index = len(whole) + exponent
        if decimal_index <= 0:
            return f"{sign}0.{'0' * -decimal_index}{digits}"
        if decimal_index >= len(digits):
            return f"{sign}{digits}{'0' * (decimal_index - len(digits))}"
        return f"{sign}{digits[:decimal_index]}.{digits[decimal_index:]}"
    normalised_mantissa = mantissa.removesuffix(".0")
    return f"{normalised_mantissa}e{'+' if exponent >= 0 else ''}{exponent}"


def camera_binding_digest(camera_binding: Mapping[str, object]) -> str:
    """Reproduce the editor's fixed-field CameraBinding wire digest."""

    projection = camera_binding["projection"]
    if not isinstance(projection, Mapping):
        raise ValueError("AI Select Anchor projection must be a pinhole object")
    camera_to_world = camera_binding["cameraToWorld"]
    if not isinstance(camera_to_world, list):
        raise ValueError(
            "AI Select Anchor cameraToWorld must contain 16 finite numbers"
        )
    camera_values = ",".join(
        _javascript_json_number(float(value)) for value in camera_to_world
    )
    projection_values = ",".join(
        (
            '"model":"pinhole"',
            f'"fx":{_javascript_json_number(float(projection["fx"]))}',
            f'"fy":{_javascript_json_number(float(projection["fy"]))}',
            f'"cx":{_javascript_json_number(float(projection["cx"]))}',
            f'"cy":{_javascript_json_number(float(projection["cy"]))}',
            f'"width":{int(projection["width"])}',
            f'"height":{int(projection["height"])}',
            f'"near":{_javascript_json_number(float(projection["near"]))}',
            f'"far":{_javascript_json_number(float(projection["far"]))}',
        )
    )
    encoded = (
        f'{{"revision":{int(camera_binding["revision"])}'
        f',"cameraToWorld":[{camera_values}]'
        f',"projection":{{{projection_values}}}'
        ',"conventionVersion":"opencv-camera-to-world/v1"}'
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def parse_camera_binding(
    value: object,
) -> tuple[dict[str, object], dict[str, object], int, int]:
    """Validate one CameraBinding and derive the exact locked-renderer camera."""

    if not isinstance(value, dict):
        raise ValueError("AI Select Anchor cameraBinding must be an object")
    if value.get("conventionVersion") != "opencv-camera-to-world/v1":
        raise ValueError(
            "AI Select Anchor cameraBinding conventionVersion is unsupported"
        )
    revision = _nonnegative_integer(value.get("revision"), "camera revision")
    camera_to_world = _number_sequence(value.get("cameraToWorld"), 16, "cameraToWorld")
    if camera_to_world[12:] != (0.0, 0.0, 0.0, 1.0):
        raise ValueError("AI Select Anchor cameraToWorld must be affine")
    rotation_rows = (
        camera_to_world[0:3],
        camera_to_world[4:7],
        camera_to_world[8:11],
    )
    for row in rotation_rows:
        if abs(sum(component * component for component in row) - 1.0) > 1e-5:
            raise ValueError(
                "AI Select Anchor cameraToWorld rotation must be unit length"
            )
    for first, second in ((0, 1), (0, 2), (1, 2)):
        if (
            abs(
                sum(
                    rotation_rows[first][axis] * rotation_rows[second][axis]
                    for axis in range(3)
                )
            )
            > 1e-5
        ):
            raise ValueError(
                "AI Select Anchor cameraToWorld rotation must be orthogonal"
            )
    determinant = (
        rotation_rows[0][0]
        * (
            rotation_rows[1][1] * rotation_rows[2][2]
            - rotation_rows[1][2] * rotation_rows[2][1]
        )
        - rotation_rows[0][1]
        * (
            rotation_rows[1][0] * rotation_rows[2][2]
            - rotation_rows[1][2] * rotation_rows[2][0]
        )
        + rotation_rows[0][2]
        * (
            rotation_rows[1][0] * rotation_rows[2][1]
            - rotation_rows[1][1] * rotation_rows[2][0]
        )
    )
    if abs(determinant - 1.0) > 1e-5:
        raise ValueError("AI Select Anchor cameraToWorld rotation must be right-handed")

    projection_value = value.get("projection")
    if (
        not isinstance(projection_value, dict)
        or projection_value.get("model") != "pinhole"
    ):
        raise ValueError("AI Select Anchor projection must be a pinhole object")
    fx = _finite_number(projection_value.get("fx"), "projection fx")
    fy = _finite_number(projection_value.get("fy"), "projection fy")
    cx = _finite_number(projection_value.get("cx"), "projection cx")
    cy = _finite_number(projection_value.get("cy"), "projection cy")
    width = _positive_integer(projection_value.get("width"), "projection width")
    height = _positive_integer(projection_value.get("height"), "projection height")
    near = _finite_number(projection_value.get("near"), "projection near")
    far = _finite_number(projection_value.get("far"), "projection far")
    if fx <= 0 or fy <= 0 or near <= 0 or far <= near:
        raise ValueError("AI Select Anchor projection is invalid")

    tx, ty, tz = camera_to_world[3], camera_to_world[7], camera_to_world[11]
    world_to_camera = [
        camera_to_world[0],
        camera_to_world[4],
        camera_to_world[8],
        -(camera_to_world[0] * tx + camera_to_world[4] * ty + camera_to_world[8] * tz),
        camera_to_world[1],
        camera_to_world[5],
        camera_to_world[9],
        -(camera_to_world[1] * tx + camera_to_world[5] * ty + camera_to_world[9] * tz),
        camera_to_world[2],
        camera_to_world[6],
        camera_to_world[10],
        -(camera_to_world[2] * tx + camera_to_world[6] * ty + camera_to_world[10] * tz),
        0.0,
        0.0,
        0.0,
        1.0,
    ]
    camera_binding: dict[str, object] = {
        "revision": revision,
        "cameraToWorld": list(camera_to_world),
        "projection": {
            "model": "pinhole",
            "fx": fx,
            "fy": fy,
            "cx": cx,
            "cy": cy,
            "width": width,
            "height": height,
            "near": near,
            "far": far,
        },
        "conventionVersion": "opencv-camera-to-world/v1",
    }
    renderer_camera: dict[str, object] = {
        "model": "pinhole",
        "convention": "opencv-world-to-camera",
        "worldToCamera": world_to_camera,
        "intrinsics": [fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0],
        "nearPlane": near,
        "farPlane": far,
    }
    return camera_binding, renderer_camera, width, height


__all__ = ["camera_binding_digest", "parse_camera_binding"]
