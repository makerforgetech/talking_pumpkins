
import math
import random
import threading
import pygame
import numpy as np
import sounddevice as sd
import soundcard as sc

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
MICROPHONE_LATENCY = "high"
AUDIO_SAMPLE_RATE = 48000
# PipeWire routes to the operating system's selected/default speaker.
AUDIO_OUTPUT_DEVICE = "pipewire"
AUDIO_MONITORING = True # Forward microphone audio to the selected speaker.
AUDIO_SOURCE = "system"  # "microphone" or "system"
AUDIO_SOURCE_GAIN = .4
# When AUDIO_SOURCE is "microphone"
MICROPHONE_MODE = "default"  # "default" or "dji"
MICROPHONE_CHANNELS = 2
MICROPHONE_DEVICE = "DJI MIC MINI" # Get this name by running the following terminal command: pactl list short sources
SYSTEM_AUDIO_NOISE_FLOOR = 0.005
SYSTEM_AUDIO_GAIN = 6.0

# Add, remove, or edit entries to control the pumpkins.  Centre coordinates
# are normalized (0.0 to 1.0) within the display; scale is a fraction of the
# display height.
PUMPKINS = [
    {
        "center": (0.29, 0.50),
        "scale": 0.3,
        "angry": False,
        "mouth_speed": 5.0,
        "use_microphone": True,
        "microphone_channel": 0,
        "mouth_audio_gain": 1.0,
    },
    {
        "center": (0.6, 0.50),
        "scale": 0.2,
        "angry": True,
        "mouth_speed": 4.0,
        "mouth_phase": 1.5,
        "use_microphone": True,
        "microphone_channel": 1,
        "mouth_audio_gain": 1.0,
    },
    {
        "center": (.85, 0.50),
        "scale": 0.2,
        "angry": False,
        "mouth_speed": 4.0,
        "mouth_phase": 1.5,
        "use_microphone": True,
        "microphone_channel": 1,
        "mouth_audio_gain": 0.9,
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
    """Capture microphone volume and convert it into mouth openings."""

    @staticmethod
    def _speaker_loopback():
        if AUDIO_OUTPUT_DEVICE in (None, "pipewire"):
            speaker = sc.default_speaker()
        else:
            configured_name = str(AUDIO_OUTPUT_DEVICE).casefold()
            speaker = next(
                (
                    candidate for candidate in sc.all_speakers()
                    if (
                        configured_name == candidate.name.casefold()
                        or configured_name in candidate.name.casefold()
                        or configured_name == candidate.id.casefold()
                    )
                ),
                None,
            )
            if speaker is None:
                raise ValueError(
                    "AUDIO_OUTPUT_DEVICE does not match a speaker: "
                    f"{AUDIO_OUTPUT_DEVICE}"
                )

        return sc.get_microphone(
            f"{speaker.id}.monitor",
            include_loopback=True,
        )

    def __init__(self):
        if AUDIO_SOURCE not in {"microphone", "system"}:
            raise ValueError(
                "AUDIO_SOURCE must be 'microphone' or 'system'"
            )
        if MICROPHONE_MODE not in {"default", "dji"}:
            raise ValueError(
                "MICROPHONE_MODE must be 'default' or 'dji'"
            )

        self.input_channels = 2 if AUDIO_SOURCE == "system" else (
            1 if MICROPHONE_MODE == "default" else MICROPHONE_CHANNELS
        )
        self.levels = np.zeros(self.input_channels)
        self.smoothed_levels = np.zeros(self.input_channels)
        if AUDIO_SOURCE == "system":
            self._levels_lock = threading.Lock()
            self._stop_loopback = threading.Event()
            self._loopback_ready = threading.Event()
            self._loopback_error = None
            self._loopback_thread = threading.Thread(
                target=self._capture_loopback,
                daemon=True,
            )
            self._loopback_thread.start()
            self._loopback_ready.wait()
            if self._loopback_error is not None:
                raise self._loopback_error
            self.stream = None
            return
        else:
            input_device = (
                None if MICROPHONE_MODE == "default" else MICROPHONE_DEVICE
            )

        if AUDIO_MONITORING and AUDIO_SOURCE == "microphone":
            self.stream = sd.Stream(
                device=(input_device, AUDIO_OUTPUT_DEVICE),
                channels=(self.input_channels, 2),
                samplerate=AUDIO_SAMPLE_RATE,
                blocksize=MICROPHONE_BLOCKSIZE,
                latency=MICROPHONE_LATENCY,
                callback=self._monitor_callback,
            )
        else:
            self.stream = sd.InputStream(
                device=input_device,
                channels=self.input_channels,
                samplerate=AUDIO_SAMPLE_RATE,
                blocksize=MICROPHONE_BLOCKSIZE,
                latency=MICROPHONE_LATENCY,
                callback=self._input_callback,
            )
        self.stream.start()

    def _capture_loopback(self):
        try:
            loopback = self._speaker_loopback()
            with loopback.recorder(
                samplerate=AUDIO_SAMPLE_RATE,
                blocksize=MICROPHONE_BLOCKSIZE,
            ) as recorder:
                self._loopback_ready.set()
                while not self._stop_loopback.is_set():
                    self._process_input(
                        recorder.record(numframes=MICROPHONE_BLOCKSIZE),
                        None,
                    )
        except Exception as error:
            self._loopback_error = error
            self._loopback_ready.set()

    def _process_input(self, indata, status):
        # Do not print recoverable overflows from the real-time callback.
        if status and not (
            status.input_overflow or status.output_underflow
        ):
            print(f"Microphone status: {status}")
        if AUDIO_SOURCE == "system":
            # Mid emphasizes centered lead vocals; side emphasizes stereo
            # backing vocals and instruments.
            mid = (indata[:, 0] + indata[:, 1]) * 0.5
            side = (indata[:, 0] - indata[:, 1]) * 0.5
            levels = np.array([
                np.sqrt(np.mean(mid ** 2)),
                np.sqrt(np.mean(side ** 2)),
            ])
        else:
            levels = np.sqrt(np.mean(indata ** 2, axis=0))
        if AUDIO_SOURCE == "system":
            with self._levels_lock:
                self.levels = levels
        else:
            self.levels = levels

    def _monitor_callback(self, indata, outdata, frames, callback_time, status):
        self._process_input(indata, status)
        if self.input_channels == 1:
            outdata[:] = indata[:, :1]
        else:
            outdata[:] = indata

    def _input_callback(self, indata, frames, callback_time, status):
        self._process_input(indata, status)

    def openings(self, dt):
        # Ignore a small ambient noise floor and smooth rapid changes.
        if AUDIO_SOURCE == "system":
            with self._levels_lock:
                levels = self.levels.copy()
        else:
            levels = self.levels
        levels = levels * AUDIO_SOURCE_GAIN
        if AUDIO_SOURCE == "system":
            target = np.clip(
                (levels - SYSTEM_AUDIO_NOISE_FLOOR)
                * SYSTEM_AUDIO_GAIN,
                0.0,
                1.0,
            )
        else:
            target = np.clip((levels - 0.015) * 12.0, 0.0, 1.0)
        for channel in range(self.input_channels):
            speed = (
                90.0
                if target[channel] > self.smoothed_levels[channel]
                else 18.0
            )
            smoothing = 1.0 - math.exp(-dt * speed)
            self.smoothed_levels[channel] += (
                target[channel] - self.smoothed_levels[channel]
            ) * smoothing
        return self.smoothed_levels.tolist()

    def close(self):
        if AUDIO_SOURCE == "system":
            self._stop_loopback.set()
            self._loopback_thread.join(timeout=1.0)
        else:
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
               microphone_openings=None):
    """Draw the configured pumpkins into one display-sized scene."""
    surface.fill(BLACK)

    for pumpkin, motion in zip(pumpkins, motion_states):
        center_x, center_y = pumpkin["center"]
        if (
            not pumpkin.get("use_microphone", False)
            or microphone_openings is None
        ):
            opening = 0.5 + 0.5 * math.sin(
                elapsed * pumpkin["mouth_speed"]
                + pumpkin.get("mouth_phase", 0.0)
            )
        else:
            channel = (
                pumpkin.get("microphone_channel", 0)
                if (
                    AUDIO_SOURCE == "system"
                    or MICROPHONE_MODE == "dji"
                )
                else 0
            )
            opening = microphone_openings[channel]
            opening *= pumpkin.get("mouth_audio_gain", 1.0)
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
        microphone_openings = (
            microphone.openings(dt) if microphone is not None else None
        )
        draw_scene(
            screen, WIDTH, HEIGHT, PUMPKINS,
            updated_motion_states, t, microphone_openings
        )

        pygame.display.flip()
        clock.tick(60)

    if microphone is not None:
        microphone.close()
    pygame.quit()


if __name__ == "__main__":
    main()
