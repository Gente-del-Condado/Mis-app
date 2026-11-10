# JackSignal Installer

## Voz sin YAML / Speech without YAML (0.7.0)

Ve a **JackSignal → Configurar → Configurar voz de un sensor**. Elige el sensor,
motor TTS, texto antes/después del valor, unidad y prioridad. Decide si hablar
manualmente, al cambiar el valor o al cruzar un umbral. El intervalo mínimo evita
avisos seguidos. Usa **Probar sin guardar** y después **Guardar**. La misma pantalla
permite editar o eliminar la regla. Necesitas un motor TTS configurado previamente.
La acción visual **JackSignal · Decir valor del sensor** permite usar la frase
guardada desde cualquier automatización, sin YAML ni Alarmo.

Open **JackSignal → Configure → Configure sensor speech**. Select the sensor,
TTS engine, text before/after its value, unit and priority. Choose manual,
value-change or threshold-crossing triggers and a minimum alert interval.
Test without saving, then save. Reopen the same sensor to edit or delete its rule.
A configured TTS engine is required. Use the visual **Speak sensor value** action
from any automation to read its current value with the saved phrase and priority.

## Español

1. Pulsa **Iniciar** y comprueba el **Registro**. El instalador se detiene solo al terminar.
2. Reinicia Home Assistant. Para una primera instalación, ve a **Ajustes → Dispositivos y servicios → Añadir integración → JackSignal**.
3. Para actualizar, instala la nueva versión de esta aplicación, pulsa **Iniciar** de nuevo y reinicia Home Assistant. La configuración de la integración y los sonidos se conservan.

El instalador escribe en `/config/custom_components/jacksignal` y guarda una copia de la versión anterior en `/config/.jacksignal-previous` si actualiza una instalación existente. Puedes dejarlo detenido después de usarlo.

En **JackSignal → Configurar → Ver sonidos asignados** puedes consultar los eventos,
sensores, archivos y prioridades. En **Asignar sonido a un sensor abierto**, elige
el sensor y configura si avisa al impedir armar Alarmo y cuándo avisa al abrir:
nunca, solo con la alarma desarmada o con cualquier estado. Solo el modo desarmada y el fallo al armar requieren vincular un
panel en **Vincular Alarmo**. Las asignaciones anteriores siguen avisando solo al
impedir el armado hasta que las edites. Abrir se interpreta como un cambio real
de `off` a `on`; recuperar conexión o iniciar Home Assistant no dispara un aviso.

## English

1. Click **Start** and check the **Log**. The installer stops when it finishes.
2. Restart Home Assistant. For a first installation, go to **Settings → Devices & services → Add integration → JackSignal**.
3. To update, install the new version of this app, click **Start** again, and restart Home Assistant. Your integration settings and audio files are preserved.

The installer writes to `/config/custom_components/jacksignal` and keeps the previous version in `/config/.jacksignal-previous` when upgrading an existing installation. You can leave it stopped after use.

Under **JackSignal → Configure → View sound assignments**, review events, sensors,
files and priorities. Edit a sensor to choose failed-arming alerts and opening
alerts (never, only while disarmed, or in any alarm state). Only disarmed mode and failed arming require a linked alarm panel. Existing rules remain failed-arming-only until edited. Opening
alerts require an `off` to `on` transition, not startup or reconnection.

## Cierre, otros sensores y voz / Closing, other sensors and speech

Desde 0.6.0, el formulario del sensor ofrece **Sonido de cierre / desactivación**
y **Aviso al cerrar / desactivarse**, independientes del aviso de apertura.
Ambos usan la prioridad de la regla. El modo **siempre** funciona sin Alarmo.
Para cualquier evento o sensor numérico, usa una automatización de Home Assistant
con `jacksignal.play_sound`; para leer valores en voz alta usa `tts.speak` con un
motor TTS configurado y `media_player.jacksignal` como destino. La voz entra con
prioridad baja y no interrumpe los avisos de mayor prioridad. Consulta los ejemplos
completos del [README](https://github.com/Gente-del-Condado/jacksignal#sensores-automatizaciones-y-voz).

Since 0.6.0, sensors have independent closing/deactivation audio and conditions.
Always mode works without Alarmo. Use Home Assistant automations with
`jacksignal.play_sound` for any trigger, or `tts.speak` with a configured TTS
engine and the JackSignal media player for dynamic speech. Speech uses low
priority and cannot interrupt higher-priority alerts.
