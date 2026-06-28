"""
Dungeon Explorer — 3D Model → Sprite Baker
Loads GLB/GLTF/OBJ meshes via trimesh and rasterises them into pygame
surfaces for use as billboards in the raycaster sprite system.
"""
from __future__ import annotations

import os
import math
import numpy as np
import pygame
import trimesh

from settings import ASSETS_DIR

PROPS_DIR = os.path.join(ASSETS_DIR, 'models', 'props')
GEM_MODEL_PATH = os.path.join(PROPS_DIR, 'gems', 'Gem.glb')
MONSTERS_DIR = os.path.join(PROPS_DIR, 'ultimate_monsters')

CRYSTAL_SPIN_FRAMES = 24
SPRITE_BAKE_SIZE = 128
_enemy_model_paths: list[str] | None = None
_sprite_cache: dict[tuple, pygame.Surface | list[pygame.Surface]] = {}


class MeshData:
    """Triangle mesh ready for software rasterisation."""

    __slots__ = ('vertices', 'faces', 'uvs', 'texture', 'solid_color')

    def __init__(self, vertices, faces, uvs, texture, solid_color):
        self.vertices = vertices
        self.faces = faces
        self.uvs = uvs
        self.texture = texture          # HxWx3 uint8 or None
        self.solid_color = solid_color  # (r,g,b) when no texture


def discover_monster_models() -> list[str]:
    """Collect every Quaternius glTF monster path."""
    global _enemy_model_paths
    if _enemy_model_paths is not None:
        return _enemy_model_paths

    paths: list[str] = []
    for category in ('Big', 'Blob', 'Flying'):
        gltf_dir = os.path.join(MONSTERS_DIR, category, 'glTF')
        if not os.path.isdir(gltf_dir):
            continue
        for name in sorted(os.listdir(gltf_dir)):
            if name.lower().endswith('.gltf'):
                paths.append(os.path.join(gltf_dir, name))

    _enemy_model_paths = paths
    return paths


def load_mesh(path: str) -> MeshData | None:
    """Load a 3D file and extract geometry + material."""
    if not os.path.exists(path):
        return None
    try:
        scene = trimesh.load(path, force='scene')
        if isinstance(scene, trimesh.Trimesh):
            meshes = [scene]
        elif hasattr(scene, 'geometry') and scene.geometry:
            meshes = list(scene.geometry.values())
        else:
            return None

        combined = trimesh.util.concatenate(meshes)
        vertices = np.asarray(combined.vertices, dtype=np.float64)
        faces = np.asarray(combined.faces, dtype=np.int32)

        uvs = None
        texture = None
        solid_color = (200, 200, 200)

        visual = combined.visual
        if hasattr(visual, 'uv') and visual.uv is not None:
            uvs = np.asarray(visual.uv, dtype=np.float64)
        if hasattr(visual, 'material') and visual.material is not None:
            mat = visual.material
            tex_img = getattr(mat, 'baseColorTexture', None)
            if tex_img is not None:
                rgba = np.asarray(tex_img.convert('RGBA'))
                texture = rgba[:, :, :3]
            else:
                factor = getattr(mat, 'baseColorFactor', None)
                if factor is not None:
                    solid_color = tuple(int(c) for c in factor[:3])

        if uvs is None:
            uvs = np.zeros((len(vertices), 2), dtype=np.float64)

        return MeshData(vertices, faces, uvs, texture, solid_color)
    except Exception:
        return None


def _normalize_vertices(vertices: np.ndarray, target_height: float,
                        ground: bool = True) -> np.ndarray:
    """Scale to target height, centre on X/Z, optionally sit on Y=0."""
    v = vertices.copy()
    v[:, 0] -= (v[:, 0].min() + v[:, 0].max()) * 0.5
    v[:, 2] -= (v[:, 2].min() + v[:, 2].max()) * 0.5
    height = v[:, 1].max() - v[:, 1].min()
    if height < 1e-6:
        height = 1.0
    v *= target_height / height
    if ground:
        v[:, 1] -= v[:, 1].min()
    return v


