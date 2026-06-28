"""
Dungeon Explorer — HUD
In-game heads-up display: health bar, score, minimap, damage flash,
attack animation overlay, and popup messages.  Uses Kenney UI assets.
"""
import math
import os
import pygame
from settings import (
    ASSETS_DIR, SCREEN_WIDTH, SCREEN_HEIGHT, HALF_WIDTH, HALF_HEIGHT,
    COLOR_HEALTH_BG, COLOR_HEALTH_FG, COLOR_HEALTH_LOW,
    COLOR_STAMINA_BG, COLOR_STAMINA_FG,
    COLOR_MANA_BG, COLOR_MANA_FG,
    COLOR_SCORE, COLOR_WHITE, COLOR_RED_FLASH,
    COLOR_MINIMAP_BG, COLOR_MINIMAP_WALL, COLOR_MINIMAP_FLOOR,
    COLOR_MINIMAP_PLAYER, COLOR_MINIMAP_CRYSTAL, COLOR_MINIMAP_ITEM,
    PLAYER_MAX_HEALTH, PLAYER_STAMINA_MAX,
    PLAYER_DODGE_DURATION, PLAYER_DODGE_COOLDOWN,
    PLAYER_ATTACK_COOLDOWN,
    FIREBALL_COOLDOWN, INVENTORY_SIZE,
)
from sprites import get_item_icon
from model_renderer import bake_weapon_swing


