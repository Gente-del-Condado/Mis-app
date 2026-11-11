# Historial de versiones

## 0.1.6 — Seguridad del código

- Limitada la complejidad MIME a 128 partes, incluidos contenedores y mensajes anidados. Los correos que exceden el límite quedan fallidos, sin reintentos automáticos ni avisos por ausencia.
- Limitados los fallos de autenticación SMTP por IP y globalmente, incluso entre conexiones nuevas. El rechazo temporal caduca automáticamente.
- Los errores externos dejan de copiarse al historial y a los registros del trabajador; se muestran diagnósticos controlados y traducidos.
- Solo se decodifican JPEG, PNG, GIF, WebP, BMP y TIFF. Se excluyen formatos que pueden invocar intérpretes externos, como EPS/PostScript.
- Corregidos los permisos del directorio de datos, SQLite y token también en instalaciones existentes, sin sustituir sus datos.
- Pruebas de regresión, documentación y catálogos español/inglés actualizados, conservando estructura y contratos de instalación.

## 0.1.5 — Seguridad de imágenes

- Actualizado Pillow de 12.3.0 a 13.0.0 para corregir vulnerabilidades de procesamiento de imágenes, incluidas corrupción de memoria y denegación de servicio.
- El requisito mínimo de Pillow también pasa a 13.0.0: las instalaciones desde fuentes no pueden seleccionar las versiones afectadas.
- Auditoría de las dependencias fijadas en CI y pruebas de compatibilidad de formatos de imagen, orientación EXIF y generación de notificaciones.
- Complemento Home Assistant y paquete YunoHost sincronizados. Se conservan estructura, opciones, identificadores e idiomas.

## 0.1.4

- Manual web en Markdown, con navegación lateral, búsqueda local, temas claro/oscuro, ejemplos y capturas reproducibles del panel con datos ficticios.
- Documentación completa del complemento Home Assistant, generada desde una única fuente: instalación, STARTTLS opcional, puertos, acceso, sensores y actualización.
- Guías de configuración, reglas, notificaciones, RTSP, copias, API, arquitectura, publicación y mantenimiento por programadores o IA.
- Comentarios y docstrings informativos en español; retirada de metadatos de escritorio y actualización de instrucciones antiguas, conservando la estructura de los instaladores.
- Exportación y workflows sin versión fija, capturas permitidas solo mediante manifiesto verificado y sumas públicas actualizables con un comando.
- Manual preparado para publicar en GitHub Pages en el futuro; esta entrega se mantiene en Forgejo.


## 0.1.3 — Español e inglés

- Selector de idioma del panel, independiente del idioma del servicio, con fechas adaptadas y protección de cambios sin guardar al recargar.
- Traducciones del panel, ayudas, errores de API y configuración, respuestas SMTP, registros propios, modelos y pruebas.
- Correos, Telegram e imágenes anotadas utilizan el idioma del servicio; se conservan los textos del usuario y los identificadores de la API.
- Traducciones nativas para opciones del complemento, formularios, errores, entidades y unidades de Home Assistant, sin cambiar identificadores únicos.
- Un catálogo JSON por idioma, descubrimiento automático y herramienta para crear idiomas, generar archivos de Home Assistant y verificar variables y cobertura.
- Se conserva la estructura del repositorio y la compatibilidad con configuraciones existentes, que mantienen español como idioma del servicio.

## 0.1.2 — Nuevo panel y temas

- Navegación lateral con iconos, secciones de monitorización y administración, y menú desplegable en móvil.
- Nueva identidad visual en grafito y verde lima, con tema claro en marfil y verde profundo.
- Selector de apariencia claro, oscuro o del sistema, con preferencia guardada en el navegador.
- Actividad reorganizada con resumen del sistema, contadores, estados diferenciados y guía inicial desplegable.
- Navegación por teclado, foco visible y tablas desplazables en pantallas pequeñas. Se conservan los permisos de consulta y administración.

## 0.1.1 — STARTTLS opcional en Home Assistant

- El certificado, la clave STARTTLS y las IP permitidas sin autenticación pasan a ser opcionales en la configuración del complemento.
- El arranque admite esos campos omitidos, vacíos o nulos y conserva los valores cuando están configurados.
- Las ayudas explican cómo usar SMTP de entrada sin STARTTLS. La autenticación sin cifrado sigue desactivada por defecto.

## 0.1.0 — Primera versión pública

- Recepción de fotos por SMTP y detección local con MobileNet y modelos YOLOX opcionales.
- Reglas por presencia o ausencia de personas, coches y animales.
- Avisos con imágenes por correo y Telegram, cola persistente y reintentos.
- Panel de configuración, pruebas de imágenes y gestión de modelos.
- Cámaras RTSP opcionales, detección de movimiento y avisos.
- Complemento e integración de sensores para Home Assistant.
- Instalador YunoHost con servicio, proxy HTTPS, SMTP con STARTTLS y copia/restauración.
- Repositorio y release únicos con fuentes en src, instaladores organizados por plataforma y documentación pública.
