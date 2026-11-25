# Clips, arrangement, session, and warping

## Contents
- [Choose the working surface](#choose-the-working-surface)
- [Navigate and audition the Arrangement](#navigate-and-audition-the-arrangement)
- [Locators, meter, and Arrangement loops](#locators-meter-and-arrangement-loops)
- [Select, move, and restructure material](#select-move-and-restructure-material)
- [Linked-track editing](#linked-track-editing)
- [Audio fades and crossfades](#audio-fades-and-crossfades)
- [Build and perform a Session](#build-and-perform-a-session)
- [Scene tempo, meter, and status](#scene-tempo-meter-and-status)
- [Move between Session and Arrangement](#move-between-session-and-arrangement)
- [Open and organize Clip View](#open-and-organize-clip-view)
- [Clip regions, loops, and scrubbing](#clip-regions-loops-and-scrubbing)
- [Groove, scale, launch, and MIDI programs](#groove-scale-launch-and-midi-programs)
- [Audio utilities and sample lifecycle](#audio-utilities-and-sample-lifecycle)
- [MIDI pitch, time, transform, and generate controls](#midi-pitch-time-transform-and-generate-controls)
- [Set tempo and choose its authority](#set-tempo-and-choose-its-authority)
- [Prepare audio for warping](#prepare-audio-for-warping)
- [Place and maintain Warp Markers](#place-and-maintain-warp-markers)
- [Repair short loops and long recordings](#repair-short-loops-and-long-recordings)
- [Choose a Warp Mode](#choose-a-warp-mode)
- [Verify and recover](#verify-and-recover)

## Choose the working surface
These are Live 12 UI procedures, not a declaration of available automation calls. Confirm the installed edition, visible controls, selected objects, and tool capabilities before acting. Protect originals before edits that replace content; do not perform file-destructive or all-track changes without approval.

| Goal | Work here | Important boundary |
| --- | --- | --- |
| Place sections at fixed song times | Arrangement | One linear timeline; time insertion/removal can affect every track. |
| Launch alternatives in an unpredictable order | Session | One clip per track can play; rows launch combinations, not a predetermined timeline. |
| Change a clip's content or playback behavior | Clip View | Audio and MIDI expose different panels; some controls are Session-only. |
| Synchronize audio to musical time | Audio Utilities + Sample Editor | Enable Warp; choose a timing map separately from the stretching algorithm. |
| Preserve free-running audio | Audio Utilities, Warp off | No tempo-following and no audio clip looping. |

## Navigate and audition the Arrangement
- Use the Overview's outlined region to move through the song: drag horizontally to scroll, vertically to zoom; double-click inside the outline to show the full Arrangement. The beat-time ruler uses bars-beats-sixteenths; drag similarly, or double-click to fit the selection, or the whole song if nothing is selected. The lower time ruler uses minutes-seconds-milliseconds and supports horizontal scrolling.
- Zoom around the selection with `+`/`-` or Ctrl-wheel (Windows)/Cmd-wheel (macOS); pan with Ctrl-Alt-drag/Cmd-Option-drag. `Z` fits a time selection; `X` steps back through previous zoom states. An Arrangement time selection also focuses that region in Clip View.
- `H`/`W` optimize Arrangement height/width. Alt-wheel/Option-wheel inside a main lane changes track height; a time selection makes this apply to tracks containing selected content. Waveform Vertical Zoom Level enlarges waveform display across audio tracks, including new recordings, without changing gain.
- Turn on Follow for automatic playhead scrolling. Editing, horizontal scrolling, or clicking the beat ruler pauses Arrangement Follow; stopping/restarting playback or clicking an Arrangement/clip scrub area resumes it.
- Space toggles transport; Shift-Space resumes from the last stopped position rather than the insert marker. Click a track's background to set the insert marker, or type/drag/use arrows in Arrangement Position and confirm typed values with Enter. Double-click Stop, Home (Windows), or Fn-left (macOS) returns to the starting play position.
- With Permanent Scrub Areas enabled in Display & Input Settings, click the scrub strip to launch from a point; jumps obey global launch quantization. Hold the mouse there to repeat that quantized portion. With the preference off, Shift-click the scrub area or beat ruler instead. Chase MIDI Notes in Options lets notes sound when playback starts partway through them; it is enabled by default.
- Tracks stack vertically; drag headers to reorder. Dropping an instrument or MIDI effect in the Mixer Drop Area creates a MIDI track; an audio effect creates an audio track. Main lanes hold arranged clips; comping take lanes can supply material to them.
- Automation Mode reveals automation lanes. Enable Lock Envelopes when automation must stay at song positions while clips move; otherwise account for clip-associated envelope movement.
- Show the mixer through View > Mixer, the bottom-right toggle, or Ctrl-Alt-M/Cmd-Option-M. Customize Mixer Controls and Arrangement Track Controls independently in View. Their shared values stay synchronized, but Performance Impact, track delays, and crossfader are mixer-only controls.

## Locators, meter, and Arrangement loops
- Add a locator with Set Locator during playback/recording; placement follows global launch quantization. While stopped, it goes at the insert marker or time-selection start. Add Locator is also available in Create or the scrub-area context menu. Set becomes Delete Locator when a locator is selected.
- Click locators or Previous/Next Locator to make quantized jumps; beyond the first/last locator these buttons reach the Arrangement start/end. Double-click a locator when stopped to select it and begin playback. Transport and locator controls can be key/MIDI mapped.
- Drag a selected locator or use arrows to reposition it; Rename and Edit Info Text organize sections. Use Loop to Next Locator to loop adjacent sections. Set Song Start Time Here on a locator overrides normal playback-from-selection; inspect this setting if playback repeatedly starts somewhere unexpected.
- Insert Time Signature Change at the insert marker using Create or the scrub context menu. Valid values have a 1–99 numerator and denominator 1, 2, 4, 8, or 16; slash, comma, period, or spaces can separate the numbers. The Control Bar signature fields also change meter at the current play position, stopped or running; their automation indicator signals existing changes.
- Meter markers appear below the beat ruler only when changes exist. Move them by dragging or left/right arrows; use Edit Time Signature (Ctrl-R/Cmd-R) to revise values. They follow the editing grid, not launch quantization, so a change inside a bar creates a crosshatched fragmentary bar.
- Treat fragmentary-bar corrections as whole-song restructuring: Delete Fragmentary Bar Time shortens every track; Complete Fragmentary Bar inserts time at the fragment's beginning. Neither is merely a display repair. MIDI import can optionally bring in saved time-signature changes as markers.
- Enable Arrangement Loop in the Control Bar; set Loop Start and Loop Length numerically, or select time and use Loop Selection (Ctrl-L/Cmd-L). With no clip/time selected, the loop spans the Arrangement. The same shortcut toggles looping with a clip/time selection. Drag brace edges to resize or its bar to move it without changing length.
- With either an Arrangement or clip loop brace selected: left/right nudges by grid; up/down moves left/right by one loop length; Ctrl/Cmd-left/right shortens/lengthens by grid; Ctrl/Cmd-up/down doubles/halves length. Arrangement brace > Set Song Start Time Here starts transport at its beginning instead of the insert marker/selection.

## Select, move, and restructure material
- Click a clip bar to select it; drag the bar to move the clip, and its edges to resize it. Dragging the waveform/MIDI display selects time instead. Clips snap to the grid and to clip edges, locators, and meter changes.
- Click background for a point selection; arrows move the insert marker in time or between tracks. Ctrl-left/right (Windows)/Option-left/right (macOS) jumps to locators and selected-track clip edges. Drag for a timespan; Shift-click or Shift-arrows extends/shortens selections across time/tracks. Clicking the loop brace performs Select Loop.
- Unfold a track to select time within its content: use the header's unfold button or `U`; Alt/Option-click or Alt/Option-U unfolds all. Resize via its lower boundary, Alt/Option-`+`/`-`, or supported Alt/Option-pinch. Alt/Option while resizing one track applies the height change to all tracks.
- Arrow-left/right nudges selected material. `0` deactivates selected material, even across clips; with a track header selected it deactivates the track instead. Confirm focus before using this shortcut.
- Slip the contents of a warped audio or MIDI clip without moving its boundaries using Ctrl-Shift-drag (Windows)/Shift-Option-drag (macOS) on the content. For unsnapped slipping use Ctrl-Alt-Shift/Cmd-Option-Shift instead.
- Configure the editing grid in a main-lane/MIDI-editor context menu. Ctrl/Cmd-1 narrows (twice as many subdivisions), -2 widens, -3 toggles triplets, -4 toggles snapping, -5 switches fixed/adaptive grids. Read the current spacing at the lower right. Alt (Windows)/Cmd (macOS) temporarily reverses snapping state during an action, including enabling it when the grid is off.
- Use Split (Ctrl-E/Cmd-E) at an insertion point for a cut, or over a selected range to isolate a new clip. Each resulting piece has independent edges. Use regular Cut/Copy/Paste/Duplicate when only selected material should change, not the duration of the whole song.

| Restructuring command | Scope and consequence to confirm first |
| --- | --- |
| Cut Time / Delete Time | Removes the selected duration across all tracks and brings the two sides together; Cut Time also retains the cut selection. |
| Paste Time / Duplicate Time | Inserts copied/duplicated duration across the Arrangement, increasing total length. |
| Insert Silence | Adds empty duration across tracks starting at the insert marker. |
| Consolidate, Ctrl-J/Cmd-J | Joins adjacent selected material into one clip per track, not one combined multitrack clip. |

- Time commands also affect meter markers inside the region. Preview the intended boundaries and protect a version before approving whole-song changes.
- Audio Consolidate creates new samples from the warping engine before track effects and mixer: clip attenuation, warping, pitch shift, and clip envelopes are included; track effects are not. Use an approved post-effects render/export workflow instead when effects must be printed. MIDI consolidation yields an editable clip whose edges can be extended for repetitions.
- Saved consolidated audio is under `Samples/Processed/Consolidate` in the Project; unsaved Sets use the Temporary Folder. Verify new clip length and effect expectations before discarding any originals.

## Linked-track editing
- For phase-related multitrack edits, select headers and use Link Tracks; the Group Track header can link its contained tracks. A track belongs to only one linked set, but a Set may have several. Hover a link indicator to see membership; click it to select the members.
- To add tracks to an existing link set, select the new tracks, then hold Ctrl/Cmd while choosing Link Tracks from an existing member's header. Selecting any subset or mixture and choosing Link Tracks forms a link set from that selection; use Unlink Track(s) on selected members to remove them.
- Linked operations include moving/resizing clips, clip/time selections, Time commands, splitting/consolidation, arming/disarming, and take-lane rename/insert/delete/Audition Mode. Hidden take lanes still participate. Fades edit together only when their start positions match; inspect all linked tracks, not just the visible one.

## Audio fades and crossfades
- Arrangement audio fades are clip properties, independent of track automation. Enlarge/unfold the track until edge handles appear; hover the clip. In Automation Mode, hold `F` over the lane to momentarily expose fades.
- Drag edge/peak handles to adjust the fade region and Fade Curve to shape it. Fade In Start and Fade Out End can change duration without moving the peaks, but cannot pass their peaks. Selecting time that includes an outer clip edge and using Create Fade In/Out (Ctrl-Alt-F/Cmd-Option-F) sets the fade over that region.
- For adjacent audio clips on one track, drag a fade handle across the shared boundary, or select time straddling it and use Create Crossfade. Adjust the slope handle for shape. Fade lengths cannot cross loop boundaries, and a clip's in/out fades cannot overlap; a selected handle's dotted limit line exposes hidden limits under overlaps.
- Create Fades on Clip Edges in Record, Warp & Launch Settings gives new edges/adjacencies 4 ms fades/crossfades. Deleting a selected fade handle restores 4 ms with that setting enabled; otherwise it removes the fade.
- Session clips instead expose Clip Fade in Audio Utilities: its signal-dependent start/end fades are 0–4 ms. It defaults on with Create Fades on Clip Edges. Do not look for this toggle on Arrangement clips; use their handles instead.

## Build and perform a Session
- Put mutually exclusive alternatives in one track and simultaneous parts across tracks. Click a clip's triangle to launch, or select its name and press Enter; arrows navigate clips. A square Clip Stop button in a slot or Track Status stops that track's clip. Stopping an individual clip does not stop transport or the song-position clock; press Control Bar Stop twice to stop/reset the Set to 1.1.1.
- Scene Launch on the Main track launches a row. Cancel Scene Launch in the Main track context menu cancels a queued scene. Select Next Scene on Launch normally advances selection to the following row; disable it in Launch Settings when that is unwanted. Keys/MIDI can launch scenes and navigate them; clips can also be mapped to MIDI note ranges for chromatic triggering.
- Rename clips/scenes, set their colors, and add Edit Info Text for cues. Rename can affect multiple clips; Tab moves between scenes during scene renaming. Scene numbers follow position, not identity. Shift-select adjacent or Ctrl/Cmd-select nonadjacent objects, then drag to reorder.
- Dragging nonadjacent scenes collapses the gaps; use Ctrl-up/down instead to preserve their spacing. Resize tracks at title-bar edges; Alt/Option-resize applies to all. Narrow tracks retain launch buttons and essential controls.
- A Group Track slot is shaded when any member has a clip in that scene; it takes the left-most clip's color. Its launch button starts the corresponding member clips, and clicking the slot selects them. Empty group slots have stop buttons.
- Import/record clips into Session, or rubber-band-select from an empty slot to reorganize them. Multiple imported raw audio/MIDI files normally stack vertically on one Session track (horizontally in Arrangement); hold Ctrl/Cmd before dropping to distribute them across tracks. This modifier does not work for Live Clips with embedded devices.
- Turn off Select on Launch in Launch Settings when launching must not steal the current editing focus. For a scene that must leave a track's current clip running, remove that row's empty-slot stop button with Add/Remove Stop Button; restore it when the scene should stop the track.
- Insert Scene adds an empty row below the selection. Capture and Insert Scene copies currently playing clips into a new row below the selection and immediately launches it without interrupting playback; use it to preserve a discovered combination.

## Scene tempo, meter, and status
- Reveal Scene Tempo and Scene Time Signature by dragging the Main track header's left edge. Assign values by typing + Enter or dragging vertically. Launching the scene applies them; its launch button becomes colored. Tempo accepts 20–999 BPM; meter accepts numerator 1–99 with denominator 1, 2, 4, 8, or 16.
- To stop a scene overriding tempo/meter, use Return to Default, Delete, or double-click the enabled control. Older pre-Live-11 Sets migrate scene-name tempo/meter values into these fields and widen Main to display them; use the fields for current editing, not name parsing.
- Scene View opens when selecting scenes, clicking their tempo/meter fields, or clicking the Main title. Edit selected scenes' Tempo and Signature above, Follow Actions below; the title shows one scene's name/number/color or the selection count. Its context menu renames/recolors selected scenes.
- Left/right arrows reach scene tempo/meter from a selected slot/scene. Tab/Shift-Tab traverses name, tempo, meter, then neighboring scenes while editing. From a selected tempo/meter control, Enter first selects the scene; a second Enter launches it.

| Track Status display | Interpret before troubleshooting |
| --- | --- |
| Pie chart | Looping Session clip; left number is the loop-play count since launch, right is length in beats. Group pie charts omit numbers. |
| Progress bar | One-shot Session clip; remaining time is minutes:seconds. |
| Microphone / keyboard | Audio / MIDI input monitoring. |
| Miniature Arrangement | The track is playing its Arrangement material. |

## Move between Session and Arrangement
- Enable Arrangement Record to capture a Session performance, launch clips/scenes, then disable recording or stop transport. Inspect the Arrangement for clips at the intended tracks and times, recorded clip-property changes, automation, and scene tempo/meter transitions. This captures clip use; it does not itself create new audio sample data.
- Session and Arrangement playback are mutually exclusive per track. Launching a Session clip overrides that track's Arrangement; a Session Clip Stop can leave silence rather than resume it. Use Back to Arrangement to restore timeline playback and check its warning light. Stop All Clips on Main can stop Arrangement clips as well; it is not a return-to-timeline command.
- Session and Arrangement clips are independent copies. Copy/paste or drag over the view selectors to transfer material; with Second Window (Ctrl-Shift-W/Cmd-Shift-W), drag between windows. Arrangement-to-Session paste lays out clips top-to-bottom to preserve their temporal order as scenes.
- Consolidate Time to New Scene, from Create or an Arrangement time-selection context menu, makes one clip per track for that interval and places them in a new Session scene below the selected scene. It creates a new sample for each selected audio track containing a clip; retain the same pre-effects limitation as Consolidate.

## Open and organize Clip View
- Double-click a clip, use the Clip View Selector/Toggle, or Ctrl-Alt-3/Cmd-Option-3. The toggle can stack Clip View above Device View. Drag the top border to resize; dragging to the bottom closes it. It always follows selected clips; clicking a Session Track Status display selects the currently playing clip for editing.
- In two-window operation, Clip View opens in the focused window. `F12` moves it to the other window; Shift-Tab does so only when Use Tab Key to Navigate is off. Selection in either window can feed the editor in the other.
- The title bar has Clip Activator, name/color, and Save Default Clip for audio. Deactivate using the activator, clip context menu, or `0`; multi-selection deactivates all. Renaming an audio clip does not rename its sample; sample-file renaming is a separate browser action.
- New clips inherit track color. Choose a clip color in its/title-bar context menu, or Assign Track Color to Clips from the header; the Group variant applies to grouped tracks/clips. These assignments affect only the current Session or Arrangement view's clips. Multi-clip titles show a count and striped color, even after batch rename/recolor.
- Panels are on the left, editor on the right. Drag the panel/editor divider left for vertical panels and right for horizontal, or use View > Arrange Clip View Panels Vertically/Horizontally/Automatically. Automatic layout follows editor height; Live remembers the choice. Double-click the title or choose Fold to minimize panels.
- Main Clip Properties contains region/loop, signature, groove, and scale. Extended Clip Properties contains Session launch controls and MIDI bank/program messages; it is absent for Arrangement audio and contains only bank/program controls for Arrangement MIDI.
- Editor tabs or View select Sample/Envelope for audio and MIDI Note/Envelope/MPE for MIDI; Alt-Tab/Option-Tab cycles them. Sample Editor handles waveform/warping; Envelope handles automation/modulation of clip, MIDI, mixer, and effects controls; MIDI Note edits notes/velocities; MPE edits per-note expression.
- Drag an editor time ruler vertically to zoom, horizontally to scroll; wheel/trackpad also scrolls. `Z` fits the clip selection and repeated `X` steps back. The Clip View Selector always depicts the full clip; drag its outlined region horizontally/vertically to scroll/zoom. Follow pauses on editing and resumes with playback restart/stop or scrub interaction.
- Multi-select clips with Shift/Ctrl/Cmd or a rubber band from an empty slot. Only shared properties appear. Differing knob/slider values show a range; moving to an absolute extreme makes the values identical, so avoid that if preserving differences matters. Clip Update Rate in Record, Warp & Launch Settings quantizes when running clips receive edits; the same settings area sets defaults such as Launch Mode and Warp Mode for new clips.

## Clip regions, loops, and scrubbing
- An unlooped clip plays from its start marker to its end or until stopped. Type Start/End positions or drag/select markers and use arrows; Alt/Option-arrows on either marker moves the whole region. Warped audio positions use bars-beats-sixteenths; unwarped audio uses minutes-seconds-milliseconds. Set Start/Set End captures current playback position with global quantization.
- Enable Warp before looping audio. Turn on Clip Loop and set Loop Position/Length, or drag brace edges; Length initially reflects the clip's full length. The clip still begins at its start marker, so place start before the loop to create an intro that runs into repetition. Brace keyboard controls match those listed for Arrangement loops.
- For a live loop capture, click Set Loop Position during playback to set the quantized start and engage looping, then Set Loop Length to place the end at playback position. If looping is off, Set Loop Length instead places the loop end at playback while preserving preset length and enabling the loop. Loop/region controls and Set buttons can be MIDI mapped.
- Duplicate Loop extends both loop length and contents. In MIDI clips it moves notes beyond the loop so their distance from the loop end stays unchanged; this is not the same as merely doubling the brace length.
- With Permanent Scrub Areas on, click the lower waveform half or strip below the ruler to jump; hold for repeated playback at the global quantization interval. Smaller intervals or None permit finer scrubbing. Ctrl/Cmd-6, -7, -8, -9, -0 change global quantization; do not confuse these with unmodified `0` deactivation. With the preference off, Shift-click the scrub strip/ruler. Enable Chase MIDI Notes when entering midway through sustained notes.
- Clip Time Signature changes the display only, independently of song meter. Use different meters/loop lengths to inspect polymetric relationships; changing this field alone does not retime playback.

## Groove, scale, launch, and MIDI programs
- Choose Clip Groove from the Groove Pool. Hot-Swap Groove opens the browser; double-click/Enter loads the choice and also replaces that groove in the pool, not just the current clip. Check other uses before replacing a shared groove.
- Commit writes groove timing/velocity effects into clip content and disables its groove assignment. Committing an audio groove with positive velocity values creates a volume clip envelope and overwrites any existing one; protect it before approval.
- Scale enables Scale Mode; Root Note and Scale Name select the scale. On MIDI clips the piano ruler highlights its notes. On audio clips the setting does not retune playback; it forwards scale information to scale-aware devices in the chain.
- Session Extended Clip Properties provides Follow Action and launch controls for successive clips, input response, launch timing, scrubbing, and MIDI-velocity influence on volume. Empty slots separate Follow Action clip groups within a track; these groups are not Group Tracks. Confirm the intended launch/follow settings separately rather than assuming a row's visual order is its playback order.
- MIDI clips can send bank/sub-bank/program messages to compatible external instruments or plug-ins on launch. Live provides 128 banks × 128 sub-banks × 128 programs; the receiver may implement fewer. Leave a chooser at `—` to send no message of that type, and verify the receiver's numbering/support before changing sounds.

## Audio utilities and sample lifecycle
- Gain is clip-level dB; multiple differing gains show split slider handles. Pitch changes semitones plus a separate cents field (100 cents = one semitone). These are clip controls, not track fader settings; Re-Pitch disables transposition because speed determines pitch.
- High Quality enables higher-quality sample-rate conversion at extra CPU cost, particularly useful for transposition or source/system sample-rate differences. Roughly ±19 semitones may be possible before audible aliasing; this is an approximation, not a quality guarantee.
- Use RAM Mode selectively for disk-throughput limits or Legato Mode dropouts. It loads the clip's referenced audio into memory; too many RAM clips can force swapping, causing rhythmic hiccups as well as mutes. If memory pressure rises, reduce RAM loading instead of assuming it is always faster.
- The Sample Editor header shows sample name, rate, bit depth, and channels; multi-selection shows counts and `*` for differing properties. Click the name or Show in Browser to locate the actual file. Show Similar Files searches alternatives.
- Save Default Clip stores audio clip settings, including Warp Markers, in the sample's accompanying analysis file. It affects future imports, not existing clips; multi-selection saves all selected samples' settings. Save defaults only for owned samples, not Core Library/Pack content. A saved Live Clip additionally carries devices/settings; sample defaults do not.
- Reverse creates a separate reversed sample and reuses clip settings. Warp Markers stay with their sample positions as those positions reverse; loop/region settings flip too, but envelopes stay at their existing musical times. Session reversal is single-clip; Arrangement Reverse Clip(s)/`R` can process an all-audio time selection across clips, never a mixed MIDI selection.
- Prepare reversals before performance: long processing can lock other actions until waveform generation begins, and reapplying warp/loop settings can glitch. Playing clips continue during processing. Original/reversed versions are cached until Live exits. Saved results use `Samples/Processed/Reverse`; before saving they use Temporary Folder.
- To crop safely, first confirm the intended retained region: unlooped audio uses Start–End; looped audio uses the earlier of clip start/loop start through loop end. Crop Clip Sample creates a new sample; Crop Clip Sample to Time Selection uses a highlighted interval instead. Both use Ctrl-Shift-J/Cmd-Shift-J according to selection context. MIDI equivalents are Crop Clip and Crop Clip to Time Selection with the same boundary rules; protect notes outside the region.
- Cropped audio is saved under `Samples/Processed/Crop`, or Temporary Folder before the Set is saved. Check the new start, ending, and loop after cropping; it is a new file, not just a hidden region in the old file.
- To replace only a clip's reference, drop a browser sample into Clip View, or double-click/Enter on a browser sample for the selected clip. Pitch/gain settings persist; Warp Markers persist only when replacement length exactly matches. Recheck alignment even for equal-length replacements.
- File-destructive editing is outside the default workflow. Edit opens the configured external sample editor; processing requires stopped playback, and Warp Markers survive only unchanged sample length. Manage Sample File opens File Manager; changes there can affect every clip/instrument using that file. Do not use either as a harmless per-clip replacement.

## MIDI pitch, time, transform, and generate controls
- Pitch and Time Utilities acts on selected notes/time; with no selection, button operations affect the whole clip. Establish selection first and preserve a version before replacing note content.
- Transpose accepts semitones, or scale degrees with a clip scale active. Fit to Scale moves selected pitches into that scale and is inactive without one. Invert exchanges high/low pitch relationships. Interval Size sets a semitone/scale-degree offset; Add Interval adds new notes at that offset relative to the originals.
- Stretch compresses/expands selected note durations; ×2 and /2 change note duration, time selection, or loop region by two. Duration + Set Length applies a chosen note length. Humanize Amount sets random start-time variation up to one quarter of a grid division before or after the original position (half a division across the full range); Humanize applies it. Reverse flips note-pattern order; Legato adjusts each selected note to reach the next note's start.
- Audio Transform contains Quantize for warped clips only, with current-grid or chosen division and Amount; audio has no Generate panel. MIDI Transform replaces the selected notes, notes within selected time, or all notes when none are selected; scale-aware pitch controls use degrees when Scale Mode is on.
- MIDI Generate creates notes within the selected time or, without that, the loop region; active Scale Mode constrains generated pitches. Individual MIDI tools and detailed MPE editing are separate operations; do not confuse these panels with real-time MIDI effects or promise an uninspected tool.

## Set tempo and choose its authority
- The Control Bar Tempo field sets BPM, with fine adjustment in hundredths; coarse/fine parts can be mapped separately. Timeline tempo automation can make ramps or steps. MIDI Clock/Link can synchronize external systems; Tempo Follower uses an external audio source. Choose the authority before diagnosing clips that seem to ignore tempo edits.
- Tap Tempo once per beat; additional taps refine the estimate. To map a key, enter Key Map Mode, select Tap Tempo, press the key, and exit mapping; MIDI Map Mode supports a note/controller such as a pedal. Start Playback with Tap Tempo in Record, Warp & Launch Settings permits tap-start; 4/4 requires four taps. Tap-start also synchronizes the playback positions of Link-connected apps, so account for connected sessions before using it.
- When roughly tempo-matched to musicians/turntables, use Phase Nudge Up/Down for temporary speed corrections rather than replacing the base tempo. These controls can be key/MIDI mapped.
- Warped clips normally Follow the Set. An Arrangement audio clip can Lead via Lead/Follow: its Warp Marker map determines tempo and the clip plays as if unwarped; the global tempo field becomes inactive. If leaders overlap across tracks, the playing leader on the bottom-most track wins.
- Leader transitions create read-only Main tempo automation that moves with the clips. Unfollow Tempo Automation in the tempo field's context menu converts all leaders to followers and makes that automation editable; confirm this Set-wide change before use. Leader automation outranks audio-input Tempo Follower. With EXT enabled, Lead/Follow is unavailable.

## Prepare audio for warping
- Leave Warp off for independently timed one-shots, ambience, speech, or effects when synchronization is unwanted. Enable it for rhythmic loops/songs, then verify the beat map: enabling Warp alone does not prove correct timing. Default Warp Mode is initially Beats.
- In Record, Warp & Launch Settings, Loop/Warp Short Samples offers Unwarped One Shot, Warped One Shot, Warped Loop, or Auto (default). Auto chooses among them; do not assume every short import loops. Auto-Warp Long Samples defaults on and places markers at bar starts; off imports long samples unwarped. No fixed short/long threshold is assumed here.
- Drag samples from local folders, or select an audio track and use Create > Import Audio File… for MP3, AAC, Ogg Vorbis, Ogg FLAC, or FLAC. The destination is the Arrangement insert marker or selected Session slot. First import must finish analysis before playback/editing; wait for the Sample Editor waveform and controls rather than issuing edits prematurely.
- Existing saved sample Warp Markers take precedence over Auto-Warp on import; use a Warp From… command to deliberately reanalyze. Set saves retain markers even without saving sample defaults.

## Place and maintain Warp Markers
- A Warp Marker ties a sample event to musical time. Double-click the Sample Editor's upper half to create one, or use Ctrl-I/Cmd-I at the insert marker; drag/arrows move it. Shift-drag a selected marker to adjust waveform position underneath it rather than simply moving the mapped beat.
- Gray transient marks locate detected attacks; hovering exposes gray pseudo-Warp Markers. Double-click/drag a pseudo-marker to make a real marker. If none exists later, this can change the clip's overall tempo; pin neighboring material when only one event should move. Ctrl/Cmd while promoting a pseudo-marker also adds markers at adjacent transients. Shift-drag the pseudo-marker to relocate the transient itself.
- Create/delete transients via Create or Ctrl-Shift-I/Cmd-Shift-I and Ctrl-Shift-Backspace/Cmd-Shift-Delete. Reset Transients removes manually created transients. Insert Warp Markers (Ctrl-I/Cmd-I) over selected time creates markers on its transients, or at selection boundaries when none exist.
- Double-click a real Warp Marker to remove it, or select its time and Backspace/Delete. To move several markers together, Ctrl/Cmd-select them before dragging. Keep a corrected region pinned at both ends before adjusting later audio.
- For a late/early hit, pin its transient and neighbors, then move only the target to the desired beat. For broad correction, focus the Sample Editor and Quantize (Ctrl-U/Cmd-U); select current grid or a specific division, including triplets, in Quantize and reduce Amount for partial movement. Quantization aligns transients to grid through Warp Markers; inspect groove preservation rather than equating full quantization with correctness.

## Repair short loops and long recordings
| Symptom / material | Procedure | Check / limitation |
| --- | --- | --- |
| Clean 1, 2, 4, 8, or 16-bar loop | Inspect the two boundary markers and estimated BPM; enter known original BPM, or Shift-drag BPM for fine adjustment. | Live initially assumes these common loop lengths; confirm the actual downbeat/end. |
| Exactly double/half the intended tempo | Correct clip BPM with ×2 or ÷2. | These adjust the tempo interpretation, not the Set's tempo. |
| Odd-bar loop | Identify known musical downbeats and map markers to them; reveal a hidden tail by moving the end marker right as needed. | Do not force an odd-length phrase into an even-length estimate. Determine the true end by counting/audition, not an assumed bar number. |
| Leading/trailing padding or unclear cut | Place the insert marker on the first downbeat, Set 1.1.1 Here, then Warp From Here. Place an end marker before unwanted trailing silence and inspect the loop bounds. | Correct timing and region selection are separate; a marker alone is not file cropping. |
| Same-length multitrack clips | Select them together, then add/adjust markers in one. | Changes propagate only under the same-length prerequisite; verify common starts and all tracks before relying on phase alignment. |
| Correct tempo, wrong downbeat | Shift-drag a marker to move waveform beneath it, Set 1.1.1 Here at the downbeat, or create a downbeat marker and move it to bar one. | Use a metronome and inspect later beats too; a correct start does not prove no drift. |
| Seamlessly cut loop with poor auto result | Use Warp Sample as… and inspect the proposed loop length. | The suggestion depends on the Set tempo. |
| Break inside a long recording | Select its time range and use Warp Selection as…. | It estimates length, adds loop boundaries, and warps to fill them; verify its guess. |

- Shift-drag an Arrangement audio clip edge to stretch/compress its tempo when that is the intended operation rather than trimming. For variable-tempo recordings, correct sections from left to right, pinning each correct section's start/end so later work does not move it.
- Warp From Here commands reset markers to the right of the chosen grid position/marker while preserving the left side; if no marker exists at the starting position, the ordinary command creates one. Choose deliberately:

| Command | Choose when |
| --- | --- |
| Warp From Here | Reanalyze the remaining audio automatically. |
| Warp From Here (Start At …) | Give analysis the current Set tempo as a starting estimate. For an unknown recording, temporarily disable Warp, tap to its natural playback, re-enable Warp, then run this command. |
| Warp From Here (Straight) | Source tempo is steady; use one starting marker with the estimated original BPM. |
| Warp … BPM From Here | Source BPM is known exactly; first set the global tempo to it, then use one starting marker with that value. |

## Choose a Warp Mode
| Mode / suitable material | Controls and decisions |
| --- | --- |
| Beats: transient-led drums/rhythmic music | Preserve = Transients follows detected attacks; a beat division imposes fixed boundaries regardless of attacks. Larger divisions plus transposition can deliberately create rhythmic artifacts. |
| Tones: clear monophonic pitch, voice, bass | Grain Size roughly sets average grains; pitch clarity also influences them. Small grains suit distinct pitch changes; larger grains may reduce noise but introduce other artifacts. |
| Texture: ambiguous/polyphonic pitch, pads, noise, drones | Grain Size is independent of pitch analysis; Fluctuation adds random variation. Choose it for texture rather than expecting monophonic pitch tracking. |
| Re-Pitch: coupled speed/pitch | Changes playback rate; twice the speed raises pitch by one octave. Transposition controls are disabled. Use a different mode when tempo must change without pitch. |
| Complex: mixed beats, melody, and texture | A candidate for whole songs/polyphonic mixtures; more CPU demand may require an approved freeze/resample workflow. |
| Complex Pro: similar mixed material | Compare with Complex; it may improve quality, not always. Formants = 100% preserves resonances during transposition; it has no effect without a pitch change. Envelope defaults to 128; try lower for high-pitched material, higher for low-pitched material. |

- In Beats, Transient Loop Mode fills the gap until the next transient: Loop Off plays the segment once then leaves silence; Loop Forward repeats from a zero crossing near its middle; Loop Back-and-Forth alternates toward that crossing and back to the end. The latter can work well when slowing preserved transients.
- Beats Transient Envelope at 100 applies no fade; at 0 segments decay quickly. Higher values sustain/smooth segments; lower values produce gating. Judge clicks and tails at the actual target tempo, not only the original speed.

## Verify and recover
- Before/after checks are verification guidance, not claims of an audition: confirm selected tracks/clips, grid, loop/start/end positions, source file, tempo authority, and whether Session or Arrangement is actually playing. Audition the entry, repeated boundary, middle, and end at the intended tempo; use the metronome for alignment, and inspect the edited region and its neighbors.
- Wrong start: inspect locator/brace Set Song Start Time Here, clip start versus loop start, downbeat markers, and song position. Correct start but later drift: inspect BPM interpretation and subsequent markers rather than moving only the first beat repeatedly.
- Cannot loop: check Warp. Cannot transpose: check Re-Pitch. Missing launch controls: check Arrangement versus Session and audio versus MIDI. Missing fades: expand the audio track or expose handles with `F`. Tempo locked: inspect Lead and EXT. Unchanged imported behavior: inspect saved sample defaults; existing clips do not inherit newly saved defaults.
- Changes appear late: inspect Clip Update Rate and global launch quantization, which serve different purposes. Unexpectedly many edits: check multi-selection, linked tracks, Time commands, shared sample references, and Groove Pool replacement. Silence after stopping a Session clip: use Back to Arrangement if timeline playback is intended.
- Preserve/restore the prior version if boundaries, shared-file scope, or timing become uncertain; do not compensate by guessing more markers. If a required control or algorithm is unavailable in the installed edition/version, report that limitation instead of assuming a tool can reproduce it.