class HUD:
    """Renders all overlay UI on top of the 3D view."""

    def __init__(self, screen):
        self.screen = screen

        # Kenney font
        font_path = os.path.join(ASSETS_DIR, 'ui', 'Font', 'Kenney Future.ttf')
        if os.path.exists(font_path):
            self.font_lg = pygame.font.Font(font_path, 28)
            self.font_md = pygame.font.Font(font_path, 20)
            self.font_sm = pygame.font.Font(font_path, 14)
        else:
            self.font_lg = pygame.font.SysFont('consolas', 28)
            self.font_md = pygame.font.SysFont('consolas', 20)
            self.font_sm = pygame.font.SysFont('consolas', 14)

        # Load Kenney UI panel backgrounds
        self._load_ui_assets()

        # Minimap settings
        self.minimap_size = 180
        self.minimap_expanded = False

        # Popup message queue
        self.messages = []   # (text, expire_time, color)

        # Damage overlay
        self.damage_surface = pygame.Surface(
            (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA
        )

        # Attack weapon frames
        knife_path = os.path.join(ASSETS_DIR, 'models', 'props', 'weapons', 'combat_knife.glb')
        self.weapon_frames = bake_weapon_swing(knife_path, size=500)
        self.attack_surface = self._create_attack_overlay() if not self.weapon_frames else None

        # Vignette (darkened edges for atmosphere)
        self.vignette = self._create_vignette()

    # ── Asset loading ────────────────────────────────────────────────────
    def _load_ui_assets(self):
        blue_dir = os.path.join(ASSETS_DIR, 'ui', 'PNG', 'Blue', 'Default')
        self.panel_img = None
        self.bar_bg_img = None
        self.star_img = None

        # Panel background (rectangle button)
        p = os.path.join(blue_dir, 'button_rectangle_flat.png')
        if os.path.exists(p):
            self.panel_img = pygame.image.load(p).convert_alpha()

        # Bar background
        p = os.path.join(blue_dir, 'slide_horizontal_color.png')
        if os.path.exists(p):
            self.bar_bg_img = pygame.image.load(p).convert_alpha()

        # Star (for score)
        p = os.path.join(blue_dir, 'star.png')
        if os.path.exists(p):
            self.star_img = pygame.image.load(p).convert_alpha()
            self.star_img = pygame.transform.scale(self.star_img, (24, 24))

    def _create_attack_overlay(self):
        """Sword-slash visual on attack."""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        # Draw a sweeping arc
        cx, cy = HALF_WIDTH, SCREEN_HEIGHT - 60
        for i in range(5):
            r = 200 + i * 15
            alpha = 120 - i * 20
            pygame.draw.arc(surf, (255, 255, 200, max(10, alpha)),
                            (cx - r, cy - r, r * 2, r * 2),
                            math.pi * 0.2, math.pi * 0.8, 4 - i)
        return surf

    def _create_vignette(self):
        """Dark vignette around screen edges for atmosphere."""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        max_r = max(HALF_WIDTH, HALF_HEIGHT) * 1.2
        for i in range(40):
            t = i / 40.0
            alpha = int(t * t * 80)
            r = int(max_r * (1.0 - t * 0.5))
            pygame.draw.circle(surf, (0, 0, 0, 0), (HALF_WIDTH, HALF_HEIGHT), r)
        # Simpler: darken edges with rectangles
        edge_w = 120
        for i in range(edge_w):
            alpha = int((1.0 - i / edge_w) * 60)
            c = (0, 0, 0, alpha)
            # Left
            pygame.draw.line(surf, c, (i, 0), (i, SCREEN_HEIGHT))
            # Right
            pygame.draw.line(surf, c,
                             (SCREEN_WIDTH - 1 - i, 0),
                             (SCREEN_WIDTH - 1 - i, SCREEN_HEIGHT))
        edge_h = 80
        for i in range(edge_h):
            alpha = int((1.0 - i / edge_h) * 50)
            c = (0, 0, 0, alpha)
            pygame.draw.line(surf, c, (0, i), (SCREEN_WIDTH, i))
            pygame.draw.line(surf, c,
                             (0, SCREEN_HEIGHT - 1 - i),
                             (SCREEN_WIDTH, SCREEN_HEIGHT - 1 - i))
        return surf

    # ── Message system ───────────────────────────────────────────────────
    def add_message(self, text, duration=2000, color=COLOR_WHITE):
        expire = pygame.time.get_ticks() + duration
        self.messages.append((text, expire, color))

    # ── Main render ──────────────────────────────────────────────────────
    def render(self, player, dungeon_map, crystals, enemies, current_time,
               world_items=None):
        # Vignette
        self.screen.blit(self.vignette, (0, 0))

        # Damage flash (red)
        if player.damage_flash > 0:
            a = int(player.damage_flash * 120)
            self.damage_surface.fill((180, 0, 0, a))
            self.screen.blit(self.damage_surface, (0, 0))

        # Crit flash (white burst + CRITICAL! text)
        if player.crit_flash > 0:
            a = int(player.crit_flash * 160)
            self.damage_surface.fill((255, 255, 255, a))
            self.screen.blit(self.damage_surface, (0, 0))
            if player.crit_flash > 0.5:
                txt = self.font_lg.render('CRITICAL!', True, (255, 230, 60))
                txt.set_alpha(int((player.crit_flash - 0.5) * 510))
                self.screen.blit(txt, (HALF_WIDTH - txt.get_width() // 2, HALF_HEIGHT - 80))

        # Attack animation (Weapon)
        if player.is_attacking:
            elapsed = current_time - player.attack_timer
            ratio = elapsed / PLAYER_ATTACK_COOLDOWN
            if self.weapon_frames:
                frame_idx = int(ratio * len(self.weapon_frames))
                if frame_idx >= len(self.weapon_frames):
                    frame_idx = len(self.weapon_frames) - 1
                img = self.weapon_frames[frame_idx]
                # Draw in bottom-right corner
                self.screen.blit(img, (SCREEN_WIDTH - img.get_width() + 100, SCREEN_HEIGHT - img.get_height() + 50))
            elif self.attack_surface:
                self.screen.blit(self.attack_surface, (0, 0))
        elif self.weapon_frames:
            # Idle weapon state
            img = self.weapon_frames[0]
            bob = math.sin(current_time * 0.005) * 10 if player.is_moving else 0
            self.screen.blit(img, (SCREEN_WIDTH - img.get_width() + 120, SCREEN_HEIGHT - img.get_height() + 150 + bob))

        self._draw_health_bar(player, current_time)
        self._draw_stamina_bar(player)
        self._draw_fireball_bar(player, current_time)
        self._draw_score(player, current_time)
        self._draw_level(player)
        self._draw_minimap(player, dungeon_map, crystals, enemies, world_items)
        self._draw_crosshair()
        self._draw_charge_meter(player)
        self._draw_interact_prompt(player, dungeon_map, world_items)
        self._draw_inventory(player)
        self._draw_messages(current_time)
        self._draw_controls_hint()

    # ── Health bar ───────────────────────────────────────────────────────
    def _draw_health_bar(self, player, current_time):
        x, y = 20, SCREEN_HEIGHT - 78
        bar_w, bar_h = 240, 24

        # Background panel
        bg = pygame.Surface((bar_w + 56, bar_h + 16), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        pygame.draw.rect(bg, (60, 55, 80, 180), bg.get_rect(), 2,
                         border_radius=6)
        self.screen.blit(bg, (x - 10, y - 8))

        # Bar background
        pygame.draw.rect(self.screen, COLOR_HEALTH_BG,
                         (x, y, bar_w, bar_h), border_radius=4)

        # Bar fill
        ratio = player.health / PLAYER_MAX_HEALTH
        fill_w = int(bar_w * ratio)
        color = COLOR_HEALTH_FG if ratio > 0.3 else COLOR_HEALTH_LOW
        if fill_w > 0:
            pygame.draw.rect(self.screen, color,
                             (x, y, fill_w, bar_h), border_radius=4)

        # Highlight shimmer
        shimmer = pygame.Surface((fill_w, bar_h // 3), pygame.SRCALPHA)
        shimmer.fill((255, 255, 255, 40))
        self.screen.blit(shimmer, (x, y + 2))

        # Text
        txt = self.font_sm.render(f'{player.health}/{PLAYER_MAX_HEALTH}',
                                  True, COLOR_WHITE)
        self.screen.blit(txt, (x + bar_w // 2 - txt.get_width() // 2,
                               y + bar_h // 2 - txt.get_height() // 2))

        # Label
        label = self.font_sm.render('HP', True, (180, 180, 200))
        self.screen.blit(label, (x + bar_w + 8, y + 3))

        self._draw_dodge_cooldown(player, current_time, x, y, bar_w, bar_h)

    def _draw_dodge_cooldown(self, player, current_time, bar_x, bar_y, bar_w, bar_h):
        cx = bar_x + bar_w + 32
        cy = bar_y + bar_h // 2
        radius = 14

        pygame.draw.circle(self.screen, (30, 28, 40), (cx, cy), radius)

        if player.dodge_timer > 0:
            ratio = player.dodge_timer / PLAYER_DODGE_DURATION
            self._draw_cooldown_arc(cx, cy, radius, ratio, (100, 200, 255))
            pygame.draw.circle(self.screen, (100, 200, 255), (cx, cy), radius, 2)
        elif current_time < player.dodge_cooldown_until:
            remaining = player.dodge_cooldown_until - current_time
            ratio = 1.0 - remaining / PLAYER_DODGE_COOLDOWN
            self._draw_cooldown_arc(cx, cy, radius, ratio, (80, 180, 220))
            pygame.draw.circle(self.screen, (60, 55, 80), (cx, cy), radius, 2)
        else:
            pygame.draw.circle(self.screen, (0, 220, 180), (cx, cy), radius, 2)

    def _draw_cooldown_arc(self, cx, cy, radius, ratio, color):
        if ratio <= 0.01:
            return
        steps = max(8, int(ratio * 32))
        points = [(cx, cy)]
        for i in range(steps + 1):
            angle = -math.pi / 2 + (i / steps) * ratio * 2 * math.pi
            points.append((cx + radius * math.cos(angle),
                           cy + radius * math.sin(angle)))
        if len(points) > 2:
            pygame.draw.polygon(self.screen, color, points)

    def _draw_stamina_bar(self, player):
        x, y = 20, SCREEN_HEIGHT - 48
        bar_w, bar_h = 240, 16

        pygame.draw.rect(self.screen, COLOR_STAMINA_BG,
                         (x, y, bar_w, bar_h), border_radius=3)

        ratio = player.stamina / PLAYER_STAMINA_MAX
        fill_w = int(bar_w * ratio)
        if fill_w > 0:
            pygame.draw.rect(self.screen, COLOR_STAMINA_FG,
                             (x, y, fill_w, bar_h), border_radius=3)

        label = self.font_sm.render('STA', True, (140, 160, 200))
        self.screen.blit(label, (x + bar_w + 8, y))

    def _draw_fireball_bar(self, player, current_time):
        x, y = 20, SCREEN_HEIGHT - 28
        bar_w, bar_h = 240, 12

        pygame.draw.rect(self.screen, COLOR_MANA_BG,
                         (x, y, bar_w, bar_h), border_radius=3)

        elapsed = current_time - player.fireball_timer
        ratio = min(1.0, elapsed / FIREBALL_COOLDOWN) if elapsed >= 0 else 1.0
        fill_w = int(bar_w * ratio)
        if fill_w > 0:
            pygame.draw.rect(self.screen, COLOR_MANA_FG,
                             (x, y, fill_w, bar_h), border_radius=3)

        label = self.font_sm.render('FIRE', True, (200, 140, 100))
        self.screen.blit(label, (x + bar_w + 8, y - 2))

    # ── Score ────────────────────────────────────────────────────────────
    def _draw_score(self, player, current_time):
        x, y = 20, SCREEN_HEIGHT - 138

        bg = pygame.Surface((200, 32), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120))
        pygame.draw.rect(bg, (60, 55, 80, 150), bg.get_rect(), 2,
                         border_radius=6)
        self.screen.blit(bg, (x - 10, y - 4))

        # Crystal icon
        crystal_icon = pygame.Surface((20, 20), pygame.SRCALPHA)
        pts = [(10, 2), (18, 10), (10, 18), (2, 10)]
        pygame.draw.polygon(crystal_icon, (120, 220, 255), pts)
        pygame.draw.polygon(crystal_icon, (200, 240, 255), pts, 1)
        self.screen.blit(crystal_icon, (x, y))

        txt = self.font_md.render(
            f' {player.crystals_collected}    Score: {player.score}',
            True, COLOR_SCORE
        )
        self.screen.blit(txt, (x + 22, y - 2))

    # ── Level indicator ──────────────────────────────────────────────────
    def _draw_level(self, player):
        x, y = SCREEN_WIDTH - 160, SCREEN_HEIGHT - 50
        bg = pygame.Surface((140, 36), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 130))
        pygame.draw.rect(bg, (60, 55, 80, 160), bg.get_rect(), 2,
                         border_radius=6)
        self.screen.blit(bg, (x, y - 6))

        txt = self.font_md.render(f'LEVEL {player.level}', True,
                                  (180, 160, 255))
        self.screen.blit(txt, (x + 70 - txt.get_width() // 2, y))

    # ── Minimap ──────────────────────────────────────────────────────────
    def _draw_minimap(self, player, dungeon_map, crystals, enemies,
                      world_items=None):
        size = self.minimap_size * (2 if self.minimap_expanded else 1)
        tile = max(2, size // dungeon_map.width)
        mw = dungeon_map.width * tile
        mh = dungeon_map.height * tile
        mx = SCREEN_WIDTH - mw - 15
        my = 15

        # Background
        bg = pygame.Surface((mw + 6, mh + 6), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        pygame.draw.rect(bg, (80, 75, 110, 200), bg.get_rect(), 2,
                         border_radius=4)
        self.screen.blit(bg, (mx - 3, my - 3))

        # Tiles - Fog of War: only draw visited cells
        visited = dungeon_map.visited_cells
        for gy in range(dungeon_map.height):
            for gx in range(dungeon_map.width):
                if (gx, gy) not in visited:
                    continue  # Fog: skip unvisited
                if dungeon_map.grid[gy][gx] != 0:
                    pygame.draw.rect(self.screen, COLOR_MINIMAP_WALL,
                                     (mx + gx * tile, my + gy * tile,
                                      tile, tile))
                else:
                    pygame.draw.rect(self.screen, COLOR_MINIMAP_FLOOR,
                                     (mx + gx * tile, my + gy * tile,
                                      tile, tile))

        # Crystals (only show if cell visited)
        for c in crystals:
            if not c.collected and (int(c.x), int(c.y)) in visited:
                px = mx + int(c.x * tile)
                py = my + int(c.y * tile)
                pygame.draw.circle(self.screen, COLOR_MINIMAP_CRYSTAL,
                                   (px, py), max(2, tile // 2))

        # Items on ground (only show if cell visited)
        if world_items:
            for wp in world_items:
                if wp.picked_up or (int(wp.x), int(wp.y)) not in visited:
                    continue
                px = mx + int(wp.x * tile)
                py = my + int(wp.y * tile)
                pygame.draw.circle(self.screen, COLOR_MINIMAP_ITEM,
                                   (px, py), max(2, tile // 2))

        # Enemies — only show in a small radius around the player
        player_ix, player_iy = int(player.x), int(player.y)
        current_time_ms = pygame.time.get_ticks()
        for e in enemies:
            # Corpse puddle: show as dark spot for 10 seconds after death
            if not e.alive and e.death_pos is not None:
                age = current_time_ms - e.corpse_timer if e.corpse_timer else 0
                if age < 10000:
                    alpha = max(0, int(160 * (1.0 - age / 10000)))
                    cpx = mx + int(e.death_pos[0] * tile)
                    cpy = my + int(e.death_pos[1] * tile)
                    corpse_surf = pygame.Surface((tile * 2, tile), pygame.SRCALPHA)
                    pygame.draw.ellipse(corpse_surf, (80, 0, 0, alpha), corpse_surf.get_rect())
                    self.screen.blit(corpse_surf, (cpx - tile, cpy - tile // 2))
                continue
            if not e.alive:
                continue
            if abs(int(e.x) - player_ix) <= 6 and abs(int(e.y) - player_iy) <= 6:
                epx = mx + int(e.x * tile)
                epy = my + int(e.y * tile)
                color = getattr(e, 'minimap_color', (255, 60, 60))
                pygame.draw.circle(self.screen, color, (epx, epy), max(2, tile // 2))
                # Alert ! icon
                if e.alert_timer > 0:
                    pulse = int(200 + 55 * math.sin(current_time_ms * 0.01))
                    alert_txt = self.font_sm.render('!', True, (pulse, pulse, 0))
                    self.screen.blit(alert_txt, (epx - alert_txt.get_width() // 2, epy - tile * 2))

        # Player
        px = mx + int(player.x * tile)
        py = my + int(player.y * tile)
        pygame.draw.circle(self.screen, COLOR_MINIMAP_PLAYER,
                           (px, py), max(3, tile // 2 + 1))
        # Direction indicator
        dx = int(math.cos(player.angle) * tile * 2)
        dy = int(math.sin(player.angle) * tile * 2)
        pygame.draw.line(self.screen, COLOR_MINIMAP_PLAYER,
                         (px, py), (px + dx, py + dy), 2)

    # ── Crosshair ───────────────────────────────────────────────────
    def _draw_crosshair(self):
        cx, cy = HALF_WIDTH, HALF_HEIGHT
        color = (200, 200, 220, 150)
        gap = 6
        length = 14
        # Four lines
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x1 = cx + dx * gap
            y1 = cy + dy * gap
            x2 = cx + dx * (gap + length)
            y2 = cy + dy * (gap + length)
            pygame.draw.line(self.screen, color[:3], (x1, y1), (x2, y2), 2)
        # Centre dot
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 2)

    def _draw_charge_meter(self, player):
        """Glowing arc around the crosshair showing charge progress."""
        if not player.is_charging or player.charge_ratio <= 0:
            return
        cx, cy = HALF_WIDTH, HALF_HEIGHT
        ratio = player.charge_ratio
        radius = 28
        g = int(220 * (1.0 - ratio))
        col = (255, g, 60)
        steps = int(ratio * 48)
        for i in range(steps):
            angle = -math.pi / 2 + (i / 48.0) * 2 * math.pi
            ax = int(cx + radius * math.cos(angle))
            ay = int(cy + radius * math.sin(angle))
            pygame.draw.circle(self.screen, col, (ax, ay), 2)
        if ratio >= 1.0:
            pulse = pygame.Surface((80, 80), pygame.SRCALPHA)
            a = int(40 + 30 * math.sin(pygame.time.get_ticks() * 0.015))
            pygame.draw.circle(pulse, (255, 200, 0, a), (40, 40), 38)
            self.screen.blit(pulse, (cx - 40, cy - 40))

    def _draw_interact_prompt(self, player, dungeon_map, world_items):
        prompt = dungeon_map.get_interact_prompt(
            player.x, player.y, world_items or [])
        if not prompt:
            return
        txt = self.font_md.render(prompt, True, (200, 220, 255))
        bg = pygame.Surface((txt.get_width() + 24, txt.get_height() + 12),
                            pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        pygame.draw.rect(bg, (80, 90, 120, 180), bg.get_rect(), 2,
                         border_radius=6)
        bx = HALF_WIDTH - bg.get_width() // 2
        by = SCREEN_HEIGHT // 2 + 60
        self.screen.blit(bg, (bx, by))
        self.screen.blit(txt, (bx + 12, by + 6))

    def _draw_inventory(self, player):
        slot_size = 48
        gap = 8
        total_w = INVENTORY_SIZE * slot_size + (INVENTORY_SIZE - 1) * gap + 24
        bx = HALF_WIDTH - total_w // 2
        by = SCREEN_HEIGHT - 95

        bg = pygame.Surface((total_w, slot_size + 24), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120 if not player.inventory_open else 180))
        pygame.draw.rect(bg, (70, 65, 90, 200), bg.get_rect(), 2,
                         border_radius=8)
        self.screen.blit(bg, (bx, by))

        azerty_labels = ['&/1', 'é/2', '" /3', "'/4"]
        for i in range(INVENTORY_SIZE):
            sx = bx + 12 + i * (slot_size + gap)
            sy = by + 12
            slot_rect = pygame.Rect(sx, sy, slot_size, slot_size)
            pygame.draw.rect(self.screen, (40, 35, 55), slot_rect,
                             border_radius=6)
            pygame.draw.rect(self.screen, (90, 85, 110), slot_rect, 2,
                             border_radius=6)

            item = player.inventory[i]
            if item is not None:
                icon = get_item_icon(item.item_type)
                scaled = pygame.transform.scale(icon, (slot_size - 8, slot_size - 8))
                self.screen.blit(scaled, (sx + 4, sy + 4))

            if player.inventory_open:
                lbl = self.font_sm.render(azerty_labels[i], True, (160, 160, 180))
                self.screen.blit(lbl, (sx + slot_size // 2 - lbl.get_width() // 2,
                                       sy + slot_size + 2))

        if player.inventory_open:
            title = self.font_sm.render('INVENTORY  (I to close)', True,
                                        (180, 170, 200))
            self.screen.blit(title, (HALF_WIDTH - title.get_width() // 2, by - 18))

    # ── Popup messages ───────────────────────────────────────────────────
    def _draw_messages(self, current_time):
        self.messages = [(t, e, c) for t, e, c in self.messages
                         if e > current_time]
        y = SCREEN_HEIGHT // 3
        for text, expire, color in self.messages:
            remaining = expire - current_time
            alpha = min(255, int(remaining / 2000 * 255 * 2))
            txt = self.font_md.render(text, True, color)
            txt.set_alpha(alpha)
            self.screen.blit(txt,
                             (HALF_WIDTH - txt.get_width() // 2, y))
            y += 30

    # ── Controls hint ────────────────────────────────────────────────────
    def _draw_controls_hint(self):
        txt = self.font_sm.render(
            'Z/Q/S/D or Arrows  |  LMB/SPACE Attack  |  F Fireball  |  '
            'RMB Dodge  |  E Interact  |  I Inventory  |  M Map',
            True, (100, 100, 120))
        self.screen.blit(txt, (HALF_WIDTH - txt.get_width() // 2,
                               SCREEN_HEIGHT - 18))