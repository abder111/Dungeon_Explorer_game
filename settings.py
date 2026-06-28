"""
Dungeon Explorer — Settings & Constants
All game configuration lives here for easy tuning.
"""
import math
import os

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')

# ─── Display ─────────────────────────────────────────────────────────────────
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
HALF_WIDTH = SCREEN_WIDTH // 2
HALF_HEIGHT = SCREEN_HEIGHT // 2
FPS = 60
TITLE = "Dungeon Explorer"

# ─── Raycaster ───────────────────────────────────────────────────────────────
FOV = math.pi / 3                          # 60 degrees field of view
HALF_FOV = FOV / 2
NUM_RAYS = SCREEN_WIDTH // 2               # half-res for performance
DELTA_ANGLE = FOV / NUM_RAYS
MAX_DEPTH = 20                             # max ray travel in tiles
SCALE = SCREEN_WIDTH // NUM_RAYS           # pixel width per ray column
SCREEN_DIST = HALF_WIDTH / math.tan(HALF_FOV)

# ─── Textures ────────────────────────────────────────────────────────────────
TEXTURE_SIZE = 64

# ─── Player ──────────────────────────────────────────────────────────────────
PLAYER_SPEED = 0.005
PLAYER_SPRINT_MULT = 1.6
PLAYER_ROT_SPEED = 0.0012                  # mouse sensitivity (tweaked)
PLAYER_SIZE = 0.15                         # collision half-size in tiles
PLAYER_MAX_HEALTH = 100
PLAYER_ATTACK_RANGE = 1.8
PLAYER_ATTACK_DAMAGE = 35
PLAYER_ATTACK_COOLDOWN = 500               # ms

# Dodge (right-click)
PLAYER_DODGE_SPEED_MULT = 1.8
PLAYER_DODGE_DURATION = 250                # ms
PLAYER_DODGE_COOLDOWN = 1000               # ms

# Stamina (shift sprint)
PLAYER_STAMINA_MAX = 100
PLAYER_STAMINA_DRAIN = 0.033               # per ms while sprinting (~3 s to empty)
PLAYER_STAMINA_REGEN = 0.025               # per ms while not sprinting (~4 s to full)

# Doors
DOOR_INTERACT_RANGE = 1.2                  # tiles

# Fireball (F key)
FIREBALL_COOLDOWN = 1500                   # ms
FIREBALL_SPEED = 0.015                     # tiles per ms
FIREBALL_DAMAGE = 40
FIREBALL_MAX_RANGE = 10                    # tiles
FIREBALL_HIT_RADIUS = 0.4                  # tiles

# Inventory & items
INVENTORY_SIZE = 4
ITEM_PICKUP_RANGE = 1.0                    # tiles
ITEM_POTION_HEAL = 40
ITEM_TORCH_DURATION = 15000                # ms
ITEM_TORCH_FOV_MULT = 1.45                 # widens field of view
ITEM_TORCH_BRIGHTNESS = 55                 # added to wall brightness

# ─── Enemy ───────────────────────────────────────────────────────────────────
ENEMY_SPEED = 0.0055                       # base move speed (player walk is 0.008)
ENEMY_CHASE_SPEED_MULT = 0.55              # slower while pursuing — player can outrun
ENEMY_TURN_SPEED = 2.6                     # rad/s — must turn toward target, no instant back-sticks
ENEMY_ATTACK_ARC = math.pi / 3             # ~60° cone required to land a hit
ENEMY_STOP_DISTANCE = 0.55                 # hold standoff instead of overlapping the player
ENEMY_HEALTH = 60
ENEMY_DAMAGE = 10
ENEMY_ATTACK_RANGE = 0.85
ENEMY_CHASE_RANGE = 8.0
ENEMY_ATTACK_COOLDOWN = 1800               # ms — slightly longer wind-up between hits
ENEMY_SIZE = 0.2                           # collision radius in tiles

# Enemy types
ENEMY_TYPE_CRAWLER = 'crawler'
ENEMY_TYPE_SHADE = 'shade'
ENEMY_TYPE_BRUTE = 'brute'

CRAWLER_SPEED_MULT = 0.6
CRAWLER_HEALTH_MULT = 2.0
SHADE_SPEED_MULT = 1.8
SHADE_HEALTH_MULT = 0.5
SHADE_TELEPORT_DIST = 2.0                  # tiles on hit
BRUTE_SPEED_MULT = 1.0
BRUTE_HEALTH_MULT = 1.5
BRUTE_PROJECTILE_COOLDOWN = 3000           # ms
BRUTE_PROJECTILE_SPEED = 0.009
BRUTE_PROJECTILE_DAMAGE = 8
BRUTE_PROJECTILE_RANGE = 12

# ─── Crystal ─────────────────────────────────────────────────────────────────
CRYSTAL_SCORE = 100
CRYSTAL_COLLECT_RANGE = 0.6

# ─── Wall types ──────────────────────────────────────────────────────────────
WALL_STONE = 1
WALL_BRICK = 2
WALL_MOSSY = 3
WALL_DARK  = 4
WALL_DOOR  = 5

# ─── Dungeon generation ─────────────────────────────────────────────────────
MAP_WIDTH = 32
MAP_HEIGHT = 32

# ─── Colors ──────────────────────────────────────────────────────────────────
COLOR_BG            = (10, 10, 15)
COLOR_FLOOR_NEAR    = (50, 42, 55)
COLOR_FLOOR_FAR     = (20, 18, 25)
COLOR_CEILING_NEAR  = (25, 22, 35)
COLOR_CEILING_FAR   = (10,  8, 15)

COLOR_MINIMAP_BG      = (0, 0, 0)
COLOR_MINIMAP_WALL    = (80, 75, 90)
COLOR_MINIMAP_FLOOR   = (35, 30, 45)
COLOR_MINIMAP_PLAYER  = (0, 200, 255)
COLOR_MINIMAP_ENEMY   = (255, 60, 60)
COLOR_MINIMAP_CRAWLER = (255, 140, 60)
COLOR_MINIMAP_SHADE   = (180, 80, 255)
COLOR_MINIMAP_BRUTE   = (220, 50, 50)
COLOR_MINIMAP_CRYSTAL = (255, 220, 50)
COLOR_MINIMAP_ITEM    = (120, 255, 120)

COLOR_MANA_BG  = (35, 28, 50)
COLOR_MANA_FG  = (255, 120, 40)

COLOR_HEALTH_BG  = (40, 35, 50)
COLOR_HEALTH_FG  = (0, 220, 100)
COLOR_HEALTH_LOW = (220, 50, 50)
COLOR_STAMINA_BG = (35, 30, 45)
COLOR_STAMINA_FG = (80, 160, 255)
COLOR_SCORE      = (255, 220, 50)
COLOR_WHITE      = (255, 255, 255)
COLOR_RED_FLASH  = (180, 0, 0)