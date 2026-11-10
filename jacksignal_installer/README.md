# JackSignal Installer

Instala o actualiza **JackSignal**, la integración que reproduce avisos, música y voz por la salida de audio local de Home Assistant.

- Sonidos de Alarmo con prioridades y sirena repetitiva.
- Sonidos independientes al abrir y cerrar sensores.
- Texto a voz de sensores, configurable sin YAML.
- Acciones visuales para cualquier automatización.
- Receptor DLNA/UPnP opcional, exclusivamente de audio.

**Instala → Inicia → Comprueba el registro → Reinicia Home Assistant.** Después añade JackSignal en Ajustes → Dispositivos y servicios.

El instalador se detiene cuando termina. No es el reproductor: el audio se ejecuta dentro de Home Assistant. Al actualizar la aplicación debes iniciarla otra vez y reiniciar Home Assistant. El arranque automático está deshabilitado por diseño (`manual_only`).

Requiere Home Assistant OS en aarch64/amd64 y una salida PulseAudio accesible desde Home Assistant. Los sonidos se gestionan en Multimedia y las reglas en la configuración de la integración.

[Instalación y actualización](DOCS.md) · [Guía completa de JackSignal](https://github.com/Gente-del-Condado/jacksignal-ha) · [Cambios](CHANGELOG.md)

## English

Install or update the JackSignal integration, then click **Start**, check the log and restart Home Assistant. The installer stops when finished. Add JackSignal under Devices & services. Repeat the start/restart steps after each installer update. Playback runs inside Home Assistant and requires FFmpeg and access to the default PulseAudio output.
