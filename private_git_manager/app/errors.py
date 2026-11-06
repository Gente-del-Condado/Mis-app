"""Error identifiers shared with both UI languages; messages never include secrets."""

ERRORS = {
    "Identificador no válido.": ("invalid_identifier", "Invalid identifier."),
    "URL no válida.": ("invalid_url", "Invalid URL."),
    "Solo se permiten conexiones SSH o HTTPS.": (
        "invalid_transport",
        "Only SSH and HTTPS connections are allowed.",
    ),
    "Nombre de servidor no válido (usa un nombre DNS o IPv4).": (
        "invalid_host",
        "Invalid server name. Use a DNS name or IP address.",
    ),
    "No incluyas contraseñas, tokens, consultas ni fragmentos en la URL.": (
        "url_credentials",
        "Do not include passwords, tokens, queries or fragments in the URL.",
    ),
    "Introduce el token en el campo de credenciales, nunca en la URL.": (
        "url_credentials",
        "Enter the token in the credentials field, never in the URL.",
    ),
    "La URL SSH debe incluir un usuario válido.": (
        "ssh_user",
        "The SSH URL must include a valid username.",
    ),
    "Falta la ruta del repositorio o el puerto es incorrecto.": (
        "url_path",
        "Repository path is missing or the port is invalid.",
    ),
    "Rama o etiqueta no válida.": ("invalid_ref", "Invalid branch or tag."),
    "La clave de host debe ser Ed25519.": (
        "host_algorithm",
        "The server host key must be Ed25519.",
    ),
    "Utiliza ssh://usuario@servidor:puerto/propietario/repo.git o HTTPS.": (
        "ssh_url",
        "Use ssh://user@server:port/owner/repo.git or HTTPS.",
    ),
    "URL SSH no válida.": ("ssh_url", "Invalid SSH URL."),
    "Puerto no válido.": ("invalid_port", "Invalid port."),
    "Clave de host no válida.": ("invalid_host_key", "Invalid server host key."),
    "Escribe un nombre de clave de hasta 80 caracteres.": (
        "invalid_name",
        "Enter a valid name up to 80 characters.",
    ),
    "Clave no encontrada.": ("key_missing", "Key not found."),
    "La clave está en uso. Cambia la clave de los repositorios antes de eliminarla.": (
        "key_in_use",
        "The key is in use. Change repository credentials before deleting it.",
    ),
    "La verificación de clave de host solo se utiliza con SSH.": (
        "ssh_only",
        "Host key verification is only used for SSH.",
    ),
    "El servidor no devuelve una clave Ed25519.": (
        "host_key_missing",
        "The server did not return an Ed25519 key.",
    ),
    "La clave no corresponde al servidor y puerto seleccionados.": (
        "host_key_marker",
        "The key does not match the selected server and port.",
    ),
    "La huella introducida no coincide con la clave del servidor.": (
        "fingerprint_mismatch",
        "The entered fingerprint does not match the server key.",
    ),
    "Escribe un nombre de repositorio de hasta 80 caracteres.": (
        "invalid_name",
        "Enter a valid name up to 80 characters.",
    ),
    "Repositorio no encontrado.": ("repo_missing", "Repository not found."),
    "Sincroniza el repositorio y selecciona una aplicación detectada.": (
        "sync_required",
        "Sync the repository and select a detected app.",
    ),
    "Otra fuente gestiona una aplicación con este slug.": (
        "slug_owned",
        "Another repository manages an app with this slug.",
    ),
    "La carpeta local ya existe y no pertenece a este gestor.": (
        "folder_owned",
        "The local folder already exists and does not belong to this manager.",
    ),
    "Utiliza Actualizar para aplicaciones ya gestionadas; Instalar para nuevas.": (
        "wrong_action",
        "Use Update for managed apps and Install for new apps.",
    ),
    "El estado instalado no coincide. Revisa la aplicación en Home Assistant.": (
        "installed_mismatch",
        "Installed state does not match. Review the app in Home Assistant.",
    ),
    "Ruta de aplicación fuera del repositorio.": (
        "unsafe_path",
        "The app path is outside the repository.",
    ),
    "No hay una recuperación pendiente para esta aplicación.": (
        "no_recovery",
        "This app has no pending recovery.",
    ),
    "Esta aplicación no está gestionada aquí.": ("unmanaged", "This app is not managed here."),
    "Acción no permitida.": ("invalid_action", "Action is not allowed."),
    "No se puede desvincular esta aplicación; revisa si tiene una recuperación pendiente.": (
        "release_blocked",
        "Cannot release this app. Check whether recovery is pending.",
    ),
    "Escribe un nombre válido de hasta 80 caracteres.": (
        "invalid_name",
        "Enter a valid name up to 80 characters.",
    ),
    "El intervalo debe ser 0 o estar entre 300 y 604800 segundos.": (
        "invalid_interval",
        "The interval must be 0 or between 5 minutes and 7 days.",
    ),
    "Servidor no encontrado.": ("host_missing", "Server not found."),
    "El repositorio tiene aplicaciones gestionadas y no se puede eliminar.": (
        "repo_in_use",
        "This repository has managed apps and cannot be removed.",
    ),
    "Selecciona una clave SSH.": ("key_required", "Select an SSH key."),
    "Verifica y guarda primero la identidad del servidor SSH.": (
        "trust_required",
        "Verify and save the SSH server identity first.",
    ),
    "Configuración enlazada o demasiado grande.": (
        "unsafe_manifest",
        "The manifest is a symlink or is too large.",
    ),
    "Slug no válido o reservado para este gestor.": (
        "invalid_slug",
        "Invalid slug or a slug reserved for this manager.",
    ),
    "Hay aplicaciones con el mismo slug dentro del repositorio.": (
        "duplicate_slug",
        "The repository contains apps with duplicate slugs.",
    ),
    "La lista de arquitecturas no es válida.": (
        "invalid_arch",
        "The architecture list is invalid.",
    ),
    "Otra carpeta local ya utiliza este slug.": (
        "slug_collision",
        "Another local folder already uses this slug.",
    ),
    "Este servidor está en uso por un repositorio.": (
        "host_in_use",
        "A repository is using this server.",
    ),
    "No se pudo leer la configuración de una aplicación.": (
        "manifest_unreadable",
        "Could not read an app manifest.",
    ),
    "El paquete contiene enlaces simbólicos o archivos especiales; no se copiará.": (
        "unsafe_package",
        "The package contains symlinks or special files and will not be copied.",
    ),
}
