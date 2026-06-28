"""
Dungeon Explorer — Raycasting Engine
DDA raycaster that renders textured walls, floor-cast floor/ceiling,
and exposes a depth buffer consumed by the sprite system.
"""
import math
import os
import random as rng

import numpy as np
import pygame

from settings import (
    ASSETS_DIR, SCREEN_WIDTH, SCREEN_HEIGHT, HALF_WIDTH, HALF_HEIGHT,
    FOV, HALF_FOV, NUM_RAYS, DELTA_ANGLE, MAX_DEPTH, SCALE, SCREEN_DIST,
    TEXTURE_SIZE,
    WALL_STONE, WALL_BRICK, WALL_MOSSY, WALL_DARK, WALL_DOOR,
    COLOR_CEILING_FAR, COLOR_CEILING_NEAR,
    COLOR_FLOOR_FAR, COLOR_FLOOR_NEAR,
    ITEM_TORCH_BRIGHTNESS,
)
from sprites import get_effective_half_fov
from dungeon_map import ROOM_TYPE_TINT

# Internal texture kinds (not wall grid values)
TEX_FLOOR = 'floor'
TEX_CEILING = 'ceiling'
FLOOR_CAST_EYE_Z = 0.5                     # player eye height for floor/ceiling math


class Raycaster:
    """Casts rays, draws textured walls, and exposes a depth buffer."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.depth_buffer = [MAX_DEPTH] * NUM_RAYS

        # Pre-build assets
        self.textures: dict[int, pygame.Surface] = {}
        self._create_textures()
        self._prepare_surface_arrays()

    # ── Texture generation ───────────────────────────────────────────────
    def _create_textures(self):
        """Build procedural wall, floor, and ceiling textures."""
        palette = {
            WALL_STONE: (100, 95, 110),
            WALL_BRICK: (140, 90, 70),
            WALL_MOSSY: (70, 110, 80),
            WALL_DARK:  (50, 45, 65),
            WALL_DOOR:  (120, 85, 55),
        }
        for wtype, base in palette.items():
            self.textures[wtype] = self._make_texture(base, wtype)

        self.floor_texture = self._make_texture(COLOR_FLOOR_NEAR, TEX_FLOOR)
        self.ceiling_texture = self._make_texture(COLOR_CEILING_NEAR, TEX_CEILING)

    def _prepare_surface_arrays(self):
        """Cache floor/ceiling textures as numpy arrays for fast sampling."""
        self._floor_array = pygame.surfarray.array3d(self.floor_texture)
        self._ceil_array = pygame.surfarray.array3d(self.ceiling_texture)
        self._ts_mask = TEXTURE_SIZE - 1

    def _make_texture(self, base, wtype):
        sz = TEXTURE_SIZE
        tex = pygame.Surface((sz, sz))
        r, g, b = base

        if wtype == WALL_BRICK:
            tex.fill((max(0, r - 20), max(0, g - 15), max(0, b - 15)))
            bh, bw = 8, 16
            mortar = (max(0, r - 45), max(0, g - 40), max(0, b - 35))
            for row in range(sz // bh + 1):
                y = row * bh
                off = (bw // 2) if row % 2 else 0
                pygame.draw.line(tex, mortar, (0, y), (sz, y), 1)
                for col in range(-1, sz // bw + 2):
                    x = col * bw + off
                    pygame.draw.line(tex, mortar, (x, y), (x, y + bh), 1)
                    cr = max(0, min(255, r + rng.randint(-18, 18)))
                    cg = max(0, min(255, g + rng.randint(-12, 12)))
                    cb = max(0, min(255, b + rng.randint(-12, 12)))
                    rect = pygame.Rect(x + 1, y + 1, bw - 2, bh - 2)
                    tex.fill((cr, cg, cb), rect)
        elif wtype == WALL_DOOR:
            # Wooden plank texture
            tex.fill(base)
            plank_w = 10
            for px in range(0, sz, plank_w):
                v = rng.randint(-15, 15)
                pr = max(0, min(255, r + v))
                pg = max(0, min(255, g + v))
                pb = max(0, min(255, b + v))
                tex.fill((pr, pg, pb), (px + 1, 0, plank_w - 2, sz))
                line_c = (max(0, r - 30), max(0, g - 25), max(0, b - 20))
                pygame.draw.line(tex, line_c, (px, 0), (px, sz - 1), 1)
            # Cross beams
            beam = (max(0, r - 20), max(0, g - 15), max(0, b - 10))
            pygame.draw.line(tex, beam, (0, sz // 4), (sz, sz // 4), 2)
            pygame.draw.line(tex, beam, (0, 3 * sz // 4), (sz, 3 * sz // 4), 2)
        elif wtype == TEX_FLOOR:
            # Worn floor flagstones — smaller tiles, lighter mortar
            tex.fill((max(0, r - 10), max(0, g - 8), max(0, b - 8)))
            blk = 8
            mortar = (max(0, r - 35), max(0, g - 30), max(0, b - 28))
            for by in range(0, sz, blk):
                off = (blk // 2) if (by // blk) % 2 else 0
                for bx in range(-blk, sz + blk, blk):
                    ax = bx + off
                    v = rng.randint(-14, 14)
                    cr = max(0, min(255, r + v))
                    cg = max(0, min(255, g + v - 2))
                    cb = max(0, min(255, b + v - 2))
                    tex.fill((cr, cg, cb), (ax + 1, by + 1, blk - 2, blk - 2))
            for i in range(0, sz + blk, blk):
                pygame.draw.line(tex, mortar, (0, i), (sz, i), 1)
            for row_idx in range(sz // blk + 1):
                off = (blk // 2) if row_idx % 2 else 0
                y_top = row_idx * blk
                y_bot = y_top + blk
                for col in range(-1, sz // blk + 2):
                    x = col * blk + off
                    pygame.draw.line(tex, mortar, (x, y_top), (x, y_bot), 1)
            # Scuff marks
            for _ in range(12):
                sx = rng.randint(0, sz - 1)
                sy = rng.randint(0, sz - 1)
                pygame.draw.circle(tex, (max(0, r - 20), max(0, g - 18), max(0, b - 15)),
                                   (sx, sy), rng.randint(1, 3))
        elif wtype == TEX_CEILING:
            # Dark rough ceiling stone — larger blocks, heavy shadow lines
            tex.fill((max(0, r - 5), max(0, g - 5), max(0, b - 3)))
            blk = 20
            mortar = (max(0, r - 40), max(0, g - 38), max(0, b - 35))
            for by in range(0, sz, blk):
                off = (blk // 3) if (by // blk) % 2 else 0
                for bx in range(-blk, sz + blk, blk):
                    ax = bx + off
                    v = rng.randint(-12, 12)
                    cr = max(0, min(255, r + v))
                    cg = max(0, min(255, g + v))
                    cb = max(0, min(255, b + v + 2))
                    tex.fill((cr, cg, cb), (ax + 1, by + 1, blk - 2, blk - 2))
            for i in range(0, sz + blk, blk):
                pygame.draw.line(tex, mortar, (0, i), (sz, i), 2)
            for row_idx in range(sz // blk + 1):
                off = (blk // 3) if row_idx % 2 else 0
                y_top = row_idx * blk
                y_bot = y_top + blk
                for col in range(-1, sz // blk + 2):
                    x = col * blk + off
                    pygame.draw.line(tex, mortar, (x, y_top), (x, y_bot), 2)
            # Subtle cracks
            for _ in range(6):
                cx = rng.randint(0, sz - 1)
                cy = rng.randint(0, sz - 1)
                pygame.draw.line(tex, (max(0, r - 25), max(0, g - 22), max(0, b - 20)),
                                 (cx, cy),
                                 (cx + rng.randint(-8, 8), cy + rng.randint(-8, 8)), 1)
        else:
            # Stone block texture
            tex.fill(base)
            blk = 16
            mortar = (max(0, r - 30), max(0, g - 25), max(0, b - 25))
            for by in range(0, sz, blk):
                off = (blk // 2) if (by // blk) % 2 else 0
                for bx in range(-blk, sz + blk, blk):
                    ax = bx + off
                    v = rng.randint(-20, 20)
                    cr = max(0, min(255, r + v))
                    cg = max(0, min(255, g + v))
                    cb = max(0, min(255, b + v))
                    tex.fill((cr, cg, cb), (ax + 1, by + 1, blk - 2, blk - 2))
            for i in range(0, sz + blk, blk):
                pygame.draw.line(tex, mortar, (0, i), (sz, i), 1)
            for row_idx in range(sz // blk + 1):
                off = (blk // 2) if row_idx % 2 else 0
                y_top = row_idx * blk
                y_bot = y_top + blk
                for col in range(-1, sz // blk + 2):
                    x = col * blk + off
                    pygame.draw.line(tex, mortar, (x, y_top), (x, y_bot), 1)

            if wtype == WALL_MOSSY:
                for _ in range(20):
                    mx = rng.randint(0, sz - 1)
                    my = rng.randint(sz // 3, sz - 1)
                    ms = rng.randint(2, 5)
                    pygame.draw.circle(tex, (30, rng.randint(90, 140), 40),
                                       (mx, my), ms)

        return tex

    def _shade_row(self, colors, dist, torch_boost):
        """Apply distance darkening (and torch boost) to a row of texels."""
        darkness = np.maximum(35, 255 - (dist * 22).astype(np.int32))
        if torch_boost:
            darkness = np.minimum(255, darkness + torch_boost)
        return (colors * darkness[:, np.newaxis] // 255).astype(np.uint8)

    def _get_pitch_offset(self, player):
        offset = int(math.sin(player.head_bob_phase) * 15)
        if player.screen_shake > 0:
            offset += int(rng.uniform(-player.screen_shake, player.screen_shake))
        return offset

    def _render_floor_ceiling(self, player, current_time):
        """Per-pixel floor/ceiling casting with tiled stone textures."""
        pitch_offset = self._get_pitch_offset(player)
        horizon = max(1, min(SCREEN_HEIGHT - 2, HALF_HEIGHT + pitch_offset))
        half_fov = get_effective_half_fov(player, current_time)
        effective_fov = half_fov * 2
        torch_boost = (ITEM_TORCH_BRIGHTNESS
                       if player.torch_until > current_time else 0)

        px, py = player.x, player.y
        pa = player.angle
        ts = TEXTURE_SIZE
        mask = self._ts_mask

        xs = np.arange(SCREEN_WIDTH, dtype=np.float64)
        ray_angles = pa - half_fov + (xs / SCREEN_WIDTH) * effective_fov
        cos_delta = np.cos(ray_angles - pa)
        cos_delta = np.where(np.abs(cos_delta) < 1e-8, 1e-8, cos_delta)
        cos_ray = np.cos(ray_angles)
        sin_ray = np.sin(ray_angles)

        buf = pygame.surfarray.pixels3d(self.screen)
        
        # Clear the single horizon line to black to prevent artifacts
        buf[:, horizon, :] = 0

        for y in range(horizon):
            p = horizon - y
            row_dist = (FLOOR_CAST_EYE_Z * SCREEN_HEIGHT) / p
            dist = row_dist / cos_delta
            wx = px + dist * cos_ray
            wy = py + dist * sin_ray
            tx = (wx * ts).astype(np.int32) & mask
            ty = (wy * ts).astype(np.int32) & mask
            buf[:, y, :] = self._shade_row(
                self._ceil_array[tx, ty], dist, torch_boost)

        for y in range(horizon + 1, SCREEN_HEIGHT):
            p = y - horizon
            row_dist = (FLOOR_CAST_EYE_Z * SCREEN_HEIGHT) / p
            dist = row_dist / cos_delta
            wx = px + dist * cos_ray
            wy = py + dist * sin_ray
            tx = (wx * ts).astype(np.int32) & mask
            ty = (wy * ts).astype(np.int32) & mask
            
            buf[:, y, :] = self._shade_row(
                self._floor_array[tx, ty], dist, torch_boost)

        del buf

    # ── Main render pass ─────────────────────────────────────────────────
    def cast_rays(self, player, dungeon_map, current_time=0):
        """
        Cast NUM_RAYS rays from the player, render textured wall columns,
        and populate self.depth_buffer for the sprite pass.
        """
        self._render_floor_ceiling(player, current_time)
        pitch_offset = self._get_pitch_offset(player)

        ox, oy = player.x, player.y
        half_fov = get_effective_half_fov(player, current_time)
        effective_fov = half_fov * 2
        delta_angle = effective_fov / NUM_RAYS
        torch_active = player.torch_until > current_time
        ray_angle = player.angle - half_fov

        for ray in range(NUM_RAYS):
            sin_a = math.sin(ray_angle)
            cos_a = math.cos(ray_angle)
            if cos_a == 0:
                cos_a = 1e-8
            if sin_a == 0:
                sin_a = 1e-8

            # ── Horizontal grid intersections ────────────────────────
            if sin_a > 0:
                y_hor = int(oy) + 1
                dy = 1
            else:
                y_hor = int(oy) - 1e-6
                dy = -1

            depth_hor = (y_hor - oy) / sin_a
            x_hor = ox + depth_hor * cos_a
            delta_depth_h = dy / sin_a
            dx_h = delta_depth_h * cos_a

            wtype_h = WALL_STONE
            for _ in range(MAX_DEPTH):
                mx, my = int(x_hor), int(y_hor)
                if 0 <= mx < dungeon_map.width and 0 <= my < dungeon_map.height:
                    if dungeon_map.grid[my][mx] != 0:
                        wtype_h = dungeon_map.grid[my][mx]
                        break
                else:
                    depth_hor = MAX_DEPTH
                    break
                x_hor += dx_h
                y_hor += dy
                depth_hor += abs(delta_depth_h)
            else:
                depth_hor = MAX_DEPTH

            # ── Vertical grid intersections ──────────────────────────
            if cos_a > 0:
                x_ver = int(ox) + 1
                dx2 = 1
            else:
                x_ver = int(ox) - 1e-6
                dx2 = -1

            depth_ver = (x_ver - ox) / cos_a
            y_ver = oy + depth_ver * sin_a
            delta_depth_v = dx2 / cos_a
            dy_v = delta_depth_v * sin_a

            wtype_v = WALL_STONE
            for _ in range(MAX_DEPTH):
                mx, my = int(x_ver), int(y_ver)
                if 0 <= mx < dungeon_map.width and 0 <= my < dungeon_map.height:
                    if dungeon_map.grid[my][mx] != 0:
                        wtype_v = dungeon_map.grid[my][mx]
                        break
                else:
                    depth_ver = MAX_DEPTH
                    break
                x_ver += dx2
                y_ver += dy_v
                depth_ver += abs(delta_depth_v)
            else:
                depth_ver = MAX_DEPTH

            # ── Pick closer hit ──────────────────────────────────────
            if depth_ver < depth_hor:
                depth = depth_ver
                wtype = wtype_v
                tex_coord = y_ver - int(y_ver)
                side = 0
            else:
                depth = depth_hor
                wtype = wtype_h
                tex_coord = x_hor - int(x_hor)
                side = 1

            # Fisheye correction
            depth *= math.cos(player.angle - ray_angle)
            if depth < 0.0001:
                depth = 0.0001
            self.depth_buffer[ray] = depth

            # ── Draw column ──────────────────────────────────────────
            proj_h = SCREEN_DIST / depth
            wall_h = int(proj_h)
            if wall_h < 1:
                wall_h = 1
            cap = SCREEN_HEIGHT * 2
            if wall_h > cap:
                wall_h = cap

            tex = self.textures.get(wtype, self.textures[WALL_STONE])
            tex_x = int(tex_coord * TEXTURE_SIZE) % TEXTURE_SIZE

            col = tex.subsurface(tex_x, 0, 1, TEXTURE_SIZE)
            col = pygame.transform.scale(col, (SCALE, wall_h))

            # Distance + side darkening
            darkness = max(35, 255 - int(depth * 22))
            if torch_active:
                darkness = min(255, darkness + ITEM_TORCH_BRIGHTNESS)
            if side == 1:
                darkness = int(darkness * 0.75)

            # Room type tint based on the hit tile's floor neighbour
            hit_wx = ox + math.cos(ray_angle - delta_angle) * depth
            hit_wy = oy + math.sin(ray_angle - delta_angle) * depth
            rtype = dungeon_map.get_room_type(hit_wx, hit_wy)
            tint = ROOM_TYPE_TINT.get(rtype, (0, 0, 0)) if rtype else (0, 0, 0)

            # Secret wall marker: slightly greenish tinge
            is_secret = False
            hit_ix, hit_iy = int(ox + math.cos(ray_angle) * depth), int(oy + math.sin(ray_angle) * depth)
            if (hit_ix, hit_iy) in dungeon_map.secret_walls:
                is_secret = True
                tint = (tint[0] - 5, tint[1] + 12, tint[2] - 5)

            dark = pygame.Surface((SCALE, wall_h))
            dr = max(0, min(255, darkness + tint[0]))
            dg = max(0, min(255, darkness + tint[1]))
            db = max(0, min(255, darkness + tint[2]))
            dark.fill((dr, dg, db))
            col.blit(dark, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

            # Subtle blue fog for distant walls
            if depth > 4:
                fog_i = min(60, int((depth - 4) * 6))
                fog = pygame.Surface((SCALE, wall_h))
                fog.fill((5, 5, fog_i))
                col.blit(fog, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

            self.screen.blit(col, (ray * SCALE, HALF_HEIGHT + pitch_offset - wall_h // 2))

            ray_angle += delta_angle
