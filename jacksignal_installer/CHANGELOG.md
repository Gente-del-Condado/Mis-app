# Changelog

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
