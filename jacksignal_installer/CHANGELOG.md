# Historial de cambios

## 0.14.1

- Propuestas editables de voz según el tipo de sensor binario: abierta/cerrada, encendido/apagado y otras equivalencias según su clase en Home Assistant.
- Se proponen al abrir el editor si aún no hay equivalencias guardadas; solo se aplican al guardar. Se conservan los textos personalizados y las listas vacías guardadas.
- Botón para añadir las sugerencias que faltan sin reemplazar las existentes. Los tipos desconocidos y sensores numéricos siguen siendo manuales.
- Sin cambios en los estados detectados, disparadores ni prioridades de Alarmo.

## 0.14.0

- Equivalencias de voz por aviso desde el panel: estado detectado → texto pronunciado, sin YAML (por ejemplo, on → abierta y off → cerrada).
- Editor con añadir/eliminar, vista previa de la frase y equivalencias visibles en las tarjetas. Hasta 32 estados por aviso, con validación de campos y duplicados.
- Los estados sin equivalencia conservan su lectura original. Los disparadores, umbrales, prioridades de Alarmo y avisos anteriores mantienen su comportamiento.
- La edición nativa, las copias y los ajustes generales de voz conservan las equivalencias.

## 0.13.0

- Configuración general de motor, idioma, voz y velocidad, con propuesta de Piper cuando hay un único motor Wyoming Piper conectado.
- Los nuevos avisos del panel heredan la voz general; los existentes conservan sus valores salvo que se marque «Aplicar a todos». Cada aviso admite personalización independiente y mantiene texto, condiciones y prioridad.
- Preparación de Piper con confirmación para administradores con Supervisor: instala la aplicación oficial si falta, configura es_ES-davefx-medium e inicio automático y la inicia. Conserva la configuración de instalaciones existentes.
- Avisos de progreso y errores, enlaces para revisar Piper y completar Wyoming; no se instala automáticamente al cargar la integración.
- Pruebas de herencia, excepciones, validación, prioridades y preparación de Piper simulada. Pendiente validar la instalación en Home Assistant OS real.

## 0.12.1

- El idioma automático de los avisos de voz prefiere español de España, español genérico u otra variante española compatible, en ese orden; si el motor no ofrece español, utiliza su idioma predeterminado.
- La voz automática corresponde al idioma efectivo, también en Piper. Se utiliza el código exacto anunciado por el motor (`es_ES`, `es-ES`, `es`, etc.).
- Se respetan los idiomas y voces seleccionados explícitamente; las reglas antiguas sin selección explícita también usan la nueva preferencia española.
- El panel muestra el idioma automático efectivo y permite cambiarlo por aviso. Las prioridades y velocidades se conservan.

## 0.12.0

- Velocidad de voz independiente por aviso, configurable desde el panel sin YAML, entre 0,5× y 2×; la tarjeta muestra la selección.
- La prueba previa usa la velocidad del borrador y mantiene P0; los avisos automáticos conservan su prioridad y la protección de Alarmo.
- Ajuste de tempo conservando el tono, compatible con Piper y otros motores TTS, sin cambiar la velocidad global del motor ni otros sonidos.
- Reglas existentes a 1×; las copias, la desactivación y la edición desde el formulario nativo conservan el ajuste.
- Validación del rango en el servidor y pruebas de duración, tono, persistencia y prioridades.

## 0.11.0

- Voz: selección de idioma y voz según las capacidades del motor, frase con valor del sensor y escucha del borrador sin guardar. Las reglas antiguas conservan sus valores predeterminados.
- Ayuda en español para instalar Piper local mediante Wyoming y corregir el idioma de Google Translate.
- Panel con vista compacta, contadores y estado de reproducción actualizado cada cinco segundos mientras está visible.
- Selección de hasta 200 avisos para modificar activación o prioridad con validación conjunta y protección contra cambios concurrentes.
- Copia de avisos de sensor o voz con revisión antes de guardar; comienza desactivada y conserva los estados de apertura/cierre del destino.
- Las pruebas mantienen P0, sin repetición, y su parada solo afecta a la prueba del panel.

## 0.10.0

