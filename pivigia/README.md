# PiVigia para Home Assistant

Servicio de análisis local de fotos recibidas por SMTP, con avisos por correo y Telegram. Incluye modelos descargables, pruebas sin avisos y cámaras RTSP opcionales.

Añade `https://gentedelcondado.es/wolfbelmi88/pivigia` a los repositorios de la tienda. Si ya está instalado, conserva la URL y la instancia que utilizas. Configura un `admin_token` de al menos 16 caracteres, guarda e inicia.

**Certificado y clave STARTTLS de entrada son opcionales.** Omite ambos si no los necesitas. La autenticación SMTP sin TLS requiere habilitarla expresamente para una red local de confianza.

Consulta [la documentación completa del complemento](DOCS.md): opciones, ejemplos YAML, puertos, acceso, primer aviso, sensores y actualización. Esa página se genera desde `docs/HOME_ASSISTANT.md`; edita allí el contenido.

Los datos privados viven en `/data` del complemento. Haz una copia antes de actualizar la instancia existente. La versión se declara en `config.yaml` y el historial está en [Cambios](CHANGELOG.md).
