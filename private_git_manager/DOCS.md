# HA Private Git Manager · 0.4.0

## Empezar

1. Abre la interfaz mediante **Abrir interfaz web**. En la esquina superior puedes elegir español o inglés.
2. En **Claves SSH**, crea una identidad Ed25519. Registra la clave pública en tu proveedor como clave de despliegue de **solo lectura**.
3. Añade un repositorio con su URL, rama o etiqueta y clave. Para Forgejo con puerto personalizado: `ssh://forgejo@servidor:2233/usuario/repo.git`.
4. Verifica la identidad del servidor: obtiene su huella, compárala por un canal de confianza y pega la huella SHA256 verificada.
5. Guarda y sincroniza. Revisa las aplicaciones detectadas, confirma el commit e instala la deseada.
6. Configura sus opciones desde Home Assistant. La primera instalación queda detenida; iníciala cuando esté configurada.

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

## Recuperación

Una desconexión no demuestra que el Supervisor haya dejado de construir. Si aparece **Recuperación pendiente**, revisa primero sus registros y comprueba que no hay una operación activa.

Después utiliza **Revisar recuperación** para restaurar código anterior o aceptar la versión actual verificada. Se comprueba su versión y la huella de los archivos. Restaurar código no revierte imágenes ni datos; puede ser necesario reconstruir o iniciar desde Home Assistant.

No borres las carpetas ocultas `.pgm-stage-*` o `.pgm-backup-*` mientras haya recuperación pendiente. Si falta una copia verificable, conserva los archivos y recupera manualmente con ayuda del diario `/data/state.json`.

## Claves y repositorios

Para rotar una clave, crea otra, registra la pública, cambia las credenciales y sincroniza antes de revocar la anterior. Las claves y servidores en uso no se pueden eliminar.

Desinstala primero la aplicación desde Home Assistant. **Borrar aplicación** elimina únicamente su carpeta local `/addons/<slug>` y su registro, después de revisar la ruta y confirmar. También permite borrar copias ya desvinculadas. Las demás aplicaciones del maestro y el repositorio Git se conservan.

La casilla **Ocultar también esta aplicación** evita que siga apareciendo como disponible; la preferencia sobrevive a sincronizaciones y reinicios. **Aplicaciones ocultas → Volver a mostrar** restaura su ficha sin instalarla. Desmarca la casilla al borrar si quieres mantenerla visible.

**Desvincular** solo retira el registro y conserva sus archivos. Solo se pueden eliminar repositorios sin aplicaciones gestionadas. Si un borrado falla, utiliza **Revisar recuperación → Terminar borrado**; conserva las carpetas `.pgm-remove-*` hasta completarlo. Se comprueba el Supervisor antes de borrar, y no se borran aplicaciones instaladas.

## Registros y privacidad

Hay búsqueda, filtros por nivel y descarga JSONL. Los registros del contenedor están en español. Se conservan 500 eventos y hasta 100 trabajos terminados, además de registros rotatorios en `/data/manager.log`.

Claves y tokens se almacenan en `/data` con permisos restringidos, sin cifrado adicional. Las copias de seguridad contienen credenciales. No se exportan claves privadas. El acceso web es exclusivo mediante Ingress y no publica un puerto del host.

El gestor necesita el rol `manager` y escritura en `/addons`. Instala solo código en el que confíes. No instala recursos HACS ni convierte repositorios arbitrarios en aplicaciones. No se admiten enlaces simbólicos, aplicaciones anidadas, submódulos o Git LFS; cada paquete debe incluir su Dockerfile o imagen precompilada.

---

## English quick start

Select **EN** in the web UI. Generate an SSH key, register the public key as a read-only deploy key, verify the server fingerprint and add a repository. Sync to detect apps, then confirm the version/commit to install. Configure options in Home Assistant before starting the app.

Jobs continue after closing the UI. Scheduled sync only downloads changes. A recovery warning means Supervisor state needs checking before restoring source or accepting a verified current version. Source recovery does not roll back images or app data. Protect app backups: they include credentials.

To remove one app: uninstall it in Home Assistant, then use **Delete app**. Other catalog apps and the remote repository are preserved. Optionally hide its listing and restore it later from **Hidden apps → Show again**. **Release** keeps its source folder. Interrupted deletion can be completed through **Review recovery → Finish deletion**.
