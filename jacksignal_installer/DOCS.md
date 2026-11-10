# JackSignal Installer

## Español

1. Pulsa **Iniciar** y comprueba el **Registro**. El instalador se detiene solo al terminar.
2. Reinicia Home Assistant. Para una primera instalación, ve a **Ajustes → Dispositivos y servicios → Añadir integración → JackSignal**.
3. Para actualizar, instala la nueva versión de esta aplicación, pulsa **Iniciar** de nuevo y reinicia Home Assistant. La configuración de la integración y los sonidos se conservan.

El instalador escribe en `/config/custom_components/jacksignal` y guarda una copia de la versión anterior en `/config/.jacksignal-previous` si actualiza una instalación existente. Puedes dejarlo detenido después de usarlo.

En **JackSignal → Configurar → Ver sonidos asignados** puedes consultar los eventos,
sensores, archivos y prioridades. En **Asignar sonido a un sensor abierto**, elige
el sensor y configura si avisa al impedir armar Alarmo y cuándo avisa al abrir:
nunca, solo con la alarma desarmada o con cualquier estado. Requiere vincular un
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
alerts (never, only while disarmed, or in any alarm state). A linked alarm panel
is required. Existing rules remain failed-arming-only until edited. Opening
alerts require an `off` to `on` transition, not startup or reconnection.
