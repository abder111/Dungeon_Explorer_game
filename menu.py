"""
Dungeon Explorer — Menus
Title screen, Settings panel, and Game Over screen.
Redesigned with Kenney UI assets and a full settings menu.
"""
import math
import os
import random
import pygame
from settings import (
    ASSETS_DIR, SCREEN_WIDTH, SCREEN_HEIGHT, HALF_WIDTH, HALF_HEIGHT,
    COLOR_WHITE, COLOR_SCORE, FPS,
)
import settings as _settings


# ─── Shared Base ─────────────────────────────────────────────────────────────

class MenuBase:
    """Shared utilities for menu screens."""

    def __init__(self, screen):
        self.screen = screen

        font_path = os.path.join(ASSETS_DIR, 'ui', 'Font', 'Kenney Future.ttf')
        if os.path.exists(font_path):
            self.font_title = pygame.font.Font(font_path, 52)
            self.font_sub   = pygame.font.Font(font_path, 24)
            self.font_body  = pygame.font.Font(font_path, 18)
            self.font_small = pygame.font.Font(font_path, 14)
        else:
            self.font_title = pygame.font.SysFont('consolas', 52, bold=True)
            self.font_sub   = pygame.font.SysFont('consolas', 24)
            self.font_body  = pygame.font.SysFont('consolas', 18)
            self.font_small = pygame.font.SysFont('consolas', 14)

        blue_dir = os.path.join(ASSETS_DIR, 'ui', 'PNG', 'Blue', 'Default')

        def _load(fname):
            p = os.path.join(blue_dir, fname)
            return pygame.image.load(p).convert_alpha() if os.path.exists(p) else None

        self.btn_img        = _load('button_rectangle_depth_flat.png')
        self.btn_hover_img  = _load('button_rectangle_depth_gradient.png')
        self.slide_track    = _load('slide_horizontal_color.png')
        self.slide_handle   = _load('slide_hangle.png')

        click_path = os.path.join(ASSETS_DIR, 'ui', 'Sounds', 'click-a.ogg')
        self.click_snd = None
        if os.path.exists(click_path):
            self.click_snd = pygame.mixer.Sound(click_path)
            self.click_snd.set_volume(0.5)

        self.particles = [self._random_particle() for _ in range(80)]

    @staticmethod
    def _random_particle():
        return {
            'x': random.randint(0, SCREEN_WIDTH),
            'y': random.randint(0, SCREEN_HEIGHT),
            'r': random.uniform(1, 3.5),
            'speed': random.uniform(0.15, 0.7),
            'alpha': random.randint(25, 110),
            'color': random.choice([
                (100, 180, 255), (150, 120, 255), (255, 200, 100),
                (80, 220, 180), (200, 200, 255), (255, 140, 160),
            ]),
        }

    def _draw_background(self, time_ms):
        self.screen.fill((8, 6, 14))
        for y in range(0, SCREEN_HEIGHT, 2):
            t = y / SCREEN_HEIGHT
            r = int(8 + t * 18)
            g = int(6 + t * 8)
            b = int(14 + t * 30)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (SCREEN_WIDTH, y))
            pygame.draw.line(self.screen, (r, g, b), (0, y+1), (SCREEN_WIDTH, y+1))

        # Side glow pillars
        for side, cx in [(0, 0), (1, SCREEN_WIDTH)]:
            for i in range(180):
                alpha = int(40 * (1 - i / 180))
                glow_col = (40 + i // 4, 20 + i // 6, 80 + i // 3)
                x = cx - i if side else cx + i
                if 0 <= x < SCREEN_WIDTH:
                    pygame.draw.line(self.screen, glow_col, (x, 0), (x, SCREEN_HEIGHT))

        for p in self.particles:
            p['y'] -= p['speed']
            if p['y'] < -10:
                p['y'] = SCREEN_HEIGHT + 10
                p['x'] = random.randint(0, SCREEN_WIDTH)
            x_off = math.sin(time_ms * 0.001 + p['x'] * 0.01) * 15
            surf = pygame.Surface((int(p['r'] * 4), int(p['r'] * 4)), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*p['color'], p['alpha']),
                               (int(p['r'] * 2), int(p['r'] * 2)), int(p['r']))
            self.screen.blit(surf, (p['x'] + x_off, p['y']))

    def _draw_button(self, text, cx, cy, width=280, height=54, active=False):
        rect = pygame.Rect(cx - width // 2, cy - height // 2, width, height)
        mouse_pos = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse_pos)

        img = self.btn_hover_img if (hovered and self.btn_hover_img) else self.btn_img
        if img:
            scaled = pygame.transform.scale(img, (width, height))
            if active:
                tint = pygame.Surface(scaled.get_size())
                tint.fill((30, 60, 20))
                scaled.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            elif hovered:
                tint = pygame.Surface(scaled.get_size())
                tint.fill((40, 40, 60))
                scaled.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            self.screen.blit(scaled, rect.topleft)
        else:
            color = (80, 170, 255) if active else ((60, 120, 200) if hovered else (40, 80, 160))
            pygame.draw.rect(self.screen, color, rect, border_radius=8)
            pygame.draw.rect(self.screen, (100, 160, 240), rect, 2, border_radius=8)

        col = (255, 255, 120) if active else COLOR_WHITE
        txt = self.font_sub.render(text, True, col)
        self.screen.blit(txt, (cx - txt.get_width() // 2, cy - txt.get_height() // 2))
        return rect

    def _draw_slider(self, label, cx, cy, value, min_val, max_val, width=320):
        """Draw a Kenney-styled horizontal slider. Returns its track rect."""
        track_h = 24
        handle_w = 28
        track_rect = pygame.Rect(cx - width // 2, cy - track_h // 2, width, track_h)

        if self.slide_track:
            scaled = pygame.transform.scale(self.slide_track, (width, track_h))
            self.screen.blit(scaled, track_rect.topleft)
        else:
            pygame.draw.rect(self.screen, (40, 40, 70), track_rect, border_radius=8)

        ratio = (value - min_val) / max(max_val - min_val, 1e-6)
        hx = int(track_rect.x + ratio * (width - handle_w))
        hy = cy - 16
        handle_rect = pygame.Rect(hx, hy, handle_w, 32)

        if self.slide_handle:
            scaled_h = pygame.transform.scale(self.slide_handle, (handle_w, 32))
            self.screen.blit(scaled_h, handle_rect.topleft)
        else:
            pygame.draw.rect(self.screen, (100, 180, 255), handle_rect, border_radius=6)

        lbl = self.font_small.render(f'{label}: {int(value)}', True, (180, 180, 210))
        self.screen.blit(lbl, (cx - lbl.get_width() // 2, cy - track_h // 2 - 20))
        return track_rect

    def _click_sound(self):
        if self.click_snd:
            self.click_snd.play()


# ─── Settings Panel ──────────────────────────────────────────────────────────

class SettingsPanel:
    """
    An in-menu overlay panel for sensitivity and volume.
    Call render() each frame while open. Call handle_event() to interact.
    Returns True from handle_event() if it consumed the event.
    """

    SENS_MIN, SENS_MAX = 0.3, 3.0   # multiplier range
    VOL_MIN, VOL_MAX   = 0, 100     # percent

    def __init__(self, screen, menu_base: MenuBase):
        self.screen = screen
        self.mb = menu_base
        self.open = False

        # Values stored as internal units
        self._sensitivity = 1.0    # multiplier
        self._volume = 70          # 0–100

        self._dragging = None  # 'sens' | 'vol'
        self._btn_close = pygame.Rect(0, 0, 0, 0)
        self._track_sens = pygame.Rect(0, 0, 0, 0)
        self._track_vol  = pygame.Rect(0, 0, 0, 0)

    # Public getters
    @property
    def sensitivity(self):
        return self._sensitivity

    @property
    def volume(self):
        return self._volume / 100.0

    def _apply_to_game(self):
        """Push current settings into game globals."""
        _settings.PLAYER_ROT_SPEED = 0.0006 * self._sensitivity
        pygame.mixer.music.set_volume(self._volume / 100)

    def render(self, time_ms):
        if not self.open:
            return

        pw, ph = 480, 360
        px, py = HALF_WIDTH - pw // 2, HALF_HEIGHT - ph // 2

        # Panel background
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((10, 8, 22, 230))
        pygame.draw.rect(panel, (80, 70, 130, 200), panel.get_rect(), 3, border_radius=14)
        self.screen.blit(panel, (px, py))

        # Title
        t = self.mb.font_sub.render('SETTINGS', True, (200, 180, 255))
        self.screen.blit(t, (HALF_WIDTH - t.get_width() // 2, py + 22))

        # Separator
        pygame.draw.line(self.screen, (60, 55, 90),
                         (px + 24, py + 58), (px + pw - 24, py + 58), 1)

        # Sensitivity slider
        cx = HALF_WIDTH
        self._track_sens = self.mb._draw_slider(
            'Mouse Sensitivity', cx, py + 120,
            self._sensitivity, self.SENS_MIN, self.SENS_MAX, width=340)

        # Volume slider
        self._track_vol = self.mb._draw_slider(
            'Volume', cx, py + 210,
            self._volume, self.VOL_MIN, self.VOL_MAX, width=340)

        # Done button
        self._btn_close = self.mb._draw_button('DONE', HALF_WIDTH, py + ph - 55,
                                               width=200, height=46)

    def handle_event(self, event):
        if not self.open:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._btn_close.collidepoint(event.pos):
                self.mb._click_sound()
                self._apply_to_game()
                self.open = False
                return True
            if self._track_sens.collidepoint(event.pos):
                self._dragging = 'sens'
                return True
            if self._track_vol.collidepoint(event.pos):
                self._dragging = 'vol'
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                self._apply_to_game()
                self._dragging = None
            return self.open

        if event.type == pygame.MOUSEMOTION and self._dragging:
            mx = event.pos[0]
            if self._dragging == 'sens':
                ratio = (mx - self._track_sens.x) / self._track_sens.width
                ratio = max(0.0, min(1.0, ratio))
                self._sensitivity = self.SENS_MIN + ratio * (self.SENS_MAX - self.SENS_MIN)
            elif self._dragging == 'vol':
                ratio = (mx - self._track_vol.x) / self._track_vol.width
                ratio = max(0.0, min(1.0, ratio))
                self._volume = int(self.VOL_MIN + ratio * (self.VOL_MAX - self.VOL_MIN))
            return True

        return False


# ─── Title Menu ──────────────────────────────────────────────────────────────

class TitleMenu(MenuBase):
    """Main title screen with Play, Difficulty, and Settings buttons."""

    def __init__(self, screen):
        super().__init__(screen)
        self.difficulties = ['easy', 'normal', 'hard']
        self.diff_idx = 1

        self.play_btn     = pygame.Rect(0, 0, 0, 0)
        self.diff_btn     = pygame.Rect(0, 0, 0, 0)
        self.settings_btn = pygame.Rect(0, 0, 0, 0)

        self.settings_panel = SettingsPanel(screen, self)

        # Animated decorative gems
        self._gems = [
            {'x': random.uniform(0, SCREEN_WIDTH),
             'y': random.uniform(0, SCREEN_HEIGHT),
             'phase': random.uniform(0, math.pi * 2),
             'size': random.uniform(4, 12),
             'col': random.choice([(100, 200, 255), (200, 140, 255), (255, 200, 100)])}
            for _ in range(18)
        ]

    @property
    def difficulty(self):
        return self.difficulties[self.diff_idx]

    def _draw_gems(self, time_ms):
        for g in self._gems:
            phase = g['phase'] + time_ms * 0.001
            y = g['y'] + math.sin(phase) * 18
            alpha = int(80 + 60 * math.sin(phase * 0.7))
            s = int(g['size'])
            surf = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
            pts = [(s, 0), (s * 2, s), (s, s * 2), (0, s)]
            pygame.draw.polygon(surf, (*g['col'], alpha), pts)
            self.screen.blit(surf, (int(g['x'] - s), int(y - s)))

    def render(self, time_ms, has_game=False):
        if self.settings_panel.open:
            self._draw_background(time_ms)
            self._draw_gems(time_ms)
            self._draw_title(time_ms)
            self.settings_panel.render(time_ms)
            return

        self._draw_background(time_ms)
        self._draw_gems(time_ms)
        self._draw_title(time_ms)

        # PLAY button (large, prominent)
        btn_text = '▶  RESUME' if has_game else '▶  PLAY'
        self.play_btn = self._draw_button(btn_text, HALF_WIDTH,
                                          SCREEN_HEIGHT // 2 + 15, width=300, height=60)

        # Difficulty button
        diff_labels = {'easy': '🌿 EASY', 'normal': '⚔  NORMAL', 'hard': '💀 HARD'}
        diff_colors = {'easy': (120, 220, 120), 'normal': (220, 200, 100), 'hard': (255, 100, 100)}
        diff_text = diff_labels.get(self.difficulty, self.difficulty.upper())
        self.diff_btn = self._draw_button(
            f'DIFFICULTY: {diff_text}', HALF_WIDTH,
            SCREEN_HEIGHT // 2 + 88, width=340, height=46)

        # Settings button (smaller, below difficulty)
        self.settings_btn = self._draw_button(
            '⚙  SETTINGS', HALF_WIDTH,
            SCREEN_HEIGHT // 2 + 148, width=220, height=40)

        # Controls
        controls = [
            'Z/Q/S/D or Arrows — Move   |   Mouse — Look',
            'LMB / SPACE — Attack   |   F — Fireball   |   RMB — Dodge',
            'E — Interact   |   I — Inventory   |   M — Map   |   ESC — Quit',
        ]
        y = SCREEN_HEIGHT * 3 // 4 + 50
        for line in controls:
            txt = self.font_small.render(line, True, (90, 85, 120))
            self.screen.blit(txt, (HALF_WIDTH - txt.get_width() // 2, y))
            y += 22

        footer = self.font_small.render(
            'Assets by Kenney.nl  |  CC0 License', True, (50, 46, 70))
        self.screen.blit(footer, (HALF_WIDTH - footer.get_width() // 2,
                                   SCREEN_HEIGHT - 26))

    def _draw_title(self, time_ms):
        title_y = SCREEN_HEIGHT // 5
        # Glowing shadow layers
        for off, alpha in [(6, 18), (4, 35), (2, 60)]:
            s = self.font_title.render('DUNGEON EXPLORER', True, (80, 40, 180))
            s.set_alpha(alpha)
            self.screen.blit(s, (HALF_WIDTH - s.get_width() // 2 + off, title_y + off))

        # Pulsing chrome title
        pulse = int(210 + 45 * math.sin(time_ms * 0.0018))
        wave_r = int(170 + 60 * math.sin(time_ms * 0.0024))
        title = self.font_title.render('DUNGEON EXPLORER', True,
                                       (wave_r, 160, pulse))
        self.screen.blit(title, (HALF_WIDTH - title.get_width() // 2, title_y))

        sub = self.font_body.render(
            'Explore the depths.  Collect crystals.  Survive.',
            True, (140, 130, 175))
        self.screen.blit(sub, (HALF_WIDTH - sub.get_width() // 2, title_y + 68))

    def handle_click(self, pos):
        if self.settings_panel.open:
            return None  # handled by handle_event

        if self.play_btn.collidepoint(pos):
            self._click_sound()
            return 'play'
        elif self.diff_btn.collidepoint(pos):
            self._click_sound()
            self.diff_idx = (self.diff_idx + 1) % len(self.difficulties)
            return 'diff'
        elif self.settings_btn.collidepoint(pos):
            self._click_sound()
            self.settings_panel.open = True
            return 'settings'
        return None

    def handle_event(self, event):
        """Call this from the main event loop when in title state."""
        return self.settings_panel.handle_event(event)


# ─── Game Over Menu ──────────────────────────────────────────────────────────

class GameOverMenu(MenuBase):
    """Game-over screen showing final stats with stylised panels."""

    def __init__(self, screen):
        super().__init__(screen)
        self.play_btn = pygame.Rect(0, 0, 0, 0)
        self._show_time = 0

    def render(self, time_ms, score, crystals, enemies_killed, level):
        if self._show_time == 0:
            self._show_time = time_ms
        t = (time_ms - self._show_time) / 1000.0

        self._draw_background(time_ms)

        title_y = SCREEN_HEIGHT // 6

        # Glowing red shadow
        for off, alpha in [(5, 20), (3, 50)]:
            s = self.font_title.render('GAME OVER', True, (150, 20, 20))
            s.set_alpha(alpha)
            self.screen.blit(s, (HALF_WIDTH - s.get_width() // 2 + off, title_y + off))

        pulse = int(200 + 55 * math.sin(time_ms * 0.003))
        title = self.font_title.render('GAME OVER', True, (pulse, 40, 40))
        self.screen.blit(title, (HALF_WIDTH - title.get_width() // 2, title_y))

        # Stats panel with slide-in animation
        slide_y = max(0.0, min(1.0, t - 0.3))
        panel_y = int(SCREEN_HEIGHT // 3 + (1 - slide_y) * 80)

        panel = pygame.Surface((440, 210), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 160))
        pygame.draw.rect(panel, (100, 60, 160, 200), panel.get_rect(), 2, border_radius=12)
        # Decorative top bar
        pygame.draw.rect(panel, (120, 60, 200, 150), (0, 0, 440, 4), border_radius=12)
        panel_x = HALF_WIDTH - 220
        self.screen.blit(panel, (panel_x, panel_y))

        stats = [
            (f'Final Score:        {score}',        COLOR_SCORE),
            (f'Crystals Collected: {crystals}',      (120, 220, 255)),
            (f'Enemies Defeated:   {enemies_killed}',(255, 120, 100)),
            (f'Dungeon Level:      {level}',         (180, 160, 255)),
        ]
        sy = panel_y + 22
        for i, (text, color) in enumerate(stats):
            item_t = max(0.0, min(1.0, t - 0.5 - i * 0.15))
            alpha  = int(item_t * 255)
            txt = self.font_body.render(text, True, color)
            txt.set_alpha(alpha)
            self.screen.blit(txt, (HALF_WIDTH - txt.get_width() // 2, sy))
            sy += 44

        self.play_btn = self._draw_button('↩  PLAY AGAIN', HALF_WIDTH,
                                          SCREEN_HEIGHT * 3 // 4 + 10,
                                          width=300, height=56)

    def handle_click(self, pos):
        if self.play_btn.collidepoint(pos):
            self._click_sound()
            self._show_time = 0
            return 'play'
        return None
