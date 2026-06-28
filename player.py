"""
Dungeon Explorer — Player
Handles input, movement, collision, and combat.
"""
import math
import pygame
from settings import (
    PLAYER_SPEED, PLAYER_SPRINT_MULT, PLAYER_ROT_SPEED, PLAYER_SIZE,
    PLAYER_MAX_HEALTH, PLAYER_ATTACK_RANGE, PLAYER_ATTACK_DAMAGE,
    PLAYER_ATTACK_COOLDOWN,
    PLAYER_DODGE_SPEED_MULT, PLAYER_DODGE_DURATION, PLAYER_DODGE_COOLDOWN,
    PLAYER_STAMINA_MAX, PLAYER_STAMINA_DRAIN, PLAYER_STAMINA_REGEN,
    FIREBALL_COOLDOWN, FIREBALL_SPEED, FIREBALL_DAMAGE, FIREBALL_MAX_RANGE,
    INVENTORY_SIZE,
)


class Player:
    """First-person player with AZERTY/arrow movement, mouse look, and melee attack."""

    def __init__(self, x, y, angle=0.0):
        self.x = x
        self.y = y
        self.angle = angle
        self.health = PLAYER_MAX_HEALTH
        self.score = 0
        self.crystals_collected = 0
        self.enemies_killed = 0
        self.level = 1

        # Attack state
        self.attack_timer = 0
        self.is_attacking = False
        self.attack_anim_timer = 0

        # Charge attack
        self.is_charging = False
        self.charge_start_time = 0
        self.charge_ratio = 0.0   # 0.0 to 1.0

        # Critical hit flash
        self.crit_flash = 0.0

        # Damage flash
        self.damage_flash = 0.0   # 0-1, fades to zero

        # Movement tracking
        self.is_moving = False
        
        # Camera modifiers
        self.head_bob_phase = 0.0
        self.screen_shake = 0.0

        # Dodge
        self.dodge_timer = 0
        self.dodge_cooldown_until = 0

        # Stamina
        self.stamina = PLAYER_STAMINA_MAX

        # Fireball
        self.fireball_timer = 0

        # Torch effect
        self.torch_until = 0

        # Inventory
        self.inventory = [None] * INVENTORY_SIZE
        self.inventory_open = False

    # ── Update ───────────────────────────────────────────────────────────
    def update(self, dungeon_map, dt, current_time):
        self._handle_mouse()
        self._handle_keys(dungeon_map, dt, current_time)

        # Fade damage flash
        if self.damage_flash > 0:
            self.damage_flash = max(0.0, self.damage_flash - dt * 0.003)
        if self.crit_flash > 0:
            self.crit_flash = max(0.0, self.crit_flash - dt * 0.006)

        # Update charge ratio
        if self.is_charging:
            elapsed = current_time - self.charge_start_time
            self.charge_ratio = min(1.0, elapsed / 1400)  # full charge in 1.4s

        if self.is_moving:
            self.head_bob_phase += dt * 0.015
        if self.screen_shake > 0:
            self.screen_shake = max(0.0, self.screen_shake - dt * 0.2)

        # Attack animation timer
        if self.is_attacking:
            self.attack_anim_timer -= dt
            if self.attack_anim_timer <= 0:
                self.is_attacking = False

        # Dodge timer
        if self.dodge_timer > 0:
            self.dodge_timer = max(0, self.dodge_timer - dt)

    def _handle_mouse(self):
        rel_x, _ = pygame.mouse.get_rel()
        self.angle += rel_x * PLAYER_ROT_SPEED
        self.angle %= 2 * math.pi

    def _handle_keys(self, dungeon_map, dt, current_time):
        keys = pygame.key.get_pressed()
        speed = PLAYER_SPEED * dt

        forward = (keys[pygame.K_z] or keys[pygame.K_UP])
        backward = (keys[pygame.K_s] or keys[pygame.K_DOWN])
        strafe_left = (keys[pygame.K_q] or keys[pygame.K_LEFT])
        strafe_right = (keys[pygame.K_d] or keys[pygame.K_RIGHT])

        sprinting = keys[pygame.K_LSHIFT] and self.stamina > 0
        if self.dodge_timer > 0:
            speed *= PLAYER_DODGE_SPEED_MULT
        elif sprinting:
            speed *= PLAYER_SPRINT_MULT
            self.stamina = max(0.0, self.stamina - PLAYER_STAMINA_DRAIN * dt)
        else:
            self.stamina = min(
                PLAYER_STAMINA_MAX,
                self.stamina + PLAYER_STAMINA_REGEN * dt,
            )

        sin_a = math.sin(self.angle)
        cos_a = math.cos(self.angle)

        dx, dy = 0.0, 0.0

        if forward:
            dx += cos_a * speed
            dy += sin_a * speed
        if backward:
            dx -= cos_a * speed
            dy -= sin_a * speed
        if strafe_left:
            dx += sin_a * speed
            dy -= cos_a * speed
        if strafe_right:
            dx -= sin_a * speed
            dy += cos_a * speed

        self.is_moving = (dx != 0 or dy != 0)
        self._move(dx, dy, dungeon_map)

    def _move(self, dx, dy, dungeon_map):
        """Move with wall-slide collision."""
        size = PLAYER_SIZE

        # Try X movement
        new_x = self.x + dx
        if not self._collides(new_x, self.y, size, dungeon_map):
            self.x = new_x

        # Try Y movement
        new_y = self.y + dy
        if not self._collides(self.x, new_y, size, dungeon_map):
            self.y = new_y

    @staticmethod
    def _collides(x, y, size, dungeon_map):
        """Check if a circle at (x, y) with radius=size hits any wall."""
        for corner_x in (x - size, x + size):
            for corner_y in (y - size, y + size):
                if dungeon_map.is_wall(corner_x, corner_y):
                    return True
        return False

    # ── Dodge ────────────────────────────────────────────────────────────
    def try_dodge(self, current_time):
        if self.dodge_timer > 0:
            return False
        if current_time < self.dodge_cooldown_until:
            return False
        self.dodge_timer = PLAYER_DODGE_DURATION
        self.dodge_cooldown_until = current_time + PLAYER_DODGE_COOLDOWN
        return True

    def add_item(self, item):
        for i, slot in enumerate(self.inventory):
            if slot is None:
                self.inventory[i] = item
                return True
        return False

    def use_inventory_slot(self, slot_idx, current_time, hud):
        if slot_idx < 0 or slot_idx >= INVENTORY_SIZE:
            return
        item = self.inventory[slot_idx]
        if item is None:
            return
        if item.use(self, current_time, hud):
            self.inventory[slot_idx] = None

    def try_fireball(self, current_time, sound_mgr):
        from sprites import Projectile
        if current_time - self.fireball_timer < FIREBALL_COOLDOWN:
            return None
        self.fireball_timer = current_time
        sound_mgr.play('attack_whoosh')
        ox = self.x + math.cos(self.angle) * 0.35
        oy = self.y + math.sin(self.angle) * 0.35
        return Projectile(
            ox, oy, self.angle, FIREBALL_SPEED,
            FIREBALL_DAMAGE, FIREBALL_MAX_RANGE, owner='player',
        )

    @property
    def fireball_ready_ratio(self):
        elapsed = pygame.time.get_ticks() - self.fireball_timer
        if elapsed >= FIREBALL_COOLDOWN:
            return 1.0
        return elapsed / FIREBALL_COOLDOWN

    # ── Combat ───────────────────────────────────────────────────────────
    def try_attack(self, current_time, sound_mgr):
        if current_time - self.attack_timer < PLAYER_ATTACK_COOLDOWN:
            return False
        self.attack_timer = current_time
        self.is_attacking = True
        self.attack_anim_timer = 200  # ms of animation
        sound_mgr.play('attack_whoosh')
        return True

    def start_charge(self, current_time):
        """Begin charging an attack."""
        if current_time - self.attack_timer < PLAYER_ATTACK_COOLDOWN:
            return
        if not self.is_charging:
            self.is_charging = True
            self.charge_start_time = current_time
            self.charge_ratio = 0.0

    def release_charge(self, enemies, current_time, sound_mgr, dungeon_map=None):
        """Release a charged attack. Returns True if hit."""
        if not self.is_charging:
            return False
        ratio = self.charge_ratio
        self.is_charging = False
        self.charge_ratio = 0.0

        if ratio < 0.1:   # Too short — do a normal attack instead
            return self.attack_enemies(enemies, current_time, sound_mgr, dungeon_map)

        # Heavy charged blow
        if current_time - self.attack_timer < PLAYER_ATTACK_COOLDOWN:
            return False
        self.attack_timer = current_time
        self.is_attacking = True
        self.attack_anim_timer = 350
        sound_mgr.play('attack_whoosh')

        damage = int(PLAYER_ATTACK_DAMAGE * (1.0 + 2.0 * ratio))
        hit_any = False
        for enemy in enemies:
            if not enemy.alive:
                continue
            dx = enemy.x - self.x
            dy = enemy.y - self.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > PLAYER_ATTACK_RANGE * (1.0 + ratio * 0.5):  # wider arc at full charge
                continue
            angle_to = math.atan2(dy, dx)
            delta = (angle_to - self.angle + math.pi) % (2 * math.pi) - math.pi
            if abs(delta) < math.pi / 2.5:
                enemy.take_damage(damage, sound_mgr, player=self, dungeon_map=dungeon_map)
                # Heavy knockback
                if dist > 0:
                    enemy.vx += (dx / dist) * 0.12 * ratio
                    enemy.vy += (dy / dist) * 0.12 * ratio
                hit_any = True
                if not enemy.alive:
                    self.enemies_killed += 1
                    self.score += 50
        return hit_any

    def attack_enemies(self, enemies, current_time, sound_mgr, dungeon_map=None):
        """Damage enemies in attack range and facing direction. Returns True if hit."""
        if not self.try_attack(current_time, sound_mgr):
            return False
        import random as _rnd
        hit_any = False
        for enemy in enemies:
            if not enemy.alive:
                continue
            dx = enemy.x - self.x
            dy = enemy.y - self.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > PLAYER_ATTACK_RANGE:
                continue
            angle_to = math.atan2(dy, dx)
            delta = (angle_to - self.angle + math.pi) % (2 * math.pi) - math.pi
            if abs(delta) < math.pi / 3:
                is_crit = _rnd.random() < 0.2
                dmg = int(PLAYER_ATTACK_DAMAGE * 2.2) if is_crit else PLAYER_ATTACK_DAMAGE
                if is_crit:
                    self.crit_flash = 1.0
                enemy.take_damage(dmg, sound_mgr, player=self, dungeon_map=dungeon_map)
                hit_any = True
                if not enemy.alive:
                    self.enemies_killed += 1
                    self.score += 50
        return hit_any


    def take_damage(self, amount, sound_mgr):
        self.health = max(0, self.health - amount)
        self.damage_flash = 1.0
        self.screen_shake = 40.0
        sound_mgr.play('player_damage')

    @property
    def alive(self):
        return self.health > 0