- Nuevo panel «Gestionar avisos» en la barra lateral, en español y para administradores, con secciones de Sensores, Alarmo y Voz.
- Buscador sin distinción de tildes, filtros por configuración y activación, edición directa y resultados paginados.
- Activación y desactivación persistentes sin borrar sonidos, condiciones ni frases; compatibilidad con las reglas existentes y los formularios tradicionales.
- Pruebas manuales con prioridad baja, sin repetición, y detención limitada al audio de prueba para proteger los avisos de Alarmo.
- Validación de cada sonido de apertura y cierre, control de cambios concurrentes y selección de archivos locales sin salir del editor.
- Pruebas de permisos, conservación de reglas, desactivación y prioridades, y revisión visual con datos simulados en escritorio y móvil.

## 0.9.0

- Nombre DLNA configurable por instalación, con validación de 1 a 64 caracteres y conservación de la identidad del receptor.
- El diagnóstico muestra el nombre anunciado; las instalaciones anteriores conservan JackSignal Audio.
- Añadida una guía de pruebas de diagnóstico, archivos, URLs y prioridades de Alarmo, con aclaraciones sobre varias estancias.
- Sin cambios en la política de prioridades ni en la reproducción de audio.

## 0.8.2

- Simplificadas las instrucciones de instalación: tienda Mis-app, HACS / Marketplace mediante jacksignal-ha o copia manual.
- Retiradas las referencias a gestores externos de las guías de JackSignal para evitar confundirlos con requisitos del reproductor.
- Sin cambios en el audio, las prioridades ni la sincronización de los catálogos.

## 0.8.1

- Unificada en español la documentación del proyecto, la ayuda del instalador y el historial de cambios.
- Traducidos el nombre y la descripción del instalador, sus mensajes y la descripción del receptor DLNA.
- Las nuevas publicaciones automáticas incluyen sus notas en español.
- Sin cambios en la reproducción, las prioridades ni las reglas de Alarmo.

## 0.8.0

- Añadidos formularios nativos para subir audio, reproducir una URL HTTP(S) o elegir archivos locales. Los archivos válidos se conservan en Mis medios/jacksignal con nombres únicos y un límite de 100 MB.
- Validación del contenido con FFprobe: se rechazan vídeos, incluidos los disfrazados de audio, y se permiten portadas de álbum.
- El envío directo usa prioridad baja y su botón de detener solo afecta a esa reproducción, para proteger Alarmo.
- Añadido un diagnóstico DLNA actualizable con estado del receptor, descubrimiento, URL de descripción, prioridad y actividad HTTP sin credenciales ni URLs de audio.
- Añadidos textos de interfaz, documentación y pruebas para las subidas, la validación, el diagnóstico y las prioridades.

## 0.7.5

- La descripción DLNA anuncia la versión instalada de la integración en lugar del valor fijo 0.7.0.
- Incluido el enlace público del proyecto en los metadatos DLNA. Ambos valores se obtienen del manifiesto.
- Verificados los metadatos servidos mediante pruebas DLNA, sin cambios en descubrimiento ni reproducción.

## 0.7.4

- Publicación automática de la distribución individual para Marketplace y de su etiqueta de versión inmutable al subir cambios a Forgejo.
- Creación de publicaciones en GitHub a partir de las ramas y etiquetas replicadas, con comprobaciones de versión y notas de cambios.
- Aclaradas la primera instalación sin reinicio en Marketplace, los avisos de reinicio y la vía independiente del instalador.
- Sin cambios en reproducción ni reglas de sensores.

## 0.7.3

- Formularios de sensores con secciones claras de apertura y cierre, cada una con su sonido y condición.
- Validación de avisos activados sin sonido e instrucciones para desactivar o eliminar reglas.
- Estados de apertura y cierre independientes, incluidos valores personalizados; se rechazan estados iguales o no disponibles.
- Sugerencia automática de estados para sensores nuevos, conservando las configuraciones existentes y los ajustes manuales.
- El resumen muestra ambas transiciones configuradas. Las reglas existentes mantienen su interpretación del cierre.

## 0.7.2

