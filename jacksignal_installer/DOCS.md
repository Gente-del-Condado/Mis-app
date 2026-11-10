# Usar JackSignal Installer

## Primera instalación

1. Instala esta aplicación desde [Mis-app](https://github.com/Gente-del-Condado/Mis-app).
2. Pulsa **Iniciar** y espera a que el registro confirme la instalación.
3. La aplicación se detiene automáticamente. Reinicia Home Assistant.
4. Abre **Ajustes → Dispositivos y servicios → Añadir integración → JackSignal**.
5. Sube un sonido en **Multimedia → Mis archivos multimedia** y pruébalo desde la configuración de JackSignal.

El audio utiliza FFmpeg y la salida PulseAudio predeterminada de Home Assistant. Comprueba la salida del equipo si quieres usar el jack de la Raspberry Pi.

## Actualizar

Actualiza la aplicación desde la tienda, pulsa **Iniciar**, revisa el registro y reinicia Home Assistant. Actualizar únicamente la aplicación no actualiza el código cargado por Home Assistant.

El instalador escribe en `/config/custom_components/jacksignal` (montado como `/homeassistant` dentro de la aplicación). Conserva los sonidos y los ajustes de la integración. Al sustituir una versión, guarda el código anterior en `/config/.jacksignal-previous`. Si ya está instalada la misma versión, no la vuelve a copiar.

## Arranque manual y diagnóstico

Esta aplicación tiene `startup: once` y `boot: manual_only`. No actives el inicio automático. El error «boot option is set to manual_only so it cannot be changed» corresponde a intentar cambiar esa opción; no implica un fallo de audio. Deja la aplicación detenida después de usarla.

Si la integración no aparece tras reiniciar, comprueba el registro del instalador y después los registros de Home Assistant. No gestiones simultáneamente la misma integración con este instalador y con HACS/Private Git Manager.

## Configurar sonidos y voz

Las reglas se configuran en **JackSignal → Configurar**, dentro de Dispositivos y servicios, no en la aplicación instaladora. Allí puedes vincular Alarmo, asignar sonidos de apertura/cierre, configurar voz de sensores, consultar las asignaciones y activar DLNA de audio.

[Guía completa: sonidos, voz, prioridades, automatizaciones y DLNA](https://github.com/Gente-del-Condado/jacksignal-ha).

## English

Start the installer and check its log. It copies the integration and stops automatically. Restart Home Assistant, then add JackSignal under Devices & services. After each installer update, start it again and restart Home Assistant. Automatic boot is intentionally unsupported. Your settings and media remain intact; previous integration code is backed up in `/config/.jacksignal-previous`.

Configure playback rules in the **JackSignal integration**, not in this installer app. See the full guide linked above for Alarmo, opening/closing sounds, sensor speech and audio-only DLNA.
