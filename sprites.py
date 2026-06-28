"""
Dungeon Explorer — Sprite System
3D-model billboards for crystals (collectibles) and enemies, with
procedural fallbacks, depth-sorted rendering, and enemy AI.
"""
import math
import random
import pygame
import os
from settings import (
    ASSETS_DIR, SCREEN_WIDTH, SCREEN_HEIGHT, HALF_WIDTH, HALF_HEIGHT,
    FOV, HALF_FOV, NUM_RAYS, SCALE, SCREEN_DIST, MAX_DEPTH,
    CRYSTAL_SCORE, CRYSTAL_COLLECT_RANGE,
    ENEMY_SPEED, ENEMY_HEALTH, ENEMY_DAMAGE,
    ENEMY_ATTACK_RANGE, ENEMY_CHASE_RANGE, ENEMY_ATTACK_COOLDOWN,
    ENEMY_CHASE_SPEED_MULT, ENEMY_TURN_SPEED, ENEMY_ATTACK_ARC,
    ENEMY_STOP_DISTANCE, ENEMY_SIZE,
    ENEMY_TYPE_CRAWLER, ENEMY_TYPE_SHADE, ENEMY_TYPE_BRUTE,
    CRAWLER_SPEED_MULT, CRAWLER_HEALTH_MULT,
    SHADE_SPEED_MULT, SHADE_HEALTH_MULT, SHADE_TELEPORT_DIST,
    BRUTE_SPEED_MULT, BRUTE_HEALTH_MULT,
    BRUTE_PROJECTILE_COOLDOWN, BRUTE_PROJECTILE_SPEED,
    BRUTE_PROJECTILE_DAMAGE, BRUTE_PROJECTILE_RANGE,
    FIREBALL_SPEED, FIREBALL_DAMAGE, FIREBALL_MAX_RANGE, FIREBALL_HIT_RADIUS,
    ITEM_PICKUP_RANGE, ITEM_POTION_HEAL, ITEM_TORCH_DURATION,
    ITEM_TORCH_FOV_MULT, PLAYER_MAX_HEALTH,
    COLOR_MINIMAP_CRAWLER, COLOR_MINIMAP_SHADE, COLOR_MINIMAP_BRUTE,
)
from model_renderer import (
    get_crystal_frames, get_enemy_sprite, tint_surface,
    discover_monster_models, bake_sprite, CRYSTAL_SPIN_FRAMES,
)


def _collides_circle(x, y, radius, dungeon_map):
    """Four-corner wall check — shared by enemies and projectiles."""
    for corner_x in (x - radius, x + radius):
        for corner_y in (y - radius, y + radius):
            if dungeon_map.is_wall(corner_x, corner_y):
                return True
    return False


def get_effective_half_fov(player, current_time):
    """Widen FOV while torch is active."""
    if player.torch_until > current_time:
        return HALF_FOV * ITEM_TORCH_FOV_MULT
    return HALF_FOV


# ═════════════════════════════════════════════════════════════════════════════
#  Procedural sprite images
# ═════════════════════════════════════════════════════════════════════════════

