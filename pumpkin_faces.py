
import math
import random
import pygame

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
GOLD = (255, 175, 0)


def polygon(surface, colour, points):
    """Draw a polygon using integer screen coordinates."""
    pygame.draw.polygon(
        surface, colour,
        [(int(x), int(y)) for x, y in points]
    )


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


def draw_eye(surface, x, y, size, angry, gaze_x, gaze_y, blink):
    """Draw a glowing eye with a moving pupil and animated blink."""

    height = size * (1.5 if not angry else 1.1) * blink

    if blink < 0.12:
        # Thin line when the eye is almost closed.
        pygame.draw.line(
            surface, GOLD,
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

    polygon(surface, GOLD, points)

    # Keep pupils inside the eye as they look around.
    pupil_x = x + gaze_x * size * 0.36
    pupil_y = y + gaze_y * size * 0.30

    pygame.draw.circle(
        surface, BLACK,
        (int(pupil_x), int(pupil_y)),
        max(2, int(size * 0.28))
    )


def draw_mouth(surface, cx, cy, width, opening, angry):
    """Draw a mouth whose opening can later be driven by microphone input."""

    opening = max(0.0, min(1.0, opening))
    w = width
    h = width * (0.04 + opening * 0.42)

    if opening < 0.08:
        pygame.draw.arc(
            surface, GOLD,
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

    polygon(surface, GOLD, points)

    # Black triangular gaps create the appearance of teeth.
    if opening > 0.25:
        tooth_y = cy + h * 0.25
        tooth_w = w * 0.12
        tooth_h = h * 0.28

        for tx in [cx - w * 0.22, cx + w * 0.22]:
            polygon(surface, BLACK, [
                (tx - tooth_w / 2, cy),
                (tx + tooth_w / 2, cy),
                (tx, tooth_y + tooth_h)
            ])


def draw_face(surface, cx, cy, scale, angry, opening, motion):
    gaze_x, gaze_y, blink = motion

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

    polygon(surface, GOLD, [
        (cx, nose_y - nose_size),
        (cx - nose_size, nose_y + nose_size),
        (cx + nose_size, nose_y + nose_size)
    ])

    # Demo mouth animation; replace with microphone input later.
    draw_mouth(
        surface, cx, cy + scale * 0.32,
        scale * 0.85, opening, angry
    )


def draw_scene(surface, width, height, left_open, right_open,
               left_motion_state, right_motion_state):
    """Draw both pumpkin faces into one display-sized scene."""
    surface.fill(BLACK)
    scale = min(width * 0.44, height * 0.38)

    draw_face(
        surface, width * 0.29, height * 0.50,
        scale, False, left_open, left_motion_state
    )
    draw_face(
        surface, width * 0.71, height * 0.50,
        scale, True, right_open, right_motion_state
    )


def main():
    running = True
    start = pygame.time.get_ticks() / 1000.0

    left_motion = FaceMotion(start)
    right_motion = FaceMotion(start)

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

        # Demo mouth movement, independent for each pumpkin.
        left_open = 0.5 + 0.5 * math.sin(t * 5.0)
        right_open = 0.5 + 0.5 * math.sin(t * 4.0 + 1.5)

        left_motion_state = left_motion.update(now, dt)
        right_motion_state = right_motion.update(now, dt)

        draw_scene(
            screen, WIDTH, HEIGHT, left_open, right_open,
            left_motion_state, right_motion_state
        )

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
