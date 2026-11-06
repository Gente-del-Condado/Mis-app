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
