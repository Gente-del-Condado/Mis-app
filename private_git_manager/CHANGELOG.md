# 0.14.0

- Detecta paquetes nativos de YunoHost en repositorios Git privados.
- Instala con las preguntas del paquete, actualiza desde el commit revisado y desinstala una instancia desde el portal de YunoHost.
- Usa la sesión de administración de YunoHost en el navegador y conserva sus valores predeterminados de copia de seguridad y purga.

# 0.13.0

- Paquete YunoHost con acceso por el portal, servicio sin privilegios y almacenamiento separado.
- Modo catálogo para sincronizar repositorios privados, revisar cambios y consultar la documentación en YunoHost.

# 0.12.0

- Paleta compartida para botones, selectores, navegación, diálogos, estados y pantalla de carga en claro y oscuro.
- Migración de claves, repositorios y estado al almacenamiento que Home Assistant conserva al desinstalar si se deja desmarcado el borrado de configuración.
- Instrucciones para actualizar la instalación existente desde la ficha o la CLI del Supervisor.

# 0.11.1

- Corrige el fondo y el contraste de los avisos del portal y los diálogos en modo claro, oscuro y automático.

# 0.11.0

- Crear una copia local antes de aplicar una actualización. La copia fallida impide aplicar el código nuevo.
- Vista de versión instalada, versión propuesta y changelog, si existe, al revisar una actualización.
- Resumen de aplicaciones nuevas, modificadas y retiradas tras sincronizar.
- Importación de copias .tar de hasta 512 MiB y revisión antes de restaurar.
- Copias locales programadas por aplicación con retención limitada a las copias que creó esa programación.

# 0.10.0

- Descarga de copias desde el gestor: archivo .tar original por streaming, cifrado intacto y sin crear una segunda copia ni cargar el archivo completo en memoria.
- Borrado confirmado desde el gestor, con casilla obligatoria, foco en Cancelar, ubicaciones revisadas, trabajo en segundo plano y comprobación del resultado.
- Advertencia explícita para copias generales: se descarga o borra el archivo completo, aunque contenga otros datos o aplicaciones. La restauración sigue limitada a la aplicación seleccionada.
- Protección ante cambios entre revisión y ejecución; exclusión de Home Assistant Link y ninguna repetición automática ante resultados inciertos.
- Cierre del streaming al terminar, cancelar o fallar; cabeceras de descarga propias sin reenviar credenciales, cookies o nombres arbitrarios del Supervisor.
- Corrección de una carrera de foco que podía desplazar la escritura rápida al cambiar de formulario.
- Pruebas de HTTP y navegador, español/inglés y prefijo Ingress con transferencia real del archivo de prueba.

# 0.9.0

- Nuevo panel Copias de seguridad por aplicación con nombre, fecha, tamaño, ubicación y cifrado, en español e inglés.
- Creación de copias parciales nativas del Supervisor, locales, con nombre y contraseña opcionales; verificación de la copia creada.
- Restauración exclusivamente de la aplicación seleccionada, incluso desde copias generales, con contraseña y consentimiento explícito antes de reemplazar datos.
- Restauración de aplicaciones desinstaladas que conservan su vínculo y código local; versión instalada visible en cada ficha, sin cambiar el checkout Git.
- Trabajos en segundo plano, progreso y eventos traducidos; sin contraseñas en estado, historial o registros, ni repetición automática de operaciones inciertas o interrumpidas.
- Confirmación accesible con foco en Cancelar y pruebas de navegador en español/inglés, móvil, cifrado, contraseña incorrecta y restauración parcial.

# 0.8.0

- Botón Abrir interfaz web para aplicaciones instaladas que declaran Ingress; estado desactivado cuando están detenidas o tienen una operación pendiente.
- Comprobación de disponibilidad, estado y propiedad antes de abrir la aplicación, con mensajes en español e inglés.
- Apertura del panel nativo de Home Assistant fuera del marco del gestor, con autenticación y renovación de sesión gestionadas por Home Assistant.
- Ruta /app/<slug> desde Core 2026.2 y compatibilidad /hassio/ingress/<slug> para versiones anteriores. Funciona sin fijar la aplicación a la barra lateral.
- Sin exponer tokens de Ingress ni abrir puertos directos o destinos externos de webui.
- Pruebas de API y navegador con prefijo Ingress, iframe, ambos idiomas y rutas actuales/anteriores.

# 0.7.0

- Formulario como vista principal de configuración, generado con el esquema UI nativo y las traducciones de cada aplicación que devuelve el Supervisor.
- Campos de texto, contraseñas ocultas, números con límites, casillas, selectores/dispositivos, campos opcionales, grupos y listas anidados con alta y baja de elementos.
- Etiquetas y ayudas nativas con alternativa en inglés; controles de arranque, vigilancia, actualizaciones, puertos, panel y audio.
- YAML como opción avanzada, con conversión segura en ambos sentidos y conservación de los valores no representables y referencias !secret.
- Conservación de valores opcionales por objeto al editar listas; distinción entre valor false y opción ausente; validación nativa de navegador y comprobación final del Supervisor.
- Corrección de valores nulos de audio e Ingress para evitar que bloqueen el guardado y de la selección de idioma durante la carga inicial.
- Nuevas pruebas de navegador ES/EN y API para el formulario nativo, límites, traducciones, listas, opciones opcionales y cambios de vista.

