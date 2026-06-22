import os
os.environ["SDL_RENDER_DRIVER"]="software"
import pygame
import sys
import random
import math
from collections import deque
pygame.init()
pygame.mixer.init()

WIDTH, HEIGHT = 1600, 1200
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Maze Horror Prototype")
pygame.event.set_grab(True)
pygame.mouse.set_visible(False)
pygame.mouse.get_rel()
clock = pygame.time.Clock()

TILE = 10
COLS = 110  # Maze width in tiles
ROWS = 70   # Maze height in tiles
MAZE_OFFSET_X = 260
MAZE_OFFSET_Y = (HEIGHT - ROWS * TILE) // 2
UI_AREA_WIDTH = MAZE_OFFSET_X - 20
VIEW_WIDTH = WIDTH - MAZE_OFFSET_X - 20
VIEW_HEIGHT = HEIGHT - 20
FOV = math.pi / 3
HALF_FOV = FOV / 2
NUM_RAYS = 320
MAX_DEPTH = 30
DIST_COEFF = VIEW_WIDTH / (2 * math.tan(HALF_FOV))
SCALE = VIEW_WIDTH / NUM_RAYS
ROT_SPEED = 0.075
MINIMAP_SMALL_WIDTH = 180
MINIMAP_SMALL_HEIGHT = 140
MINIMAP_EXPANDED_WIDTH = 420
MINIMAP_EXPANDED_HEIGHT = 320
MINIMAP_MARGIN = 20
MINIMAP_BG = (12, 14, 28)
MINIMAP_FLOOR = (25, 25, 35)
MINIMAP_WALL = (70, 70, 90)
MINIMAP_GRID = (30, 34, 48)
MINIMAP_PLAYER = (230, 230, 255)
MINIMAP_MONSTER = (200, 20, 40)
MINIMAP_DISTORT = (180, 80, 80)
MINIMAP_LEVER = (220, 120, 180)
MINIMAP_ARROW = (255, 100, 100)
MINIMAP_HUNT = (255, 80, 80)

WALL = (36, 36, 44)
FLOOR = (25, 90, 20)
PLAYER_COLOR = (200, 20, 20)
MONSTER_COLOR = (180, 0, 90)
DARK_BG = (4, 4, 8)
MAZE_BORDER_BG = (8, 8, 16)
UI_BG =(18, 18, 26)
LEVER_COLOR = (180, 20, 100)
VISION_RANGE = 28  # How far player can see
BLOOD_RED = (180, 20, 40)
MAX_STAMINA = 100
STAMINA_RECOVERY = 0.3
STAMINA_DRAIN = 0.6
WALK_SPEED = 0.16
RUN_SPEED = 0.24
MOUSE_SENSITIVITY = 0.008
LOW_STAMINA_THRESHOLD = 0.25

# Sound system
walk_sound = pygame.mixer.Sound("freesound_community-walking-on-tile-with-shoes-73981.mp3")
run_sound = pygame.mixer.Sound("freesoundsxx-running-on-concrete-268478.mp3")
smile_jumpscare_sounds = [
    pygame.mixer.Sound("freesounds123-jumpscare-v3-335600.mp3")
]
monster_jumpscare_sound = pygame.mixer.Sound("freesound_community-jumpscare-94984.mp3")
horror_chase_sound = pygame.mixer.Sound("freesound_community-horror-chase-34447.mp3")

# Sprite assets
wailer_sheet = pygame.image.load("file_00000000c79c720bb030e9b9af8b66c1.png").convert_alpha()
SMILE_SPRITE_SHEET = pygame.image.load("_storage_emulated_0_Pictures_file_0000000059f8720bbfe651806ba5cf68.png").convert_alpha()

# Crop the right half of the Wailer sheet for monster frames
wailer_half_x = wailer_sheet.get_width() // 2
wailer_frames_source = wailer_sheet.subsurface((wailer_half_x, 0, wailer_sheet.get_width() - wailer_half_x, wailer_sheet.get_height())).copy()
MONSTER_SPRITE_COLS = 6
MONSTER_IDLE_FRAMES = []
frame_w = wailer_frames_source.get_width() // MONSTER_SPRITE_COLS
frame_h = wailer_frames_source.get_height() // 6
for i in range(MONSTER_SPRITE_COLS):
    MONSTER_IDLE_FRAMES.append(wailer_frames_source.subsurface((i * frame_w, 0, frame_w, frame_h)).copy())

