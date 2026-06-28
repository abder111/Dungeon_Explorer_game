"""
Dungeon Explorer — Sound Manager
Loads and plays all game audio using Kenney asset packs.
Synthesises ambient dungeon sounds procedurally.
"""
import pygame
import os
import random
import numpy as np
from settings import ASSETS_DIR


class SoundManager:
    """Manages all game audio: footsteps, combat, pickups, UI clicks, music, ambient."""

    def __init__(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(16)

        self.sounds = {}
        self.footstep_sounds = []
        self.footstep_timer = 0
        self.footstep_interval = 350  # ms between footsteps
        self.ambient_timer = 0
        self.ambient_interval = random.randint(5000, 12000)

        self._load_sounds()
        self._synth_ambient()
        self._start_music()

    # ── Loading ──────────────────────────────────────────────────────────
    def _load_sounds(self):
        sfx_dir = os.path.join(ASSETS_DIR, 'audio', 'sfx')
        ui_dir = os.path.join(ASSETS_DIR, 'ui', 'Sounds')

        # Footsteps (concrete surface for dungeon)
        for i in range(5):
            path = os.path.join(sfx_dir, f'footstep_concrete_{i:03d}.ogg')
            if os.path.exists(path):
                snd = pygame.mixer.Sound(path)
                snd.set_volume(0.25)
                self.footstep_sounds.append(snd)

        # Combat & interaction sounds (load multiple variants)
        sound_map = {
            'enemy_hit':      ('impactPunch_heavy', 0.5),
            'crystal_pickup': ('impactMetal_light',  0.45),
            'player_damage':  ('impactGlass_light',  0.4),
            'enemy_death':    ('impactGlass_heavy',  0.5),
            'attack_whoosh':  ('impactSoft_medium',  0.35),
        }
        for key, (prefix, vol) in sound_map.items():
            variants = []
            for i in range(5):
                path = os.path.join(sfx_dir, f'{prefix}_{i:03d}.ogg')
                if os.path.exists(path):
                    snd = pygame.mixer.Sound(path)
                    snd.set_volume(vol)
                    variants.append(snd)
            if variants:
                self.sounds[key] = variants

        # UI sounds
        for name in ('click-a', 'tap-a', 'switch-a'):
            path = os.path.join(ui_dir, f'{name}.ogg')
            if os.path.exists(path):
                snd = pygame.mixer.Sound(path)
                snd.set_volume(0.5)
                self.sounds[name] = [snd]

        # Synthesized crit hit sound (sharp metallic crack)
        crit_buf = self._synth_crit()
        if crit_buf is not None:
            self.sounds['crit_hit'] = [crit_buf]

    def _start_music(self):
        music_dir = os.path.join(ASSETS_DIR, 'audio', 'music')
        if not os.path.isdir(music_dir):
            return
        files = [f for f in os.listdir(music_dir)
                 if f.endswith(('.ogg', '.mp3', '.wav'))]
        if files:
            pygame.mixer.music.load(os.path.join(music_dir, files[0]))
            pygame.mixer.music.set_volume(0.3)
            pygame.mixer.music.play(-1)

    def _make_sound(self, samples_left, samples_right, volume=0.4):
        """Convert two float32 numpy arrays into a stereo pygame.mixer.Sound."""
        samples_left  = np.clip(samples_left,  -1.0, 1.0)
        samples_right = np.clip(samples_right, -1.0, 1.0)
        stereo = np.column_stack([samples_left, samples_right])
        buf = (stereo * 32767 * volume).astype(np.int16)
        snd = pygame.sndarray.make_sound(buf)
        return snd

    def _synth_crit(self):
        """Sharp metallic zing — played on critical hits."""
        try:
            sr = 44100
            dur = 0.18
            t = np.linspace(0, dur, int(sr * dur), False)
            freq = 1200 * np.exp(-t * 18)
            wave = np.sin(2 * np.pi * freq * t)
            env  = np.exp(-t * 14)
            samples = wave * env
            return self._make_sound(samples, samples, volume=0.5)
        except Exception:
            return None

    def _synth_ambient(self):
        """Pre-bake drip and wind ambient sounds."""
        try:
            sr = 44100
            # Water drip: short transient followed by resonant ring
            dur = 0.8
            t = np.linspace(0, dur, int(sr * dur), False)
            drip = np.sin(2 * np.pi * 900 * t) * np.exp(-t * 12)
            drip += np.random.normal(0, 0.04, len(t)) * np.exp(-t * 30)
            drip_snd = self._make_sound(drip, drip, volume=0.22)

            # Wind: filtered white noise sweeping
            wind_dur = 3.0
            tw = np.linspace(0, wind_dur, int(sr * wind_dur), False)
            noise = np.random.normal(0, 1, len(tw))
            # Simple moving average (low-pass) for "whoosh"
            from numpy.lib.stride_tricks import sliding_window_view
            window = min(2048, len(noise))
            padded = np.pad(noise, (window//2, window//2), mode='edge')
            wind = np.convolve(padded, np.ones(window)/window, mode='valid')[:len(noise)]
            env_w = np.sin(np.pi * tw / wind_dur)
            wind = wind * env_w * 0.6
            wind_snd = self._make_sound(wind, wind * 0.8, volume=0.18)

            self.sounds['ambient_drip'] = [drip_snd]
            self.sounds['ambient_wind'] = [wind_snd]
        except Exception:
            pass  # Ambient is nice-to-have; silently skip on error

    # ── Playback ─────────────────────────────────────────────────────────
    def play(self, sound_key):
        """Play a random variant of the named sound."""
        variants = self.sounds.get(sound_key)
        if variants:
            random.choice(variants).play()

    def play_footstep(self, current_time):
        """Play a footstep sound if enough time has elapsed."""
        if current_time - self.footstep_timer >= self.footstep_interval:
            if self.footstep_sounds:
                random.choice(self.footstep_sounds).play()
            self.footstep_timer = current_time

    def play_ambient(self, current_time, dungeon_map, player_x, player_y):
        """Occasionally play a synthesized ambient dungeon sound."""
        if current_time - self.ambient_timer < self.ambient_interval:
            return
        self.ambient_timer = current_time
        self.ambient_interval = random.randint(5000, 14000)

        # Choose sound type based on openness around player
        # Count open tiles in a small radius
        open_tiles = sum(
            1 for dy in range(-3, 4) for dx in range(-3, 4)
            if not dungeon_map.is_wall(player_x + dx, player_y + dy)
        )
        key = 'ambient_wind' if open_tiles > 25 else 'ambient_drip'
        self.play(key)
