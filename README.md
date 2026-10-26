# Pumpkin Face Projection

This project renders animated pumpkin faces fullscreen using Pygame. Each face
has independent eye movement and blinking, while its mouth can either animate
continuously or respond to microphone volume.

The display uses the second monitor when one is available and falls back to the
primary display otherwise.

## Running

The project now uses one program, `pumpkin_faces.py`:

```bash
./run_pumpkin.sh
```

Choose the microphone mode by editing `MICROPHONE_MODE` near the top of
`pumpkin_faces.py`:

- `"default"` uses the operating system's default microphone. All
  microphone-enabled pumpkins respond to that one input.
- `"custom"` uses the two-channel `DJI MIC MINI` receiver. Channel 1 drives the
  left pumpkin's mouth and channel 2 drives the right pumpkin's mouth.

The DJI receiver must output the microphones as separate stereo channels. If
it is in mono or merged mode, both USB channels contain the combined signal and
both mouths will respond to both microphones.

To switch the DJI receiver to separate stereo output:

1. Turn on the receiver and both transmitters.
2. Connect the receiver to the computer.
3. Press the receiver's **Link** button to switch the audio output between
   merged mono and separate stereo.
4. Start `./run_pumpkin.sh` again after changing the mode.

## Installation

Create the virtual environment, activate it, and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The launcher scripts use `.venv/bin/python` directly, so activation is not
required when using the launchers.

## Controls

- Press **Escape** to exit fullscreen mode.
- Edit the `PUMPKINS` configuration in `pumpkin_faces.py` to change positions,
  scale, appearance, or microphone assignments.

The DJI mode identifies the receiver by the device name `DJI MIC MINI`. If the
operating system reports a different name, update `MICROPHONE_DEVICE`.

## Configuration

Settings are edited near the top of `pumpkin_faces.py`.

### Quick start

The default is `AUDIO_SOURCE = "system"`. This should display the pumpkins on a second screen (projector), output anything you play to your device speakers, as well as forward sound to the second screen's audio output.

Three pumpkins will be displayed on the screen, each with independent mouth and eye movements.

To use the microphone instead, set `AUDIO_SOURCE = "microphone"` and configure `MICROPHONE_MODE` and `MICROPHONE_DEVICE` accordingly. `default` is the operating system's default microphone.

A `custom` microphone mode uses the device specified in `MICROPHONE_DEVICE` and the number of channels specified in `MICROPHONE_CHANNELS`. Each channel can drive a different pumpkin's mouth. This script is configured to support the `DJI MIC MINI` with two channels.

### Display and colours

- `BLACK` is the background colour.
- `PUMPKIN` is the main pumpkin colour.
- `CARVE_GLOW` is the orange glow used for the carved features.

Colours use RGB tuples, with each component from `0` to `255`. For example,
`(255, 0, 0)` is red.

The program automatically uses display 2 when it is available and otherwise
uses display 1. The fullscreen display selection is controlled by the
`target_display` expression near the top of the file; its values are
zero-based, so `0` is the first display and `1` is the second.

### Audio settings

These settings are available in both programs:

(Leave these alone unless you know what you are doing.)
- `MICROPHONE_BLOCKSIZE` controls the number of audio samples processed per
  callback. Smaller values can reduce latency but use more processing.
- `MICROPHONE_LATENCY` is passed to the audio driver. `"high"` gives the
  speaker output more buffering to avoid playback underflows.
- `AUDIO_SAMPLE_RATE` sets the shared input/output sample rate. It is set to
  `48000` so the DJI receiver and the speaker output can be used in one
  duplex stream.
- `AUDIO_OUTPUT_DEVICE` selects the speaker output used for live microphone
  monitoring. It defaults to `pipewire`, which follows the operating system's
  selected/default speaker or display audio sink on Linux. Set it to an exact
  speaker or HDMI display audio device name only if you need to override the
  system default.
- `SYSTEM_AUDIO_NOISE_FLOOR` prevents low-level speaker-loopback noise from
  opening the mouths when no system audio is playing.
- `SYSTEM_AUDIO_GAIN` controls how strongly system playback opens the mouths.

