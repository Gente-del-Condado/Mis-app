# PiVigia en Home Assistant

El complemento ejecuta el receptor SMTP, el detector y el panel. La integración opcional añade sensores a Home Assistant. Son componentes distintos y se actualizan por separado.

## Instalar el complemento

Necesitas Home Assistant con Supervisor, arquitectura AMD64 o ARM64 y conexión para descargar dependencias y el modelo inicial.

1. En la tienda de aplicaciones/complementos, abre **Repositorios**.
2. Añade `https://gentedelcondado.es/wolfbelmi88/pivigia`. Supervisor necesita poder clonar el repositorio desde tu instalación.
3. Busca **PiVigia** e instala. La construcción inicial puede tardar varios minutos.
4. En **Configuración**, introduce un `admin_token` propio de al menos 16 caracteres. Guarda.
5. Inicia el complemento, revisa **Registro** y abre **Interfaz web**.
6. Sigue los primeros pasos de esta página para crear un buzón y enviar una prueba.

Si ya tienes PiVigia instalado, conserva **la URL y la instancia existentes**. Añadir el mismo proyecto con otra URL puede crear otro identificador de repositorio; no traslada automáticamente los datos.

## Opciones del complemento

| Opción | Obligatoria | Uso |
| --- | --- | --- |
| `admin_token` | Sí | Secreto de al menos 16 caracteres para acceso directo y sensores. |
| `panel_login` | Sí; inicial `both` | `both`, `homeassistant` o `token`. |
| `allow_plain_auth` | Sí; inicial `false` | Permite usuario y contraseña SMTP sin TLS cuando se activa. |
| `language` | No | `es` o `en`; omitido/vacío permite elegir el idioma del servicio desde el panel. |
| `trusted_networks` | No | IP o redes CIDR, separadas por comas, autorizadas sin autenticación SMTP. |
| `tls_cert` | No | Ruta absoluta al certificado STARTTLS de entrada. |
| `tls_key` | No | Ruta absoluta a la clave del certificado de entrada. |

**Certificado y clave STARTTLS son opcionales.** Déjalos ambos vacíos u omite ambas claves. Si configuras uno, necesitas el otro. Si el formulario oculta las opciones, activa la visualización de campos opcionales.

Una configuración mínima, sin STARTTLS de entrada:

```yaml
admin_token: "SUSTITUYE_POR_UN_SECRETO_LARGO_Y_PROPIO"
panel_login: both
allow_plain_auth: false
```

Este ejemplo inicia el servicio, pero no permite AUTH sin TLS. Elige a continuación el modo de entrada que admite tu cámara.

## Acceso SMTP desde las cámaras

### Cámara con usuario y contraseña, sin TLS

En una red local de confianza:

```yaml
admin_token: "SUSTITUYE_POR_UN_SECRETO_LARGO_Y_PROPIO"
panel_login: both
allow_plain_auth: true
```

Omite `tls_cert` y `tls_key`. Configura la cámara sin SSL/STARTTLS, con la dirección del buzón como usuario y la contraseña creada en PiVigia. Restringe el acceso a esa red; estas credenciales viajan sin cifrar.

### Cámara sin autenticación

Autoriza únicamente su IP real. Ejemplo ficticio:

```yaml
admin_token: "SUSTITUYE_POR_UN_SECRETO_LARGO_Y_PROPIO"
panel_login: both
allow_plain_auth: false
trusted_networks: "192.0.2.20/32"
```

Sustituye la IP de ejemplo por la que ve el servicio. No utilices una red universal para solucionar un rechazo. Si existe NAT, comprueba qué dirección llega a PiVigia.

### Cámara con STARTTLS

Coloca el certificado y su clave en el directorio SSL de Home Assistant y configura las dos rutas. Los nombres son ejemplos; los archivos deben existir y corresponderse:

```yaml
admin_token: "SUSTITUYE_POR_UN_SECRETO_LARGO_Y_PROPIO"
panel_login: both
allow_plain_auth: false
tls_cert: "/ssl/fullchain.pem"
tls_key: "/ssl/privkey.pem"
```

Reinicia tras cambiar las opciones. La cámara debe admitir STARTTLS y confiar en el certificado del servidor. Este certificado protege **la entrada SMTP**; no configura HTTPS de Home Assistant ni el SMTP de salida.

## Puertos

| Puerto interno | Función | Configuración |
| --- | --- | --- |
| `2525/tcp` | Correo SMTP que envían las cámaras | Publica un puerto accesible desde su red. |
| `8099/tcp` | Panel directo y API para sensores | Necesita token; Ingress usa el puerto interno. |

Los puertos publicados se cambian en **Configuración → Red** del complemento. Si eliges otro puerto del anfitrión, utiliza ese valor en la cámara o integración. No cambies los puertos internos del contenedor.

## Entrar al panel

