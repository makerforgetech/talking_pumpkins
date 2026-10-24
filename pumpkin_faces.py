
import math
import random
import pygame
import numpy as np
import sounddevice as sd

pygame.init()

# Use display 2 when it exists; otherwise use the primary display.
target_display = 1 if len(pygame.display.get_desktop_sizes()) >= 2 else 0
screen = pygame.display.set_mode(
    (0, 0), pygame.FULLSCREEN, display=target_display
)
WIDTH, HEIGHT = screen.get_size()

pygame.display.set_caption("Pumpkin Face Projection")

clock = pygame.time.Clock()

BLACK = (0, 0, 0)
PUMPKIN = (152, 55, 8)
CARVE_GLOW = (255, 174, 24)

MICROPHONE_BLOCKSIZE = 512
MICROPHONE_LATENCY = "low"

# Add, remove, or edit entries to control the pumpkins.  Centre coordinates
# are normalized (0.0 to 1.0) within the display; scale is a fraction of the
# display height.
PUMPKINS = [
    {
        "center": (0.29, 0.50),
        "scale": 0.2,
        "angry": False,
        "mouth_speed": 5.0,
        "use_microphone": True,
    },
    {
        "center": (0.6, 0.50),
        "scale": 0.2,
        "angry": True,
        "mouth_speed": 4.0,
        "mouth_phase": 1.5,
        "use_microphone": True,
    },
]


def polygon(surface, colour, points):
    """Draw a polygon using integer screen coordinates."""
    pygame.draw.polygon(
        surface, colour,
        [(int(x), int(y)) for x, y in points]
    )


def scaled_points(points, cx, cy, scale):
    return [
        (cx + (x - cx) * scale, cy + (y - cy) * scale)
        for x, y in points
    ]


def glowing_polygon(surface, points, cx, cy):
    """Draw a dark carved opening with a warm light behind its edge."""
    for size, colour in [
        (1.20, (255, 91, 0, 28)),
        (1.10, (255, 137, 0, 70)),
        (1.03, (255, 186, 35, 150)),
    ]:
        layer_points = scaled_points(points, cx, cy, size)
        min_x = math.floor(min(x for x, _ in layer_points))
        max_x = math.ceil(max(x for x, _ in layer_points))
        min_y = math.floor(min(y for _, y in layer_points))
        max_y = math.ceil(max(y for _, y in layer_points))
        padding = max(4, int(max(max_x - min_x, max_y - min_y) * 0.12))
        bounds = pygame.Rect(
            min_x - padding,
            min_y - padding,
            max_x - min_x + padding * 2 + 1,
            max_y - min_y + padding * 2 + 1,
        )
        glow = pygame.Surface(bounds.size, pygame.SRCALPHA)
        polygon(
            glow,
            colour,
            [(x - bounds.left, y - bounds.top) for x, y in layer_points],
        )
        surface.blit(glow, bounds.topleft, special_flags=pygame.BLEND_ADD)

    polygon(surface, (18, 5, 1), points)


class FaceMotion:
    """Independent random gaze and blinking behaviour for each face."""

    def __init__(self, now):
        self.gaze_x = 0.0
        self.gaze_y = 0.0
        self.target_x = 0.0
        self.target_y = 0.0

        self.next_gaze = now + random.uniform(0.5, 2.0)

        self.blink_start = None
        self.blink_duration = 0.16
        self.next_blink = now + random.uniform(1.5, 4.0)

    def update(self, now, dt):
        # Occasionally choose a new direction to look.
        if now >= self.next_gaze:
            directions = [
                (0, 0),       # Centre
                (-1, 0),      # Left
                (1, 0),       # Right
                (0, -1),      # Up
                (0, 1),       # Down
                (-0.7, -0.5), # Upper left
                (0.7, -0.5),  # Upper right
                (-0.7, 0.5),  # Lower left
                (0.7, 0.5),   # Lower right
            ]

            self.target_x, self.target_y = random.choice(directions)
            self.next_gaze = now + random.uniform(1.0, 3.0)

        # Smoothly move the pupils towards the target direction.
        smoothing = 1.0 - math.exp(-dt * 5.0)

        self.gaze_x += (self.target_x - self.gaze_x) * smoothing
        self.gaze_y += (self.target_y - self.gaze_y) * smoothing

        # Schedule independent, occasional blinks.
        if self.blink_start is None and now >= self.next_blink:
            self.blink_start = now
            self.blink_duration = random.uniform(0.12, 0.20)

        blink = 1.0

        if self.blink_start is not None:
            progress = (now - self.blink_start) / self.blink_duration

            if progress >= 1.0:
                self.blink_start = None
                self.next_blink = now + random.uniform(1.5, 5.0)
            else:
                # Close halfway through, then reopen.
                blink = abs(1.0 - 2.0 * progress)

        return self.gaze_x, self.gaze_y, max(0.04, blink)


