# Changelog

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
