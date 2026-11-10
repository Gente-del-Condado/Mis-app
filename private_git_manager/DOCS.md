# HA Private Git Manager

[Manual web con capturas](https://gente-del-condado.github.io/HA-Private-Git-Manager/#home-assistant) · [English quick start](#english-quick-start)

## Instalación y actualización del gestor

Desde Mis-app, instala e inicia **HA Private Git Manager** y abre su interfaz web. Si lo instalas como aplicación local, copia la carpeta completa del paquete a `/addons/private_git_manager`, recarga la tienda con `ha addons reload` y busca el gestor en **Aplicaciones locales**.

Para actualizar una instalación local, haz primero una copia, detén el gestor, reemplaza su carpeta de programa y recarga la tienda. Actualiza y vuelve a iniciar desde su ficha. Si usas la terminal, consulta el identificador con `ha addons list` y usa ese mismo identificador en `ha addons update` y `ha addons start`.

Conserva los datos de configuración al reinstalar. Las versiones actuales usan `/config/private-git-manager` en la carpeta dedicada de la aplicación. Si vienes de una versión anterior a 0.12.0, actualiza antes de desinstalar para que el primer inicio pueda migrar los datos desde `/data`.

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

El gestor ocupa `/addons/private_git_manager`; cada aplicación privada se coloca en `/addons/<slug>`. El botón **Instalar** revisa primero esa carpeta. Si está vacía se reutiliza. Si contiene una aplicación con el mismo identificador, revisa su ruta y versión, marca la autorización y pulsa **Adoptar y aplicar**.

La adopción guarda una copia del código anterior durante la operación. Si la aplicación ya estaba instalada, se actualiza/reconstruye en lugar de instalarla dos veces. Una carpeta que contiene otra aplicación o que cambia tras la revisión no se sobrescribe. No necesitas borrarla para resolver una colisión legítima.

## Slug duplicado y sincronización

El slug está en el campo `slug` de cada manifiesto. Si el error aparece al sincronizar, busca dos manifiestos con el mismo valor en la rama seleccionada. Si solo aparece al instalar, comprueba también las carpetas de `/addons`, incluidas copias antiguas. Conserva el slug de la aplicación instalada y distingue las plantillas de los manifiestos instalables, por ejemplo con `config.yaml.in`.

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

No borres las carpetas ocultas `.pgm-stage-*` o `.pgm-backup-*` mientras haya recuperación pendiente. Si falta una copia verificable, conserva los archivos y recupera manualmente con ayuda del diario `/config/private-git-manager/state.json`.

## Claves y repositorios

Para rotar una clave, crea otra, registra la pública, cambia las credenciales y sincroniza antes de revocar la anterior. Las claves y servidores en uso no se pueden eliminar.

**Instalar** y **Desinstalar** funcionan desde este gestor mediante el Supervisor. Desinstalar conserva el código local para instalarlo de nuevo. **Borrar aplicación** elimina únicamente `/addons/<slug>` y su registro; si está instalada, ofrece **Desinstalar y borrar** y exige autorización. También permite borrar copias ya desvinculadas. Las demás aplicaciones del maestro y el repositorio Git se conservan.

Home Assistant elimina los datos internos y las opciones al desinstalar. La carpeta pública `app_config` se conserva por defecto; su borrado requiere marcar una casilla independiente. Revisa el aviso de pérdida de datos antes de confirmar.

La casilla **Ocultar también esta aplicación** evita que siga apareciendo como disponible; la preferencia sobrevive a sincronizaciones y reinicios. **Aplicaciones ocultas → Volver a mostrar** restaura su ficha sin instalarla. Desmarca la casilla al borrar si quieres mantenerla visible.

**Desvincular** solo retira el registro y conserva sus archivos. Solo se pueden eliminar repositorios sin aplicaciones gestionadas. Si un borrado falla, utiliza **Revisar recuperación → Terminar borrado**; conserva las carpetas `.pgm-remove-*` hasta completarlo. Se verifica que el Supervisor haya desinstalado la aplicación antes de borrar sus archivos. Si el resultado es incierto, la recuperación solo comprueba su estado; reintentar exige una autorización adicional y verificar que no hay una operación activa. Un reinicio no repite desinstalaciones.

## Registros y privacidad

Hay búsqueda, filtros por nivel y descarga JSONL. Los registros del contenedor están en español. Se conservan 500 eventos y hasta 100 trabajos terminados, además de registros rotatorios en `/config/private-git-manager/manager.log`.

Claves y tokens se almacenan en `/config/private-git-manager` con permisos restringidos, sin cifrado adicional. Las copias de seguridad contienen credenciales. No se exportan claves privadas. El acceso web es exclusivo mediante Ingress y no publica un puerto del host.

El gestor necesita el rol `manager` y escritura en `/addons`. Instala solo código en el que confíes. No instala recursos HACS ni convierte repositorios arbitrarios en aplicaciones. No se admiten enlaces simbólicos, aplicaciones anidadas, submódulos o Git LFS; cada paquete debe incluir su Dockerfile o imagen precompilada.

---

## Exportar e importar la configuración del gestor

1. Crea un repositorio privado dedicado en Forgejo o GitHub. En **Repositorios**, conéctalo por SSH y verifica la huella. La clave de despliegue necesita escritura para exportar y solo lectura para importar.
2. Genera un par de claves de recuperación con `age-keygen -o recuperacion-pgm.txt` en un equipo de confianza. Guarda ese archivo fuera de la instalación. Para ver solo la clave pública ejecuta `age-keygen -y recuperacion-pgm.txt`.
3. En **Preferencias → Copia y migración del gestor → Exportar configuración cifrada**, selecciona el repositorio y pega la clave pública `age1…`. El gestor publica el archivo cifrado como una etiqueta `pgm-config-…`.
4. En una instalación nueva, conecta el repositorio de recuperación con una clave de lectura y abre **Importar desde repositorio**. Selecciona una copia, pega la línea `AGE-SECRET-KEY-1…` y revisa las URL antes de confirmar. Configura las credenciales y verifica las huellas antes de sincronizar.

Se exportan nombres, URL, referencias y huellas de origen. Las claves SSH privadas, tokens, datos de aplicaciones y registros quedan fuera. La importación solo añade repositorios y conserva las entradas existentes. Puedes mover un catálogo entre Home Assistant OS y YunoHost.

## Instalar o actualizar integraciones de Core

Abre **Componentes** en el menú del gestor para consultar los catálogos sincronizados, comparar las versiones y filtrar por estado. Desde la ficha de cada integración puedes abrir el README del repositorio, sincronizarlo y revisar el commit antes de instalar o actualizar.

Añade y sincroniza por SSH **Mis-component** o un repositorio con `custom_components/<dominio>/manifest.json` y `__init__.py`. Usa una clave de despliegue de lectura para el catálogo. En la fila de la integración, pulsa **Instalar integración** o **Actualizar integración**, revisa el commit y confirma. Tras finalizar el trabajo, reinicia Home Assistant Core. Usa **Ajustes → Dispositivos y servicios** para configurar una integración nueva.

Supervisor monta la configuración de Core con escritura para habilitar este flujo. Instala código Python solo de repositorios en los que confíes. Una copia existente se conserva antes de reemplazarla, incluso cuando proviene de una instalación manual. La copia queda bajo una carpeta oculta `.pgm-<dominio>-*` en `custom_components`. Para volver a esa versión, detén Core, mueve la carpeta activa aparte, coloca `previous` con el nombre del dominio y vuelve a iniciar Core.

## Copias completas en Forgejo

La integración complementaria **Private Git Manager · Forgejo Backup** añade Forgejo como ubicación de las copias nativas de todo Home Assistant. Configúrala por SSH con una clave de despliegue de escritura para un repositorio privado dedicado a las copias y deja activado el cifrado. Desde el README de ese repositorio puedes consultar las copias recientes y descargar sus fragmentos cifrados sin usar SSH. Consulta la [guía de instalación y recuperación](https://github.com/Gente-del-Condado/HA-Private-Git-Manager/blob/main/FORGEJO_BACKUPS.md).

## Copias de seguridad de cada aplicación

**Copias de seguridad** abre las copias nativas de Home Assistant que contienen esa aplicación: nombre, fecha, tamaño, ubicación y protección con contraseña. También aparecen copias generales o creadas fuera del gestor. La lista se filtra por el identificador exacto de la aplicación.

**Crear copia** guarda los datos y la configuración de la aplicación instalada en el almacenamiento local de copias de Home Assistant. Puedes poner nombre y cifrar con una contraseña opcional, repetida para evitar errores. Sin contraseña se guarda sin cifrar. El Supervisor puede detener temporalmente aplicaciones que requieren copia en frío. Las copias son compatibles con Home Assistant y aparecen también en su listado de copias.

**Restaurar copia** muestra la versión guardada y exige confirmar que se reemplazarán los datos actuales; el foco inicial está en **Cancelar**. Si está cifrada, introduce su contraseña. Se restaura únicamente esa aplicación, incluso al elegir una copia completa con otras aplicaciones y datos de Home Assistant. También puedes restaurar una aplicación desinstalada mientras siga vinculada al gestor y conserve su copia local. La creación de nuevas copias requiere que esté instalada.

La restauración puede detener/reiniciar la aplicación y cambiar su versión instalada, visible en la ficha. Conserva el código Git local y su commit: revisa la versión antes de volver a actualizar o reconstruir. Las carpetas compartidas, Core y otras aplicaciones no se incluyen ni restauran desde estos botones. Las copias disponibles en una ubicación de red se restauran desde esa ubicación; Home Assistant Link (`.cloud_backup`) es exclusivo de Core y no está disponible para el gestor.

Ambas operaciones son trabajos en segundo plano con progreso e historial en español e inglés. Puedes cerrar el gestor mientras terminan. Las contraseñas solo se mantienen en memoria durante la operación y no se guardan en estado, trabajos, logs o almacenamiento del navegador. Guárdalas de forma segura: el gestor no puede recuperarlas. Si se pierde la conexión con el Supervisor, el resultado se marca incierto y no se reintenta automáticamente; actualiza las copias y comprueba el estado antes de repetir. Tras reiniciar el gestor, los trabajos interrumpidos tampoco se repiten.

Estas copias nativas de datos son distintas de las copias temporales de código `.pgm-backup-*` usadas para recuperar instalaciones fallidas.

### Actualizaciones con copia, importación y programación

En la revisión de una aplicación instalada verás la versión actual, la propuesta y el changelog disponible en el repositorio. **Crear copia y actualizar** guarda primero una copia local sin cifrar. Si no se confirma la copia, el gestor detiene la actualización. **Cambios de la última sincronización** agrupa aplicaciones nuevas, modificadas y retiradas del catálogo, incluso si el código cambió con la misma versión.

En **Copias de seguridad → Importar copia** puedes subir un .tar nativo de hasta 512 MiB. El gestor comprueba que contiene la aplicación y lo incorpora al listado del Supervisor. Después se abre la revisión con la versión de la copia y la confirmación habitual de restauración.

En **Programar copias** eliges un intervalo de 1 a 720 horas y cuántas copias conservar, entre 1 y 30. Usa 0 horas para desactivar la programación. La primera copia vence al cumplirse el intervalo y se muestran la próxima fecha y la última copia completada. Las copias automáticas se guardan localmente sin cifrar. Después de una copia correcta, la retención elimina solo copias locales creadas por esa programación.

### Descargar y borrar copias

En **Copias de seguridad**, cada archivo ofrece **Descargar copia** y **Borrar copia**. Ambos permiten revisar nombre, fecha, tamaño, cifrado y si contiene otros datos. **La descarga y el borrado afectan al archivo completo**, también cuando la copia incluye Core, carpetas u otras aplicaciones; la restauración sigue siendo únicamente de la aplicación elegida.

**Descargar copia** entrega el `.tar` original por streaming, conservando su cifrado. No requiere la contraseña ni guarda otro archivo en el gestor. La descarga utiliza la ubicación mostrada; el navegador indica el progreso y permite elegir dónde guardarla. Si se interrumpe, vuelve a descargar el archivo completo: no se ofrecen descargas parciales ni reanudación. El gestor registra el inicio, sin afirmar que la transferencia haya terminado en el navegador.

**Borrar copia** muestra todas las ubicaciones accesibles que se eliminarán, pide marcar una casilla de consentimiento y enfoca inicialmente **Cancelar**. Borra el archivo completo en esas ubicaciones; no desinstala aplicaciones ni altera sus datos actuales. Las copias ya descargadas y Home Assistant Link quedan fuera del borrado. No puede deshacerse. Si cambian los datos revisados o las ubicaciones antes de ejecutar la operación, hay que actualizar y revisar de nuevo.

El borrado se ejecuta en segundo plano y comprueba el resultado. Si no se puede confirmar o queda una eliminación parcial, el gestor lo indica sin reintentar automáticamente. La descarga y el borrado también están disponibles para aplicaciones desinstaladas que conservan su vínculo y código local.

## English quick start

Select **EN** in the web UI. Generate an SSH key, register the public key as a read-only deploy key, verify the server fingerprint and add a repository. Sync to detect apps, then confirm the version/commit to install. Use **Configure** to edit options and **App logs** to inspect output before starting the app.

Jobs continue after closing the UI. Scheduled sync only downloads changes. A recovery warning means Supervisor state needs checking before restoring source or accepting a verified current version. Source recovery does not roll back images or app data. Protect app backups: they include credentials.

Use **Install** and **Uninstall** directly in this manager. **Uninstall** keeps source for reinstallation. **Delete app** also offers **Uninstall and delete** when needed. Internal app data/options are deleted on uninstall; public `app_config` is kept unless you explicitly choose to remove it. Other catalog apps and the remote repository are preserved. Optionally hide its listing and restore it later from **Hidden apps → Show again**. **Release** keeps its source folder. Interrupted deletion can be completed through **Review recovery → Finish deletion**.

**Open web interface** opens an installed, running Ingress app through Home Assistant’s native app panel, outside the manager iframe. Home Assistant maintains the user session. No direct ports, external URLs or session tokens are exposed by the manager. Sidebar pinning is not required.

### App backups / Copias de aplicaciones

**Backups** lists native Home Assistant backups containing the exact app slug, including general backups and backups created outside the manager. It shows name, date, size, location and password protection.

**Create backup** saves the installed app’s data and configuration to Home Assistant local backup storage. Name and encryption password are optional; passwords must be repeated to avoid typos. Without a password the backup is unencrypted. Supervisor may temporarily stop apps requiring cold backups. These native backups are also listed in Home Assistant.

**Restore backup** shows the saved app version and requires explicit consent to replace current data, with initial focus on **Cancel**. Encrypted backups require their password. Only the chosen app is restored, even from a full backup containing Core, folders and other apps. Uninstalled apps can be restored while still linked to the manager with their local source retained; creating a backup requires an installed app.

Restoring can stop/restart the app and change its installed version, shown on its card. Local Git source and commit are retained: review the version before updating or rebuilding again. Shared folders, Core and other apps are never included or restored by these controls. Existing backups on network storage restore from their location. Home Assistant Link (`.cloud_backup`) is exclusive to Core and unavailable here.

Both operations use background jobs with translated progress and history and continue after closing the manager. Passwords are kept only in memory during the operation, never in state, jobs, logs or browser storage; retain them securely because the manager cannot recover them. A lost Supervisor connection produces an uncertain outcome with no automatic retry. Refresh backups and check the app before repeating. Interrupted jobs are never replayed on restart.

These native data backups are separate from temporary `.pgm-backup-*` source trees used for deployment recovery.

### Backup before updating, import and schedules

The update review shows the installed and proposed versions plus the repository changelog when available. **Back up and update** creates a local unencrypted backup first. The update stops if the backup cannot be confirmed. **Changes from the last sync** groups added, changed and removed apps, including source changes with the same version.

Use **Backups → Import backup** to upload a native .tar archive up to 512 MiB. The manager checks that the archive contains the selected app and imports it into Supervisor. The restore review then shows its version and asks for the usual confirmation.

In **Schedule backups**, choose a 1–720 hour interval and keep 1–30 backups. Enter 0 hours to disable the schedule. The first backup becomes due after the interval. The next due time and last successful backup appear in the form. Scheduled copies are stored locally without encryption. After a successful backup, retention removes only local copies created by that schedule.

### Download and delete backups

Each backup offers **Download backup** and **Delete backup**, with a review of its name, date, size, encryption and whether it contains other data. **Both actions affect the whole archive**, including Core, folders or other apps in a general backup. Restore remains limited to the chosen app.

**Download backup** streams the original `.tar` archive from the displayed location, preserving encryption and requiring no password. No second archive is stored in the manager. Your browser handles progress and destination. Interrupted downloads must restart from the beginning; partial downloads and resuming are not offered. The manager records download start, without claiming completion in your browser.

**Delete backup** shows all accessible locations to remove, requires a consent checkbox and initially focuses **Cancel**. It deletes the whole archive from those locations, keeping installed apps and their current data. Downloaded copies and Home Assistant Link are excluded. Deletion cannot be undone. If reviewed metadata or locations change before execution, refresh and review again.

Deletion runs in the background and verifies the result. Unconfirmed or partial deletion is reported with no automatic retry. Downloading and deleting remain available for uninstalled apps that retain their manager link and local source.