def _make_crystal_image(size=64):
    """Glowing diamond-shaped crystal sprite."""
    path = os.path.join(ASSETS_DIR, 'models', 'props', 'crystal.png')
    if os.path.exists(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except:
            pass
    
    img = pygame.Surface((size, size), pygame.SRCALPHA)

    cx, cy = size // 2, size // 2
    # Glow aura
    for r in range(size // 2, 4, -2):
        alpha = max(5, 40 - r * 2)
        pygame.draw.circle(img, (100, 200, 255, alpha), (cx, cy), r)

    # Crystal body — diamond shape
    pts = [
        (cx, cy - size // 3),       # top
        (cx + size // 4, cy),       # right
        (cx, cy + size // 3),       # bottom
        (cx - size // 4, cy),       # left
    ]
    pygame.draw.polygon(img, (120, 220, 255), pts)
    pygame.draw.polygon(img, (180, 240, 255), pts, 2)

    # Inner highlight
    inner = [
        (cx, cy - size // 5),
        (cx + size // 7, cy),
        (cx, cy + size // 5),
        (cx - size // 7, cy),
    ]
    pygame.draw.polygon(img, (200, 240, 255, 180), inner)

    # Bright center spot
    pygame.draw.circle(img, (255, 255, 255), (cx, cy - 2), 3)

    return img


def _make_enemy_image(size=64):
    """Skull-like enemy sprite."""
    path = os.path.join(ASSETS_DIR, 'models', 'props', 'goblin.png')
    if os.path.exists(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except:
            pass
            
    img = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2

    # Dark aura
    for r in range(size // 2, 6, -2):
        alpha = max(5, 30 - r)
        pygame.draw.circle(img, (180, 30, 30, alpha), (cx, cy), r)

    # Skull body
    head_r = size // 3
    pygame.draw.circle(img, (200, 190, 170), (cx, cy - 4), head_r)
    pygame.draw.circle(img, (160, 150, 130), (cx, cy - 4), head_r, 2)

    # Jaw
    jaw_rect = pygame.Rect(cx - head_r + 4, cy + head_r // 3,
                           (head_r - 4) * 2, head_r // 2)
    pygame.draw.rect(img, (180, 170, 150), jaw_rect, border_radius=3)

    # Eye sockets
    eye_y = cy - 7
    for ex in (cx - 7, cx + 7):
        pygame.draw.circle(img, (30, 0, 0), (ex, eye_y), 5)
        pygame.draw.circle(img, (220, 30, 30), (ex, eye_y), 3)

    # Nose hole
    pygame.draw.polygon(img, (60, 40, 30), [
        (cx, cy + 1), (cx - 3, cy + 5), (cx + 3, cy + 5)
    ])

    # Teeth
    for tx in range(cx - 8, cx + 9, 4):
        pygame.draw.rect(img, (220, 215, 200),
                         (tx, cy + head_r // 3, 3, 5))

    return img


_CRYSTAL_FRAMES = None
_FALLBACK_CRYSTAL = None
_FALLBACK_ENEMY = None
_USE_3D_MODELS = False


def _init_3d_assets():
    """Load 3D model sprites once at startup."""
    global _CRYSTAL_FRAMES, _USE_3D_MODELS
    if _CRYSTAL_FRAMES is not None:
        return

    frames = get_crystal_frames()
    monsters = discover_monster_models()
    if frames and monsters:
        _CRYSTAL_FRAMES = frames
        _USE_3D_MODELS = True
        # Pre-bake a handful of monsters so the first level doesn't hitch
        warm = random.sample(monsters, min(8, len(monsters)))
        for path in warm:
            bake_sprite(path, target_height=0.95)
        print(f'[3D] Loaded gem model ({len(frames)} spin frames), '
              f'{len(monsters)} monster models')
    else:
        _CRYSTAL_FRAMES = []
        print('[3D] Model assets not found — using procedural sprites')


def get_crystal_image():
    global _FALLBACK_CRYSTAL
    _init_3d_assets()
    if _CRYSTAL_FRAMES:
        return _CRYSTAL_FRAMES[0]
    if _FALLBACK_CRYSTAL is None:
        _FALLBACK_CRYSTAL = _make_crystal_image()
    return _FALLBACK_CRYSTAL


def get_crystal_frame(current_time, bob_offset=0.0):
    """Return the crystal sprite for the current spin frame."""
    _init_3d_assets()
    if _CRYSTAL_FRAMES:
        t = current_time * 0.003 + bob_offset
        idx = int(t * CRYSTAL_SPIN_FRAMES / (2 * math.pi)) % len(_CRYSTAL_FRAMES)
        return _CRYSTAL_FRAMES[idx]
    return get_crystal_image()


def get_enemy_image(model_path=None):
    global _FALLBACK_ENEMY
    _init_3d_assets()
    if _USE_3D_MODELS:
        sprite = get_enemy_sprite(model_path)
        if sprite is not None:
            return sprite
    if _FALLBACK_ENEMY is None:
        _FALLBACK_ENEMY = _make_enemy_image()
    return _FALLBACK_ENEMY


def get_enemy_hurt_image(base_image):
    return tint_surface(base_image, (255, 60, 60), alpha=100)


def _make_fireball_image(size=48):
    """Glowing fireball billboard."""
    img = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    for r in range(size // 2, 2, -2):
        alpha = max(10, 80 - r * 3)
        t = r / (size // 2)
        color = (255, int(180 - 80 * t), int(40 - 20 * t), alpha)
        pygame.draw.circle(img, color, (cx, cy), r)
    pygame.draw.circle(img, (255, 255, 200), (cx, cy - 2), size // 6)
    return img


def _make_enemy_projectile_image(size=32):
    img = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    pygame.draw.circle(img, (180, 60, 60, 200), (cx, cy), size // 3)
    pygame.draw.circle(img, (255, 100, 80), (cx, cy), size // 5)
    return img


def _make_potion_icon(size=32):
    img = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(img, (200, 60, 80), (size // 2 - 4, 6, 8, 10), border_radius=2)
    pygame.draw.polygon(img, (220, 50, 70), [
        (size // 2, 16), (size // 2 + 10, size - 4),
        (size // 2 - 10, size - 4),
    ])
    pygame.draw.polygon(img, (255, 120, 140), [
        (size // 2, 20), (size // 2 + 6, size - 8),
        (size // 2 - 6, size - 8),
    ])
    return img


def _make_torch_icon(size=32):
    img = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(img, (120, 80, 40), (size // 2 - 3, 14, 6, 14))
    for i in range(4):
        r = 10 - i * 2
        pygame.draw.circle(img, (255, 160 - i * 20, 40, 180 - i * 30),
                           (size // 2, 10), r)
    return img


_FIREBALL_IMG = None
_ENEMY_PROJ_IMG = None
_POTION_ICON = None
_TORCH_ICON = None


def get_fireball_image():
    global _FIREBALL_IMG
    if _FIREBALL_IMG is None:
        _FIREBALL_IMG = _make_fireball_image()
    return _FIREBALL_IMG


def get_enemy_projectile_image():
    global _ENEMY_PROJ_IMG
    if _ENEMY_PROJ_IMG is None:
        _ENEMY_PROJ_IMG = _make_enemy_projectile_image()
    return _ENEMY_PROJ_IMG


def get_item_icon(item_type):
    global _POTION_ICON, _TORCH_ICON
    if item_type == 'potion':
        if _POTION_ICON is None:
            _POTION_ICON = _make_potion_icon()
        return _POTION_ICON
    if _TORCH_ICON is None:
        _TORCH_ICON = _make_torch_icon()
    return _TORCH_ICON


# ═════════════════════════════════════════════════════════════════════════════
#  Projectile
# ═════════════════════════════════════════════════════════════════════════════

class Projectile:
    """Billboard projectile for player fireballs and brute throws."""

    def __init__(self, x, y, angle, speed, damage, max_range, owner='player'):
        self.x = x
        self.y = y
        self.angle = angle
        self.speed = speed
        self.damage = damage
        self.max_range = max_range
        self.owner = owner
        self.traveled = 0.0
        self.alive = True
        self.image = (get_fireball_image() if owner == 'player'
                      else get_enemy_projectile_image())

    def update(self, dungeon_map, enemies, player, dt, sound_mgr):
        if not self.alive:
            return
        dx = math.cos(self.angle) * self.speed * dt
        dy = math.sin(self.angle) * self.speed * dt
        new_x = self.x + dx
        new_y = self.y + dy

        if _collides_circle(new_x, new_y, 0.08, dungeon_map):
            self.alive = False
            return

        self.x = new_x
        self.y = new_y
        self.traveled += math.hypot(dx, dy)
        if self.traveled >= self.max_range:
            self.alive = False
            return

        if self.owner == 'player':
            for enemy in enemies:
                if not enemy.alive:
                    continue
                if math.hypot(enemy.x - self.x, enemy.y - self.y) < FIREBALL_HIT_RADIUS:
                    enemy.take_damage(self.damage, sound_mgr, player=player,
                                      dungeon_map=dungeon_map)
                    if not enemy.alive:
                        player.enemies_killed += 1
                        player.score += 50
                    self.alive = False
                    return
        elif player.alive:
            if math.hypot(player.x - self.x, player.y - self.y) < 0.35:
                player.take_damage(self.damage, sound_mgr)
                self.alive = False


# ═════════════════════════════════════════════════════════════════════════════
#  Items
# ═════════════════════════════════════════════════════════════════════════════

class Item:
    """Inventory item — potion or torch."""

    TYPE_POTION = 'potion'
    TYPE_TORCH = 'torch'

    def __init__(self, item_type):
        self.item_type = item_type

    def use(self, player, current_time, hud):
        if self.item_type == self.TYPE_POTION:
            before = player.health
            player.health = min(PLAYER_MAX_HEALTH,
                                player.health + ITEM_POTION_HEAL)
            healed = player.health - before
            if healed > 0:
                hud.add_message(f'+{healed} HP', color=(120, 255, 120))
            return True
        if self.item_type == self.TYPE_TORCH:
            player.torch_until = current_time + ITEM_TORCH_DURATION
            hud.add_message('Torch lit — wider vision!',
                            color=(255, 180, 80))
            return True
        return False

    @property
    def label(self):
        return 'Potion' if self.item_type == self.TYPE_POTION else 'Torch'


class WorldPickup:
    """Item sitting on the dungeon floor."""

    def __init__(self, x, y, item_type):
        self.x = x
        self.y = y
        self.item = Item(item_type)
        self.picked_up = False

    def check_pickup(self, player):
        if self.picked_up:
            return False
        if math.hypot(player.x - self.x, player.y - self.y) > ITEM_PICKUP_RANGE:
            return False
        if player.add_item(self.item):
            self.picked_up = True
            return True
        return False

    @property
    def icon(self):
        return get_item_icon(self.item.item_type)


# ═════════════════════════════════════════════════════════════════════════════
#  Crystal
# ═════════════════════════════════════════════════════════════════════════════

class Crystal:
    """Collectible crystal that bobs up and down."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.collected = False
        self.bob_offset = random.uniform(0, math.pi * 2)

    def check_collect(self, player, sound_mgr, current_time):
        if self.collected:
            return
        dx = player.x - self.x
        dy = player.y - self.y
        if math.sqrt(dx * dx + dy * dy) < CRYSTAL_COLLECT_RANGE:
            self.collected = True
            player.score += CRYSTAL_SCORE
            player.crystals_collected += 1
            sound_mgr.play('crystal_pickup')


# ═════════════════════════════════════════════════════════════════════════════
#  Enemy
# ═════════════════════════════════════════════════════════════════════════════

class Enemy:
    """Dungeon enemy — Crawler, Shade, or Brute with distinct AI."""

    MINIMAP_COLORS = {
        ENEMY_TYPE_CRAWLER: COLOR_MINIMAP_CRAWLER,
        ENEMY_TYPE_SHADE: COLOR_MINIMAP_SHADE,
        ENEMY_TYPE_BRUTE: COLOR_MINIMAP_BRUTE,
    }

    def __init__(self, x, y, difficulty='normal', enemy_type=ENEMY_TYPE_CRAWLER):
        self.x = x
        self.y = y
        self.enemy_type = enemy_type

        diff_mult = {'easy': 0.5, 'normal': 1.0, 'hard': 1.5}.get(difficulty, 1.0)
        diff_speed = (0.6 if difficulty == 'easy'
                      else (1.2 if difficulty == 'hard' else 1.0))

        type_speed = {
            ENEMY_TYPE_CRAWLER: CRAWLER_SPEED_MULT,
            ENEMY_TYPE_SHADE: SHADE_SPEED_MULT,
            ENEMY_TYPE_BRUTE: BRUTE_SPEED_MULT,
        }[enemy_type]
        type_health = {
            ENEMY_TYPE_CRAWLER: CRAWLER_HEALTH_MULT,
            ENEMY_TYPE_SHADE: SHADE_HEALTH_MULT,
            ENEMY_TYPE_BRUTE: BRUTE_HEALTH_MULT,
        }[enemy_type]

        self.health = ENEMY_HEALTH * diff_mult * type_health
        self.alive = True
        self.speed = ENEMY_SPEED * diff_speed * type_speed
        self.damage = ENEMY_DAMAGE * diff_mult
        self.attack_cooldown = ENEMY_ATTACK_COOLDOWN * (
            2.0 if difficulty == 'easy' else (0.8 if difficulty == 'hard' else 1.2))

        # Physics & movement
        self.vx = 0.0
        self.vy = 0.0
        self.bob_phase = random.uniform(0, math.pi * 2)

        self.state = 'patrol'
        self._prev_state = 'patrol'
        self.facing = random.uniform(0, math.pi * 2)
        self.patrol_angle = random.uniform(0, math.pi * 2)
        self.patrol_timer = 0
        self.attack_timer = 0
        self.projectile_timer = 0

        self.hurt_timer = 0
        self.alert_timer = 0    # ms, shows ! on minimap when > 0
        self.corpse_timer = 0   # ms alive after death for linger
        self.death_pos = None   # (x, y) at time of death
        _init_3d_assets()
        models = discover_monster_models()
        self.model_path = random.choice(models) if models else None
        self.image = get_enemy_image(self.model_path)
        self.death_anim = 0.0

    @property
    def minimap_color(self):
        return self.MINIMAP_COLORS.get(self.enemy_type, COLOR_MINIMAP_CRAWLER)

    def update(self, player, dungeon_map, dt, current_time, projectiles=None, other_enemies=None):
        if not self.alive:
            self.death_anim = min(1.0, self.death_anim + dt * 0.004)
            if self.death_pos is None:
                self.death_pos = (self.x, self.y)
            if self.corpse_timer == 0:
                self.corpse_timer = current_time
            return

        self._prev_state = self.state
        if self.hurt_timer > 0:
            self.hurt_timer = max(0, self.hurt_timer - dt)
        if self.alert_timer > 0:
            self.alert_timer = max(0, self.alert_timer - dt)

        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        if self.enemy_type == ENEMY_TYPE_BRUTE and projectiles is not None:
            self._try_brute_throw(player, dist, dx, dy, current_time, projectiles)

        if dist < ENEMY_ATTACK_RANGE:
            self._do_attack(player, current_time, dist, dx, dy, dt, dungeon_map)
        elif dist < ENEMY_CHASE_RANGE:
            self._do_chase(dx, dy, dist, dungeon_map, dt)
            # Trigger alert flash when first spotting player
            if self._prev_state == 'patrol':
                self.alert_timer = 1800
        else:
            self._do_patrol(dungeon_map, dt, current_time)

        self._apply_physics(dt, dungeon_map, other_enemies)

    def _try_brute_throw(self, player, dist, dx, dy, current_time, projectiles):
        if dist > ENEMY_CHASE_RANGE or dist < ENEMY_STOP_DISTANCE:
            return
        if current_time - self.projectile_timer < BRUTE_PROJECTILE_COOLDOWN:
            return
        angle = math.atan2(dy, dx)
        if abs(self._angle_delta(self.facing, angle)) > ENEMY_ATTACK_ARC:
            return
        self.projectile_timer = current_time
        ox = self.x + math.cos(angle) * 0.3
        oy = self.y + math.sin(angle) * 0.3
        projectiles.append(Projectile(
            ox, oy, angle, BRUTE_PROJECTILE_SPEED,
            BRUTE_PROJECTILE_DAMAGE, BRUTE_PROJECTILE_RANGE, owner='enemy',
        ))

    @staticmethod
    def _angle_delta(from_angle, to_angle):
        return (to_angle - from_angle + math.pi) % (2 * math.pi) - math.pi

    def _turn_toward(self, target_angle, dt, turn_speed):
        delta = self._angle_delta(self.facing, target_angle)
        step = turn_speed * dt
        if abs(delta) <= step:
            self.facing = target_angle
        else:
            self.facing += step if delta > 0 else -step
        self.facing %= 2 * math.pi

    def _do_patrol(self, dungeon_map, dt, current_time):
        self.state = 'patrol'
        if current_time - self.patrol_timer > 2000:
            self.patrol_angle = random.uniform(0, math.pi * 2)
            self.patrol_timer = current_time

        self._turn_toward(self.patrol_angle, dt, ENEMY_TURN_SPEED * 0.4)
        move = self.speed * dt * 0.002
        self._apply_acceleration(math.cos(self.facing) * move, math.sin(self.facing) * move)

    def _do_chase(self, dx, dy, dist, dungeon_map, dt):
        self.state = 'chase'
        target_angle = math.atan2(dy, dx)
        self._turn_toward(target_angle, dt, ENEMY_TURN_SPEED)

        if abs(self._angle_delta(self.facing, target_angle)) > math.pi / 2:
            return

        if dist <= ENEMY_STOP_DISTANCE:
            return

        closeness = min(1.0, (dist - ENEMY_STOP_DISTANCE) / 2.5)
        move = (self.speed * ENEMY_CHASE_SPEED_MULT * dt
                * (0.0035 + 0.0065 * closeness))
        self._apply_acceleration(math.cos(self.facing) * move, math.sin(self.facing) * move)

    def _do_attack(self, player, current_time, dist, dx, dy, dt, dungeon_map):
        self.state = 'attack'
        target_angle = math.atan2(dy, dx)
        self._turn_toward(target_angle, dt, ENEMY_TURN_SPEED * 1.5)

        if (dist > ENEMY_STOP_DISTANCE
                and abs(self._angle_delta(self.facing, target_angle)) < math.pi / 3):
            creep = self.speed * 0.001 * dt
            self._apply_acceleration(math.cos(self.facing) * creep, math.sin(self.facing) * creep)

        if abs(self._angle_delta(self.facing, target_angle)) > ENEMY_ATTACK_ARC:
            return
        if current_time - self.attack_timer >= self.attack_cooldown:
            self.attack_timer = current_time
            if player.alive:
                player.take_damage(self.damage, player._sound_mgr_ref)

    def _apply_acceleration(self, dx, dy):
        self.vx += dx
        self.vy += dy

    def _apply_physics(self, dt, dungeon_map, other_enemies):
        # 1. Boids Separation (push away from other enemies)
        if other_enemies:
            for other in other_enemies:
                if other is self or not other.alive:
                    continue
                dx = self.x - other.x
                dy = self.y - other.y
                dist = math.hypot(dx, dy)
                if 0 < dist < ENEMY_SIZE * 2.5:
                    force = (ENEMY_SIZE * 2.5 - dist) / dist * 0.001 * dt
                    self.vx += dx * force
                    self.vy += dy * force

        # 2. Integrate velocity
        new_x = self.x + self.vx * dt
        if not _collides_circle(new_x, self.y, ENEMY_SIZE, dungeon_map):
            self.x = new_x
        else:
            self.vx *= -0.5  # Bounce off walls slightly

        new_y = self.y + self.vy * dt
        if not _collides_circle(self.x, new_y, ENEMY_SIZE, dungeon_map):
            self.y = new_y
        else:
            self.vy *= -0.5

        # 3. Apply friction
        friction = max(0.0, 1.0 - 0.008 * dt)
        self.vx *= friction
        self.vy *= friction

        # 4. Walking Bob Animation
        speed = math.hypot(self.vx, self.vy)
        if speed > 0.0001:
            self.bob_phase += speed * dt * 4.0

    def _teleport_away(self, player, dungeon_map):
        dx = self.x - player.x
        dy = self.y - player.y
        dist = math.hypot(dx, dy) or 1.0
        dx /= dist
        dy /= dist
        tx = self.x + dx * SHADE_TELEPORT_DIST
        ty = self.y + dy * SHADE_TELEPORT_DIST
        if not _collides_circle(tx, ty, ENEMY_SIZE, dungeon_map):
            self.x, self.y = tx, ty

    def take_damage(self, amount, sound_mgr, player=None, dungeon_map=None):
        self.health -= amount
        self.hurt_timer = 150
        sound_mgr.play('enemy_hit')
        
        # Apply knockback
        if player:
            dx = self.x - player.x
            dy = self.y - player.y
            dist = math.hypot(dx, dy)
            if dist > 0:
                self.vx += (dx / dist) * 0.04
                self.vy += (dy / dist) * 0.04

        if (self.enemy_type == ENEMY_TYPE_SHADE and player is not None
                and dungeon_map is not None and self.alive):
            self._teleport_away(player, dungeon_map)
        if self.health <= 0:
            self.alive = False
            self.death_anim = 0.0
            sound_mgr.play('enemy_death')

    @property
    def current_image(self):
        if self.hurt_timer > 0:
            return get_enemy_hurt_image(self.image)
        return self.image


# ═════════════════════════════════════════════════════════════════════════════
#  Sprite Renderer
# ═════════════════════════════════════════════════════════════════════════════

class SpriteRenderer:
    """Projects and draws all world sprites with depth-buffer occlusion."""

    def __init__(self, screen):
        self.screen = screen

    def render(self, player, crystals, enemies, depth_buffer, current_time,
               projectiles=None, world_items=None):
        """Render all sprites sorted back-to-front."""
        sprite_list = []
        half_fov = get_effective_half_fov(player, current_time)
        effective_fov = half_fov * 2

        for c in crystals:
            if c.collected:
                continue
            dx = c.x - player.x
            dy = c.y - player.y
            dist = math.sqrt(dx * dx + dy * dy)
            bob = math.sin(current_time * 0.003 + c.bob_offset) * 8
            frame = get_crystal_frame(current_time, c.bob_offset)
            sprite_list.append((dist, frame, dx, dy, bob, 1.0, 0.7))

        if world_items:
            for wp in world_items:
                if wp.picked_up:
                    continue
                dx = wp.x - player.x
                dy = wp.y - player.y
                dist = math.sqrt(dx * dx + dy * dy)
                bob = math.sin(current_time * 0.004 + wp.x) * 4
                sprite_list.append((dist, wp.icon, dx, dy, bob, 1.0, 0.45))

        if projectiles:
            for proj in projectiles:
                if not proj.alive:
                    continue
                dx = proj.x - player.x
                dy = proj.y - player.y
                dist = math.sqrt(dx * dx + dy * dy)
                sprite_list.append((dist, proj.image, dx, dy, 0, 1.0, 0.35))

        for e in enemies:
            if not e.alive and e.death_anim >= 1.0:
                continue
            dx = e.x - player.x
            dy = e.y - player.y
            dist = math.sqrt(dx * dx + dy * dy)
            alpha = 1.0 - e.death_anim if not e.alive else 1.0
            bob = math.sin(e.bob_phase) * 35 if e.alive else 0
            sprite_list.append((dist, e.current_image, dx, dy, bob, alpha, 1.0))

        sprite_list.sort(key=lambda s: s[0], reverse=True)

        torch_active = player.torch_until > current_time
        for dist, image, dx, dy, y_offset, alpha, scale in sprite_list:
            self._draw_sprite(player, image, dx, dy, dist, y_offset,
                              alpha, depth_buffer, effective_fov, scale,
                              torch_active)

    def _draw_sprite(self, player, image, dx, dy, dist, y_offset,
                     alpha, depth_buffer, effective_fov, scale_mult,
                     torch_active=False):
        sprite_angle = math.atan2(dy, dx)
        delta = sprite_angle - player.angle
        while delta > math.pi:
            delta -= 2 * math.pi
        while delta < -math.pi:
            delta += 2 * math.pi

        half_fov = effective_fov / 2
        if abs(delta) > half_fov + 0.3:
            return

        screen_x = int((delta / effective_fov + 0.5) * SCREEN_WIDTH)

        if dist < 0.1:
            dist = 0.1
        proj_h = int(SCREEN_DIST / dist * scale_mult)
        if proj_h < 4:
            return
        if proj_h > SCREEN_HEIGHT * 2:
            proj_h = SCREEN_HEIGHT * 2

        half_w = proj_h // 2
        screen_y = int(HALF_HEIGHT - proj_h // 2 + y_offset)

        scaled = pygame.transform.scale(image, (proj_h, proj_h))

        if alpha < 1.0:
            scaled.set_alpha(int(alpha * 255))

        darkness = max(40, 255 - int(dist * 22))
        if torch_active:
            darkness = min(255, darkness + 55)
        dark = pygame.Surface(scaled.get_size())
        dark.fill((darkness, darkness, darkness))
        scaled.blit(dark, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        start_x = screen_x - half_w
        for col in range(proj_h):
            sx = start_x + col
            if sx < 0 or sx >= SCREEN_WIDTH:
                continue
            ray_idx = sx * NUM_RAYS // SCREEN_WIDTH
            if ray_idx < 0 or ray_idx >= NUM_RAYS:
                continue
            if dist < depth_buffer[ray_idx]:
                strip = scaled.subsurface(col, 0, 1, proj_h)
                self.screen.blit(strip, (sx, screen_y))
