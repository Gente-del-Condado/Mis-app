# Aplicaciones de Gente del Condado

![Icono del catálogo](icon.png)

Catálogo de complementos de Home Assistant publicado en Forgejo.

[Manual del gestor](https://gente-del-condado.github.io/HA-Private-Git-Manager/) · [Catálogo de integraciones y Forgejo Backup](https://gente-del-condado.github.io/HA-Private-Git-Manager/#componentes)

## Instalación con HA Private Git Manager

En **HA Private Git Manager**, añade este repositorio como catálogo y selecciona la clave SSH que tenga acceso.

```text
ssh://forgejo@gentedelcondado.es:2233/wolfbelmi88/Mis-app.git
```

Sincroniza el catálogo y elige el complemento que quieras instalar o actualizar. El catálogo incluye HA Private Git Manager. Para administrar el propio gestor, usa su procedimiento de instalación o actualización desde Home Assistant.

## Aplicaciones

| Aplicación | Qué hace | Arquitecturas |
| --- | --- | --- |
| [HA Private Git Manager](private_git_manager/README.md) | Gestiona claves SSH, repositorios y complementos privados. | `amd64`, `aarch64` |
| [JackSignal Installer](jacksignal_installer/DOCS.md) | Instala JackSignal para reproducir avisos por el jack de la Raspberry Pi con prioridades y Alarmo. | `amd64`, `aarch64` |
| [PiVigia](pivigia/README.md) | Recibe fotos de cámaras por correo y analiza detecciones. | `amd64`, `aarch64` |
| [Headscale Gateway](headscale_gateway/README.md) | Ejecuta y administra Headscale Gateway en Home Assistant. | `amd64`, `aarch64` |

## Sincronización desde Forgejo

Cada complemento se copia desde `main` de su repositorio de origen. Solo se publica su carpeta instalable, incluidos los archivos necesarios para construir la imagen. Edita el complemento en el repositorio de origen y aumenta allí la versión de su `config.yaml` para que Home Assistant ofrezca la actualización.

| Repositorio de origen | Carpeta de origen | Carpeta en Mis-app |
| --- | --- | --- |
| [HA-Private-Git-Manager](https://gentedelcondado.es/wolfbelmi88/HA-Private-Git-Manager) | `private_git_manager` | `private_git_manager` |
| [jacksignal](https://gentedelcondado.es/wolfbelmi88/jacksignal) | `custom_components` | `jacksignal_installer` |
| [pivigia](https://gentedelcondado.es/wolfbelmi88/pivigia) | `addons/pivigia` | `pivigia` |
| [headscale-gateway](https://gentedelcondado.es/wolfbelmi88/headscale-gateway) | `addons/headscale_gateway` | `headscale_gateway` |

### Activar la sincronización automática

1. Habilita Forgejo Actions para este repositorio y comprueba que tiene un runner con la etiqueta `ubuntu-latest`, Bash, Git, tar y OpenSSH.
2. Crea una clave SSH dedicada a la sincronización. Autorízala para leer los cuatro orígenes y escribir en `main` de `Mis-app`. Puedes usar una cuenta de servicio o registrar la misma clave pública de despliegue con lectura en los orígenes y escritura en la tienda, si tu instancia lo permite.
3. En **Mis-app → Ajustes → Actions → Secrets**, crea `MIS_APP_SYNC_SSH_KEY` con la clave privada dedicada. El runner usa esa clave, ya que el agente SSH de tu ordenador solo está disponible en tu sesión.
4. En **Actions → Sincronizar catálogo Mis-app**, ejecuta una primera sincronización manual de `main`. Después, Forgejo comprueba cambios cada 15 minutos. Si una carpeta cambia, publica un commit. Si falla un origen, la sincronización no publica cambios parciales.

Para sincronizar desde un clon de `Mis-app` con tu agente SSH, ejecuta `bash scripts/sync-apps.sh`, revisa el diff y publica los cambios en `main`.
