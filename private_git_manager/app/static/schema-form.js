// Formulario de schema_ui del Supervisor. Las opciones se mantienen en memoria.
const own = (object, key) => Object.hasOwn(object || {}, key);
const put = (object, key, value) =>
  Object.defineProperty(object, key, {
    value,
    enumerable: true,
    writable: true,
    configurable: true,
  });
const node = (tag, text, className) => {
  const result = document.createElement(tag);
  if (text !== undefined) result.textContent = text;
  if (className) result.className = className;
  return result;
};
let nextId = 0;

export class SchemaForm {
  constructor(
    container,
    {
      values,
      schema,
      translations = {},
      networkDescription = {},
      language,
      t,
      onChange,
    },
  ) {
    Object.assign(this, {
      container,
      translations,
      networkDescription,
      language,
      t,
      onChange,
    });
    this.value = structuredClone(values);
    this.optionalValues = new WeakMap();
    this.schema = Array.isArray(schema) ? schema : [];
    this.render();
  }
  data() {
    return structuredClone(this.value);
  }
  text(path, field) {
    const find = (language) => {
      let current = this.translations[language]?.configuration;
      for (const [index, part] of path
        .filter((p) => typeof p !== "number")
        .entries()) {
        current = index ? current?.fields?.[part] : current?.[part];
      }
      return typeof current?.[field] === "string" ? current[field] : undefined;
    };
    return find(this.language) ?? find("en");
  }
  changed() {
    this.onChange?.();
  }
  infer(name, value) {
    if (Array.isArray(value))
      return {
        ...this.infer(name, value[0] ?? ""),
        multiple: true,
        optional: true,
      };
    if (value && typeof value === "object")
      return {
        name,
        type: "schema",
        optional: true,
        schema: Object.entries(value).map(([key, val]) => this.infer(key, val)),
      };
    return {
      name,
      type:
        typeof value === "boolean"
          ? "boolean"
          : typeof value === "number"
            ? Number.isInteger(value)
              ? "integer"
              : "float"
            : "string",
      format: /password|token|secret/i.test(name) ? "password" : undefined,
      optional: true,
    };
  }
  defaultValue(schema) {
    if (schema.multiple) return [];
    if (schema.type === "schema") return {};
    if (schema.type === "boolean") return false;
    return "";
  }
  render() {
    this.container.replaceChildren();
    if (this.container.tagName === "FIELDSET")
      this.container.append(
        node("legend", this.t("configurationForm"), "sr-only"),
      );
    const options = node("fieldset");
    options.append(node("legend", this.t("applicationOptions")));
    const dictionary = this.value.options || {};
    put(this.value, "options", dictionary);
    const schema = [...this.schema];
    for (const [name, value] of Object.entries(dictionary)) {
      if (!schema.some((s) => s.name === name))
        schema.push(this.infer(name, value));
    }
    if (!schema.length)
      options.append(node("p", this.t("noDeclaredOptions"), "muted"));
    for (const field of schema)
      this.field(options, field, dictionary, field.name, [field.name]);
    this.container.append(options);
    this.renderSystem();
  }
  field(parent, schema, object, key, path, listItem = false) {
    const box = node("div", undefined, "schema-field");
    const name =
      schema.label ||
      (listItem
        ? `${this.t("listItem")} ${Number(key) + 1}`
        : this.text(path, "name") || String(key));
    const description = schema.label
      ? undefined
      : this.text(path, "description");
    const present = own(object, key);
    const optional = !listItem && (schema.optional || !schema.required);
    let contents = node("div", undefined, "schema-field-content");
    let enabled = present || !optional;
    if (optional) {
      const label = node("label", undefined, "radio optional-option");
      const toggle = node("input");
      toggle.type = "checkbox";
      toggle.id = `pgm-field-${++nextId}`;
      toggle.name = `${JSON.stringify(path)}:enabled`;
      toggle.checked = enabled;
      toggle.dataset.optionalPath = JSON.stringify(path);
      label.htmlFor = toggle.id;
      label.append(
        toggle,
        document.createTextNode(`${name} · ${this.t("optionalOption")}`),
      );
      box.append(label);
      toggle.addEventListener("change", () => {
        let previous = this.optionalValues.get(object);
        if (!previous) {
          previous = new Map();
          this.optionalValues.set(object, previous);
        }
        if (toggle.checked)
          put(
            object,
            key,
            previous.has(key) ? previous.get(key) : this.defaultValue(schema),
          );
        else {
          previous.set(key, object[key]);
          delete object[key];
        }
        this.changed();
        this.render();
        [...this.container.querySelectorAll("[data-optional-path]")]
          .find((el) => el.dataset.optionalPath === JSON.stringify(path))
          ?.focus();
      });
    }
    if (
      description &&
      (schema.multiple || schema.type === "schema" || !enabled)
    )
      box.append(node("p", description, "field-help"));
    box.append(contents);
    parent.append(box);
    if (!enabled) return;
    if (schema.multiple) {
      const group = node("fieldset");
      group.append(node("legend", name));
      contents.append(group);
      contents = group;
      if (!present && !optional) put(object, key, []);
      if (!Array.isArray(object[key])) {
        contents.append(node("p", this.t("unsupportedFormValue"), "muted"));
        return;
      }
      const values = object[key];
      values.forEach((value, index) => {
        const group = node("fieldset", undefined, "schema-list-item");
        group.append(node("legend", `${this.t("listItem")} ${index + 1}`));
        this.field(
          group,
          { ...schema, multiple: false, required: true, optional: false },
          values,
          index,
          [...path, index],
          true,
        );
        const remove = node("button", this.t("removeListItem"));
        remove.type = "button";
        remove.addEventListener("click", () => {
          values.splice(index, 1);
          this.changed();
          this.render();
          [...this.container.querySelectorAll("[data-list-path]")]
            .find((el) => el.dataset.listPath === JSON.stringify(path))
            ?.focus();
        });
        group.append(remove);
        contents.append(group);
      });
      const add = node("button", this.t("addListItem"));
      add.type = "button";
      add.dataset.listPath = JSON.stringify(path);
      add.addEventListener("click", () => {
        values.push(this.defaultValue({ ...schema, multiple: false }));
        this.changed();
        this.render();
        const prefix = JSON.stringify([...path, values.length - 1]);
        const first = [
          ...this.container.querySelectorAll("[data-option-path]"),
        ].find(
          (el) =>
            JSON.stringify(
              JSON.parse(el.dataset.optionPath).slice(0, path.length + 1),
            ) === prefix,
        );
        (
          first ||
          [...this.container.querySelectorAll("[data-list-path]")].find(
            (el) => el.dataset.listPath === JSON.stringify(path),
          )
        )?.focus();
      });
      contents.append(add);
      return;
    }
    if (schema.type === "schema") {
      const group = node("fieldset");
      group.append(node("legend", name));
      contents.append(group);
      if (
        object[key] !== null &&
        typeof object[key] === "object" &&
        !Array.isArray(object[key])
      ) {
        const fields = Array.isArray(schema.schema) ? [...schema.schema] : [];
        for (const [child, value] of Object.entries(object[key]))
          if (!fields.some((s) => s.name === child))
            fields.push(this.infer(child, value));
        for (const child of fields)
          this.field(group, child, object[key], child.name, [
            ...path,
            child.name,
          ]);
      } else group.append(node("p", this.t("unsupportedFormValue"), "muted"));
      return;
    }
    if (!present && !optional && schema.type === "boolean")
      put(object, key, false);
    const raw = own(object, key) ? object[key] : undefined;
    if (raw !== null && typeof raw === "object") {
      contents.append(
        node("p", `${name}: ${this.t("unsupportedFormValue")}`, "muted"),
      );
      return;
    }
    const secret = typeof raw === "string" && raw.startsWith("!secret ");
    const label = node(
      "label",
      `${name}${schema.required && !schema.nullable ? " *" : ""}`,
    );
    let input;
    // Los selectores compactos facilitan usar grupos repetidos en pantallas estrechas.
    if (schema.type === "select" && !secret) {
      input = node("select");
      const items = [...(Array.isArray(schema.options) ? schema.options : [])];
      if (present && !items.some((value) => String(value) === String(raw)))
        items.unshift(raw);
      if (!present) {
        const placeholder = node("option", this.t("chooseOption"));
        placeholder.value = "";
        input.append(placeholder);
      }
      for (const value of items) {
        const option = node("option", String(value));
        option.value = String(value);
        input.append(option);
      }
      input.value = raw == null ? "" : String(raw);
    } else {
      input = node("input");
      input.type = secret
        ? "text"
        : schema.type === "boolean"
          ? "checkbox"
          : ["integer", "float"].includes(schema.type)
            ? "number"
            : ["password", "email", "url"].includes(schema.format)
              ? schema.format
              : "text";
      if (input.type === "checkbox") {
        input.checked = raw === true;
        label.className = "radio";
      } else input.value = raw == null ? "" : String(raw);
      input.autocomplete = input.type === "password" ? "new-password" : "off";
      input.setAttribute("autocorrect", "off");
      input.setAttribute("autocapitalize", "off");
      input.spellcheck = false;
      if (input.type === "number") {
        input.step = schema.type === "integer" ? "1" : "any";
        if (Number.isFinite(schema.lengthMin)) input.min = schema.lengthMin;
        if (Number.isFinite(schema.lengthMax)) input.max = schema.lengthMax;
      } else if (!secret) {
        if (Number.isFinite(schema.lengthMin))
          input.minLength = schema.lengthMin;
        if (Number.isFinite(schema.lengthMax))
          input.maxLength = schema.lengthMax;
      }
    }
    input.id = `pgm-field-${++nextId}`;
    input.name = JSON.stringify(path);
    input.dataset.optionPath = JSON.stringify(path);
    input.required = Boolean(
      schema.required && !schema.nullable && input.type !== "checkbox",
    );
    label.htmlFor = input.id;
    if (input.type === "checkbox") {
      label.textContent = "";
      label.append(input, document.createTextNode(name));
      contents.append(label);
    } else contents.append(label, input);
    if (description) {
      const help = node("p", description, "field-help");
      help.id = `${input.id}-help`;
      input.setAttribute("aria-describedby", help.id);
      contents.append(help);
    }
    const update = () => {
      let value =
        input.type === "checkbox"
          ? input.checked
          : input.type === "number" && Number.isFinite(input.valueAsNumber)
            ? input.valueAsNumber
            : input.value;
      if (schema.nullable && value === "") value = null;
      put(object, key, value);
      this.changed();
    };
    input.addEventListener("input", update);
    input.addEventListener("change", update);
    if (schema.format === "password" && !secret) {
      const show = node(
        "button",
        this.t("showPassword"),
        "subtle password-toggle",
      );
      show.type = "button";
      show.setAttribute("aria-pressed", "false");
      show.setAttribute("aria-controls", input.id);
      show.addEventListener("click", () => {
        const visible = input.type === "password";
        input.type = visible ? "text" : "password";
        show.setAttribute("aria-pressed", String(visible));
        show.textContent = this.t(visible ? "hidePassword" : "showPassword");
      });
      contents.append(show);
    }
  }
  renderSystem() {
    const group = node("fieldset");
    group.append(node("legend", this.t("supervisorSettings")));
    for (const key of [
      "boot",
      "watchdog",
      "auto_update",
      "ingress_panel",
      "audio_input",
      "audio_output",
    ]) {
      if (!own(this.value, key)) continue;
      const schema = {
        name: key,
        required: true,
        nullable: ["audio_input", "audio_output"].includes(key),
        type: ["watchdog", "auto_update", "ingress_panel"].includes(key)
          ? "boolean"
          : key === "boot"
            ? "select"
            : "string",
        ...(key === "boot" ? { options: ["auto", "manual"] } : {}),
      };
      // Los ajustes nativos usan las etiquetas traducidas del gestor.
      const labels = {
        boot: "bootSetting",
        watchdog: "watchdogSetting",
        auto_update: "autoUpdateSetting",
        ingress_panel: "ingressPanelSetting",
        audio_input: "audioInputSetting",
        audio_output: "audioOutputSetting",
      };
      this.field(
        group,
        { ...schema, label: this.t(labels[key]) },
        this.value,
        key,
        [key],
      );
    }
    if (this.value.network && typeof this.value.network === "object") {
      const ports = node("fieldset");
      ports.append(node("legend", this.t("networkSettings")));
      for (const key of Object.keys(this.value.network)) {
        const row = node("div", undefined, "schema-field");
        const label = node("label", `${key} · ${this.t("portBinding")}`);
        const input = node("input");
        input.type = "text";
        input.id = `pgm-field-${++nextId}`;
        input.name = `network:${key}`;
        input.value = this.value.network[key] ?? "";
        input.placeholder = this.t("disabledPort");
        label.htmlFor = input.id;
        row.append(label, input);
        const help =
          this.translations[this.language]?.network?.[key] ||
          this.translations.en?.network?.[key] ||
          this.networkDescription[key];
        if (typeof help === "string") row.append(node("p", help, "field-help"));
        input.addEventListener("input", () => {
          const raw = input.value.trim();
          put(
            this.value.network,
            key,
            raw === "" ? null : /^\d+$/.test(raw) ? Number(raw) : raw,
          );
          this.changed();
        });
        ports.append(row);
      }
      group.append(ports);
    }
    this.container.append(group);
  }
}
