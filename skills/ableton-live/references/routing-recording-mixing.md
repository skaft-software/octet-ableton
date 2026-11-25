# Routing, recording, mixing, bounce, comping, and stems

## Contents
- [Choose a workflow and establish boundaries](#choose-a-workflow-and-establish-boundaries)
- [Inputs and monitoring](#inputs-and-monitoring)
- [MIDI ports, clocks, and external instruments](#midi-ports-clocks-and-external-instruments)
- [Internal routing and signal taps](#internal-routing-and-signal-taps)
- [Mixer, tracks, groups, and returns](#mixer-tracks-groups-and-returns)
- [Crossfading, cueing, delay, and CPU](#crossfading-cueing-delay-and-cpu)
- [Record into Arrangement or Session](#record-into-arrangement-or-session)
- [Timing, quantization, and recording files](#timing-quantization-and-recording-files)
- [Recover an unrecorded performance with Capture MIDI](#recover-an-unrecorded-performance-with-capture-midi)
- [Bounce or paste rendered audio](#bounce-or-paste-rendered-audio)
- [Build and revise a comp](#build-and-revise-a-comp)
- [Separate stems locally](#separate-stems-locally)
- [Verification and recovery checklist](#verification-and-recovery-checklist)

## Choose a workflow and establish boundaries
These are Live UI procedures, not a promise of extension/API coverage. Confirm the installed edition/build, visible commands, available devices, input/output hardware, and current routing before acting. Availability of Bounce, Stem Separation, External Instrument, and Max for Live must be checked rather than assumed; exact minimum versions and edition entitlements are not specified here.

| Goal | Choose | Important boundary |
| --- | --- | --- |
| Record a new performance | Armed audio/MIDI track in Arrangement or Session | Different from recording Session clip launches into Arrangement. |
| Record processing as audio while playing | Another audio track tapping the source Post FX/Post Mixer | The source track's own input recording does not print its device chain. |
| Capture the current full mix | Audio track with Audio From = Resampling | Includes Main output; the recorder excludes its own output. |
| Commit clips or instruments without real-time performance | Bounce to New Track or Paste Bounced Audio | Individual-track and group bounces use different signal stages. |
| Assemble alternative performances | Arrangement take lanes and comping | Main-lane copies and take-lane originals are independently editable. |
| Extract components of existing audio | Separate Stems | Estimated Vocals/Drums/Bass/Others, not guaranteed isolated originals. |

Preserve source material before replacements, cropping, or cleanup. Prefer new-track operations over in-place replacement unless the user requests replacement. Verification steps below are checks to perform, not reports of completed Live tests.

## Inputs and monitoring
1. Show the mixer and **In/Out** through the bottom-right mixer menu or View → Mixer Controls. In Arrangement, unfold/resize the track if necessary. Each chooser pair uses its upper field for a source/destination type and its lower field for a channel or tap point.
2. Set **Audio From** or **MIDI From** explicitly; do not trust defaults (audio initially uses mono external input 1 or 2; MIDI initially accepts active external inputs). Return tracks receive sends rather than clip-track input selectors. Instruments turn a MIDI track's output into audio; a MIDI track without an instrument outputs MIDI.
3. For hardware audio choose **Ext. In**, then the required mono input or stereo pair. Watch the channel-entry meters for activity/red overload. Use **Configure…** to enable missing channels in Audio Settings and define mono/stereo availability; configure physical outputs through the matching output choosers. Changes apply to every selected track.
4. Rename interface channels in Channel Configuration for reliable identification; Tab advances through names. Names belong to that audio device, not all interfaces. Microphones, guitars, and turntables need suitable preamplification rather than an unamplified line-input connection.

| Monitor | Input heard through devices? | Clip playback / use |
| --- | --- | --- |
| **Auto** | When armed, except while the track plays clips | Ordinary record/playback switching. |
| **In** | Continuously, regardless of arm state | Suppresses that track's clip output; useful for a processing/auxiliary track. Its Activator appears blue. |
| **Off** | No | Use acoustic, external-console, or interface direct monitoring while still recording input; avoids a second delayed monitor path. |

- A Monitor change affects all selected tracks. With In/Out expanded, focus the Monitor control and use Edit → Return to Default (or Delete while that control is focused) to restore **Off for audio**, **Auto for MIDI**; do not confuse those reset values with a recommendation for every session.
- With In/Auto, **Keep Monitoring Latency in Recorded Audio** defaults on: recorded timing follows what is heard through Live. Leave it on for playing through software instruments/effects; turn it off when relying on acoustic/external monitoring. Access the track toggle or the In/Auto context menu; labels may shorten to Keep Monitoring Latency in Recording.
- With Off/direct monitoring, check Audio Settings latency calibration rather than compensating blindly with clip moves. Verify a test recording's placement against the intended timing before committing a session.
- A mono input records a mono file, but the device chain always processes stereo. Mono playback duplicates the signal to L/R; routing stereo to a mono output sums L+R and attenuates the result by **6 dB**. Check the result when collapsing stereo.

## MIDI ports, clocks, and external instruments
Configure ports in Settings → **Link, Tempo & MIDI**. Select a specific input port/channel for isolation, or **All Ins** / **All Channels** for merged inputs; channel-entry meters show activity. Multi-track selections share chooser edits.

| Port switch | Enable input for | Enable output for |
| --- | --- | --- |
| **Track** | Playing/recording notes and MIDI CC | Hardware sound generators, virtual MIDI-bus notes, or CC automation to hardware/apps. A controller without a sound generator usually needs no Track output. |
| **Sync** | Receiving MIDI Clock or MIDI Timecode from another sequencer | Sending MIDI Clock to sequencers, clocked LFOs/arpeggiators, or another DAW. A plain keyboard without sequencing/arpeggiation generally needs neither direction. |
| **Remote** | Custom parameter mappings or mapped clip triggers | LED/motor-fader feedback for mapped controls. This is distinct from note routing. |

- For an enabled Sync output, unfold its options. **MIDI Clock Sync Delay** adjusts outgoing sync timing in milliseconds. **Song** sends Song Position Pointer (SPP) and Continue when playback position changes; **Pattern** instead sends Start at the following bar boundary, useful when a device cannot understand SPP.
- Enable **Resync External Hardware** to expose the Control Bar button for drift recovery. Per-port **Hardware Resync** chooses **Stop and Start** (default), **Start Only** for devices that respond better to it, or **Don't Resync**. Verify the hardware's response rather than resyncing every port indiscriminately.
- To drive a hardware synth, route **MIDI To** to its port and MIDI channel. Alternatively, **External Instrument** combines outgoing MIDI and returning audio on one track. When one keyboard synth supplies both keys and sound, set its **Local Off** so Live routes the notes without a parallel local-trigger path.
- Diagnose missing notes with the Control Bar's three LED pairs: left = sync Clock/Timecode (visible when an external sync source is enabled), middle = remote-control MIDI, right = track MIDI; upper means received, lower means sent. A remote-mapped message is consumed by the mapping and does not reach MIDI tracks.
- Without hardware, enable **Computer MIDI Keyboard** in the Control Bar/Options, or press **M**. The middle letter row starts at C3 on white notes; the upper row supplies black notes. On a US keyboard, **Z/X** move octaves and **C/V** change input velocity in steps of **20**. The C3–C4 middle-row mapping matches Impulse's sample slots.
- Disable Computer MIDI Keyboard when it steals mapped keys; while enabled, add Shift to single-letter shortcuts, e.g. **Shift+S** for solo. Step-recording can also use this keyboard.

## Internal routing and signal taps
Choose direction deliberately: set each source's **To** to one destination for many-to-one submixing/shared instruments; set several receivers' **From** to one source for one-to-many layers or parallel recording. Sending to a bus leaves its input settings alone; tapping a source leaves the source routing intact. Set the receiving track's monitoring appropriately.

| Audio From tap | Includes | Excludes / solo consequence |
| --- | --- | --- |
| **Pre FX** | Raw track signal | Source devices and mixer; soloing the receiver keeps the tapped source available. |
| **Post FX** | Device-chain output | Source mixer level/pan; soloing the receiver keeps the tapped source available. |
| **Post Mixer** | Devices plus track mixer | Soloing the receiver does not preserve the source output automatically; check source solo state if the tap becomes silent. |

- In a many-to-one route, soloing the bus allows its feeder tracks through; soloing one feeder lets that feeder through the bus while other feeders are muted. Do not infer the same solo behavior for a Post Mixer input tap.
- **Instrument/Effect Rack** chains expose Pre FX, Post FX, and Post Mixer taps: respectively at Rack entry before chain devices, after chain devices before its mixer, and after its mixer before chain summing. **Drum Rack** return chains also expose internal routing points. Soloing any such chain-tap receiver keeps that chain output available.

| Task | Procedure and check |
| --- | --- |
| Print wet input | Put effects on a dedicated input track, Monitor **In**. On a second audio track choose source → **Post FX**, Monitor **Off**, arm and record. Use **Post Mixer** only when source fader/pan must be printed too. Confirm only one monitor path is audible. |
| Print a software instrument | Play the instrument on its MIDI track; record its output on an audio receiver. This also suits long evolving single-note sounds from instruments such as Absynth. Confirm whether the chosen tap includes the desired processing. |
| Build a submix | Route source outputs to an audio bus, monitor the bus, and send it to Main; or use a Group Track for automatic routing/folding. A third method is **Sends Only** plus a raised send, making its return the submixer. |
| Share one Simpler/other instrument | Route feeder MIDI tracks to the instrument track, then select the **instrument itself**, not **Track In**, in the channel chooser. This bypasses the destination recording/monitor stage; Track In targets that input stage instead. |
| Independently mute shared-instrument parts | Keep MIDI clips on separate feeders and the instrument on a dedicated container. Muting the instrument track otherwise mutes every part. Set container input to **No Input** when it should not record; its Arm button disappears. |
| Process Impulse slots separately | On an audio receiver select the Impulse track, then one of its **eight** sample-named outputs. Tapping a slot removes it from Impulse's internal sum; do not assume other plug-ins do this. Soloing its receiver keeps that slot audible. |
| Route a multi-timbral plug-in | Host it once; aim each MIDI feeder at that track and the intended part/channel, then tap its individual audio outputs onto audio tracks. Verify MIDI channel and audio-output identity separately. |
| Combine part MIDI/audio in one track | Put **External Instrument** on a feeder, set its first MIDI To to the plug-in host, second to the part's MIDI channel, and Audio From to that part's secondary output. Repeat per part or per Rack chain. Only auxiliary outputs are available here; main outputs stay on the host track. |
| Feed a sidechain | Prefer a built-in device's own sidechain source/tap choosers. Otherwise route a source track's output to the target track and select the effect's sidechain inlet. For a vocoder instrument with an internal carrier, the target is a MIDI track but the sidechain is still audio. |
| Layer instruments from one performance | On the second instrument's MIDI track, tap the first track's **Post FX** MIDI. This is after its MIDI effects but immediately before its instrument, even though that source track ultimately outputs audio. |

For **Resampling**, create an audio track, choose Audio From → Resampling, set the intended Main mix with mute/solo, check Main peak level, arm, and record an empty slot. The recording track's own output is suppressed during capture, so it is excluded. Files go to **Samples/Recorded** in the Project, or the configured Temporary Folder until the Set is saved.

## Mixer, tracks, groups, and returns
- Show the mixer in either view using its bottom-right control; its menu exposes optional components. Arrangement also offers per-track Track Controls. Meters display **peak and RMS output**, switching to input while monitoring; peaks show transients, RMS is a broader level/loudness indication.
- Drag the mixer's upper edge upward for taller meters, tick marks, numeric volume, and resettable peaks; widen a track to add a dB scale. Internal **32-bit floating-point** headroom is not a reason to overload physical I/O, Main, or files being recorded/exported: check these boundaries for clipping.
- Volume changes output gain. Pan's context menu switches **Stereo Pan Mode** (balances the channels by raising one while lowering the other) to **Split Stereo Pan Mode** (positions L/R independently without changing the other channel's level). Double-click Pan or use its reset triangle to restore default; panning is not sonically neutral.
- Turning **Track Activator** off mutes a track's output. **Solo** or S isolates it, subject to routing/return exceptions. **Arm** record-enables it. Selecting multiple tracks makes these edits apply across the selection; differing continuous mixer values retain their relative offsets.
- Normally Solo and Arm are exclusive. Hold **Ctrl (Windows)/Cmd (macOS)** for another solo/arm, select tracks together, or disable **Exclusive Solo/Arm** in Record, Warp & Launch. With Exclusive Arm on, inserting an instrument into a new/empty MIDI track auto-arms it. Arming selects the track; arming a MIDI track also locks a supported control surface to its instrument.
- Create tracks via Create or **Ctrl/Cmd+T** (audio), **Ctrl/Cmd+Shift+T** (MIDI). Loading browser content into empty track space creates the appropriate type; dragging existing clips into empty track space creates a track with their original devices.
- Select title bars for track operations. **Ctrl/Cmd+R**, then Tab, renames successive tracks; a leading **#** makes an automatically updated track number, with extra # characters adding leading zeros. **Edit Info Text** stores track notes.
- Drag headers to reorder and edges to resize. Select adjacent ranges with Shift, or nonadjacent tracks with the platform selection modifier. Dragging a nonadjacent selection collects it into one block; **Ctrl+arrow** moves it without that collapse. Drag a track header into a browser Places folder to save it as a Set; **Collect Files on Export** determines referenced-sample copying.

### Groups and shared effects
1. Select tracks and choose **Group Tracks**; an existing group can be nested. A group holds audio effects and mixer controls, not clips. Members normally route to it automatically, **except existing non-Main custom routes are retained**. Recheck each Audio To; an organizing-only folder can leave members routed elsewhere.
2. Fold/unfold from its header, and move members in/out by dragging. **Ungroup Tracks** returns individual tracks; deleting the group also deletes its members, so it is not an ungrouping substitute.
3. Arrangement shows member-clip overviews. Session group slots launch/stop contained clips for that scene; selecting a group slot selects contained clips. A half-colored group Solo indicates a soloed descendant.
4. **Assign Track Color to Grouped Tracks and Clips** applies group color, but clips change only in the view where the command was invoked (Session or Arrangement).
5. Create shared processing with **Insert Return Track**, put an effect on it, and raise sends from clip/group tracks. Return tracks and the single **Main** track cannot play clips; Main is the default mix destination and processes the summed signal with its own devices. Return visibility is available in Mixer Controls.
6. Set each return's **Pre/Post** switch: **Post** follows source pan, volume, and active state; **Pre** taps before those controls. A Pre return routed to a separate physical output can provide an independent musician monitor mix. Verify mute behavior rather than assuming a muted source is absent from a Pre send.
7. Return-to-return/self sends are disabled by default because feedback can escalate rapidly. **Enable Send/Enable All Sends** exists in a return send's context menu; leave it disabled unless intentional feedback is explicitly requested and controlled.

## Crossfading, cueing, delay, and CPU
- Show **Crossfader** in Mixer Controls. Assign any number of tracks/returns to **A** or **B**, or neither. A is the left side and fades toward the right, B the converse; each is silent at the opposite extreme. With neither assigned, the track is unaffected. Assignments alter gain, **not routing** or output-bus membership.
- Select among **seven curves** in the crossfader context menu. Inspect/audition the chosen response; do not assume every curve has the same center gain or transition shape.
- Map a continuous absolute or incremental MIDI controller to the slider; left/center/right mapping targets also exist. A key mapped to one target toggles the two extremes. Mapping two targets enables snap-back by holding one key while pressing/releasing the other.
- For Arrangement automation, use each track's **Mixer → X-Fade Assign** for assignment and Main's **Mixer → Crossfade** for the fader movement.
- **Solo in Place** (Solo context menu, or Options default) keeps returns audible when a clip track is soloed. Soloing a return mutes other tracks' main outputs while leaving their sends feeding that return. Stereo pan remains in the soloed signal.
- For private cueing, require **four dedicated hardware outputs / two stereo pairs**. Enable them in Audio Settings; set **Main Out** and **Cue Out** to different pairs, switch **Solo/Cue Mode** to Cue, then use headphone-icon Cue switches. Set **Cue Volume** for headphones. The Track Activator still governs Main audibility: cueing alone does not remove a track from the audience mix. Browser previews also use Cue Out.
- Show **Track Delay** through Mixer Controls → Track Options, or Arrangement Track Controls → Track Options. Select **milliseconds or samples**, then delay or pre-delay a track for real-world timing offsets. Do not change it during a performance: discontinuities can click/pop. For Session micro-offsets, use the clip's **Nudge Backward/Forward** controls instead.
- Track Delay differs from automatic device/plug-in delay compensation. Large delays or plug-in latencies can make interaction sluggish; investigate those causes first. Disabling device delay compensation is not the normal fix, and also makes Track Delay unavailable.
- Show **Performance Impact** indicators to locate costly tracks. Their **six rectangles** show relative contribution to the current Set's CPU load, not absolute per-track percentage. Freezing a high-impact track is a reversible CPU-reduction option; verify the resulting load and playback.

## Record into Arrangement or Session
First choose input, monitor path, file settings, and track arm state; confirm signal reaches the expected meter without clipping. Arrangement suits linear/multitrack takes; Session suits separately bounded clips while launching other material.

### Arrangement procedure
1. Position transport and set any loop/punch range. **Punch-In** uses Arrangement Loop start; **Punch-Out** uses its end. Enable either independently to protect material before/after the intended span and allow pre-roll.
2. Press **Arrangement Record**. With **Start Playback with Record** enabled it starts immediately; otherwise press Play or launch Session clips to start. Holding Shift while pressing Arrangement Record temporarily reverses that preference's behavior.
3. All armed tracks receive new clips. Enable **MIDI Arrangement Overdub** only when combining existing MIDI with new notes; it does not overdub audio.
4. Loop recording retains every audio pass; take lanes expose the takes. The recorded sample also contains the full continuous recording: inspect it in Clip View and move the loop/start markers backward to audition earlier passes rather than assuming only the last pass survived.

### Session procedure
1. Choose a Global Quantization other than **None** for grid-aligned clip boundaries; arm the intended tracks. Empty armed slots show Clip Record buttons.
2. **Session Record** records into the selected scene on armed tracks; press again to switch immediately to looping playback. Alternatively click an empty slot's Record, then its Launch to loop. Clip Stop or transport Stop ends playback.
3. A scene launch does **not** normally record empty armed slots. Enable **Start Recording on Scene Launch** only if that behavior is wanted.
4. Map **New** in Key/MIDI Map Mode (it is exposed only there) for successive takes: it stops clips on armed tracks and selects an available recording scene, creating one if needed.
5. For a looping MIDI pattern (e.g. Impulse drums or chromatic Simpler notes), set Global Quantization to **one bar**, choose Record Quantization, double-click an empty MIDI slot, and set its loop length (initially **one bar**). Arm and press Session Record; notes accumulate each loop. Toggle Session Record off to rehearse over playback, on to resume overdubbing. Alt/Option-double-clicking an empty slot also arms and launches it. Undo removes the latest overdub; the MIDI editor remains editable.

### Step entry and hands-free recording
- With transport stopped, arm the MIDI track, enable the MIDI Editor's **Preview**, and place the insertion marker. Hold notes and press **Right** to insert one grid step; keep holding and press Right again to extend them. With those notes still held, **Left** removes the notes just entered. Empty Right steps advance without notes.
- Key/MIDI mappings can target transport, Arrangement Record, Arm, Session Record, New, individual slots, relative scene navigation/track launch, and step navigators. A foot controller can advance steps while both hands play. These are Live mappings, not evidence of an automation endpoint.

## Timing, quantization, and recording files
- Record against existing material or the enabled metronome; changing tempo before, during, or after recording does not replace establishing a useful rhythmic reference. Audio timing/interpretation can later be adjusted with Warp Markers; use the MIDI editor for MIDI note timing.
- Metronome starts with transport or a launched clip. Its level uses **Preview Volume**; open the adjacent menu/context menu for count-in, tick sound, and **Rhythm**. Auto follows the time-signature denominator. Divisions that do not fit a bar are unavailable; a time-signature change that invalidates the selected division temporarily falls back to Auto and restores that division when it fits again.
- **Enable Only While Recording** can show an active metronome during playback but makes it audible only while recording. With Arrangement Punch-In active, it does not sound until the punch-in point; do not expect it to supply audible pre-roll in that configuration.
- Set a count-in other than **None** to delay recording until it finishes. The blue Arrangement Position display counts negative bars/beats/sixteenths up to **1.1.1**; a two-bar count-in starts at **-2.1.1**.
- Choose **Edit → Record Quantization** before normal Session/Arrangement recording; it cannot be changed mid-recording. Arrangement recording stores quantization as a separate Undo step, so Undo can remove quantization without removing the performance.
- Exception: during looped MIDI overdubbing with Clip View Loop enabled, quantization changes apply immediately and are **not independently undoable**. Alternatively record freely and use Quantize afterward.
- Set **File Type**, **Bit Depth**, and a suitable default **Warp Mode** in Record, Warp & Launch before audio recording. Choose based on the material, not an arbitrary universal sound preference.
- Recorded/resampled audio lives in the Project's **Samples/Recorded**. Before saving a new Set it resides in **Temporary Folder**, configured in File/Folder Settings. Check free space there and save the Set to establish its project storage.

## Recover an unrecorded performance with Capture MIDI
Capture listens on **armed or input-monitored MIDI tracks**; it is not audio recovery. After playing, press **Capture MIDI**. Push 1/2 use held Record + New; Push 3 has a dedicated Capture button.

| Set state | Result and next check |
| --- | --- |
| No clips, stopped transport, no tempo automation | Creates clips on monitored MIDI tracks in the **focused view**, detects phrase/loop and tempo, then starts loop playback. Tempo detection is bounded to **80–160 BPM**; manually correct half/double-time interpretations or out-of-range intentions. End on the next bar's downbeat to aid phrase detection. |
| Transport running, any existing clips, or tempo automated | Keeps the existing tempo and infers a loop against it. Playing along on a track with a playing clip, then capturing, adds the new material to that clip as an overdub. |

All played material remains in the clip, including notes before the detected phrase/start marker; inspect and move start/end/loop markers before deciding anything is missing. A first capture consisting of one note uses that note's start/end to derive a **one-, two-, four-, or eight-bar** loop and tempo, useful for a rhythmic sample triggered by one note. Preserve unused material until the chosen phrase is verified.

## Bounce or paste rendered audio
Use bounce for commitment, editing audio, or reducing active processing. Confirm command availability and selection in **both views**, because tracks are shared. Do not assume an individual-track bounce is a mixdown including sends.

| Operation | Result / signal stage |
| --- | --- |
| **Bounce to New Track** | Selected clips/time become audio on separate tracks; source clips/selection are muted. Individual tracks render **post-FX, pre-mixer**: devices are printed without retaining the device chain on the new audio track; source mixer volume/pan/sends become new track settings rather than being baked. A multi-track Arrangement selection creates one audio track per track with selected clips. |
| **Bounce Track in Place** | Replaces the entire source track, including clips in **both Session and Arrangement**, with audio. This replaces older Freeze and Flatten/Flatten commands; preserve the original before deliberately choosing it. |
| **Bounce Group to New Track** | Selected group material becomes a combined audio track and its sources are muted. Group bounce is **post-mixer**, includes group-path effects and sends, and excludes Main-track processing. Audit routing first. |
| **Bounce Group in Place** | Replaces the whole group with its bounced audio track; not a safe substitute for merely hiding or freezing it. |

- Individual commands are in track/clip/selection context menus; **Ctrl/Cmd+B** invokes new-track bounce for the selection. Group commands are in group headers/Session group slots/Arrangement group main lanes as applicable; use the group slot or main lane for group new-track bounce.
- For a new-track bounce, only the selected view's material is rendered; the new shared track appears **empty in the other view**. New tracks/clips add **(Bounce)** to source names (an unnamed clip becomes (Bounce)); track color is inherited. Files go to **Samples/Processed/Bounce** in the Current Project.
- Group signal is collected through its path toward Main, before Main processing. A member routed outside the group is excluded and can make the bounce silent; returns contribute only if their final output reaches Main. Check routing rather than assuming visual membership guarantees inclusion.
- **Paste Bounced Audio** makes variations without repeatedly copying: copy Session clips from one track, Arrangement clips/time, or a group main-lane time selection; then use the destination context command or **Ctrl+Alt+V / Cmd+Option+V** on an audio track, empty MIDI track, or take lane. An empty MIDI destination converts to audio.
- Paste Bounced Audio renders the source's **current state at paste time**, so source edits/effect changes after copying affect later pastes. If the copied source is removed, recopy available material to restore the command. Verify printed processing and source mute state without discarding the original.

## Build and revise a comp
Use take lanes for alternative performances, Arrangement variants, or sample assembly on audio/MIDI tracks. The **main lane** normally plays; take lanes play only while auditioned. They are not additional simultaneously mixed tracks.

1. Show lanes via track-header **Show Take Lanes**, the main-lane toggle, or **Ctrl+Alt+U / Cmd+Option+U**. Left Arrow returns from a take lane to the main lane and folds takes. Automation Mode hides lanes; showing/inserting takes exits that mode.
2. **Insert Take Lane** from Create/header menus or **Shift+Alt+T / Shift+Option+T** adds lanes to selected tracks and reveals existing lanes. Live also supports lane creation/clip insertion through Max for Live's API, but use automation only if separately verified in the host.
3. Arrangement recording automatically creates lanes on armed audio/MIDI tracks. Recording over material or loop passes creates takes; an existing lane is reused if no clip lies after the punch-in point. The newest recording is copied to the main lane for immediate playback. **Theme & Colors → Clip Color → Random** distinguishes takes; otherwise clips inherit track color.
4. Drag audio samples/MIDI files from the browser or Finder/Explorer onto lanes. With multiple samples, hold **Ctrl/Cmd** during dragging to distribute them over sequential tracks.
5. Use the speaker **Audition Take Lane** button or **T**. Only one lane per track auditions, but lanes on different tracks can audition together. A multi-lane selection auditions the last selected lane on each track.
6. Select a take region and press **Enter** or **Copy Selection to Main Lane**. In Draw Mode, click-drag-release a take region to comp in one gesture, or select main-lane time and click the desired take to replace that interval.
7. To compare alternatives for selected clip headers/time, use **Ctrl/Cmd+Up/Down** to replace with previous/next take content; empty lanes are skipped. If selection is in a take lane, selection follows the next/previous take too. With a lane-header selection, the same modifier-arrow combination instead reorders lanes: confirm focus.
8. Main-lane comp clips are independent copies. Editing either main or take content does not edit its counterpart. Take clips support ordinary Arrangement moves/copies/pastes, consolidation, cropping, duplication, and transfer to Session slots; preserve alternates until the comp is approved.
9. Avoid edit clicks with **Create Fades on Clip Edges** in Record, Warp & Launch: adjacent clips get **4 ms crossfades**. For selected clips, **Ctrl+Alt+F / Cmd+Option+F** creates fades manually; check transients and transitions afterward.
10. Source portions used by the comp are highlighted in track color; unused portions are desaturated. Highlights require **matching position and properties** between source and comp. Drag a highlight edge to change the split between adjacent comp parts; missing highlight alone does not prove a take is unused.

Manage lanes with header **Duplicate** / Ctrl/Cmd+D, rename / Ctrl/Cmd+R (Tab/Shift+Tab navigates during renaming), drag to reorder, and edge handles to resize. **Alt/Option +/-** or Alt/Option+mousewheel resizes selected lanes together. Multiple lanes can be renamed together. Cleanup commands include Delete All Take Lanes and Delete All Unused Take Lanes (unused means absent from the current main-lane comp); prefer hiding lanes until preservation is confirmed, since unused alternatives may still be valuable.

## Separate stems locally
Use on mono/stereo recorded audio to extract **Vocals, Drums, Bass, Others**; Others holds material not detected in the first three families. Processing is local, with no internet connection or external tool installation required. Confirm feature availability in the installed edition/build and use material the user is authorized to process.

1. Select a browser audio file or a Session/Arrangement audio clip; use **Separate Stems to New Audio Tracks** from its context menu or Create. Before starting, inspect clip start/end and loop markers: separation includes the audible start–end region, or for a warped loop the start marker through the active loop region.
2. For only an Arrangement interval, make a selection inside the clip and choose **Separate Stems for Time Selection**. This splits the source at the selection boundaries and processes only that portion; retain the original if those splits are undesirable.
3. Enable the wanted families. **Merge to Single Track** is available for **two or three** selected families, not one or all four. Choose **High Speed** or **High Quality**; clicking Separate stops running playback, so do not initiate it during a performance.
4. Multiple separate stems create clips on individual tracks within a new Group Track; one chosen family creates a single track, as does a merged result. Family tracks/clips use dialog-toggle colors; the group uses source track color, and a merged track/clip also uses source track color.
5. With grouped results, source-track effects are copied to the new group rather than printed into stem files; track automation is copied to the group, while clip envelope automation/modulation is copied onto individual stem clips. Verify settings explicitly for single/merged outputs rather than assuming a group exists.
6. The source clip is deactivated to prevent doubling. To compare it, select it and press **0**, while ensuring stems and source are not unintentionally sounding together. Browser separation places results in the focused view; in an empty Set it updates project tempo to the source when sample warping is enabled in Record, Warp & Launch.

| Processing choice | Tradeoff / limits |
| --- | --- |
| **High Speed** | One separation pass for all stems; useful for draft inspection. Older hardware can still take minutes. |
| **High Quality** | Dedicated Vocals, Drums, and Bass passes, then Others from the remainder; higher measured Signal-to-Distortion Ratio at a time cost, not guaranteed artifact-free isolation. Selecting fewer families saves time **only when Others is not included**. |
| Any selection including **Others** in High Quality | Other families must still be processed. For Vocals+Others, Drums/Bass are generated and stored but not added as tracks. |
| Shorter source | Restrict the active/time-selected region; for additional cropping use a preserved copy and **Crop Clip Sample to Time Selection** in Sample Editor or **Crop Clip** from an Arrangement selection (Ctrl/Cmd+Shift+J). |

- Windows and Intel Macs use CPU for separation; Apple-silicon Macs can use GPU. Processing time depends on system configuration; no fixed completion time should be promised.
- Files go to **Samples/Processed/Stems** in the Current Project. Merging stores individual stem files **and** the merged file. Output uses the chosen recording **File Type**, **44.1 kHz** sample rate, and **the source's bit depth** rather than an assumed session bit depth.
- Expect leakage: hi-hat highs may appear in Others and chorused synths in Vocals. Compare the relevant transitions/regions and try the other quality mode if the allocation is unsuitable; do not declare that family toggles guarantee exact instrument isolation. Stems remain ordinary editable/warpable audio clips.

## Verification and recovery checklist
- **No audio:** inspect input/channel activity → monitor mode → device output → Track Activator/solo → destination. In suppresses clips; Off suppresses input monitoring; armed Auto stops monitoring while clips play. Check group custom routes and Post Mixer solo dependencies.
- **MIDI activity but no notes:** distinguish Remote and Track LEDs; inspect consumed mappings, enabled Track ports, channel selection, shared-instrument destination versus Track In, and synth Local Off. Do not compensate by enabling every MIDI switch.
- **Doubled or delayed sound:** identify simultaneous direct/Live monitoring or a source left playing beside its print/stems; set one intended monitor path and verify latency-retention settings before moving recordings.
- **Wrong render:** check individual post-FX/pre-mixer versus group post-mixer versus Main resampling, effects on returns/Main, group exits, selection boundaries, and focused view. Verify output duration, name, routing, clip activation, and file location.
- **Comp seems missing:** show take lanes outside Automation Mode, disable audition to hear the main comp, inspect earlier passes and highlight matching conditions; preserve unused takes instead of cleaning up prematurely.
- **Unexpected clicks, drift, or load:** inspect comp fades, avoid live Track Delay jumps, use appropriate hardware clock/resync settings, and examine Performance Impact. Run a short representative test after changes; report only observed UI, meters, files, and playback results.
