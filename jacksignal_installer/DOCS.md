# Usar Instalador de JackSignal

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

Si la integración no aparece tras reiniciar, comprueba el registro del instalador y después los registros de Home Assistant. Usa una sola vía para actualizar JackSignal: este instalador, HACS / Marketplace o la copia manual.

## Alternativa: Marketplace

El repositorio [jacksignal-ha](https://github.com/Gente-del-Condado/jacksignal-ha) instala la integración directamente. En una primera instalación con Home Assistant 2026.11 o posterior puede configurarla sin reiniciar si no se había cargado antes. En actualizaciones, sigue el aviso de Home Assistant. Esto no cambia los pasos de esta aplicación instaladora. Usa una sola vía para gestionar las actualizaciones.

## Configurar sonidos y voz

Las reglas se configuran en **JackSignal → Configurar**, dentro de Dispositivos y servicios, no en la aplicación instaladora. Allí puedes vincular Alarmo, asignar sonidos de apertura/cierre, configurar voz de sensores, consultar las asignaciones y activar DLNA de audio.

[Guía completa: sonidos, voz, prioridades, automatizaciones y DLNA](https://github.com/Gente-del-Condado/jacksignal-ha).


## Envío directo y diagnóstico (0.8.0)

Tras actualizar el instalador, pulsa Iniciar y reinicia Home Assistant. En la integración JackSignal → Configurar aparecen **Enviar audio** (subir archivo, URL o Mis medios, siempre P0) y **Diagnóstico DLNA**. Solo se admite audio. Los archivos válidos de hasta 100 MB quedan en Mis medios/jacksignal; las URLs no se guardan. Detener el envío directo no corta Alarmo. No es necesario activar DLNA para usar el envío directo.

## Panel Gestionar avisos (0.10.0)

Después de actualizar, iniciar el instalador y reiniciar Home Assistant, abre **JackSignal** en la barra lateral con una cuenta administradora. También tienes un enlace en **JackSignal → Configurar → Gestionar avisos**. Si el panel no aparece, recarga la página del navegador. Puedes buscar, filtrar, editar y activar o desactivar avisos sin borrar su configuración. Las pruebas usan P0, sin repetición, y su botón de detener no corta Alarmo. El acceso **Configuración y audio** conserva el resto de herramientas de la integración.

## Mejoras del panel (0.11.0)

El panel añade vista compacta, contadores y estado de reproducción actualizado cada cinco segundos. Selecciona avisos para cambiar activación/prioridad en bloque o usa **Copiar a…** para revisar una copia en otro sensor antes de guardarla. En **Voz**, elige idioma y voz compatibles con el motor, revisa la frase y escúchala antes de guardar. Las pruebas siguen siendo P0.

Para voz local, instala **Piper**, configura una voz española, inicia la aplicación y añade la integración **Wyoming** descubierta. Pulsa **Actualizar** en JackSignal para seleccionar ese motor. Google Translate puede usar **es**; el idioma de la interfaz no determina el de la voz.