class MicrophoneLevel:
    """Capture microphone volume and convert it into a smooth mouth opening."""

    def __init__(self):
        self.level = 0.0
        self.smoothed_level = 0.0
        self.stream = sd.InputStream(
            channels=1,
            samplerate=None,
            blocksize=MICROPHONE_BLOCKSIZE,
            latency=MICROPHONE_LATENCY,
            callback=self._callback,
        )
        self.stream.start()

    def _callback(self, indata, frames, callback_time, status):
        # Do not print recoverable overflows from the real-time callback.
        if status and not status.input_overflow:
            print(f"Microphone status: {status}")
        self.level = float(np.sqrt(np.mean(indata[:, 0] ** 2)))

    def opening(self, dt):
        # Ignore a small ambient noise floor and smooth rapid changes.
        target = max(0.0, self.level - 0.015) * 12.0
        target = min(1.0, target)
        speed = 90.0 if target > self.smoothed_level else 18.0
        smoothing = 1.0 - math.exp(-dt * speed)
        self.smoothed_level += (target - self.smoothed_level) * smoothing
        return self.smoothed_level

    def close(self):
        self.stream.stop()
        self.stream.close()


def draw_eye(surface, x, y, size, angry, gaze_x, gaze_y, blink):
    """Draw an eye-shaped opening with a warm light behind it."""

    height = size * (1.5 if not angry else 1.1) * blink

    if blink < 0.12:
        # Thin line when the eye is almost closed.
        pygame.draw.line(
            surface, CARVE_GLOW,
            (int(x - size), int(y)),
            (int(x + size), int(y)),
            max(2, int(size * 0.12))
        )
        return

    points = [
        (x - size, y),
        (x - size * 0.55, y - height * 0.75),
        (x, y - height),
        (x + size * 0.55, y - height * 0.75),
        (x + size, y),
        (x + size * 0.55, y + height * 0.65),
        (x, y + height * 0.8),
        (x - size * 0.55, y + height * 0.65),
    ]

    glowing_polygon(surface, points, x, y)


def draw_mouth(surface, cx, cy, width, opening, angry):
    """Draw a jagged carved opening with a warm light behind it."""

    opening = max(0.0, min(1.0, opening))
    w = width
    h = width * (0.04 + opening * 0.42)

    if opening < 0.08:
        pygame.draw.arc(
            surface, CARVE_GLOW,
            (int(cx - w / 2), int(cy - 5), int(w), 16),
            math.pi, 2 * math.pi,
            max(2, int(width * 0.025))
        )
        return

    if angry:
        points = [
            (cx - w / 2, cy),
            (cx - w * 0.28, cy - h * 0.25),
            (cx - w * 0.15, cy + h * 0.15),
            (cx, cy - h * 0.1),
            (cx + w * 0.15, cy + h * 0.15),
            (cx + w * 0.30, cy - h * 0.25),
            (cx + w / 2, cy),
            (cx + w * 0.35, cy + h),
            (cx, cy + h * 1.1),
            (cx - w * 0.35, cy + h),
        ]
    else:
        points = [
            (cx - w / 2, cy),
            (cx - w * 0.3, cy - h * 0.2),
            (cx, cy - h * 0.12),
            (cx + w * 0.3, cy - h * 0.2),
            (cx + w / 2, cy),
            (cx + w * 0.32, cy + h),
            (cx, cy + h * 1.1),
            (cx - w * 0.32, cy + h),
        ]

    glowing_polygon(surface, points, cx, cy)

    # Leave a few darker triangular notches in the carved edge.
    if opening > 0.25:
        tooth_y = cy + h * 0.25
        tooth_w = w * 0.12
        tooth_h = h * 0.28

        for tx in [cx - w * 0.22, cx + w * 0.22]:
            polygon(surface, (3, 1, 0), [
                (tx - tooth_w / 2, cy),
                (tx + tooth_w / 2, cy),
                (tx, tooth_y + tooth_h)
            ])


