# Changelog

## 0.8.0

- Add native direct audio upload, HTTP(S) URL and local media forms; valid uploads are retained in My media/jacksignal with unique filenames (100 MB maximum).
- Inspect actual audio streams with FFprobe and reject video, including disguised files; allow embedded album artwork.
- Route direct audio through low-priority playback and scope its stop button to direct playback so Alarmo remains protected.
- Add refreshable DLNA runtime diagnostics with receiver/discovery status, description URL, playback priority and sanitized HTTP activity/errors.
- Add English/Spanish form text, documentation and regression coverage for uploads, rejection, diagnostics and priority handling.

## 0.7.5

- Advertise the installed integration version in the DLNA device description instead of the fixed 0.7.0 value.
- Include the public project URL in DLNA model metadata. Both values now come from the packaged manifest.
- Verify the served device metadata in the DLNA regression suite. Discovery and playback behavior are unchanged.

## 0.7.4

- Automatically publish the individual Marketplace distribution and its immutable version tag from a source push to Forgejo.
- Create GitHub releases from mirrored branches/tags, with version checks and changelog notes.
- Clarify Marketplace first-install configuration without restart, restart notices for loaded integrations, and the separate installer workflow.
- No audio playback or sensor-rule behavior changes.

## 0.7.3

- Group sensor settings into clearly labelled opening and closing fields, each with its own sound and condition.
- Reject enabled opening/closing alerts without a selected sound and explain how to disable or remove a rule.
- Configure opening and closing states independently, including custom values; reject identical or unavailable states.
- Suggest a state pair from a new sensor’s current vocabulary while preserving existing rules and manual overrides.
- Show both configured transitions in the assignment overview. Existing rules keep their previous closing-state interpretation.

## 0.7.2

- Prevent PulseAudio from discarding the end of finite clips: request a 200 ms output buffer and append one second of silence before FFmpeg disconnects.
- Keep the same interruption priorities and uninterrupted repeating sirens; the player may remain active briefly during the silent tail.
- Show the current raw sensor state and allow explicit opening polarity for on/off, true/false and open/closed entities; preserve existing on=open rules.
- Report priority rejection to Media playback callers instead of silently ignoring the request.
- Add debug messages for playback replacement/rejection and sensor conditions to diagnose missing opening/closing alerts without logging audio URLs.
- Add an opt-in regression capturing real FFmpeg output from an isolated PulseAudio null sink for 2- and 20-second clips.

## 0.7.1

- Refresh Spanish/English installation, sound rules, sensor speech, priorities and audio-only DLNA documentation.
- Separate installer instructions from integration configuration and document manual-only startup.
- Add integration documentation/support links, code owner and local brand assets; align HACS and installer metadata with the tested Home Assistant baseline.
- Document the current Forgejo/GitHub publication paths. No playback behavior changes.

## 0.7.0

- Configure sensor speech in native Home Assistant forms: engine, surrounding text, unit and priority, without YAML.
- Add manual, state-change and numeric threshold-crossing triggers, with a minimum interval between alerts.
- Preview without saving, edit/delete saved rules and list them in the assignment overview.
- Expose the saved sensor speech as a visual automation action.
- Ignore unavailable values, startup/recovery transitions and obsolete speech after options change.

## 0.6.0

- Add an independent closing/deactivation sound and condition for each binary sensor.
- Allow always-on sensor rules without linking Alarmo; preserve disarmed-only checks and alarm priorities.
- Keep closing-only rules and show closing assignments in the overview.
- Document arbitrary Home Assistant automation triggers and native TTS announcements with dynamic sensor values.

## 0.5.0

- Add a configuration overview showing assigned and unassigned Alarmo events and opening sensors, with sound, priority, repeat and playback conditions.
- Configure each sensor to announce failed arming and/or opening (only while disarmed or with any alarm state).
- Preserve existing failed-arming-only rules; ignore startup, reconnection and attribute-only sensor changes.
- Keep all sensor playback under the existing priority and critical-siren protection.

## 0.4.0

- Select the listening IPv4 from Home Assistant's visible network interfaces or enter it manually.
- Allow disabling SSDP multicast for manual receivers over routed networks/VPNs.
- Preserve discovery for existing configurations; document VPN routing and sender requirements.

## 0.3.0

- Add an optional audio-only UPnP MediaRenderer, advertised as JackSignal Audio.
- Reuse async-upnp-client for SSDP, device/service descriptions and SOAP actions.
- Add transport, output volume/mute and state event subscriptions for DLNA controllers.
- Validate remote inputs with FFprobe, rejecting video and non-audio resources.
- Route network playback through the existing priority manager and protect alarm audio from remote controls.
- Add LAN address/port configuration, listener cleanup and rollback on configuration failure.
- Test HTTP/SOAP, subscriptions and real audio/video inspection locally.

## 0.2.0

- Apply Alarmo configuration changes without reloading playback.
- Stop obsolete entry/exit announcements when the alarm changes state.
- Add volume and mute controls for the default PulseAudio output.
- Expose current priority and originating alarm event as player attributes.
- Add automated checks using Home Assistant 2026.11 classes and selectors.
- Document the native Google Cast receiver dependency and remaining hardware checks.

## 0.1.0

- Initial JackSignal integration with local playback, Alarmo rules and audio priorities.
- One-shot installer for Home Assistant OS app repositories.
