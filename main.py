"""
Dungeon Explorer — Main Entry Point
Game loop, state management, and system initialisation.
"""
import sys
import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE, COLOR_BG
from sound_manager import SoundManager
from dungeon_map import DungeonMap
from raycaster import Raycaster
from player import Player
from sprites import Crystal, Enemy, SpriteRenderer, WorldPickup
from hud import HUD
from menu import TitleMenu, GameOverMenu


# ─── Game States ─────────────────────────────────────────────────────────────
STATE_TITLE = 'title'
STATE_PLAYING = 'playing'
STATE_GAMEOVER = 'gameover'


class Game:
    """Top-level game controller."""

    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        # Hide cursor during gameplay
        self.sound_mgr = SoundManager()

        # Subsystems (created once, reused across levels)
        self.raycaster = Raycaster(self.screen)
        self.sprite_renderer = SpriteRenderer(self.screen)
        self.hud = HUD(self.screen)

        # Menus
        self.title_menu = TitleMenu(self.screen)
        self.gameover_menu = GameOverMenu(self.screen)

        self.state = STATE_TITLE
        self.running = True

        # Level data (populated by _start_level)
        self.dungeon = None
        self.player = None
        self.crystals = []
        self.enemies = []
        self.world_items = []
        self.projectiles = []
        self.current_level = 1
        self.hit_stop_timer = 0   # ms remaining in hit-stop freeze
        self.decals: list[tuple[float, float, int]] = []  # (x, y, birth_ms) blood splatters

    # ── Level management ─────────────────────────────────────────────────
    def _start_level(self, level=1):
        self.current_level = level
        self.dungeon = DungeonMap(level=level)
        sx, sy = self.dungeon.player_spawn
        self.player = Player(sx, sy)
        self.player.level = level
        # Carry over score if advancing levels
        self.player._sound_mgr_ref = self.sound_mgr   # for enemy callbacks

        self.crystals = [Crystal(x, y) for x, y in self.dungeon.crystal_positions]
        self.enemies = [
            Enemy(x, y, difficulty=self.title_menu.difficulty, enemy_type=etype)
            for x, y, etype in self.dungeon.enemy_spawns
        ]
        self.world_items = [
            WorldPickup(x, y, itype) for x, y, itype in self.dungeon.item_spawns
        ]
        self.projectiles = []
        self.decals = []

        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)

        self.hud.add_message(f'Level {level} — Explore the dungeon!',
                             duration=3000, color=(180, 160, 255))

    def _advance_level(self):
        """Move to next level when all crystals are collected."""
        old_score = self.player.score
        old_crystals = self.player.crystals_collected
        old_kills = self.player.enemies_killed
        old_health = self.player.health
        old_inventory = list(self.player.inventory)
        old_torch = self.player.torch_until
        old_fireball = self.player.fireball_timer

        self._start_level(self.current_level + 1)
        self.player.score = old_score
        self.player.crystals_collected = old_crystals
        self.player.enemies_killed = old_kills
        self.player.health = min(100, old_health + 25)
        self.player.inventory = old_inventory
        self.player.torch_until = old_torch
        self.player.fireball_timer = old_fireball

    # ── Main loop ────────────────────────────────────────────────────────
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            current_time = pygame.time.get_ticks()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                self._handle_event(event, current_time)

            if self.state == STATE_TITLE:
                self._update_title(current_time)
            elif self.state == STATE_PLAYING:
                self._update_playing(dt, current_time)
            elif self.state == STATE_GAMEOVER:
                self._update_gameover(current_time)

            pygame.display.flip()

        pygame.quit()
        sys.exit()

    # ── Event handling ───────────────────────────────────────────────────
    def _handle_event(self, event, current_time):
        # Forward events to settings panel when open
        if self.state == STATE_TITLE:
            if self.title_menu.handle_event(event):
                return  # settings panel consumed it

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.state == STATE_PLAYING:
                    self.state = STATE_TITLE
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
                else:
                    self.running = False

            if self.state == STATE_PLAYING:
                if event.key == pygame.K_SPACE:
                    hit = self.player.attack_enemies(
                        self.enemies, current_time, self.sound_mgr,
                        self.dungeon)
                    if hit:
                        self.hit_stop_timer = 45
                if event.key == pygame.K_f:
                    proj = self.player.try_fireball(current_time, self.sound_mgr)
                    if proj:
                        self.projectiles.append(proj)
                if event.key == pygame.K_e:
                    self._try_interact(current_time)
                if event.key == pygame.K_i:
                    self.player.inventory_open = not self.player.inventory_open
                slot = self._inventory_slot_from_key(event.key, event.unicode)
                if slot is not None:
                    self.player.use_inventory_slot(slot, current_time, self.hud)
                if event.key == pygame.K_m:
                    self.hud.minimap_expanded = not self.hud.minimap_expanded

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.state == STATE_PLAYING:
                if event.button == 1:
                    self.player.start_charge(current_time)
                elif event.button == 3:
                    self.player.try_dodge(current_time)
            elif event.button == 1:
                if self.state == STATE_TITLE:
                    action = self.title_menu.handle_click(event.pos)
                    if action == 'play':
                        if self.dungeon is None:
                            self._start_level(1)
                        self.state = STATE_PLAYING
                        pygame.mouse.set_visible(False)
                        pygame.event.set_grab(True)
                elif self.state == STATE_GAMEOVER:
                    action = self.gameover_menu.handle_click(event.pos)
                    if action == 'play':
                        self._start_level(1)
                        self.state = STATE_PLAYING

        if event.type == pygame.MOUSEBUTTONUP:
            if self.state == STATE_PLAYING and event.button == 1:
                hit = self.player.release_charge(
                    self.enemies, current_time, self.sound_mgr, self.dungeon)
                if hit:
                    self.hit_stop_timer = 60
                    # Add blood decal near hit enemies
                    for e in self.enemies:
                        if e.hurt_timer > 0:
                            self.decals.append((e.x, e.y, current_time))

    @staticmethod
    def _inventory_slot_from_key(key, unicode_char):
        """Map number keys and AZERTY top-row (& é " ') to inventory slots."""
        key_map = {
            pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3,
            pygame.K_AMPERSAND: 0,
        }
        if key in key_map:
            return key_map[key]
        unicode_map = {
            '&': 0, '1': 0, 'é': 1, '2': 1, '"': 2, '3': 2, "'": 3, '4': 3,
        }
        if unicode_char in unicode_map:
            return unicode_map[unicode_char]
        return None

    def _try_interact(self, current_time):
        item = self.dungeon.find_nearby_item(
            self.player.x, self.player.y, self.world_items)
        if item is not None:
            if item.check_pickup(self.player):
                self.hud.add_message(f'Picked up {item.item.label}!',
                                       color=(120, 255, 160))
            else:
                self.hud.add_message('Inventory full!', color=(255, 120, 80))
            return
        door = self.dungeon.find_nearby_door(self.player.x, self.player.y)
        if door:
            self.dungeon.toggle_door(*door)

    # ── State updates ────────────────────────────────────────────────────
    def _update_title(self, current_time):
        self.title_menu.render(current_time, has_game=(self.dungeon is not None))

    def _update_gameover(self, current_time):
        self.gameover_menu.render(
            current_time,
            score=self.player.score,
            crystals=self.player.crystals_collected,
            enemies_killed=self.player.enemies_killed,
            level=self.player.level,
        )

    def _update_playing(self, dt, current_time):
        # Hit-stop: freeze game simulation but keep rendering
        if self.hit_stop_timer > 0:
            self.hit_stop_timer = max(0, self.hit_stop_timer - dt)
            # Only render, skip all logic
            self.raycaster.cast_rays(self.player, self.dungeon, current_time)
            self.sprite_renderer.render(
                self.player, self.crystals, self.enemies,
                self.raycaster.depth_buffer, current_time,
                self.projectiles, self.world_items,
            )
            self.hud.render(self.player, self.dungeon,
                            self.crystals, self.enemies, current_time,
                            self.world_items)
            return

        # Player update
        self.player.update(self.dungeon, dt, current_time)

        # Update Fog of War
        self.dungeon.update_visited(self.player.x, self.player.y)

        # Prune old blood decals (> 30 seconds)
        self.decals = [(x, y, t) for x, y, t in self.decals
                       if current_time - t < 30000]

        # Ambient sounds
        self.sound_mgr.play_ambient(current_time, self.dungeon, self.player.x, self.player.y)

        # Footstep sounds
        if self.player.is_moving:
            self.sound_mgr.play_footstep(current_time)

        # Crystal collection
        for crystal in self.crystals:
            crystal.check_collect(self.player, self.sound_mgr, current_time)

        # Enemy AI
        for enemy in self.enemies:
            enemy.update(self.player, self.dungeon, dt, current_time,
                         self.projectiles, self.enemies)

        # Projectiles
        for proj in self.projectiles:
            proj.update(self.dungeon, self.enemies, self.player, dt,
                        self.sound_mgr)
        self.projectiles = [p for p in self.projectiles if p.alive]

        # Check if all crystals collected → advance level
        if all(c.collected for c in self.crystals):
            self.hud.add_message('All crystals collected! Descending deeper...',
                                 color=(120, 255, 120))
            self._advance_level()

        # Check player death
        if not self.player.alive:
            pygame.mouse.set_visible(True)
            pygame.event.set_grab(False)
            self.state = STATE_GAMEOVER
            return

        # Blood decal on normal attack hit
        if self.player.is_attacking:
            for e in self.enemies:
                if e.hurt_timer > 100:
                    if not any(abs(dx - e.x) < 0.5 and abs(dy - e.y) < 0.5
                               for dx, dy, _ in self.decals[-3:]):
                        self.decals.append((e.x, e.y, current_time))

        # ── Render ───────────────────────────────────────────────────
        self.raycaster.cast_rays(self.player, self.dungeon, current_time)

        self.sprite_renderer.render(
            self.player, self.crystals, self.enemies,
            self.raycaster.depth_buffer, current_time,
            self.projectiles, self.world_items,
        )

        self.hud.render(self.player, self.dungeon,
                        self.crystals, self.enemies, current_time,
                        self.world_items)

        # FPS counter (debug)
        fps_txt = self.hud.font_sm.render(
            f'FPS: {int(self.clock.get_fps())}', True, (80, 80, 100))
        self.screen.blit(fps_txt, (10, 10))


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    game = Game()
    game.run()