# HA Private Git Manager · 0.8.0

## Empezar

1. Abre la interfaz mediante **Abrir interfaz web**. En la esquina superior puedes elegir español o inglés.
2. En **Claves SSH**, crea una identidad Ed25519. Registra la clave pública en tu proveedor como clave de despliegue de **solo lectura**.
3. Añade un repositorio con su URL, rama o etiqueta y clave. Para Forgejo con puerto personalizado: `ssh://forgejo@servidor:2233/usuario/repo.git`.
4. Verifica la identidad del servidor: obtiene su huella, compárala por un canal de confianza y pega la huella SHA256 verificada.
5. Guarda y sincroniza. Revisa las aplicaciones detectadas, confirma el commit e instala la deseada.
6. Pulsa **Configurar** para editar sus opciones y **Logs de la aplicación** para revisar su salida. La primera instalación queda detenida; iníciala desde el gestor cuando esté configurada.

Para HTTPS, utiliza una URL sin credenciales y completa usuario/token si es privado. Dejar el token vacío al cambiar credenciales elimina la credencial guardada.

## Leer presentaciones y catálogos privados

Se admiten aplicaciones sueltas y repositorios maestros con `README.md`, `repository.yaml` y varias carpetas de aplicaciones. Verás el tipo, nombre del catálogo, mantenedor, resumen y número de aplicaciones. Puedes buscar por esos datos.

**Ver catálogo** abre la presentación general. **Ver README** muestra la de cada aplicación y **Documentación** abre `DOCS.md`, si existe. Los enlaces Markdown locales y las imágenes PNG/JPEG/GIF/WebP permanecen dentro de Ingress. No hace falta hacer público el repositorio.

El lector formatea Markdown, tablas y bloques de código. El HTML se muestra como texto; las imágenes externas y SVG no se cargan automáticamente. Se bloquean rutas fuera del repositorio, claves, `.git` y enlaces simbólicos. Sincroniza para descargar cambios de documentación.

## Si la carpeta local ya existe

El gestor ocupa `/addons/private_git_manager`; cada aplicación privada se coloca en `/addons/<slug>`. En **0.2.1**, el botón **Instalar** revisa primero esa carpeta. Si está vacía se reutiliza. Si contiene una aplicación con el mismo identificador, revisa su ruta y versión, marca la autorización y pulsa **Adoptar y aplicar**.

La adopción guarda una copia del código anterior durante la operación. Si la aplicación ya estaba instalada, se actualiza/reconstruye en lugar de instalarla dos veces. Una carpeta que contiene otra aplicación o que cambia tras la revisión no se sobrescribe. No necesitas borrarla para resolver una colisión legítima.

## Trabajos y actualizaciones

Las instalaciones y reconstrucciones continúan en segundo plano al cerrar la interfaz. Puedes consultar progreso y resultado en **Registros y actividad**.

Sincronizar descarga cambios sin aplicarlos. **Actualizar / reconstruir** aplica el commit confirmado y conserva el estado de ejecución anterior. En **Editar** puedes programar comprobaciones desde 5 minutos hasta 7 días. `0` significa manual. La programación nunca instala automáticamente.

## Configuración y logs de aplicaciones

**Configurar** abre un formulario generado con el `schema` nativo y las traducciones que entrega el Supervisor para esa aplicación: texto, contraseñas ocultas, casillas, números con límites, selectores/dispositivos y grupos o listas anidados. Reutiliza los nombres y ayudas de `translations/<idioma>.yaml`, con alternativa en inglés.

Puedes añadir o quitar elementos y activar opciones opcionales, conservando la diferencia entre omitir un valor y guardar `false`. Los ajustes disponibles de arranque, watchdog, puertos, actualizaciones, panel Ingress y audio también tienen controles de formulario.

**YAML avanzado** es una opción adicional. Los cambios se conservan al alternar ambas vistas; si el YAML no es válido, permanece visible sin perder el texto. Los valores no representables y las referencias existentes `!secret nombre` se conservan. No necesitas añadir otro formato a tus aplicaciones.

Valida antes de guardar. El Supervisor comprueba las opciones y los ajustes al guardar; los cambios se aplican al próximo inicio. Puedes reiniciar una aplicación que ya esté en marcha. Una aplicación detenida no se inicia sola. Los conflictos y errores conservan el editor, y cerrar con cambios requiere descartarlos explícitamente.

Las opciones no se guardan en el historial, estado ni trabajos del gestor. El envío admite hasta 24.000 caracteres, dentro del límite HTTP de 32 KiB.

**Logs de la aplicación** permite buscar, actualizar cada cinco segundos, pausar, refrescar manualmente y descargar. La salida se muestra como texto, con límite de 512 KiB por lectura; el refresco se pausa al ocultar la página y termina al cerrar. Se ocultan valores sensibles conocidos, aunque no se pueden detectar todos los secretos que una aplicación imprima. Los logs no se almacenan en el gestor y siguen disponibles durante una recuperación pendiente.

## Abrir interfaz web