- Evitado que PulseAudio descarte el final de los sonidos: búfer de salida de 200 ms y un segundo de silencio antes de desconectar FFmpeg.
- Conservadas las prioridades y las sirenas repetitivas sin pausas entre repeticiones; el reproductor puede permanecer activo durante el silencio final.
- Visualización del estado interno del sensor y selección de polaridad para on/off, true/false y open/closed, conservando las reglas anteriores.
- Los intentos de reproducción desde Multimedia informan del rechazo por prioridad.
- Añadidos mensajes de depuración para interrupciones y condiciones de sensores, sin registrar URLs de audio.
- Añadida una prueba opcional con FFmpeg y una salida nula aislada de PulseAudio para clips de 2 y 20 segundos.

## 0.7.1

- Actualizada la documentación de instalación, reglas de sonidos, voz, prioridades y DLNA exclusivo de audio.
- Separadas las instrucciones del instalador y la integración; documentado el arranque manual.
- Añadidos enlaces de documentación y soporte, responsable del código y recursos gráficos; alineados los metadatos de HACS y del instalador con la versión de Home Assistant probada.
- Documentadas las rutas de publicación entre Forgejo y GitHub, sin cambios en reproducción.

## 0.7.0

- Configuración de voz de sensores con formularios nativos: motor, texto anterior y posterior, unidad y prioridad, sin YAML.
- Disparadores manuales, por cambio de estado y por cruce de umbral, con intervalo mínimo entre avisos.
- Prueba sin guardar, edición y eliminación de reglas y visualización en el resumen de asignaciones.
- Acción visual de automatización para leer el sensor con su configuración guardada.
- Se ignoran valores no disponibles, transiciones de inicio o recuperación y avisos obsoletos tras cambiar opciones.

## 0.6.0

- Sonido y condición de cierre o desactivación independientes para cada sensor binario.
- Reglas que funcionan siempre sin vincular Alarmo, conservando las condiciones de alarma desarmada y las prioridades.
- Conservadas las reglas de solo cierre y mostradas en el resumen.
- Documentadas las automatizaciones de Home Assistant y los anuncios de voz con valores dinámicos.

## 0.5.0

- Resumen de eventos de Alarmo y sensores con y sin sonido, prioridad, repetición y condiciones de reproducción.
- Configuración de avisos por fallo al armar y por apertura, con alarma desarmada o en cualquier estado.
- Conservadas las reglas anteriores de fallo al armar; se ignoran inicio, reconexión y cambios únicamente de atributos.
- Todos los avisos de sensores respetan las prioridades y la protección de la sirena crítica.

## 0.4.0

- Selección de la IPv4 entre las interfaces visibles para Home Assistant o introducción manual.
- Opción para desactivar SSDP multicast y usar receptores manuales mediante redes enrutadas o VPN.
- Conservado el descubrimiento de las configuraciones existentes; documentados los requisitos de rutas y emisores para VPN.

## 0.3.0

- Receptor UPnP MediaRenderer opcional y exclusivo de audio, anunciado como JackSignal Audio.
- Uso de async-upnp-client para SSDP, descripciones de dispositivos y servicios y acciones SOAP.
- Controles de reproducción, volumen, silencio y suscripciones a cambios de estado para emisores DLNA.
- Validación de entradas remotas con FFprobe, rechazando vídeos y recursos sin audio.
- Reproducción de red mediante el gestor de prioridades y protección de Alarmo frente a controles remotos.
- Configuración de dirección y puerto, liberación de conexiones y recuperación de la configuración anterior si falla el arranque.
- Pruebas locales de HTTP/SOAP, suscripciones y validación real de audio y vídeo.

## 0.2.0

- Aplicación de cambios de Alarmo sin recargar la reproducción.
- Detención de avisos de entrada o salida obsoletos cuando cambia el estado de la alarma.
- Controles de volumen y silencio para la salida PulseAudio predeterminada.
- Prioridad y evento de alarma de origen disponibles como atributos del reproductor.
- Pruebas automáticas con clases y selectores de Home Assistant 2026.11.
- Documentada la dependencia de un receptor nativo para Google Cast y las comprobaciones físicas pendientes.

## 0.1.0

- Primera integración JackSignal con reproducción local, reglas de Alarmo y prioridades de audio.
- Instalador de ejecución puntual para repositorios de aplicaciones de Home Assistant OS.