Change these only if you need to customize the audio input or output behavior.
- `AUDIO_MONITORING` toggles forwarding microphone audio to the selected
  speaker. Set it to `False` to analyze the microphones without playback.
- `AUDIO_SOURCE` selects the signal used for mouth animation:
  - `"microphone"` uses the configured default or DJI microphone input.
  - `"system"` captures the stereo system-audio loopback from
    `AUDIO_OUTPUT_DEVICE`.
- `AUDIO_SOURCE_GAIN` scales the captured waveform before any mouth processing.
  This changes only animation sensitivity; it does not change the actual
  microphone or speaker volume. For example, `0.5` makes all mouths respond
  to half-strength input, which helps prevent loud songs from holding them
  fully open.
- `MICROPHONE_MODE` selects `"default"` or `"custom"`.
- `MICROPHONE_CHANNELS`, which should remain `2` for the two-transmitter
  receiver when `MICROPHONE_MODE` is `"custom"`.
- `MICROPHONE_DEVICE`, the audio device name used for the DJI receiver when
  `MICROPHONE_MODE` is `"custom"`.

When `AUDIO_SOURCE` is `"system"`, the script derives the loopback source from
`AUDIO_OUTPUT_DEVICE`. The generic `pipewire` value follows the operating
system's default speaker. If `AUDIO_OUTPUT_DEVICE` is changed to a specific
speaker or HDMI device name, its corresponding monitor is captured instead.

In system-audio mode, the first microphone channel uses the centered
mid-signal (`left + right`) as a lead-vocal estimate. The second uses the
stereo side-signal (`left - right`) as a backing-vocal/music estimate. This is
a lightweight stereo heuristic; it cannot perfectly separate vocals from a
finished stereo mix. Audio monitoring is disabled in this mode to avoid
feeding the captured playback back into the speakers.

### Number, placement, and appearance of pumpkins

The `PUMPKINS` list controls how many pumpkins are drawn. Each dictionary in
the list creates one pumpkin. Add a dictionary to add a pumpkin, remove one to
remove it, or reorder dictionaries to change their order and microphone
assignments.

Each pumpkin supports these settings:

- `center`: `(x, y)` position as normalized coordinates from `0.0` to `1.0`.
  `(0.0, 0.0)` is the top-left corner and `(1.0, 1.0)` is the bottom-right.
  For example, `(0.25, 0.5)` places a pumpkin one quarter across and halfway
  down the display.
- `scale`: pumpkin size as a fraction of the display height. Increase it to
  make the pumpkin larger.
- `angry`: `True` gives the pumpkin angular angry eyes and mouth; `False` gives
  it the regular face.
- `mouth_speed`: speed of the automatic mouth animation when microphone input
  is disabled.
- `mouth_phase`: optional starting phase for the automatic mouth animation.
  This is useful for keeping multiple non-microphone mouths out of sync.
- `use_microphone`: `True` makes the mouth respond to microphone input;
  `False` uses the automatic animation instead.
- `mouth_audio_gain`: per-pumpkin volume control for waveform-driven mouth
  movement. `1.0` is the current response, `0.5` makes the mouth half as
  sensitive, and values above `1.0` amplify the response.

- `microphone_channel`: zero-based input channel used by this pumpkin. Use
  `0` for the first receiver channel and `1` for the second receiver channel
  when `MICROPHONE_MODE` is `"custom"`. It is ignored in `"default"` mode.

For example, this creates three pumpkins across the display:

```python
PUMPKINS = [
    {
        "center": (0.20, 0.50),
        "scale": 0.16,
        "angry": False,
        "mouth_speed": 5.0,
        "use_microphone": True,
        "microphone_channel": 0,
    },
    {
        "center": (0.50, 0.50),
        "scale": 0.16,
        "angry": True,
        "mouth_speed": 4.0,
        "mouth_phase": 1.5,
        "use_microphone": True,
        "microphone_channel": 1,
    },
    {
        "center": (0.80, 0.50),
        "scale": 0.16,
        "angry": False,
        "mouth_speed": 6.0,
        "mouth_phase": 3.0,
        "use_microphone": False,
    },
]
```

In `"default"` mode, all microphone-enabled pumpkins respond to the single
default microphone. In `"custom"` mode, each pumpkin uses its configured
`microphone_channel`.
