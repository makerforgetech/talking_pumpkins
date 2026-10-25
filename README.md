# Pumpkin Face Projection

This project renders animated pumpkin faces fullscreen using Pygame. Each face
has independent eye movement and blinking, while its mouth can either animate
continuously or respond to microphone volume.

The display uses the second monitor when one is available and falls back to the
primary display otherwise.

## Programs

### `pumpkin_faces.py`

The original single-microphone version. It opens the system default audio
input and uses that input to animate the mouths. Both pumpkins respond to the
same microphone level.

Run it with:

```bash
./run_pumpkin.sh
```

### `pumpkin_dji_mic_mini.py`

The dual-microphone DJI version. It opens the `DJI MIC MINI` USB audio device
with two input channels:

- Channel 1 drives the left pumpkin's mouth.
- Channel 2 drives the right pumpkin's mouth.

Run it with:

```bash
./run_pumpkin_dji.sh
```

The DJI receiver must output the microphones as separate stereo channels. If
it is in mono or merged mode, both USB channels contain the combined signal and
both mouths will respond to both microphones.

To switch the DJI receiver to separate stereo output:

1. Turn on the receiver and both transmitters.
2. Connect the receiver to the computer.
3. Press the receiver's **Link** button to switch the audio output between
   merged mono and separate stereo.
4. Start `./run_pumpkin_dji.sh` again after changing the mode.

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
- Edit the `PUMPKINS` configuration in either Python file to change positions,
  scale, appearance, or microphone assignments.

The DJI version identifies the receiver by the device name
`DJI MIC MINI`. If the operating system reports a different name, update
`MICROPHONE_DEVICE` in `pumpkin_dji_mic_mini.py`.

## Configuration

Settings are edited near the top of the Python file you intend to run. Make
the same changes in both files if you want the original and DJI versions to
look identical.

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

- `MICROPHONE_BLOCKSIZE` controls the number of audio samples processed per
  callback. Smaller values can reduce latency but use more processing.
- `MICROPHONE_LATENCY` is passed to the audio driver. `"low"` prioritizes
  responsiveness.

The original `pumpkin_faces.py` uses the operating system's default input
device and one shared microphone level.

The DJI version also has:

- `MICROPHONE_CHANNELS`, which should remain `2` for the two-transmitter
  receiver.
- `MICROPHONE_DEVICE`, the audio device name used for the DJI receiver.

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

The DJI version additionally supports:

- `microphone_channel`: zero-based input channel used by this pumpkin. Use
  `0` for the first receiver channel and `1` for the second receiver channel.

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

The `microphone_channel` setting is only used by
`pumpkin_dji_mic_mini.py`. The original file can use the same list, but all
microphone-enabled pumpkins respond to its single default microphone.