def _rotate_3d(vertices: np.ndarray, yaw: float, pitch: float, roll: float) -> np.ndarray:
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    Ry = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
    Rx = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]])
    Rz = np.array([[cr, -sr, 0.0], [sr, cr, 0.0], [0.0, 0.0, 1.0]])
    return vertices @ (Rz @ Rx @ Ry).T


def _sample_color(texture, uvs, solid_color):
    if texture is None:
        return np.array(solid_color, dtype=np.float64)

    h, w = texture.shape[:2]
    u = uvs[0] % 1.0
    v = 1.0 - (uvs[1] % 1.0)
    px = min(int(u * w), w - 1)
    py = min(int(v * h), h - 1)
    return texture[py, px].astype(np.float64)


def _render_mesh(mesh: MeshData, yaw: float, size: int,
                 target_height: float = 1.0, pitch: float = 0.0, roll: float = 0.0) -> pygame.Surface:
    """Software-rasterise a mesh into an RGBA surface."""
    verts = _normalize_vertices(mesh.vertices, target_height)
    verts = _rotate_3d(verts, yaw, pitch, roll)

    # Orthographic front view: X → screen X, Y → screen Y, Z → depth
    xs = verts[:, 0]
    ys = -verts[:, 1]
    zs = verts[:, 2]

    pad = size * 0.08
    span = max(xs.max() - xs.min(), ys.max() - ys.min(), 1e-6)
    scale = (size - 2 * pad) / span
    cx = (xs.min() + xs.max()) * 0.5
    cy = (ys.min() + ys.max()) * 0.5

    proj = np.zeros((len(verts), 3), dtype=np.float64)
    proj[:, 0] = (xs - cx) * scale + size * 0.5
    proj[:, 1] = (ys - cy) * scale + size * 0.5
    proj[:, 2] = zs

    color_buf = np.zeros((size, size, 3), dtype=np.float64)
    alpha_buf = np.zeros((size, size), dtype=np.float64)
    depth_buf = np.full((size, size), -np.inf)

    faces = mesh.faces
    uvs = mesh.uvs

    for fi in range(len(faces)):
        i0, i1, i2 = faces[fi]
        v0, v1, v2 = proj[i0], proj[i1], proj[i2]
        uv0, uv1, uv2 = uvs[i0], uvs[i1], uvs[i2]

        min_x = max(0, int(min(v0[0], v1[0], v2[0])))
        max_x = min(size - 1, int(max(v0[0], v1[0], v2[0])) + 1)
        min_y = max(0, int(min(v0[1], v1[1], v2[1])))
        max_y = min(size - 1, int(max(v0[1], v1[1], v2[1])) + 1)
        if min_x > max_x or min_y > max_y:
            continue

        area = (v1[0] - v0[0]) * (v2[1] - v0[1]) - (v2[0] - v0[0]) * (v1[1] - v0[1])
        if abs(area) < 1e-8:
            continue

        for py in range(min_y, max_y + 1):
            for px in range(min_x, max_x + 1):
                w0 = ((v1[0] - v0[0]) * (py - v0[1]) - (v1[1] - v0[1]) * (px - v0[0])) / area
                w1 = ((v2[0] - v1[0]) * (py - v1[1]) - (v2[1] - v1[1]) * (px - v1[0])) / area
                w2 = 1.0 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue

                depth = w0 * v0[2] + w1 * v1[2] + w2 * v2[2]
                if depth <= depth_buf[py, px]:
                    continue

                uv = w0 * uv0 + w1 * uv1 + w2 * uv2
                color = _sample_color(mesh.texture, uv, mesh.solid_color)
                depth_buf[py, px] = depth
                color_buf[py, px] = color
                alpha_buf[py, px] = 255.0

    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[:, :, :3] = np.clip(color_buf, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = np.clip(alpha_buf, 0, 255).astype(np.uint8)

    # Simple emissive glow for gems / bright props
    if mesh.texture is None and mesh.solid_color[2] > mesh.solid_color[0]:
        glow = np.clip(color_buf * 0.25, 0, 80).astype(np.uint8)
        mask = alpha_buf > 0
        rgba[mask, :3] = np.clip(rgba[mask, :3].astype(np.int16) + glow[mask], 0, 255)

    return pygame.image.frombuffer(rgba.tobytes(), (size, size), 'RGBA').copy()


def bake_sprite(path: str, size: int = SPRITE_BAKE_SIZE,
                yaw: float = 0.0, target_height: float = 1.0) -> pygame.Surface | None:
    """Bake a single billboard frame from a model file."""
    key = ('sprite', path, size, round(yaw, 4), target_height)
    if key in _sprite_cache:
        return _sprite_cache[key]

    mesh = load_mesh(path)
    if mesh is None:
        return None
    surf = _render_mesh(mesh, yaw, size, target_height)
    _sprite_cache[key] = surf
    return surf


def bake_spin_frames(path: str, frames: int = CRYSTAL_SPIN_FRAMES,
                     size: int = SPRITE_BAKE_SIZE,
                     target_height: float = 0.55) -> list[pygame.Surface] | None:
    """Bake a full 360° spin animation for collectibles."""
    key = ('spin', path, frames, size, target_height)
    if key in _sprite_cache:
        return _sprite_cache[key]

    mesh = load_mesh(path)
    if mesh is None:
        return None

    result = []
    for i in range(frames):
        yaw = (2 * math.pi * i) / frames
        result.append(_render_mesh(mesh, yaw, size, target_height))

    _sprite_cache[key] = result
    return result


def get_crystal_frames() -> list[pygame.Surface] | None:
    """Return spinning gem frames, or None if the model is missing."""
    if os.path.exists(GEM_MODEL_PATH):
        return bake_spin_frames(GEM_MODEL_PATH)
    return None

def bake_weapon_swing(path: str, size: int = 256) -> list[pygame.Surface] | None:
    """Bake 5 frames of a knife swinging."""
    key = ('weapon_swing', path, size)
    if key in _sprite_cache:
        return _sprite_cache[key]

    mesh = load_mesh(path)
    if mesh is None:
        return None

    result = []
    # Knife slash animation keyframes (yaw, pitch, roll)
    # Start: held up/back, Mid: slashing down across screen, End: finished slice
    keyframes = [
        (0.5, 0.2, -0.2),    # Ready
        (0.3, 0.5, -0.4),    # Winding up
        (0.0, 1.2, -0.8),    # Fast slash!
        (-0.3, 1.6, -1.0),   # Follow through
        (-0.5, 1.7, -1.1),   # Resting
    ]
    for yaw, pitch, roll in keyframes:
        # Scale it up slightly larger than default 1.0
        surf = _render_mesh(mesh, yaw=yaw, pitch=pitch, roll=roll, size=size, target_height=1.4)
        result.append(surf)

    _sprite_cache[key] = result
    return result


def get_enemy_sprite(model_path: str | None = None) -> pygame.Surface | None:
    """Bake (or retrieve cached) front-facing enemy billboard."""
    if model_path is None:
        models = discover_monster_models()
        if not models:
            return None
        import random
        model_path = random.choice(models)
    return bake_sprite(model_path, target_height=0.95)


def tint_surface(base: pygame.Surface, tint_rgb: tuple, alpha: int = 100) -> pygame.Surface:
    """Return a copy of *base* with a colour overlay (e.g. hurt flash)."""
    copy = base.copy()
    overlay = pygame.Surface(copy.get_size(), pygame.SRCALPHA)
    overlay.fill((*tint_rgb, alpha))
    copy.blit(overlay, (0, 0))
    return copy
