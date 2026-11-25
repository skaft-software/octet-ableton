# Max devices, expression, and remote control

## Contents
- [Choose a method and confirm availability](#choose-a-method-and-confirm-availability)
- [Build, edit, save, and package Max devices](#build-edit-save-and-package-max-devices)
- [DS percussion instruments](#ds-percussion-instruments)
- [Align Delay](#align-delay)
- [Shared modulator mapping](#shared-modulator-mapping)
- [Audio-driven and cyclic modulation](#audio-driven-and-cyclic-modulation)
- [Note-driven and expression modulation](#note-driven-and-expression-modulation)
- [Inspect and transform MIDI/MPE](#inspect-and-transform-midimpe)
- [Configure hardware control](#configure-hardware-control)
- [Create and interpret remote mappings](#create-and-interpret-remote-mappings)
- [Relative Session navigation and Clip View control](#relative-session-navigation-and-clip-view-control)
- [Verification and recovery](#verification-and-recovery)

## Choose a method and confirm availability

These are Live UI procedures, not claims that any automation integration exposes the controls. Inspect available capabilities before attempting tool-driven changes; use the UI or report the boundary when a feature is not exposed.

| Need | Choose | Prerequisite or important distinction |
| --- | --- | --- |
| Construct/customize a device or access Set/control-surface behavior through the Live API | Max for Live | Included with Suite; Standard requires the Max for Live add-on. The bundled Max needs no separate install. An API's existence is not proof of automation-tool support. |
| Transform/generate notes in a MIDI clip | Max MIDI Transformation/Generator | A MIDI Tool is not an ordinary device-chain MIDI effect; save it in an indexed location. |
| Follow an audio signal, oscillation, or drawn curve | Envelope Follower, LFO, or Shaper | Select modulation versus exclusive Remote Control deliberately. |
| Follow notes, expression gestures, or per-note MPE | Envelope MIDI, Shaper MIDI, Expression Control, or MPE Control | Distinguish mapping a parameter from transforming incoming MIDI/MPE data. |
| Play instruments from a controller | MIDI-track input | Notes assigned to remote commands are consumed by those assignments instead of playing the instrument. |
| Operate Live controls from hardware or keys | Control-surface instant mappings, MIDI Map, or Key Map | This is separate from generating musical MIDI notes. |

Device availability varies with Live edition and installation; confirm the named device is present rather than assuming all editions include it. Browse Instruments, Audio Effects, MIDI Effects, or Modulators for built-in devices. The Max for Live browser label also gathers installed third-party/saved Max devices and Max MIDI Tools. Presets can be loaded and saved like other device presets.

## Build, edit, save, and package Max devices

1. For a new chain device, drag **Max Instrument**, **Max MIDI Effect**, or **Max Audio Effect** into the Set; alternatively start with an existing Max device. Its connected objects determine its behavior. In the default audio effect, `plugin~` receives chain audio and `plugout~` passes it onward: retain an intentional signal path when changing the patch.
2. Open the device title-bar context menu or **Show Options** menu and choose **Edit in Max**. This opens the Max patcher. Before Live 12.2, devices used a title-bar Edit button; the `-MaxForLiveDeveloperMode` Options.txt option restores that button. Do not require the old button on a current installation.
3. Save intentionally: Max's **File > Save** updates every instance of that device in the Set. **Save As** asks whether the change should apply only to the edited preset or to all instances. For an isolated experiment, use Save As and choose the single-instance scope rather than altering shared instances.
4. Keep the AMXD in the appropriate User Library device-type folder, such as Max Audio Effect or Max MIDI Effect. The Set references a separate AMXD; it does not contain the device file. If a move/rename breaks the reference, locate the AMXD with Live's File Manager instead of rebuilding the device.
5. Inspect dependencies such as samples, pictures, and subsidiary patches. A **frozen Max device** bundles required files; it is not Live's **Freeze Track**. Use Max's device-freezing workflow for dependency packaging. If the controls are unfamiliar, consult **Help > Reference** in Max before acting; do not substitute track freezing.
6. To choose a different installed Max editor, set its application path in Live's **File & Folder Settings**. The change takes effect after restarting Live; preserve the current work before that restart. Verify the intended editor launches from the device afterward.

### Build an indexed MIDI Tool

1. In Clip View's Transformation or Generative Tools tab/panel, select **Max MIDI Transformation** or **Max MIDI Generator**, or select an existing Max MIDI Tool. Use that tool's **Edit** button to open Max.
2. Edit the patch, then use Max's **File > Save** or **Save As**. Default locations are `User Library/MIDI Tools/Max Transformations` and `User Library/MIDI Tools/Max Generators`.
3. An alternative folder works only if it is within Live's browser **Places**. Add the containing folder to Places, then confirm the tool appears in the corresponding Transformation/Generative drop-down. An AMXD outside both the default location and Places is not found by Live's Indexer and will not appear there.
4. For object-level patching help, use Max **Help > Reference > Max for Live > Guides**. For general learning, use the Max for Live documentation category and, if available, the **Building Max Devices** Pack's lessons. Do not infer undocumented object wiring from a device's name.

## DS percussion instruments

Choose the generator by the components you need, then set timbre, pitch, duration, and output level. All eight devices have **Decay** for sound length and **Volume** for overall level. Click anywhere in the **upper half of the display** to audition current settings; auditioning is an action to perform, not evidence of a completed listening test.

| Device / use | Timbre and transient controls | Pitch control |
| --- | --- | --- |
| **DS Clang**: cowbell, clave, noise percussion from two tones, white noise, and a filter | **Tone A/B** independently level the cowbell tones; **Filter** adjusts high-pass/band-pass cutoff, with higher settings giving more high-frequency content. **Noise** adds white noise. Enable **Clave** before using **Repeat** for clave repeats. | **Pitch** |
| **DS Clap**: tight or loose handclaps from filtered noise and an impulse through panned delays | **Sloppy** sets the separation between the two delay lines; **Tail** adds filtered noise to the clap impulse. **Spread**: 0% mono, 100% widened stereo. Higher **Tone** gives more high-frequency content. | **Tune** |
| **DS Cymbal**: ride/crash timbres from sine/pulse waves and high-passed noise | **Tone** raises/lowers high-pass cutoff; higher values emphasize higher-frequency content. | **Pitch** |
| **DS FM**: metallic/noisy FM percussion | **Tone** sets low-pass cutoff. **Feedb.** adds algorithm feedback; more produces more noise. **Amnt** sets FM modulation amount; **Mod** blends modulation types. | **Pitch**, global |
| **DS HH**: open/closed hats from noise and sine waves | Choose white/pink with **Noise**. **Tone** sets high-pass cutoff. The pitched component's resonant high-pass filter offers **12/24 dB** slopes; **Attack** sets attack time. | **Pitch**, global |
| **DS Kick**: modulated-sine kick | **Drive** adds distortion; **OT** adds harmonics. **Attack** smooths the sine onset; **Click** adds a sharper transient. **Env** sets pitch modulation. | **Pitch**, in Hz |
| **DS Snare**: pitched oscillator plus noise | **Color** shapes the pitched component; **Tone** controls noise presence. Select low-pass, high-pass, or band-pass filtering for the noise component. | **Tune**, global |
| **DS Tom**: impulse plus pitched oscillators | **Color** adjusts filter gain/cutoff; **Tone** levels resonant band-pass filters for membrane-like tuning. **Bend** changes the pitch envelope. | **Pitch**, in Hz |

Verify the audition responds before debugging clip playback. If audition works but sequenced notes do not, inspect MIDI routing and remote-note assignments rather than changing synthesis parameters blindly.

## Align Delay

Use this utility to delay incoming audio for alignment; choose units that match the problem, not a musical repeat pattern.

| Delay Mode | Use and setup |
| --- | --- |
| **Time** | Set milliseconds for A/V alignment or subtle left/right timing offsets. |
| **Samples** | Set sample counts to offset latency introduced elsewhere. |
| **Distance** | Enter meters or feet for physical spacing in a PA system. Match **Temperature** to the room and choose Celsius/Fahrenheit; temperature affects sound travel time. |

Enable **Link L/R** for identical channel delays: the right slider becomes unavailable and **Delay Left** controls both. Disable it only when independent left/right offsets are intended. Verify units, channel linkage, and the timing relationship being corrected; a delay adds time, so choose the signal that actually needs delaying.

## Shared modulator mapping

Use this procedure for **Envelope Follower, LFO, Shaper, Envelope MIDI, and Shaper MIDI**. Expression Control has its own source/output layout below.

1. Click **Map**, then click an automatable device or mixer parameter. Expand **Show/Hide Multimap** for more targets: each of these five devices supports **eight targets total**. Use the target's **Unmap** button to release an assignment.
2. Keep the default **Modulation** mode when the target's base value must remain editable. **Modulation Polarity** selects **Bipolar** movement around the base value or **Unipolar** movement in one direction from it; set target-relative depth with **Modulation Amount**.
3. Switch the **Mod** toggle to **Remote Control** when the modulator should own the target value. Manual target adjustment is then unavailable; set the controlled range with **Min/Max**. If the target appears locked, check this mode before assuming a fault.
4. Separate each mapping's range/amount from a device-wide **Depth** or **Amount** control where provided. A zero global amount yields no applied modulation even if a mapping exists. Check both the modulation signal and the actual target response.

## Audio-driven and cyclic modulation

### Envelope Follower

Choose this when input amplitude should move a target, such as a filter or level control. After mapping, adjust **Gain** on the detector input, then **Rise** for attack smoothing and **Fall** for release smoothing. **Delay** postpones the envelope; its **Delay Mode** buttons select time units or tempo-synced beat divisions.

By default the envelope follows the track input. For an external trigger:
1. Expand **Audio Routing** with the upper-left triangle; enable **Sidechain**.
2. Select a source in the first **Audio From** chooser and **Pre FX**, **Post FX**, or **Post Mixer** in the second. With Racks, choose the exact input channel if needed.
3. Watch **Direct** for track-input level and **S.C.** for external-source level. **Sidechain Mix** blends the detector sources: **0%** uses only the track input; **100%** only the external source.
4. If the target fails to follow the intended track, confirm source meter, tap point, Mix, Gain, and mapping mode before altering the target itself.

### LFO

Choose repeating or randomized parameter motion independent of note-triggered envelopes. Map the target, select a waveform, then set timing and range.

| Control | Operational distinction |
| --- | --- |
| **Waveform** | Sine, Up, Down, Triangle, Square, Random, Bin, Stray, Glider. |
| **Shape / Steps** | Shape bends/skews; Steps quantizes to as many as **24 steps**. Shape is unavailable for Random/Bin/Stray/Glider; Steps is unavailable for Random/Bin/Square. These disabled controls are expected, not a mapping failure. |
| **Jitter / Smooth** | Jitter randomizes output; Smooth softens abrupt movement, including jitter. |
| **Rate / Time Mode** | Choose Hz or tempo-synced beat divisions. In Hz mode, **×10** multiplies the frequency. |
| **Depth / Offset** | Depth affects all mapped targets: 0% none, 100% full LFO output. Offset 0% centers the signal; positive shifts it up, negative down. Use the horizontal display line as a center reference. |
| **Phase / R** | Phase moves the cycle position from 0% start to 100% end. **R (Retrigger)** starts from the Phase-defined position. |
| **Hold** | Freeze the current output value; disabling Hold resumes from that held value. |

Verify the display and target move together. If the output is static, check Hold, Depth, rate, and whether the selected waveform permits the control being adjusted.

### Shaper

Choose a drawn breakpoint envelope when a stock oscillator shape is insufficient. Click to add points; **Alt-drag (Windows) / Option-drag (macOS)** between points curves a segment. **Shift-click** removes a point. **Clear** removes the whole envelope; six preset shapes are available next to it. Preserve a custom shape before replacing it.

Set **Grid** divisions and enable **Snap** to align newly created or moved points. The small upper-right display shows the output signal. **Jitter** adds randomness; **Smooth** softens abrupt changes. **Offset** centers at 0%, shifts upward with positive values and downward with negative values; use the output display's horizontal line as reference.

| Trigger mode | How to use |
| --- | --- |
| **Loop** | Repeat continuously at **Rate**. |
| **1-Shot** | Trigger a single traversal using the mappable **T** button. |
| **Manual** | Scrub backward/forward using **Manual**. |

**Time Mode** chooses Hz or tempo-synced divisions. **Phase** spans 0–100% of the cycle; **R** retriggers from that point, but is unavailable when Time Mode is **Sync**. **Depth** scales all mapped targets from 0% none to 100% full output. Verify the selected trigger mode rather than expecting all shapes to loop automatically.

## Note-driven and expression modulation

### Envelope MIDI

Use a note-responsive ADSR to modulate mapped targets. **Attack** reaches the peak; **Decay** moves from peak to **Sustain**; **Release** returns to zero after note release. Change ADR curvature with the corresponding **Slope** sliders or adjust ADSR and slopes using the display handles.

| Loop Mode | Timing/trigger source |
| --- | --- |
| **Free** | Each played note triggers the envelope. |
| **Sync** | Retrigger at **Sync Rate** beat divisions. |
| **Loop** | Repeat at the rate defined by **Global Time**. |
| **Echo** | Repeat envelopes at **Env Echo Time** intervals; **Env Feedback** determines persistence. |

**Global Time** scales the whole duration: **1.00** preserves ADSR timing, larger values stretch, smaller values compress. **Amount** affects all targets: 0% none, 100% full output. With **Velocity** enabled, lower note velocity gives a lower envelope peak. With **Sustain** enabled, a held note stays at Sustain until release; with it off, the envelope passes through Attack, Decay, and Release as a one-shot irrespective of note length. Verify triggers with the LED beside Loop Mode.

### Expression Control

Use this to map MIDI/MPE gestures or note-triggered values to automatable device/mixer parameters. Configure each of its **five Mod Source tabs** separately: select **Velocity, Modwheel, Pitchbend, Pressure, Keytrack, Expression, Random, Increment, Slide, or Sustain**, click **Map**, then click the target.

- **Modulation toggle = Modulate:** the target's base value remains editable and combines with the generated modulation. Choose bipolar or unipolar behavior; **Output Range Max** sets output modulation for maximum input.
- **Remote Control:** the device owns the target value; **Output Range Min/Max** set its range. Do not confuse these output limits with the curve's own Min/Max controls.
- **Curve Type:** the two-breakpoint linear setting uses **Curve A** for the whole curve. The three-breakpoint S setting uses A for the upper segment and B for the lower. **Curve Link** lets A adjust both segments inversely.
- Set curve endpoints with **Min/Max**; in the S setting move the middle point with **X-Y**. You can also drag points/curve directly in the display.
- **Increment:** set **Increment Steps** to **1–32** note triggers per traversal of the modulation range. Stopping transport resets the count; the first note after restart outputs the configured minimum.
- **Random:** **Random Amount** sets deviation at each note trigger.
- **Smoothing Type:** choose linear or logarithmic smoothing. **Smoothing Rise/Fall** independently set how long increasing/decreasing values take to reach the latest input value, from **0–1000 ms**.

Verify the selected source is actually arriving before changing its curve. For unexpected resets with Increment, check transport stops; for apparently delayed gestures, check Rise/Fall.

### Shaper MIDI

Choose this rather than audio Shaper when each MIDI note should trigger a custom breakpoint envelope, optionally scaled by velocity. Use the shared eight-target mapping procedure and Shaper's point creation, curved-segment, Shift-click, Clear, six-preset, Grid/Snap, Jitter/Smooth, Offset, and Depth controls.

Create **one sustain breakpoint** with **Ctrl-click (Windows) / Cmd-click (macOS)**. It is larger than ordinary points and holds that level while the note remains held. **Loop** instead repeats at **Rate** while a note is held and **bypasses the sustain breakpoint**. Time Mode offers Hz or tempo-synced beat divisions.

**Velocity = 0%** makes depth independent of note velocity; higher settings scale lower-velocity notes down and higher-velocity notes up. **Depth** scales all mapped targets from 0% none to 100% full output. The small oscilloscope shows the signal and its LED flashes on triggers. **Echo** sets envelope-echo feedback/persistence; **Time** sets intervals between echoes. These are envelope repeats, not the extra MIDI notes produced by Note Echo.

## Inspect and transform MIDI/MPE

### MIDI Monitor

Use this utility to inspect what is arriving before diagnosing a synthesis or mapping problem. **Note** shows notes, root/related chord information, and velocity on a keyboard. **Flow** streams note and other MIDI messages, including pitch bend/aftertouch; **Freeze** pauses the display and **Clear** empties it. Neither is a substitute for checking actual incoming data. **MPE** displays note, velocity, slide, pressure, and per-note pitch in a stream.

### MPE Control

Use this to reshape incoming per-note expression before it reaches an instrument or expression mapping, or convert expression for a non-MPE instrument. MPE can address individual notes; standard/global expression affects notes collectively. Do not promise retained per-note independence after conversion to global MIDI.

1. Select **Press**, **Slide**, or **NotePB**; the selected curve comes forward. All are on by default; each has its own enable toggle.
2. Choose a two-breakpoint linear curve or a three-breakpoint S curve. In the linear setting use **Curve**, **Min/Max**, or direct dragging to reshape response and endpoints. In the S setting move the middle breakpoint directly or with **X-Y**; **Curve Link** initially links the two segments, and unlinking permits independent curve adjustments.
3. Expand advanced settings with the bottom-right triangle. Each source has **Smooth** plus independent **Rise/Fall** times. Set these per source, then inspect the resulting expression rather than assuming one source's smoothing applies to all.

| Source | Advanced options and when to choose them |
| --- | --- |
| **Press** | Pressure is generated per note after the initial strike. **Default** supplies an MPE value for notes lacking MPE data. **Swap to Slide** routes pressure as slide, useful when a controller supplies polyphonic aftertouch but not a slide gesture. **Press to AT** converts to monophonic aftertouch for non-MPE destinations. |
| **Slide** | Slide is **CC74**, commonly vertical finger movement. **Default** supplies a value for non-MPE notes. **Centered** gives zero at the pad center and increases modulation as the finger moves vertically away from center. **Abs** uses absolute position; **Rel** starts at midrange regardless of initial touch and responds to subsequent vertical movement; **Ons** updates only on Note On and automatically disables smoothing. **Slide to Mod** converts to Mod Wheel **CC1**. |
| **NotePB** | Per-note pitch bend commonly follows horizontal finger movement. **Pitch Range** compensates for different controller/instrument bend ranges: **2x** maps a controller's **±48-semitone** range to an instrument's **±24-semitone** range. For non-pitch mappings, higher scaling covers more target range with smaller gestures. **NotePB to PB** converts per-note bend to standard pitch-bend messages. |

Check controller and instrument bend settings together. These conversion controls do not specify a universal policy for simultaneous conflicting per-note values; test the actual destination with a chord before relying on converted global behavior.

### Note Echo

Choose this to produce extra MIDI notes with declining velocity, not merely to repeat a modulation curve.
1. Enable **Sync** to use the numbered delay chooser: values count **sixteenth notes**, so **4 = four sixteenths = one quarter note**. Adjust the **Delay Time percentage** for fractional timing offsets/swing. With Sync off, set milliseconds by dragging the Delay Time slider or typing into its field.
2. **Input Thru** retains the original note plus echoes; **Mute** plays only the echoes. **Pitch** transposes each successive repeat. **Delay** sets echo velocity amount; **Fback** returns output to the delay input.
3. Enable **MPE** to echo expression with notes/velocity; otherwise MPE data is filtered out. When enabled, **Press**, **Slide**, and **Note PB** control their respective feedback amounts. Below **100%**, expression decays progressively across repeats.
4. Inspect repeat timing, pitch, velocity, and MPE separately. If the original note is absent, check Input mode; if expression disappears, check MPE and its feedback controls.

## Configure hardware control

Open Settings with **Ctrl+, (Windows) / Cmd+, (macOS)**, then choose **Tempo & MIDI** (older layouts: **Link, Tempo & MIDI**). Live supports dedicated Push 1/2/3 control as well as other surfaces; do not assume another surface uses Push's controls.

| Controller situation | Setup and verification |
| --- | --- |
| Listed in **Control Surface** chooser | Select its name and input/output ports. Live supports **up to six** such surfaces simultaneously. If **Dump** becomes available, it sends a hardware preset: confirm authorization and the hardware's receive-ready state before sending. Do not guess the manufacturer's receive procedure. |
| Not listed, or making manual overrides | In **MIDI Ports**, enable **Remote** on the relevant input. Any number of ports can supply manual remote mappings; their incoming signals are merged. Send a message and check the Control Bar MIDI indicators. |
| Needs LED/motor-fader feedback | Also enable **Remote** on its output port so Live can communicate changed values. Input Remote alone does not supply feedback. |

Native **instant mappings** normally follow the selected device. To keep a surface on one device, use that device title bar's **Lock to…** context-menu entry; a hand icon identifies locked devices. Not all surfaces support locking. By default, arming a MIDI track automatically locks its instrument to the surface. Manual assignments can override instant mappings; enable the relevant port's Remote switch for those overrides.

### Choose Takeover Mode for absolute controls

Use this setting especially when bank switching makes a physical fader disagree with its current destination.
- **None:** the next movement sends the physical value immediately; expect a jump.
- **Pick-Up:** movement has no effect until the hardware reaches the destination's current value; after that it tracks 1:1. Apparent non-response may be intentional waiting, not failed MIDI.
- **Value Scaling:** movement smoothly converges the hardware and destination values, then tracks 1:1.

Relative encoders avoid this absolute-position mismatch by sending increments/decrements; verify their message mode instead of treating them as ordinary absolute faders.

## Create and interpret remote mappings

For MIDI: enable **MIDI Map Mode** with the upper-right **MIDI** switch; eligible controls turn blue. Click a target, send a note/knob/fader message, confirm the assignment in the **Mapping Browser**, then exit MIDI Map Mode. If the browser is closed, **Ctrl+Alt+B (Windows) / Cmd+Option+B (macOS)** opens it.

For computer keys: enable upper-right **KEY**, choose a red-highlighted control, press the desired key, confirm the Mapping Browser entry, then exit Key Map Mode. Show the browser via the View menu if needed. Key remote assignments are not the computer keyboard's pseudo-MIDI instrument-playing mode.

The Mapping Browser appears in manual MIDI, key, or Macro mapping mode and lists that mode's assignments: source control, target path/name, and **Min/Max**. Edit limits there or invert them via the context menu. Remove only an intended assignment using **Backspace (Windows) / Delete (macOS)**. Context-dependent instant mappings do **not** appear here.

| Target | MIDI note assignment | Absolute CC assignment | Relative CC assignment |
| --- | --- | --- | --- |
| **Session slot** | Note On/Off follow the contained clip's **Launch Mode**. | **64–127** acts as Note On; **0–63** as Note Off. | Increment acts as Note On; decrement as Note Off. |
| **Switch** | Note On toggles. | For **Track Activator/device on-off**: values inside mapping Min/Max turn on; outside turn off. Reversing Min/Max reverses that rule. Other switches, including transport: **≥64 on, <64 off**. | Increment on; decrement off. |
| **Radio choice**, e.g. crossfader assignment A / unaffected / B | Note On cycles options. | The 0–127 range spans the options. | Increment next; decrement previous. |
| **Continuous parameter** | One note toggles Min/Max; a note range assigns equally spaced discrete values. | The 0–127 range spans the parameter range. | Encoding-specific increments/decrements adjust the current value. |

Pitch bend and **14-bit Absolute** mappings use **0–16383** rather than 0–127; the split is **8191/8192** instead of 63/64. Do not apply 7-bit threshold assumptions to these messages. Mixer volume, pan, sends, crossfader, and eligible buttons are remote-control targets; only highlighted controls can be assigned in the active mapping mode.

For chromatic Session-slot playing, first play the root note that should launch at the clip's default transposition. Keep it held, then hold one note below and one above to establish the range. Slot assignments stay with the **slot**, not the clip moved into or out of it. A note used by a remote assignment no longer reaches a MIDI-track instrument as a playing note.

For relative encoders, match **Signed Bit, Signed Bit 2, Bin Offset, or Twos Complement**, including their **linear** variants where appropriate. Some hardware internally accelerates faster turns. During assignment, turn slowly left to help Live detect the type/acceleration; inspect the Status Bar **mode** chooser and select the known encoding explicitly if detection is wrong.

Mapped computer keys launch Session clips according to Launch Mode, toggle switches, and cycle radio choices. Do not assume they behave as continuous absolute controllers.

## Relative Session navigation and Clip View control

In MIDI or Key Map Mode, use the assignable strip below the Session grid to avoid mapping every slot separately:
- Assign the scene up/down buttons to keys, notes, or controllers.
- Assign the scene-number field to a MIDI controller, preferably an endless encoder, for scrolling.
- Assign launch-highlighted-scene and cancel-triggered-scene controls separately.
- For sequential operation, enable **Settings > Record, Warp & Launch > Select Next Scene on Launch** deliberately; a scene launch then advances the selection.
- Assign each track's highlighted-scene clip-launch button for track-local launching. Live keeps the highlighted scene centered during relative navigation.

Identify these controls by their visible purpose in the current UI, not by assumed screen coordinates. Test selection movement separately from launching before using a large Set.

**Clip View mappings follow selection**, including multi-selected clips, so they may act on different clips anywhere in the Set. Prefer relative controllers to avoid absolute-value jumps, and verify the selected clip(s) before each edit. A fixed Session-slot mapping and a selection-following Clip View mapping are different targeting models.

## Verification and recovery

These are proposed checks, not claims of completed Live, controller, or listening tests.

| Symptom | First checks / scoped recovery |
| --- | --- |
| Max unavailable or device absent | Check edition/add-on, installed device/Pack, and selected Max application; a configured editor path only changes after restart. |
| Saved device missing or MIDI Tool absent | Resolve AMXD references with File Manager; for tools, verify the default MIDI Tools folder or a folder within Places, then inspect the correct tool drop-down. |
| One patch edit changes other instances | Check Save versus Save As scope; use an isolated saved variant for further work. Do not assume instances contain independent device files. |
| Target cannot be adjusted manually | Check Remote Control versus Modulation/Modulate; release only the intended mapping or change its mode. |
| Mapping exists but nothing moves | Check source signal/message, trigger/loop mode, Hold, global Depth/Amount, mapping range, and detector source/mix as applicable. |
| MIDI notes disappear from the instrument | Check whether those notes are reserved by remote assignments; confirm incoming MIDI indicators and inspect mappings before changing the instrument. |
| Hardware moves but Live jumps, reverses, or waits | Check absolute takeover versus relative encoding; Pick-Up waits intentionally. For feedback problems also check output Remote. |
| Different clips change unexpectedly | Inspect current Clip View selection/multi-selection and distinguish it from slot-bound assignments. |

Before reporting success, confirm the requested target, scope, and observable result; separate file persistence, visible UI response, MIDI data, and any actual audible verification. Report unsupported automation and untested hardware behavior explicitly.