Las aplicaciones instaladas que declaran `ingress: true` tienen el botón **Abrir interfaz web**. Primero inicia la aplicación; el botón se desactiva mientras esté detenida o tenga una operación pendiente.

El gestor comprueba su estado con el Supervisor y abre el panel de Ingress de Home Assistant fuera del marco del gestor. Home Assistant crea y mantiene la sesión de tu usuario; el gestor no devuelve ni guarda tokens de Ingress y no utiliza puertos directos ni URLs externas de `webui`.

No es necesario fijar la aplicación a la barra lateral. La ruta se adapta a la versión de Core: `/app/<slug>` desde 2026.2 y `/hassio/ingress/<slug>` en las anteriores. Vuelve al gestor con Atrás o la navegación de Home Assistant.

## Recuperación

Una desconexión no demuestra que el Supervisor haya dejado de construir. Si aparece **Recuperación pendiente**, revisa primero sus registros y comprueba que no hay una operación activa.

Después utiliza **Revisar recuperación** para restaurar código anterior o aceptar la versión actual verificada. Se comprueba su versión y la huella de los archivos. Restaurar código no revierte imágenes ni datos; puede ser necesario reconstruir o iniciar desde Home Assistant.

No borres las carpetas ocultas `.pgm-stage-*` o `.pgm-backup-*` mientras haya recuperación pendiente. Si falta una copia verificable, conserva los archivos y recupera manualmente con ayuda del diario `/data/state.json`.

## Claves y repositorios

Para rotar una clave, crea otra, registra la pública, cambia las credenciales y sincroniza antes de revocar la anterior. Las claves y servidores en uso no se pueden eliminar.

**Instalar** y **Desinstalar** funcionan desde este gestor mediante el Supervisor. Desinstalar conserva el código local para instalarlo de nuevo. **Borrar aplicación** elimina únicamente `/addons/<slug>` y su registro; si está instalada, ofrece **Desinstalar y borrar** y exige autorización. También permite borrar copias ya desvinculadas. Las demás aplicaciones del maestro y el repositorio Git se conservan.

Home Assistant elimina los datos internos y las opciones al desinstalar. La carpeta pública `app_config` se conserva por defecto; su borrado requiere marcar una casilla independiente. Revisa el aviso de pérdida de datos antes de confirmar.

La casilla **Ocultar también esta aplicación** evita que siga apareciendo como disponible; la preferencia sobrevive a sincronizaciones y reinicios. **Aplicaciones ocultas → Volver a mostrar** restaura su ficha sin instalarla. Desmarca la casilla al borrar si quieres mantenerla visible.

**Desvincular** solo retira el registro y conserva sus archivos. Solo se pueden eliminar repositorios sin aplicaciones gestionadas. Si un borrado falla, utiliza **Revisar recuperación → Terminar borrado**; conserva las carpetas `.pgm-remove-*` hasta completarlo. Se verifica que el Supervisor haya desinstalado la aplicación antes de borrar sus archivos. Si el resultado es incierto, la recuperación solo comprueba su estado; reintentar exige una autorización adicional y verificar que no hay una operación activa. Un reinicio no repite desinstalaciones.

## Registros y privacidad

Hay búsqueda, filtros por nivel y descarga JSONL. Los registros del contenedor están en español. Se conservan 500 eventos y hasta 100 trabajos terminados, además de registros rotatorios en `/data/manager.log`.

Claves y tokens se almacenan en `/data` con permisos restringidos, sin cifrado adicional. Las copias de seguridad contienen credenciales. No se exportan claves privadas. El acceso web es exclusivo mediante Ingress y no publica un puerto del host.

El gestor necesita el rol `manager` y escritura en `/addons`. Instala solo código en el que confíes. No instala recursos HACS ni convierte repositorios arbitrarios en aplicaciones. No se admiten enlaces simbólicos, aplicaciones anidadas, submódulos o Git LFS; cada paquete debe incluir su Dockerfile o imagen precompilada.

---

## English quick start

Select **EN** in the web UI. Generate an SSH key, register the public key as a read-only deploy key, verify the server fingerprint and add a repository. Sync to detect apps, then confirm the version/commit to install. Use **Configure** to edit options and **App logs** to inspect output before starting the app.

Jobs continue after closing the UI. Scheduled sync only downloads changes. A recovery warning means Supervisor state needs checking before restoring source or accepting a verified current version. Source recovery does not roll back images or app data. Protect app backups: they include credentials.

Use **Install** and **Uninstall** directly in this manager. **Uninstall** keeps source for reinstallation. **Delete app** also offers **Uninstall and delete** when needed. Internal app data/options are deleted on uninstall; public `app_config` is kept unless you explicitly choose to remove it. Other catalog apps and the remote repository are preserved. Optionally hide its listing and restore it later from **Hidden apps → Show again**. **Release** keeps its source folder. Interrupted deletion can be completed through **Review recovery → Finish deletion**.

**Open web interface** opens an installed, running Ingress app through Home Assistant’s native app panel, outside the manager iframe. Home Assistant maintains the user session. No direct ports, external URLs or session tokens are exposed by the manager. Sidebar pinning is not required.