- **`both`:** permite sesión de Home Assistant mediante Ingress y token.
- **`homeassistant`:** el panel usa los permisos que transmite Supervisor. El token se conserva para consultar el estado desde la integración de sensores.
- **`token`:** el panel solicita el token de PiVigia.

Ingress debe transmitir grupos de usuario compatibles. Los administradores reciben edición; los usuarios admitidos sin rol administrador reciben consulta de actividad y cámaras. No se confía en cabeceras de usuario de conexiones externas al proxy de Supervisor.

El acceso directo al puerto web no hereda una sesión de Home Assistant. Para administración directa con token, usa `both` o `token`.

## Primer aviso

1. En **Buzones y reglas**, crea `patio@pivigia.local` con contraseña propia, categoría **Personas**, confianza inicial 0,50 y un destino de correo.
2. En **Configuración**, guarda el SMTP de salida de tu proveedor o prepara Telegram. Son credenciales distintas de las del buzón.
3. En **Pruebas**, envía un correo manual para comprobar la salida.
4. Prueba una foto seleccionando el buzón. **Analizar imagen sin enviar avisos** muestra la decisión sin notificar.
5. Configura la cámara con la IP de Home Assistant, el puerto SMTP publicado, el buzón como usuario y destinatario, y su contraseña.
6. Genera un evento real y comprueba **Actividad**. Un mensaje filtrado no genera aviso; revisa la regla antes de considerarlo un fallo.

La guía ampliada está en [Primeros pasos](https://gentedelcondado.es/wolfbelmi88/pivigia/src/branch/main/docs/PRIMEROS_PASOS.md), con [reglas y ejemplos](https://gentedelcondado.es/wolfbelmi88/pivigia/src/branch/main/docs/BUZONES.md), [Telegram y correo](https://gentedelcondado.es/wolfbelmi88/pivigia/src/branch/main/docs/NOTIFICACIONES.md) y [diagnóstico](https://gentedelcondado.es/wolfbelmi88/pivigia/src/branch/main/docs/PROBLEMAS.md).

## Idioma y apariencia

El selector del acceso o menú lateral cambia el idioma de ese navegador. **Configuración → Idioma del servicio** cambia los registros propios y avisos automáticos. Si has fijado `language` en las opciones del complemento, ese valor tiene prioridad y el selector del servicio aparece bloqueado; omite la opción y reinicia para liberarlo.

Español e inglés están incluidos. Las traducciones de los formularios del complemento y entidades se adaptan al idioma de Home Assistant. En **Apariencia** puedes elegir sistema, oscuro o claro.

## Sensores opcionales

Instala `custom_components/pivigia` dentro de la carpeta de configuración de Home Assistant y reinicia. En **Dispositivos y servicios → Añadir integración**, busca PiVigia e introduce una URL accesible desde Home Assistant, por ejemplo `http://192.0.2.10:8099`, y el token.

La URL debe apuntar a la API directa, no a una ruta temporal de Ingress. HACS requiere un repositorio en GitHub; Forgejo por sí solo no es un repositorio personalizado de HACS. Consulta [Integración y automatizaciones](https://gentedelcondado.es/wolfbelmi88/pivigia/src/branch/main/docs/INTEGRACION.md) para la instalación manual, entidades y ejemplos.

## Actualizar sin perder datos

1. Crea una copia de Home Assistant que incluya los datos del complemento y la configuración de Home Assistant.
2. Busca actualizaciones en la tienda del repositorio que ya utilizas.
3. Actualiza **la instancia existente**. No la desinstales para actualizar.
4. Revisa el registro, abre el panel y comprueba versión, buzones, modelo y una imagen de prueba.
5. Actualiza la integración de sensores por separado si la nueva versión lo requiere.

Los datos del complemento están en `/data`, incluidos SQLite, token y modelos opcionales en `/data/models`. El código público y las capturas del manual no incluyen esos datos.

Para instalar desde una carpeta local de desarrollo, conserva su identidad y sustituye las fuentes del mismo complemento antes de reconstruirlo. Un cambio de repositorio o de identificador requiere una migración planificada con copia y restauración.

## Si algo falla

- **Sigue pidiendo certificado:** comprueba la versión instalada, recarga Configuración y omite ambos campos TLS en YAML.
- **No llegan mensajes:** revisa puerto de entrada, autenticación y registro. La prueba SMTP de salida no comprueba la cámara.
- **No aparecen cambios:** confirma que has guardado y reiniciado cuando el ajuste sea de arranque.
- **No aparece una actualización:** revisa el repositorio de la instancia y el registro de Supervisor.

Consulta [Copias](https://gentedelcondado.es/wolfbelmi88/pivigia/src/branch/main/docs/COPIAS.md) y [Solución de problemas](https://gentedelcondado.es/wolfbelmi88/pivigia/src/branch/main/docs/PROBLEMAS.md). Las pruebas del proyecto incluyen contratos del complemento, pero no sustituyen la comprobación en tu instalación real de Supervisor.
