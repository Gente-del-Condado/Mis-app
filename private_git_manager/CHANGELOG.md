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