# Use the left half of the second image as the Smile entity sprite
smile_half_w = SMILE_SPRITE_SHEET.get_width() // 2
SMILE_SPRITE = SMILE_SPRITE_SHEET.subsurface((0, 0, smile_half_w, SMILE_SPRITE_SHEET.get_height())).copy()
SMILE_SPRITE = pygame.transform.smoothscale(SMILE_SPRITE, (SMILE_SPRITE.get_width() // 3, SMILE_SPRITE.get_height() // 3))

# Ambient background sounds
horror_ambience = pygame.mixer.Sound("thellywellyn-horror-ambience-3-303646.mp3")
small_chimes = pygame.mixer.Sound("freesound_community-small-chimes-22872.mp3")

walk_sound.set_volume(0.22)
run_sound.set_volume(0.25)
for scare in smile_jumpscare_sounds:
    scare.set_volume(0.7)
monster_jumpscare_sound.set_volume(0.75)
horror_chase_sound.set_volume(0.45)

horror_ambience.set_volume(0.6)
small_chimes.set_volume(0.18)

# Audio channels for background loops
ambience_channel = pygame.mixer.Channel(0)
chimes_channel = pygame.mixer.Channel(1)
chase_channel = pygame.mixer.Channel(2)

# Test mode: show-only (no AI, no movement). Set True to freeze everything except animations.
TEST_SHOW_ONLY = False
# Step timing: distance threshold before next step triggers
# Calibrated so audio footsteps sync with player movement speed
STEP_INTERVAL_WALK = 0.35
STEP_INTERVAL_RUN = 0.32

# Threatening phrases for stalk mode
THREATENING_PHRASES = [
    "RUN",
    "You Deserve This",
    "Nowhere To Go",
    "I See You",
    "Not Safe Here",
    "No Escape",
    "Can You Feel Me?",
    "Time's Up",
    "Always Watching",
    "Inevitable",
]

# Create fonts for UI
try:
    title_font = pygame.font.Font(None, 36)
    font = pygame.font.Font(None, 24)
except:
    title_font = pygame.font.Font(None, 36)
    font = pygame.font.Font(None, 24)

# Monster AI phases
PHASE_STALK = 0       # Slowly pursuing
PHASE_SUDDEN = 1      # Brief aggressive burst
PHASE_HUNT = 2        # Full hunt mode

# Initialize grid (exact window size)
grid = [[1 for _ in range(COLS)] for _ in range(ROWS)]

class Monster:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.phase = PHASE_STALK
        self.phase_timer = 0
        self.phase_duration = {
            PHASE_STALK: 300,      # 5 seconds at 60 fps
            PHASE_SUDDEN: 120,     # 2 seconds
            PHASE_HUNT: 240        # 4 seconds
        }
        self.animation_frames = MONSTER_IDLE_FRAMES
        self.animation_index = 0
        self.animation_timer = 0
        self.animation_speed = 8
        self.detection_range = 15  # Tiles
        self.aware_threshold = 8   # Tiles to trigger hunt
        
        # Corner spawn tracking
        self.corner_spawn_timer = 0
        self.corner_spawn_cooldown = 7200  # 2 minutes at 60 fps
        self.original_x = x
        self.original_y = y
        self.at_corner = False
        
        # Patrol system for roaming
        self.patrol_sections = self._generate_patrol_points()
        self.patrol_index = 0
        self.current_patrol_target = self.patrol_sections[0] if self.patrol_sections else (5, 5)
        self.passive_speed = WALK_SPEED * 0.35
        self.stalk_speed = WALK_SPEED * 1.1
        self.hunt_speed = WALK_SPEED * 1.2
        self.patrol_speed = WALK_SPEED * 1.15
    
    def _generate_patrol_points(self):
        """Generate patrol points throughout the map in a grid pattern"""
        patrol_points = []
        # Divide map into 4x4 grid of sections and generate patrol points
        section_w = COLS // 4
        section_h = ROWS // 4
        for row in range(4):
            for col in range(4):
                # Pick a spot in the center of each section
                px = section_w * col + section_w // 2
                py = section_h * row + section_h // 2
                # Clamp to valid maze bounds
                px = max(2, min(COLS - 3, px))
                py = max(2, min(ROWS - 3, py))
                patrol_points.append((px, py))
        return patrol_points
        
    def distance_to_player(self, px, py):
        return math.sqrt((self.x - px)**2 + (self.y - py)**2)
    
    def get_direction_to_player(self, px, py):
        """Returns normalized direction towards player"""
        dx = px - self.x
        dy = py - self.y
        dist = math.sqrt(dx**2 + dy**2)
        if dist == 0:
            return 0, 0
        return dx / dist, dy / dist
    
    def can_move_to(self, x, y):
        """Check if position is walkable using a small collision radius."""
        return check_collision(x, y)

    def get_current_frame(self):
        return self.animation_frames[self.animation_index]

    def animate(self):
        self.animation_timer += 1
        if self.animation_timer >= self.animation_speed:
            self.animation_timer = 0
            self.animation_index = (self.animation_index + 1) % len(self.animation_frames)

    def _find_nearest_walkable(self, point, max_radius=3):
        x0, y0 = point
        best = None
        best_dist = None
        for r in range(max_radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    nx, ny = x0 + dx, y0 + dy
                    if 0 <= nx < COLS and 0 <= ny < ROWS and self.can_move_to(nx + 0.5, ny + 0.5):
                        d = abs(dx) + abs(dy)
                        if best_dist is None or d < best_dist:
                            best_dist = d
                            best = (nx, ny)
            if best is not None:
                break
        return best

    def find_path(self, tx, ty):
        """Find a walkable path on the grid from monster to target."""
        start = (int(self.x), int(self.y))
        target = (int(tx), int(ty))
        if start == target:
            return []

        if not self.can_move_to(start[0] + 0.5, start[1] + 0.5):
            start = self._find_nearest_walkable(start)
            if start is None:
                return []

        if not self.can_move_to(target[0] + 0.5, target[1] + 0.5):
            target = self._find_nearest_walkable(target)
            if target is None:
                return []

        if start == target:
            return []

        queue = deque([start])
        came_from = {start: None}
        while queue:
            x, y = queue.popleft()
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nx, ny = x + dx, y + dy
                if (nx, ny) not in came_from and is_walkable_tile(nx, ny):
                    came_from[(nx, ny)] = (x, y)
                    if (nx, ny) == target:
                        queue.clear()
                        break
                    queue.append((nx, ny))
        if target not in came_from:
            return []

        path = []
        current = target
        while current != start:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path

    def move_along_path(self, tx, ty, speed):
        """Move the monster one step along a grid path toward the target."""
        path = self.find_path(tx, ty)
        if path:
            next_tile = path[0]
            target_x = next_tile[0] + 0.5
            target_y = next_tile[1] + 0.5
            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.sqrt(dx**2 + dy**2)
            if dist < 0.1:
                self.x, self.y = target_x, target_y
                return

            mx = (dx / dist) * min(speed, dist)
            my = (dy / dist) * min(speed, dist)
            moved = False

            if self.can_move_to(self.x + mx, self.y + my):
                self.x += mx
                self.y += my
                moved = True
            else:
                if abs(mx) > abs(my):
                    if self.can_move_to(self.x + mx, self.y):
                        self.x += mx
                        moved = True
                    elif self.can_move_to(self.x, self.y + my):
                        self.y += my
                        moved = True
                else:
                    if self.can_move_to(self.x, self.y + my):
                        self.y += my
                        moved = True
                    elif self.can_move_to(self.x + mx, self.y):
                        self.x += mx
                        moved = True

                if not moved:
                    for nx, ny in [(math.copysign(0.3, dx), 0), (0, math.copysign(0.3, dy)), (math.copysign(0.3, dx), math.copysign(0.3, dy))]:
                        if self.can_move_to(self.x + nx, self.y + ny):
                            self.x += nx
                            self.y += ny
                            moved = True
                            break

            if not moved:
                for dx, dy in [(math.copysign(0.2, dx), 0), (0, math.copysign(0.2, dy)), (math.copysign(0.2, dx), math.copysign(0.2, dy))]:
                    if self.can_move_to(self.x + dx, self.y + dy):
                        self.x += dx
                        self.y += dy
                        moved = True
                        break

            if not moved and not self.can_move_to(self.x, self.y):
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    nx = self.x + dx * 0.3
                    ny = self.y + dy * 0.3
                    if self.can_move_to(nx, ny):
                        self.x = nx
                        self.y = ny
                        break
        else:
            # No path found: attempt a direct move toward target with simple collision avoidance
            dx = tx - self.x
            dy = ty - self.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist == 0:
                return
            mx = (dx / dist) * speed
            my = (dy / dist) * speed
            if self.can_move_to(self.x + mx, self.y + my):
                self.x += mx
                self.y += my
            else:
                # try sliding along walls
                if self.can_move_to(self.x + mx, self.y):
                    self.x += mx
                elif self.can_move_to(self.x, self.y + my):
                    self.y += my
                else:
                    # tiny random nudge to escape tight spots
                    nx = self.x + random.choice([-0.5, 0.5])
                    ny = self.y + random.choice([-0.5, 0.5])
                    if self.can_move_to(nx, ny):
                        self.x = nx
                        self.y = ny

    def patrol(self):
        """Systematically patrol the map section by section"""
        # Check if close enough to current patrol target
        target_x, target_y = self.current_patrol_target
        dist_to_target = math.sqrt((self.x - target_x)**2 + (self.y - target_y)**2)
        
        if dist_to_target < 2.0:
            # Reached patrol point, move to next
            self.patrol_index = (self.patrol_index + 1) % len(self.patrol_sections)
            self.current_patrol_target = self.patrol_sections[self.patrol_index]
        else:
            # Move towards current patrol target
            self.move_along_path(target_x, target_y, self.patrol_speed)

    def update(self, player_x, player_y, lever_active=False, player_speed=WALK_SPEED):
        """Update monster state and behavior"""
        dist = self.distance_to_player(player_x, player_y)
        chase_speed = max(WALK_SPEED + 0.02, player_speed + 0.02)

        if lever_active:
            self.phase = PHASE_HUNT
            self.phase_timer = 0
            current_speed = chase_speed + 0.04
        elif frame_count < 3600:
            # Passive monster during the first minute
            self.phase = PHASE_STALK
            self.phase_timer = 0
            self.corner_spawn_timer = 0
            self.move_along_path(self.current_patrol_target[0], self.current_patrol_target[1], self.passive_speed)
            if math.hypot(self.x - self.current_patrol_target[0], self.y - self.current_patrol_target[1]) < 0.5:
                self.patrol_index = (self.patrol_index + 1) % len(self.patrol_sections)
                self.current_patrol_target = self.patrol_sections[self.patrol_index]
            return
        else:
            self.phase_timer += 1

            # Phase transitions
            if dist < self.aware_threshold:
                # Player too close - trigger hunt
                self.phase = PHASE_HUNT
                self.phase_timer = 0
            elif dist < self.detection_range:
                # Player detected - stalk/sudden
                if self.phase == PHASE_STALK and self.phase_timer > self.phase_duration[PHASE_STALK]:
                    self.phase = PHASE_SUDDEN
                    self.phase_timer = 0
                elif self.phase == PHASE_SUDDEN and self.phase_timer > self.phase_duration[PHASE_SUDDEN]:
                    self.phase = PHASE_STALK
                    self.phase_timer = 0
            else:
                # Player not detected - random walk
                self.phase = PHASE_STALK

            current_speed = chase_speed if self.phase == PHASE_STALK else chase_speed + 0.03

        # Behavior based on phase
        if self.phase == PHASE_STALK:
            if dist < self.detection_range:
                # Track corner spawn cooldown
                self.corner_spawn_timer += 1
                
                # During stalk, teleport to a corner once every 2 minutes
                if self.corner_spawn_timer >= self.corner_spawn_cooldown and not self.at_corner:
                    # Store original position before teleporting
                    self.original_x = self.x
                    self.original_y = self.y
                    
                    # Teleport to corner
                    corners = [(2, 2), (COLS - 3, 2), (2, ROWS - 3), (COLS - 3, ROWS - 3)]
                    corner = random.choice(corners)
                    if not self.can_move_to(corner[0], corner[1]):
                        # Find nearest walkable spot near corner
                        found = False
                        for dx in range(-3, 4):
                            for dy in range(-3, 4):
                                test_x = corner[0] + dx
                                test_y = corner[1] + dy
                                if self.can_move_to(test_x, test_y):
                                    self.x, self.y = float(test_x), float(test_y)
                                    found = True
                                    break
                            if found:
                                break
                    else:
                        self.x, self.y = float(corner[0]), float(corner[1])
                    
                    self.at_corner = True
                    self.corner_spawn_timer = 0
                
                # If player sees the monster at corner, teleport back
                if self.at_corner and dist < 5.0:
                    self.x = self.original_x
                    self.y = self.original_y
                    self.at_corner = False
                    self.corner_spawn_timer = 0
                
                # Resume normal stalking movement if not at corner
                if not self.at_corner:
                    self.move_along_path(player_x, player_y, current_speed)
            else:
                self.patrol()
                self.corner_spawn_timer = 0
                self.at_corner = False
        elif self.phase == PHASE_SUDDEN:
            self.move_along_path(player_x, player_y, current_speed)
        elif self.phase == PHASE_HUNT:
            self.move_along_path(player_x, player_y, current_speed)

    def draw(self, surface):
        """Draw monster with sprite animation based on phase"""
        sprite = self.get_current_frame()
        draw_sprite(surface, self.x + 0.5, self.y + 0.5, MONSTER_COLOR, player_x, player_y, player_angle, 0, sprite=sprite)


SMILE_COLOR = MONSTER_COLOR
SMILE_SPAWN_COOLDOWN = 3600  # 60 seconds between spawns at 60fps
SMILE_ALERT_TEXTS = [
    "Smile.",
    "LOOK.",
    "I'M RIGHT THERE.",
    "CAN YOU SEE ME?",
    "DON'T BLINK.",
    "HERE.",
    "RIGHT HERE.",
    "WIDE EYES.",
]

class SmileStalker:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.active = False
        self.alert_ready = False
        self.sound_played = False
        self.label = "Smile"
        self.spawn_cooldown = SMILE_SPAWN_COOLDOWN
        self.cooldown = self.spawn_cooldown

    def spawn(self, player_x, player_y, player_angle):
        directions = [0, 0.15, -0.15, 0.4, -0.4, 0.7, -0.7, 1.0, -1.0]
        for dist in range(3, 8):
            for offset in directions:
                angle = player_angle + offset
                tx = player_x + math.cos(angle) * dist
                ty = player_y + math.sin(angle) * dist
                ix, iy = int(tx), int(ty)
                if is_walkable_tile(ix, iy):
                    obj_x = ix + 0.5
                    obj_y = iy + 0.5
                    if not is_directly_visible(obj_x, obj_y, player_x, player_y, player_angle):
                        self.x = obj_x
                        self.y = obj_y
                        self.active = True
                        self.will_vanish = False
                        self.cooldown = self.spawn_cooldown
                        return
        self.active = False
        self.cooldown = self.spawn_cooldown

    def update(self, player_x, player_y, player_angle):
        if self.active:
            if is_directly_visible(self.x, self.y, player_x, player_y, player_angle):
                if not self.sound_played:
                    self.alert_ready = True
                    self.sound_played = True
                return
            return
        if self.cooldown > 0:
            self.cooldown -= 1
            return
        self.spawn(player_x, player_y, player_angle)

    def draw(self, surface, player_x, player_y, player_angle):
        # In normal mode, only draw if active. In TEST_SHOW_ONLY, always draw.
        if not self.active and not TEST_SHOW_ONLY:
          return

        if TEST_SHOW_ONLY:
            visible = True
        else:
            visible = is_directly_visible(self.x, self.y, player_x, player_y, player_angle)

        draw_sprite(surface, self.x, self.y, SMILE_COLOR, player_x, player_y, player_angle, 0, sprite=SMILE_SPRITE)
        if visible:
            label_surf = font.render(self.label, True, (255, 255, 255))
            label_rect = label_surf.get_rect(center=(VIEW_WIDTH // 2, VIEW_HEIGHT // 2 + 20))
            surface.blit(label_surf, label_rect)
            if self.alert_ready and not TEST_SHOW_ONLY:
                global smile_alert_text, smile_alert_timer, last_smile_jumpscare_sound
                smile_alert_text = random.choice(SMILE_ALERT_TEXTS)
                smile_alert_timer = 30
                last_smile_jumpscare_sound = random.choice(smile_jumpscare_sounds)
                last_smile_jumpscare_sound.play()
                self.alert_ready = False
            if not TEST_SHOW_ONLY:
                self.active = False
                self.sound_played = False
                self.cooldown = self.spawn_cooldown


def carve_maze():
    """Generate maze using proper recursive backtracking"""
    x, y = 1, 1
    grid[y][x] = 0
    stack = [(x, y)]
    while stack:
        x, y = stack[-1]
        neighbors = []
        for dx, dy in [(2, 0), (-2, 0), (0, 2), (0, -2)]:
            nx, ny = x + dx, y + dy
            if 1 <= nx < COLS - 1 and 1 <= ny < ROWS - 1:
                if grid[ny][nx] == 1:
                    neighbors.append((nx, ny, dx, dy))
        if neighbors:
            nx, ny, dx, dy = random.choice(neighbors)
            grid[y + dy // 2][x + dx // 2] = 0  # Carve passage between cells
            grid[ny][nx] = 0  # Carve destination cell
            stack.append((nx, ny))
        else:
            stack.pop()


def flood_fill_floor(start_x, start_y):
    """Return all connected floor tiles reachable from a start point."""
    start_x = int(round(start_x))
    start_y = int(round(start_y))
    if not (0 <= start_x < COLS and 0 <= start_y < ROWS) or grid[start_y][start_x] != 0:
        return set()

    visited = {(start_x, start_y)}
    stack = [(start_x, start_y)]

    while stack:
        x, y = stack.pop()
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < COLS and 0 <= ny < ROWS and grid[ny][nx] == 0 and (nx, ny) not in visited:
                visited.add((nx, ny))
                stack.append((nx, ny))

    return visited


def connect_isolated_floor(main_points):
    """Connect any isolated floor regions to the main reachable floor."""
    all_floor = [(x, y) for y in range(ROWS) for x in range(COLS) if grid[y][x] == 0]
    main_set = set(main_points)
    isolated = [(x, y) for x, y in all_floor if (x, y) not in main_set]

    while isolated:
        # Find nearest isolated floor tile to the main component
        best_pair = None
        best_dist = None
        for ix, iy in isolated:
            for mx, my in main_set:
                dist = abs(ix - mx) + abs(iy - my)
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_pair = (mx, my, ix, iy)
        if best_pair is None:
            break

        mx, my, ix, iy = best_pair
        # Carve a straight tunnel between main and isolated floor components
        x, y = mx, my
        while x != ix:
            x += 1 if ix > x else -1
            if 0 < x < COLS - 1 and 0 < y < ROWS - 1:
                grid[y][x] = 0
        while y != iy:
            y += 1 if iy > y else -1
            if 0 < x < COLS - 1 and 0 < y < ROWS - 1:
                grid[y][x] = 0

        main_set = flood_fill_floor(mx, my)
        isolated = [(x, y) for x, y in all_floor if (x, y) not in main_set]


def enforce_border():
    """Keep the outer maze border solid so all passages remain inside the screen."""
    for x in range(COLS):
        grid[0][x] = 1
        grid[ROWS - 1][x] = 1
    for y in range(ROWS):
        grid[y][0] = 1
        grid[y][COLS - 1] = 1


def check_collision(x, y):
    """Check if position is walkable (floor, not wall) and within bounds."""
    radius = 0.25
    for ox in (-radius, radius):
        for oy in (-radius, radius):
            ix = int(x + ox)
            iy = int(y + oy)
            if not (0 <= iy < ROWS and 0 <= ix < COLS):
                return False
            if grid[iy][ix] == 1:
                return False
    return True


def is_walkable_tile(x, y):
    return 0 <= x < COLS and 0 <= y < ROWS and grid[y][x] == 0 and check_collision(x + 0.5, y + 0.5)


def is_directly_visible(obj_x, obj_y, player_x, player_y, player_angle):
    dx = obj_x - player_x
    dy = obj_y - player_y
    dist = math.hypot(dx, dy)
    if dist > VISION_RANGE:
        return False
    angle = math.atan2(dy, dx)
    delta = (angle - player_angle + math.pi) % (2 * math.pi) - math.pi
    if abs(delta) > HALF_FOV:
        return False
    cur_dist = 0.0
    step = 0.1
    while cur_dist < dist:
        cur_dist += step
        tx = player_x + math.cos(angle) * cur_dist
        ty = player_y + math.sin(angle) * cur_dist
        if not (0 <= int(tx) < COLS and 0 <= int(ty) < ROWS):
            return False
        if grid[int(ty)][int(tx)] == 1:
            return False
    return True


def count_walkable_neighbors(x, y):
    return sum(
        1
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if is_walkable_tile(x + dx, y + dy)
    )


def ray_cast(px, py, angle):
    """Cast a ray and return the distance to the first wall."""
    sin_a = math.sin(angle)
    cos_a = math.cos(angle)
    depth = 0.0
    while depth < MAX_DEPTH:
        depth += 0.05
        x = px + cos_a * depth
        y = py + sin_a * depth
        if not (0 <= int(x) < COLS and 0 <= int(y) < ROWS):
            return depth
        if grid[int(y)][int(x)] == 1:
            return depth
    return MAX_DEPTH


def draw_sprite(surface, obj_x, obj_y, color, px, py, pa, offset_x=0, sprite=None):
    dx = obj_x - px
    dy = obj_y - py
    dist = math.hypot(dx, dy)
    if dist < 0.5:
        return
    angle = math.atan2(dy, dx)
    delta = angle - pa
    delta = (delta + math.pi) % (2 * math.pi) - math.pi
    if abs(delta) > HALF_FOV:
        return
    step = 0.1
    cur_dist = 0.0
    while cur_dist < dist:
        cur_dist += step
        tx = px + math.cos(angle) * cur_dist
        ty = py + math.sin(angle) * cur_dist
        if not (0 <= int(tx) < COLS and 0 <= int(ty) < ROWS):
            return
        if grid[int(ty)][int(tx)] == 1:
            return
    screen_x = offset_x + int((delta / HALF_FOV) * (VIEW_WIDTH / 2) + VIEW_WIDTH / 2)
    height = min(VIEW_HEIGHT, int(DIST_COEFF / (dist if dist > 0.1 else 0.1)))
    if sprite is not None:
        aspect = sprite.get_width() / sprite.get_height()
        width = max(8, int(height * aspect))
        sprite_scaled = pygame.transform.smoothscale(sprite, (width, height))
        surface.blit(sprite_scaled, (screen_x - width // 2, 10 + VIEW_HEIGHT // 2 - height // 2))
        return
    width = max(8, int(height * 0.5))
    pygame.draw.rect(surface, color, (screen_x - width // 2, 10 + VIEW_HEIGHT // 2 - height // 2, width, height))


def show_intro():
    """Display an intro/title screen and wait for the player to start."""
    intro_clock = pygame.time.Clock()
    splash_alpha = 255
    intro_minimap_visible = False
    while True:
        intro_clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    intro_minimap_visible = not intro_minimap_visible
                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    return
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

        screen.fill(DARK_BG)
        title = title_font.render("Escape.", True, (240, 240, 240))
        subtitle = font.render("Press ENTER or SPACE to begin", True, (200, 200, 200))
        controls = font.render("WASD: Move    SHIFT: Sprint    E: Interact    TAB: Toggle Minimap    ESC: Quit", True, (190, 190, 190))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 80))
        screen.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, HEIGHT // 2 - 20))
        screen.blit(controls, (WIDTH // 2 - controls.get_width() // 2, HEIGHT // 2 + 20))

        # small pulsing effect for subtitle
        pulse = 128 + int(127 * math.sin(pygame.time.get_ticks() * 0.008))
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 0))
        screen.blit(overlay, (0, 0))
        # Draw minimap while TAB is held on the intro
        if intro_minimap_visible:
            minimap_width = MINIMAP_EXPANDED_WIDTH
            minimap_height = MINIMAP_EXPANDED_HEIGHT
            minimap_x = (WIDTH - minimap_width) // 2
            minimap_y = (HEIGHT - minimap_height) // 2
            minimap_rect = pygame.Rect(minimap_x, minimap_y, minimap_width, minimap_height)
            pygame.draw.rect(screen, MINIMAP_BG, minimap_rect)
            pygame.draw.rect(screen, WALL, minimap_rect, 2)
            tile_w = minimap_width / COLS
            tile_h = minimap_height / ROWS
            for my in range(ROWS):
                for mx in range(COLS):
                    color = MINIMAP_FLOOR if grid[my][mx] == 0 else MINIMAP_WALL
                    pygame.draw.rect(screen, color, (minimap_x + mx * tile_w, minimap_y + my * tile_h, tile_w + 1, tile_h + 1))
            px_screen = minimap_x + player_x * tile_w
            py_screen = minimap_y + player_y * tile_h
            mx_screen = minimap_x + monster.x * tile_w
            my_screen = minimap_y + monster.y * tile_h
            lx_screen = minimap_x + lever_x * tile_w
            ly_screen = minimap_y + lever_y * tile_h
            pygame.draw.rect(screen, MINIMAP_LEVER, (int(lx_screen) - 4, int(ly_screen) - 4, 8, 8))
            pygame.draw.circle(screen, MINIMAP_PLAYER, (int(px_screen), int(py_screen)), 4)
            pygame.draw.rect(screen, MINIMAP_MONSTER, (int(mx_screen) - 4, int(my_screen) - 4, 8, 8))
            arrow_dx = lx_screen - px_screen
            arrow_dy = ly_screen - py_screen
            length = math.hypot(arrow_dx, arrow_dy)
            if length > 1:
                arrow_dx *= 24 / length
                arrow_dy *= 24 / length
                pygame.draw.line(screen, MINIMAP_ARROW, (int(px_screen), int(py_screen)), (int(px_screen + arrow_dx), int(py_screen + arrow_dy)), 2)
        pygame.display.flip()

carve_maze()
main_floor = flood_fill_floor(1, 1)
if main_floor:
    connect_isolated_floor(main_floor)

# Reset the gameplay state when returning to the intro or starting a new run.
def reset_game_state():
    global player_spawn_x, player_spawn_y, player_x, player_y, player_angle, speed, stamina
    global step_distance, current_step_interval, last_player_x, last_player_y, last_smile_jumpscare_sound
    global monster_spawn_x, monster_spawn_y, monster, smile_stalker, frame_count, smile_alert_text, smile_alert_timer
    global is_running, lever_active, minimap_visible, lever_x, lever_y, running
    global exit_x, exit_y, exit_active, win_active, win_timer
    global threat_text, threat_timer, threat_x, threat_y, phase_change_text, phase_change_timer
    global previous_phase, jumpscare_active, jumpscare_timer, jumpscare_sound_played, minimap_zoom

    player_spawn_x, player_spawn_y = find_spawn_point(20, 20, min_open_neighbors=2)
    player_x, player_y = player_spawn_x + 0.5, player_spawn_y + 0.5
    player_angle = 0.0
    speed = WALK_SPEED
    stamina = MAX_STAMINA

    step_distance = 0.0
    current_step_interval = STEP_INTERVAL_WALK
    last_player_x, last_player_y = player_x, player_y
    last_smile_jumpscare_sound = None

    monster_spawn_x, monster_spawn_y = find_spawn_point(COLS - 20, ROWS - 20, min_open_neighbors=2)
    monster = Monster(monster_spawn_x + 0.5, monster_spawn_y + 0.5)
    smile_stalker = SmileStalker()
    frame_count = 0
    smile_alert_text = ""
    smile_alert_timer = 0
    is_running = False
    lever_active = False
    minimap_visible = False
    minimap_zoom = 1.0
    lever_x, lever_y = find_spawn_point(COLS // 2, ROWS // 2)
    running = True

    exit_x = None
    exit_y = None
    exit_active = False
    win_active = False
    win_timer = 0

    threat_text = None
    threat_timer = 0
    threat_x = 0
    threat_y = 0
    phase_change_text = None
    phase_change_timer = 0
    previous_phase = None

    jumpscare_active = False
    jumpscare_timer = 0
    jumpscare_sound_played = False

    if ambience_channel.get_busy():
        ambience_channel.stop()
    if chimes_channel.get_busy():
        chimes_channel.stop()
    if chase_channel.get_busy():
        chase_channel.stop()

# Find valid spawn points with guaranteed visibility
def find_spawn_point(target_x, target_y, min_open_neighbors=2, max_search_radius=50):
    """Find a safe walkable spawn point near the target, preferring open tiles."""
    target_x = max(1, min(COLS - 2, target_x))
    target_y = max(1, min(ROWS - 2, target_y))

    candidates = []
    for y in range(max(1, target_y - max_search_radius), min(ROWS - 1, target_y + max_search_radius + 1)):
        for x in range(max(1, target_x - max_search_radius), min(COLS - 1, target_x + max_search_radius + 1)):
            if grid[y][x] == 0:
                neighbors = count_walkable_neighbors(x, y)
                dist = abs(x - target_x) + abs(y - target_y)
                candidates.append((neighbors, dist, x, y))

    if candidates:
        # Prefer tiles with enough adjacent open space to avoid dead-ends
        candidates.sort(key=lambda c: (0 if c[0] >= min_open_neighbors else 1, c[1], -c[0]))
        return float(candidates[0][2]), float(candidates[0][3])

    for y in range(ROWS):
        for x in range(COLS):
            if grid[y][x] == 0:
                return float(x), float(y)

    return float(target_x), float(target_y)

# Player state with valid spawn point (ensure in bounds and visible)
player_spawn_x, player_spawn_y = find_spawn_point(20, 20, min_open_neighbors=2)
player_x, player_y = player_spawn_x + 0.5, player_spawn_y + 0.5
player_angle = 0.0
speed = WALK_SPEED
stamina = MAX_STAMINA

# Sound/step tracking for footstep audio sync
step_distance = 0.0
current_step_interval = STEP_INTERVAL_WALK
last_player_x, last_player_y = player_x, player_y
last_smile_jumpscare_sound = None  # Keep reference to prevent garbage collection

# Initialize monster with valid spawn point (far corner)
monster_spawn_x, monster_spawn_y = find_spawn_point(COLS - 20, ROWS - 20, min_open_neighbors=2)
monster = Monster(monster_spawn_x + 0.5, monster_spawn_y + 0.5)
smile_stalker = SmileStalker()
frame_count = 0
smile_alert_text = ""
smile_alert_timer = 0
is_running = False
lever_active = False
minimap_visible = False
minimap_zoom = 1.0  # Zoom level for minimap (1.0 = normal, 2.0 = 2x zoom, etc.)
lever_x, lever_y = find_spawn_point(COLS // 2, ROWS // 2)
running = True

# Exit / win state
exit_x = None
exit_y = None
exit_active = False
win_active = False
win_timer = 0

# Threat text display
threat_text = None
threat_timer = 0
threat_x = 0
threat_y = 0

# Phase change display
phase_change_text = None
phase_change_timer = 0
previous_phase = None

# Jumpscare effect
jumpscare_active = False
jumpscare_timer = 0
jumpscare_sound_played = False

print(f"Maze: {COLS}x{ROWS} tiles (fits {WIDTH}x{HEIGHT} window exactly)")
print(f"Player spawned at: ({player_x:.1f}, {player_y:.1f})")
print(f"Monster spawned at: ({monster.x:.1f}, {monster.y:.1f})")

# Initialize gameplay state, show intro, then start background ambient sounds.
reset_game_state()
show_intro()
ambience_channel.play(horror_ambience, loops=-1)
chimes_channel.play(small_chimes, loops=-1)

while running:
    clock.tick(60)
    
    # Handle events
    mouse_dx = 0
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                minimap_visible = not minimap_visible
            elif event.key == pygame.K_r and (jumpscare_active or jumpscare_timer > 0):
                reset_game_state()
                show_intro()
                ambience_channel.play(horror_ambience, loops=-1)
                chimes_channel.play(small_chimes, loops=-1)
            elif event.key == pygame.K_EQUALS or event.key == pygame.K_RIGHTBRACKET:
                minimap_zoom = min(4.0, minimap_zoom + 0.2)
            elif event.key == pygame.K_MINUS or event.key == pygame.K_LEFTBRACKET:
                minimap_zoom = max(0.5, minimap_zoom - 0.2)
            elif event.key == pygame.K_ESCAPE:
                running = False
        elif event.type == pygame.MOUSEMOTION:
            mouse_dx += event.rel[0]

    if mouse_dx != 0:
        mouse_dx = max(-20, min(20, mouse_dx))
    
    # Get pressed keys and update player position
    keys = pygame.key.get_pressed()
    forward = 0.0
    side = 0.0
    is_running = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and stamina > 0
    player_speed = RUN_SPEED if is_running else WALK_SPEED

    if minimap_visible and (keys[pygame.K_w] or keys[pygame.K_s] or keys[pygame.K_a] or keys[pygame.K_d]):
        minimap_visible = False

    if keys[pygame.K_w]:
        forward += player_speed
    if keys[pygame.K_s]:
        forward -= player_speed
    if keys[pygame.K_a]:
        side -= player_speed
    if keys[pygame.K_d]:
        side += player_speed
    if keys[pygame.K_LEFT]:
        player_angle -= ROT_SPEED
    if keys[pygame.K_RIGHT]:
        player_angle += ROT_SPEED
    if keys[pygame.K_q]:
        player_angle -= ROT_SPEED
    if keys[pygame.K_e]:
        player_angle += ROT_SPEED

    player_angle += mouse_dx * MOUSE_SENSITIVITY
    player_angle %= (2 * math.pi)

    dx = math.cos(player_angle) * forward + math.cos(player_angle + math.pi / 2) * side
    dy = math.sin(player_angle) * forward + math.sin(player_angle + math.pi / 2) * side

    new_x = player_x + dx
    new_y = player_y
    if check_collision(new_x, new_y):
        player_x = new_x

    new_y = player_y + dy
    if check_collision(player_x, new_y):
        player_y = new_y

    # Stamina handling
    if is_running and (new_x != player_x or new_y != player_y):
        stamina = max(0, stamina - STAMINA_DRAIN)
    else:
        stamina = min(MAX_STAMINA, stamina + STAMINA_RECOVERY)
    
    # Step sound tracking - sync footsteps with movement speed
    player_moved_dist = math.hypot(player_x - last_player_x, player_y - last_player_y)
    step_distance += player_moved_dist
    current_step_interval = STEP_INTERVAL_RUN if is_running else STEP_INTERVAL_WALK
    
    if step_distance >= current_step_interval and player_moved_dist > 0.001:
        step_distance = 0.0
        if is_running:
            run_sound.play()
        else:
            walk_sound.play()
    
    last_player_x, last_player_y = player_x, player_y
    
    # Lever interaction
    lever_prompt = False
    if abs(player_x - lever_x) + abs(player_y - lever_y) <= 1.5:
        lever_prompt = True
        if keys[pygame.K_e]:
            lever_active = True

    # Create exit when lever is pulled
    if lever_active and not exit_active:
        # Find a perimeter wall tile adjacent to an accessible floor and carve it into an exit
        created = False
        # check top/bottom rows then left/right columns near center
        candidates = []
        for x in range(1, COLS - 1):
            candidates.append((x, 1))
            candidates.append((x, ROWS - 2))
        for y in range(1, ROWS - 1):
            candidates.append((1, y))
            candidates.append((COLS - 2, y))

        random.shuffle(candidates)
        for cx, cy in candidates:
            if grid[cy][cx] == 1:
                # check if adjacent inwards tile is floor and reachable
                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    ax, ay = cx + dx, cy + dy
                    if 0 <= ax < COLS and 0 <= ay < ROWS and grid[ay][ax] == 0:
                        # carve the wall to create an exit
                        grid[cy][cx] = 0
                        exit_x, exit_y = float(cx), float(cy)
                        exit_active = True
                        created = True
                        break
            if created:
                break
    
    # Update the hidden stalker and monster AI (or freeze in TEST_SHOW_ONLY)
    if not TEST_SHOW_ONLY:
        smile_stalker.update(player_x, player_y, player_angle)
        monster.update(player_x, player_y, lever_active, player_speed)

        monster_player_dist = math.hypot(monster.x - player_x, monster.y - player_y)
        if monster_player_dist <= monster.detection_range:
            if not chase_channel.get_busy():
                chase_channel.play(horror_chase_sound, loops=-1)
            chase_volume = 0.1 + 0.7 * max(0.0, 1.0 - monster_player_dist / monster.detection_range)
            chase_channel.set_volume(min(1.0, chase_volume))
        else:
            if chase_channel.get_busy():
                chase_channel.fadeout(500)
    else:
        # Show-only mode: mute ambience and prevent movement, but run animations
        ambience_channel.set_volume(0.0)
        chimes_channel.set_volume(0.0)
        chase_channel.stop()
        # Keep monster at its spawn and advance its animation
        monster.x = monster_spawn_x + 0.5
        monster.y = monster_spawn_y + 0.5
        monster.phase = PHASE_STALK
        monster.animate()
        # Ensure Smile is active and positioned in front of the player
        smile_stalker.active = True
        smile_stalker.x = player_x + 3.0
        smile_stalker.y = player_y
    
    # Detect phase change and display appropriate message
    if previous_phase != monster.phase:
        previous_phase = monster.phase
        if monster.phase == PHASE_STALK:
            phase_change_text = "He's Watching..."
            phase_change_timer = 120
        elif monster.phase == PHASE_SUDDEN:
            phase_change_text = "HE'S COMING"
            phase_change_timer = 120
        elif monster.phase == PHASE_HUNT:
            phase_change_text = "RUN."
            phase_change_timer = 120
    
    phase_change_timer -= 1
    
    frame_count += 1
    # Check for jumpscare collision
    if monster_player_dist < 1.2:  # Very close collision
        if not jumpscare_active:
            jumpscare_active = True
            jumpscare_sound_played = False
        if not jumpscare_sound_played:
            monster_jumpscare_sound.play()
            jumpscare_sound_played = True
        jumpscare_timer = 60  # Display for 1 second at 60fps
    
    jumpscare_timer = max(0, jumpscare_timer - 1)
    if jumpscare_timer == 0:
        jumpscare_active = False
    
    # Handle threat text during stalk mode
    in_stalk_threat = monster.phase == PHASE_STALK and math.hypot(monster.x - player_x, monster.y - player_y) <= monster.detection_range
    threat_timer -= 1
    if threat_timer <= 0:
        if in_stalk_threat and random.random() < 0.015:  # ~1.5% chance per frame during active stalk
            threat_text = random.choice(THREATENING_PHRASES)
            threat_x = random.randint(MAZE_OFFSET_X + 50, MAZE_OFFSET_X + VIEW_WIDTH - 50)
            threat_y = random.randint(30, VIEW_HEIGHT - 30)
            threat_timer = random.randint(30, 90)  # Display for 0.5-1.5 seconds
    
    # Draw everything with dark ambience
    screen.fill(DARK_BG)
    
    # Draw side UI panel
    ui_rect = pygame.Rect(10, 10, UI_AREA_WIDTH, HEIGHT - 20)
    pygame.draw.rect(screen, UI_BG, ui_rect)
    pygame.draw.rect(screen, WALL, ui_rect, 2)

    small_font = pygame.font.Font(None, 20)
    ui_title = title_font.render("OBJECTIVES", True, (220, 220, 220))
    screen.blit(ui_title, (20, 18))

    current_tasks = [
        "Find and pull the lever",
        "Stay out of the hunter's path",
        "Hold SHIFT to sprint",
        "Press E near the lever",
    ]
    for i, line in enumerate(current_tasks):
        task_surf = small_font.render(line, True, (190, 190, 190))
        screen.blit(task_surf, (20, 62 + i * 22))

    control_title = title_font.render("CONTROLS", True, (220, 220, 220))
    screen.blit(control_title, (20, 165))
    control_lines = [
        "W: Move forward",
        "S: Move backward",
        "A: Strafe left",
        "D: Strafe right",
        "Left/Right Arrows: Turn",
        "Q / E: Turn left / right",
        "SHIFT: Run",
        "TAB: Toggle minimap",
        "+/-: Zoom minimap",
        "R: Back to intro",
        "F: Interact / activate",
        "ESC: Quit",
    ]
    for i, line in enumerate(control_lines):
        control_surf = small_font.render(line, True, (190, 190, 190))
        screen.blit(control_surf, (20, 202 + i * 20))

    status_title = title_font.render("STATUS", True, (220, 220, 220))
    screen.blit(status_title, (20, 345))
    lever_state = "PULLED" if lever_active else "NOT PULLED"
    minutes = frame_count // 60
    seconds = frame_count % 60
    time_text = f"Time: {minutes}:{seconds:02d}"
    status_lines = [
        f"Lever: {lever_state}",
        f"Stamina: {int(stamina)}",
        f"Hunter: {'HUNT' if monster.phase == PHASE_HUNT else 'STALK'}",
    ]
    for i, line in enumerate(status_lines):
        status_surf = small_font.render(line, True, (220, 180, 160))
        screen.blit(status_surf, (20, 382 + i * 20))
    time_color = (255, 40, 40) if monster.phase == PHASE_HUNT else (220, 180, 160)
    if monster.phase == PHASE_HUNT and frame_count % 30 < 15:
        time_color = (255, 220, 220)
    time_surf = small_font.render(time_text, True, time_color)
    screen.blit(time_surf, (20, 382 + len(status_lines) * 20))

    # Draw first-person 3D view into a separate surface for low-stamina effects
    view_surface = pygame.Surface((VIEW_WIDTH, VIEW_HEIGHT))
    view_surface.fill(MAZE_BORDER_BG)

    sky_color = (10, 16, 40)
    floor_color = (16, 16, 16)
    pygame.draw.rect(view_surface, sky_color, (0, 0, VIEW_WIDTH, VIEW_HEIGHT // 2))
    pygame.draw.rect(view_surface, floor_color, (0, VIEW_HEIGHT // 2, VIEW_WIDTH, VIEW_HEIGHT // 2))

    for ray in range(NUM_RAYS):
        ray_angle = player_angle - HALF_FOV + ray * (FOV / NUM_RAYS)
        distance = ray_cast(player_x, player_y, ray_angle)
        correction = math.cos(player_angle - ray_angle)
        distance *= correction
        if distance <= 0:
            distance = 0.0001
        line_height = min(VIEW_HEIGHT, int(DIST_COEFF / distance))
        shade = max(12, min(180, int(220 / (1 + distance * distance * 0.02))))
        wall_color = (int(shade * 0.4), int(shade * 0.2), int(shade * 0.25))
        x = int(ray * SCALE)
        pygame.draw.rect(view_surface, wall_color, (x, VIEW_HEIGHT // 2 - line_height // 2, int(SCALE) + 1, line_height))

    # Small weapon/hands model
    gun_w = 60
    gun_h = 14
    gun_x = VIEW_WIDTH // 2 - gun_w // 2
    gun_y = VIEW_HEIGHT - gun_h - 20
    pygame.draw.rect(view_surface, (40, 40, 40), (gun_x, gun_y, gun_w, gun_h), border_radius=6)
    pygame.draw.rect(view_surface, (100, 100, 120), (gun_x + gun_w // 2 - 6, gun_y - 10, 12, 10), border_radius=4)

    draw_sprite(view_surface, lever_x + 0.5, lever_y + 0.5, LEVER_COLOR, player_x, player_y, player_angle, 0)
    smile_stalker.draw(view_surface, player_x, player_y, player_angle)
    draw_sprite(view_surface, monster.x + 0.5, monster.y + 0.5, (255, 0, 0), player_x, player_y, player_angle, 0, sprite=monster.get_current_frame())
    if exit_active and exit_x is not None:
        draw_sprite(view_surface, exit_x + 0.5, exit_y + 0.5, (255, 255, 255), player_x, player_y, player_angle, 0)

    if smile_alert_timer > 0:
        if frame_count % 2 == 0:
            smile_alert_text = random.choice(SMILE_ALERT_TEXTS)
        alert_surf = font.render(smile_alert_text, True, (255, 220, 220))
        alert_x = VIEW_WIDTH // 2 - alert_surf.get_width() // 2 + random.randint(-8, 8)
        alert_y = VIEW_HEIGHT // 2 - alert_surf.get_height() // 2 + random.randint(-8, 8)
        view_surface.blit(alert_surf, (alert_x, alert_y))
        smile_alert_timer -= 1

    if stamina < MAX_STAMINA * LOW_STAMINA_THRESHOLD:
        blur_amount = 3
        small = pygame.transform.smoothscale(view_surface, (VIEW_WIDTH // blur_amount, VIEW_HEIGHT // blur_amount))
        view_surface = pygame.transform.smoothscale(small, (VIEW_WIDTH, VIEW_HEIGHT))
        overlay = pygame.Surface((VIEW_WIDTH, VIEW_HEIGHT), pygame.SRCALPHA)
        overlay_alpha = int(80 + 120 * (1.0 - stamina / (MAX_STAMINA * LOW_STAMINA_THRESHOLD)))
        overlay.fill((30, 30, 30, overlay_alpha))
        view_surface.blit(overlay, (0, 0))

    screen.blit(view_surface, (MAZE_OFFSET_X, 10))
    pygame.draw.rect(screen, WALL, pygame.Rect(MAZE_OFFSET_X, 10, VIEW_WIDTH, VIEW_HEIGHT), 4)

    if minimap_visible:
        # Draw centered minimap overlay with zoom
        minimap_width = int(MINIMAP_EXPANDED_WIDTH * minimap_zoom)
        minimap_height = int(MINIMAP_EXPANDED_HEIGHT * minimap_zoom)
        minimap_x = (WIDTH - minimap_width) // 2
        minimap_y = (HEIGHT - minimap_height) // 2
        minimap_rect = pygame.Rect(minimap_x, minimap_y, minimap_width, minimap_height)
        pygame.draw.rect(screen, MINIMAP_BG, minimap_rect)
        pygame.draw.rect(screen, WALL, minimap_rect, 2)
        tile_w = minimap_width / COLS
        tile_h = minimap_height / ROWS
        for my in range(ROWS):
            for mx in range(COLS):
                color = MINIMAP_FLOOR if grid[my][mx] == 0 else MINIMAP_WALL
                pygame.draw.rect(screen, color, (minimap_x + mx * tile_w, minimap_y + my * tile_h, tile_w + 1, tile_h + 1))
        for gx in range(0, COLS, 10):
            pygame.draw.line(screen, MINIMAP_GRID, (minimap_x + gx * tile_w, minimap_y), (minimap_x + gx * tile_w, minimap_y + minimap_height))
        for gy in range(0, ROWS, 10):
            pygame.draw.line(screen, MINIMAP_GRID, (minimap_x, minimap_y + gy * tile_h), (minimap_x + minimap_width, minimap_y + gy * tile_h))
        px_screen = minimap_x + player_x * tile_w
        py_screen = minimap_y + player_y * tile_h
        mx_screen = minimap_x + monster.x * tile_w
        my_screen = minimap_y + monster.y * tile_h
        lx_screen = minimap_x + lever_x * tile_w
        ly_screen = minimap_y + lever_y * tile_h
        ex_screen = None
        ey_screen = None
        pygame.draw.rect(screen, MINIMAP_LEVER, (int(lx_screen) - 4, int(ly_screen) - 4, 8, 8))

        hide_monster = monster.phase == PHASE_HUNT
        roaming = monster.phase == PHASE_STALK and math.hypot(monster.x - player_x, monster.y - player_y) > monster.detection_range
        if hide_monster:
            overlay = pygame.Surface((VIEW_WIDTH, VIEW_HEIGHT), pygame.SRCALPHA)
            overlay.fill((180, 0, 0, 90))
            screen.blit(overlay, (MAZE_OFFSET_X, 10))
            pygame.draw.rect(screen, MINIMAP_MONSTER, (int(mx_screen) - 4, int(my_screen) - 4, 8, 8))
        elif roaming:
            pygame.draw.rect(screen, MINIMAP_MONSTER, (int(mx_screen) - 4, int(my_screen) - 4, 8, 8))
        else:
            offset = 4
            distorted_x = mx_screen + math.sin(pygame.time.get_ticks() * 0.008) * offset * tile_w
            distorted_y = my_screen + math.cos(pygame.time.get_ticks() * 0.008) * offset * tile_h
            pygame.draw.rect(screen, MINIMAP_DISTORT, (int(distorted_x) - 4, int(distorted_y) - 4, 8, 8))

        pygame.draw.circle(screen, MINIMAP_PLAYER, (int(px_screen), int(py_screen)), 4)
        heading_x = px_screen + math.cos(player_angle) * 18
        heading_y = py_screen + math.sin(player_angle) * 18
        pygame.draw.line(screen, MINIMAP_PLAYER, (int(px_screen), int(py_screen)), (int(heading_x), int(heading_y)), 2)
        arrow_dx = lx_screen - px_screen
        arrow_dy = ly_screen - py_screen
        length = math.hypot(arrow_dx, arrow_dy)
        if length > 1:
            arrow_dx *= 24 / length
            arrow_dy *= 24 / length
            pygame.draw.line(screen, MINIMAP_ARROW, (int(px_screen), int(py_screen)), (int(px_screen + arrow_dx), int(py_screen + arrow_dy)), 2)
        compass = font.render("N", True, (220, 220, 220))
        screen.blit(compass, (minimap_x + minimap_width - 24, minimap_y + 6))
        e_text = font.render("E", True, (220, 220, 220))
        screen.blit(e_text, (minimap_x + minimap_width - 12, minimap_y + minimap_height // 2 - 8))
        s_text = font.render("S", True, (220, 220, 220))
        screen.blit(s_text, (minimap_x + minimap_width // 2 - 4, minimap_y + minimap_height - 22))
        w_text = font.render("W", True, (220, 220, 220))
        screen.blit(w_text, (minimap_x + 4, minimap_y + minimap_height // 2 - 8))
        if hide_monster:
            alert_text = font.render("MONSTER HUNT MODE", True, MINIMAP_HUNT)
            screen.blit(alert_text, (minimap_x + 10, minimap_y + minimap_height - 30))
        # Draw exit on minimap if active
        if exit_active and exit_x is not None:
            ex_screen = minimap_x + exit_x * tile_w
            ey_screen = minimap_y + exit_y * tile_h
            pygame.draw.rect(screen, (255, 255, 255), (int(ex_screen) - 6, int(ey_screen) - 6, 12, 12))

    # Draw stamina meter
    stamina_bar_width = 220
    stamina_bar_height = 16
    stamina_x = WIDTH - stamina_bar_width - 20
    stamina_y = 20
    pygame.draw.rect(screen, (30, 30, 30), (stamina_x, stamina_y, stamina_bar_width, stamina_bar_height))
    pygame.draw.rect(screen, (50, 200, 50), (stamina_x + 2, stamina_y + 2, int((stamina_bar_width - 4) * (stamina / MAX_STAMINA)), stamina_bar_height - 4))
    stamina_text = font.render("STAMINA", True, (200, 200, 200))
    screen.blit(pygame.transform.scale(stamina_text, (120, 20)), (stamina_x - 130, stamina_y))
    
    if lever_prompt and not lever_active:
        prompt_text = font.render("PRESS E TO PULL LEVER", True, (255, 255, 255))
        prompt_rect = prompt_text.get_rect(center=(WIDTH // 2, HEIGHT - 30))
        screen.blit(prompt_text, prompt_rect)

    if lever_active:
        active_text = font.render("LEVER PULLED: MONSTER HUNT MODE", True, (255, 80, 80))
        active_rect = active_text.get_rect(center=(WIDTH // 2, HEIGHT - 60))
        screen.blit(active_text, active_rect)
    
    # Draw "ESCAPE" text in blood red at the top
    escape_text = font.render("ESCAPE", True, BLOOD_RED)
    text_rect = escape_text.get_rect(center=(WIDTH // 2, 50))
    # Add slight glow effect by drawing shadow
    shadow_text = font.render("ESCAPE", True, (80, 0, 10))
    screen.blit(shadow_text, (text_rect.x + 2, text_rect.y + 2))
    screen.blit(escape_text, text_rect)
    
    # Draw threat text if active
    if threat_text and threat_timer > 0:
        threat_font = pygame.font.Font(None, random.randint(32, 56))
        threat_surf = threat_font.render(threat_text, True, (220, 30, 30))
        # Add glitch/shake effect
        shake_x = random.randint(-2, 2)
        shake_y = random.randint(-2, 2)
        screen.blit(threat_surf, (threat_x + shake_x, threat_y + shake_y))
    
    # Draw phase change text at top
    if phase_change_text and phase_change_timer > 0:
        # Calculate alpha based on timer for fade effect
        alpha_phase = int(255 * (phase_change_timer / 120.0))
        if monster.phase == PHASE_STALK:
            # White creepy text for stalk
            phase_font = pygame.font.Font(None, 48)
            phase_surf = phase_font.render(phase_change_text, True, (200, 200, 200))
            screen.blit(phase_surf, (WIDTH // 2 - phase_surf.get_width() // 2, 100))
        elif monster.phase == PHASE_HUNT or monster.phase == PHASE_SUDDEN:
            # Red shaking text for hunt/sudden
            phase_font = pygame.font.Font(None, 64)
            phase_surf = phase_font.render(phase_change_text, True, (255, 40, 40))
            shake_x = random.randint(-3, 3)
            shake_y = random.randint(-3, 3)
            screen.blit(phase_surf, (WIDTH // 2 - phase_surf.get_width() // 2 + shake_x, 100 + shake_y))
    
    # Draw jumpscare effect
    if jumpscare_active and jumpscare_timer > 0:
        # Intense red screen overlay with heavy distortion
        scare_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        intensity = int(255 * (jumpscare_timer / 60.0))  # Fade out over time
        scare_surf.fill((200, 0, 0, intensity))
        screen.blit(scare_surf, (0, 0))
        
        # Draw jumpscare text in huge distorted font
        jumpscare_font = pygame.font.Font(None, 120)
        scare_text = jumpscare_font.render("You're Not Getting Away...", True, (255, 255, 255))
        shake_intensity = int(8 * (jumpscare_timer / 60.0))
        for _ in range(3):
            shake_x = random.randint(-shake_intensity, shake_intensity)
            shake_y = random.randint(-shake_intensity, shake_intensity)
            screen.blit(scare_text, (WIDTH // 2 - scare_text.get_width() // 2 + shake_x, HEIGHT // 2 - scare_text.get_height() // 2 + shake_y))

        restart_text = font.render("PRESS R TO RETURN TO INTRO SCREEN", True, (255, 255, 255))
        screen.blit(restart_text, (WIDTH // 2 - restart_text.get_width() // 2, HEIGHT // 2 + scare_text.get_height() // 2 + 40))

    # Check for reaching exit (win)
    if exit_active and exit_x is not None and not win_active:
        if math.hypot(player_x - exit_x, player_y - exit_y) < 1.2:
            win_active = True
            win_timer = 240

    # Draw win overlay if active
    if win_active and win_timer > 0:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, int(200 * (win_timer / 240.0))))
        screen.blit(overlay, (0, 0))
        win_font = pygame.font.Font(None, 72)
        win_text = win_font.render("The Nightmare Is Only Beginning...", True, (10, 10, 10))
        screen.blit(win_text, (WIDTH // 2 - win_text.get_width() // 2, HEIGHT // 2 - win_text.get_height() // 2))
        win_timer -= 1
        if win_timer <= 0:
            running = False
    
    pygame.display.flip()

pygame.quit()