def draw_face(surface, cx, cy, scale, angry, opening, motion):
    gaze_x, gaze_y, blink = motion

    # Layered ellipses give the pumpkin a ribbed, uneven surface.
    body = pygame.Rect(
        int(cx - scale * 1.05), int(cy - scale * 0.98),
        int(scale * 2.10), int(scale * 1.95)
    )
    pygame.draw.ellipse(surface, (76, 22, 3), body.inflate(scale * 0.08, scale * 0.08))
    pygame.draw.ellipse(surface, PUMPKIN, body)
    for offset, colour in [
        (-0.52, (105, 31, 4)),
        (-0.24, (184, 65, 7)),
        (0.24, (111, 30, 3)),
        (0.52, (70, 18, 2)),
    ]:
        rib = body.inflate(-abs(offset) * scale * 0.24, -scale * 0.04)
        rib.centerx += int(offset * scale * 0.35)
        pygame.draw.ellipse(surface, colour, rib, max(2, int(scale * 0.035)))

    eye_y = cy - scale * 0.22
    eye_dx = scale * 0.34
    eye_size = scale * 0.17

    # Both eyes look in the same direction.
    draw_eye(
        surface, cx - eye_dx, eye_y, eye_size,
        angry, gaze_x, gaze_y, blink
    )
    draw_eye(
        surface, cx + eye_dx, eye_y, eye_size,
        angry, gaze_x, gaze_y, blink
    )

    # Nose
    nose_y = cy + scale * 0.02
    nose_size = scale * 0.09

    nose_points = [
        (cx, nose_y - nose_size),
        (cx - nose_size, nose_y + nose_size),
        (cx + nose_size, nose_y + nose_size)
    ]
    glowing_polygon(surface, nose_points, cx, nose_y)

    # Demo mouth animation; replace with microphone input later.
    draw_mouth(
        surface, cx, cy + scale * 0.32,
        scale * 0.85, opening, angry
    )


def draw_scene(surface, width, height, pumpkins, motion_states, elapsed,
               microphone_opening=None):
    """Draw the configured pumpkins into one display-sized scene."""
    surface.fill(BLACK)

    for pumpkin, motion in zip(pumpkins, motion_states):
        center_x, center_y = pumpkin["center"]
        if not pumpkin.get("use_microphone", False) or microphone_opening is None:
            opening = 0.5 + 0.5 * math.sin(
                elapsed * pumpkin["mouth_speed"]
                + pumpkin.get("mouth_phase", 0.0)
            )
        else:
            opening = microphone_opening
        draw_face(
            surface,
            width * center_x,
            height * center_y,
            height * pumpkin["scale"],
            pumpkin.get("angry", False),
            opening,
            motion,
        )


def main():
    running = True
    start = pygame.time.get_ticks() / 1000.0

    motion_states = [FaceMotion(start) for _ in PUMPKINS]
    microphone = (
        MicrophoneLevel()
        if any(pumpkin.get("use_microphone", False) for pumpkin in PUMPKINS)
        else None
    )

    previous_time = start

    while running:
        now = pygame.time.get_ticks() / 1000.0
        dt = min(now - previous_time, 0.05)
        previous_time = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        t = now - start

        updated_motion_states = [
            motion.update(now, dt) for motion in motion_states
        ]
        microphone_opening = (
            microphone.opening(dt) if microphone is not None else None
        )
        draw_scene(
            screen, WIDTH, HEIGHT, PUMPKINS,
            updated_motion_states, t, microphone_opening
        )

        pygame.display.flip()
        clock.tick(60)

    if microphone is not None:
        microphone.close()
    pygame.quit()


if __name__ == "__main__":
    main()
