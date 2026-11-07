"""Stable event identifiers, translated for the UI; container logs default to Spanish."""

EVENTS = {
    "app_backup_imported": ("Copia de seguridad importada.", "Backup imported."),
    "app_backup_schedule_saved": ("Programación de copias guardada.", "Backup schedule saved."),
    "app_backup_download_started": ("Descarga de copia iniciada.", "Backup download started."),
    "app_backup_delete_started": ("Borrando copia de seguridad.", "Deleting backup."),
    "app_backup_deleted": ("Copia de seguridad borrada.", "Backup deleted."),
    "app_backup_started": ("Creando copia de seguridad de la aplicación.", "Creating app backup."),
    "app_backup_created": ("Copia de seguridad de la aplicación creada.", "App backup created."),
    "app_backup_restore_started": ("Restaurando copia de la aplicación.", "Restoring app backup."),
    "app_backup_restored": ("Copia de la aplicación restaurada.", "App backup restored."),
    "app_configured": ("Configuración de la aplicación guardada.", "App configuration saved."),
    "app_uninstalled": (
        "Aplicación desinstalada; código local conservado.",
        "App uninstalled; local source kept.",
    ),
    "app_removed": ("Copia local eliminada.", "Local copy deleted."),
    "app_restored": ("Aplicación visible de nuevo en el catálogo.", "App restored to the catalog."),
    "local_adopted": (
        "Carpeta local adoptada por el gestor.",
        "Local folder adopted by the manager.",
    ),
    "key_created": ("Clave SSH creada.", "SSH key created."),
    "key_deleted": ("Clave SSH eliminada.", "SSH key deleted."),
    "host_trusted": ("Identidad SSH verificada.", "SSH server identity verified."),
    "host_deleted": ("Identidad SSH eliminada.", "SSH server identity removed."),
    "repo_added": ("Repositorio añadido.", "Repository added."),
    "repo_edited": ("Configuración de repositorio actualizada.", "Repository settings updated."),
    "repo_deleted": (
        "Repositorio y credenciales eliminados.",
        "Repository and credentials deleted.",
    ),
    "credentials_changed": ("Credenciales actualizadas.", "Credentials updated."),
    "sync_started": ("Descargando repositorio.", "Downloading repository."),
    "sync_done": ("Repositorio sincronizado.", "Repository synchronized."),
    "deploy_started": (
        "Preparando instalación o actualización.",
        "Preparing installation or update.",
    ),
    "deploy_done": ("Aplicación instalada o actualizada.", "App installed or updated."),
    "deploy_failed": (
        "Operación fallida. Consulta la recuperación de la aplicación.",
        "Operation failed. Review app recovery.",
    ),
    "interrupted": (
        "Operación interrumpida. Es necesario revisar su estado.",
        "Operation interrupted. Review its state.",
    ),
    "job_started": ("Operación iniciada.", "Operation started."),
    "job_done": ("Operación completada.", "Operation completed."),
    "job_failed": ("Operación fallida.", "Operation failed."),
    "runtime_action": ("Acción enviada al Supervisor.", "Action sent to Supervisor."),
    "recovered": (
        "Código recuperado. Revisa el estado de ejecución.",
        "Source recovered. Review runtime state.",
    ),
    "released": ("Aplicación desvinculada del gestor.", "App released from this manager."),
    "startup": ("Gestor preparado.", "Manager ready."),
}


def event_text(code, language="es"):
    pair = EVENTS.get(code)
    return pair[1 if language == "en" else 0] if pair else code
