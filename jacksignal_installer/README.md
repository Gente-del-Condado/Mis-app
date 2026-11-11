# Instalador de JackSignal

Instala o actualiza **JackSignal**, la integración que reproduce avisos, música y voz por la salida de audio local de Home Assistant.

- Panel «Gestionar avisos»: buscador, filtros, vista compacta, copias, edición en bloque y activación sin borrar.
- Sonidos de Alarmo con prioridades y sirena repetitiva.
- Sonidos independientes al abrir y cerrar sensores.
- Texto a voz de sensores, con idioma, voz y prueba previa sin YAML; compatible con Piper local mediante Wyoming.
- Acciones visuales para cualquier automatización.
- Receptor DLNA/UPnP opcional, exclusivamente de audio.

**Instala → Inicia → Comprueba el registro → Reinicia Home Assistant.** Después añade JackSignal en Ajustes → Dispositivos y servicios.

El instalador se detiene cuando termina. No es el reproductor: el audio se ejecuta dentro de Home Assistant. Al actualizar la aplicación debes iniciarla otra vez y reiniciar Home Assistant. El arranque automático está deshabilitado por diseño (`manual_only`).

Requiere Home Assistant OS en aarch64/amd64 y una salida PulseAudio accesible desde Home Assistant. Los sonidos se gestionan en Multimedia y las reglas en la configuración de la integración.

[Instalación y actualización](DOCS.md) · [Guía completa de JackSignal](https://github.com/Gente-del-Condado/jacksignal-ha) · [Cambios](CHANGELOG.md)