# 0.6.0

- Editor YAML de configuración por aplicación instalada: opciones anidadas, referencias !secret y ajustes nativos de arranque, watchdog, puertos, actualizaciones, panel Ingress y audio.
- Validación preliminar y comprobación del Supervisor al guardar; detección de cambios desde otra ventana, conservación del editor ante errores y confirmación antes de descartar cambios.
- Reinicio opcional tras guardar, limitado a aplicaciones que estén en marcha. Las opciones no se persisten en el estado ni historial del gestor.
- Visor de logs por aplicación: texto seguro, búsqueda, actualización automática cada cinco segundos, pausa, refresco y descarga; límite de 512 KiB y ocultación de valores sensibles conocidos.
- Logs disponibles durante recuperaciones pendientes y lectura privada exclusiva mediante Ingress.
- Interfaz y documentación en español e inglés; pruebas de navegador, API y protección de datos.

# 0.5.0

- Selección del endpoint oficial: actualizar cuando cambia la versión y reconstruir código local cuando mantiene su versión.
- Desinstalación de aplicaciones desde el gestor mediante la API del Supervisor, conservando el código para volver a instalar.
- Borrado combinado: desinstalar y retirar únicamente la copia local de la aplicación seleccionada, sin afectar al resto del catálogo maestro.
- Consentimiento explícito para la pérdida de datos internos; configuración pública `app_config` conservada por defecto y borrado opcional separado.
- Diario persistente de desinstalación, comprobación del resultado real y recuperación tras cortes o reinicios. No hay reintentos destructivos automáticos; un reintento necesita autorización adicional.
- Verificación del ciclo instalar/desinstalar/reinstalar/borrar en español e inglés, del contrato HTTP del Supervisor y de la conservación de otras aplicaciones.

# 0.4.0

- Borrado individual de la copia local de una aplicación, incluida una copia ya desvinculada, sin borrar las demás aplicaciones de un catálogo maestro ni el repositorio Git.
- Revisión de la ruta, consentimiento explícito y comprobación de desinstalación en Home Assistant antes del borrado. Rechazo de carpetas ajenas, enlaces y borrado del propio gestor.
- Ocultación opcional del catálogo persistente entre sincronizaciones y reinicios, con opción de volver a mostrar sin instalar.
- Diario de borrado y recuperación explícita tras fallos o reinicios; limpieza limitada a la carpeta apartada para la aplicación.
- Reinstalación de aplicaciones gestionadas que se habían desinstalado desde Home Assistant; indicación de estado real y controles de ejecución únicamente cuando está instalada.
- Interfaz, registros y documentación actualizados en español e inglés.

# 0.3.0

- Fichas para repositorios individuales y catálogos maestros privados con `repository.yaml`, `.yml` o `.json`.
- Presentaciones README generales y por aplicación, documentación DOCS, tablas, código e iconos locales.
- Búsqueda por nombre de catálogo, mantenedor, resumen y aplicaciones incluidas.
- Navegación entre documentos Markdown e imágenes raster locales mediante Ingress; sin exponer credenciales.
- HTML de origen desactivado, sanitización nativa con alternativa DOMPurify local, sin imágenes externas automáticas ni lectura de rutas privadas.
- Comparación de cambios por aplicación en catálogos: un cambio del README general no marca todas las aplicaciones como actualizables.
- Recuperación de metadatos de presentación en repositorios ya descargados.
- Conserva la corrección 0.2.1 de revisión y adopción de carpetas locales existentes.

# 0.2.1

- Corrección de instalaciones bloqueadas por una carpeta local preexistente: revisión previa con ruta, versión y estado.
- Reutilización de carpetas vacías y adopción explícita de aplicaciones con el mismo slug, sin eliminar la protección de archivos ajenos.
- Verificación de huella de la carpeta tras la revisión y durante la preparación para impedir sobrescribir cambios no confirmados.
- Copia del código anterior durante la operación y recuperación que conserva la carpeta original si falla la adopción.
- Adopción de aplicaciones ya instaladas mediante actualización/reconstrucción; registro de instalaciones idénticas sin reconstrucción innecesaria.
- Diálogo de consentimiento en español e inglés, validación en servidor, foco inicial en Cancelar y pruebas de navegador aisladas.

# 0.2.0

- Interfaz completamente traducida al español y al inglés, tema claro/oscuro/sistema y mejor accesibilidad.
- Identidad visual, icono y logotipo de la aplicación.
- Cola persistente de trabajos y progreso; las operaciones largas no dependen de la conexión Ingress.
- Registros estructurados en español, rotación, filtros, búsqueda y exportación traducida.
- Diario anterior a la sustitución de archivos y recuperación explícita después de desconexiones o reinicios.
- Verificación de versión instalada, commit confirmado y huella de archivos para recuperación.
- Inicio, parada y reinicio; conservación del estado previo después de reconstruir.
- Edición de referencias y sincronización programada por repositorio.
- Validación de paquetes, colisiones de slug, archivos especiales, tamaño y espacio libre.
- Mejor protección de credenciales, errores traducidos y comprobación de salud/watchdog.
- Pruebas con Git SSH/HTTPS reales, rutas Ingress con prefijo y contenedores aislados.

# 0.1.0

- Primera versión: claves SSH, repositorios, detección, instalación y actualización manual.
