# Aplicaciones de Gente del Condado

![Icono del catálogo](icon.png)

Mi repositorio oficial de aplicaciones para Home Assistant.

[![Añadir a Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FGente-del-Condado%2FMis-app)

[Manual del gestor](https://gente-del-condado.github.io/HA-Private-Git-Manager/) · [Catálogo de integraciones y Forgejo Backup](https://gente-del-condado.github.io/HA-Private-Git-Manager/#componentes)

## Instalación

Pulsa el botón anterior o añade este repositorio desde **Ajustes → Aplicaciones →
Tienda → menú ⋮ → Repositorios**:

```text
https://github.com/Gente-del-Condado/Mis-app
```

Después selecciona **HA Private Git Manager**, instala, inicia y abre su interfaz web.
La primera instalación construye la app y requiere conexión a Internet.

## Aplicaciones

| Aplicación | Descripción | Arquitecturas |
| --- | --- | --- |
| [JackSignal Installer](jacksignal_installer/DOCS.md) | Instala y actualiza el reproductor de audio local con avisos de Alarmo y receptor DLNA. | `amd64`, `aarch64` |
| [HA Private Git Manager](private_git_manager/README.md) | Gestiona claves SSH y aplicaciones de repositorios GitHub, Forgejo y Gitea desde Home Assistant. | `amd64`, `aarch64` |

[Guía de uso](private_git_manager/DOCS.md) · [Historial de versiones](private_git_manager/CHANGELOG.md)

## Actualizaciones y desarrollo

`private_git_manager/` se publica automáticamente con GitHub Actions cuando se
actualiza la app en la rama `main` de
[HA-Private-Git-Manager](https://github.com/Gente-del-Condado/HA-Private-Git-Manager).
El desarrollo se realiza allí; los cambios manuales en esta copia se sustituyen
en la siguiente publicación. Otras aplicaciones de este repositorio se conservan.

Para que Home Assistant ofrezca una actualización hay que aumentar la versión en
el manifiesto de la app original. Las actualizaciones se instalan desde Home Assistant.

[Automatización de publicación](https://github.com/Gente-del-Condado/HA-Private-Git-Manager/blob/main/PUBLISHING.md)

`jacksignal_installer/` se publica automáticamente desde [JackSignal](https://github.com/Gente-del-Condado/jacksignal). Incluye el instalador y la integración. Tras instalar o actualizar la app, pulsa **Iniciar**, comprueba el registro y reinicia Home Assistant. [Publicación y actualizaciones de JackSignal](https://github.com/Gente-del-Condado/jacksignal/blob/main/PUBLISHING.md).
