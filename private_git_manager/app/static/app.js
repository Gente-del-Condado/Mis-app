const $ = (selector) => document.querySelector(selector);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const storage = {
  get(key) {
    try {
      return localStorage.getItem(key);
    } catch (_) {
      return null;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (_) {}
  },
};
const preferences = {
  language: storage.get("pgm-language") || "es",
  theme: storage.get("pgm-theme") || "system",
};
let dictionary,
  state,
  supervisor,
  view = "repos",
  modalContext = {},
  loadingModal = false;
let checkingDeployment = false;
let repoSearch = "",
  logSearch = "",
  logLevel = "",
  pollTimer,
  lastRender = "",
  disconnected = false;
const terminal = new Set(["succeeded", "failed", "interrupted"]);
const rememberedJobs = new Set();
const t = (key, values = {}) =>
  Object.entries(values).reduce(
    (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
    dictionary?.[key] ?? key,
  );
const date = (seconds) =>
  seconds
    ? new Date(seconds * 1000).toLocaleString(preferences.language, {
        dateStyle: "short",
        timeStyle: "short",
      })
    : t("never");
const short = (commit) => (commit ? commit.slice(0, 10) : t("unconfirmed"));
const bytes = (value) =>
  new Intl.NumberFormat(preferences.language, {
    maximumFractionDigits: 1,
  }).format(value / 1024 ** 3) + " GiB";
const badge = (text, kind = "") =>
  `<span class="badge ${esc(kind)}">${esc(text)}</span>`;
const button = (action, label, data = "", kind = "") =>
  `<button type="button" data-action="${action}" ${data} class="${kind}">${esc(label)}</button>`;
const empty = (title, text, action = "") =>
  `<div class="empty"><span class="empty-symbol" aria-hidden="true">⑂</span><strong>${esc(title)}</strong><p>${esc(text)}</p>${action}</div>`;
const controls = (id, field = "repo") => `data-${field}="${esc(id)}"`;
const field = (label, name, value = "", extra = "") =>
  `<label>${esc(t(label))}<input name="${name}" value="${esc(value)}" ${extra}></label>`;
const actions = (label = "save") =>
  `${button("close-modal", t("cancel"))}<button type="submit" class="primary">${esc(t(label))}</button>`;

function setTheme(theme) {
  preferences.theme = theme;
  storage.set("pgm-theme", theme);
  document.documentElement.dataset.theme = theme;
}
async function setLanguage(language) {
  if (!["es", "en"].includes(language)) language = "es";
  const response = await fetch(`static/locales/${language}.json`);
  if (!response.ok) throw new Error("Unable to load language");
  dictionary = await response.json();
  preferences.language = language;
  storage.set("pgm-language", language);
  document.documentElement.lang = language;
  document
    .querySelectorAll("[data-t]")
    .forEach((node) => (node.textContent = t(node.dataset.t)));
  $("#header-language").value = language;
  lastRender = "";
  render();
}
function errorText(error) {
  if (preferences.language === "es" && error.message) return error.message;
  return t(error.code || "operation_failed");
}
function notice(message, error = false) {
  $("#notice-message").textContent = message;
  $("#notice").className = error ? "error" : "";
  $("#notice").hidden = false;
}
async function api(path, method = "GET", data, requestId) {
  const controller = new AbortController(),
    timeout = setTimeout(() => controller.abort(), 22000);
  try {
    const response = await fetch("api/" + path, {
      method,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        "X-PGM-Request": "1",
        ...(requestId ? { "Idempotency-Key": requestId } : {}),
      },
      body: data === undefined ? undefined : JSON.stringify(data),
    });
    const result = await response.json();
    if (!response.ok) {
      const error = new Error(result.detail);
      error.code = result.code;
      throw error;
    }
    return result;
  } catch (error) {
    if (error.name === "AbortError" || error instanceof TypeError) {
      error.code = "connectionLost";
      error.message = t("connectionLost");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
async function refresh() {
  const next = await api("state");
  for (const job of Object.values(next.jobs)) {
    if (
      state &&
      terminal.has(job.status) &&
      !terminal.has(state.jobs[job.id]?.status) &&
      !rememberedJobs.has(job.id)
    ) {
      rememberedJobs.add(job.id);
      notice(
        job.status === "succeeded"
          ? t("stage_done")
          : errorText({ message: job.error, code: job.code }),
        job.status !== "succeeded",
      );
    }
  }
  state = next;
  if (disconnected) {
    disconnected = false;
    notice(t("connectedAgain"));
  }
  render();
}
async function checkSupervisor() {
  try {
    supervisor = await api("supervisor");
  } catch (error) {
    supervisor = { connected: false, error: errorText(error) };
  }
  lastRender = "";
  render();
}
function environmentText() {
  return !state?.supervisor
    ? t("development")
    : supervisor?.connected
      ? t("supervisorConnected")
      : supervisor?.error
        ? t("supervisorError")
        : t("supervisorUnknown");
}
function jobCard(job) {
  const active = !terminal.has(job.status);
  const title = t("job_" + job.kind),
    resource = job.resource.replace(/^(repo|app):/, "");
  const repo = state.repos[resource];
  return `<article class="job ${active ? "job-active" : ""}"><div class="job-status ${active ? "spinner" : job.status}" aria-hidden="true">${active ? "" : job.status === "succeeded" ? "✓" : "!"}</div><div class="job-main"><strong>${esc(title)}</strong> ${badge(t(job.status), job.status === "failed" || job.status === "interrupted" ? "error" : active ? "pending" : "")}<p>${esc(repo?.name || resource)} · ${esc(t("stage_" + job.stage))}</p>${job.error ? `<div class="job-error">${esc(errorText({ message: job.error, code: job.code }))}</div>` : ""}<small>${esc(date(job.created_at))} · ${esc(job.id.slice(0, 8))}</small></div></article>`;
}
function render() {
  if (!dictionary) return;
  const titleKeys = {
    repos: ["reposTitle", "reposSubtitle", "addRepo"],
    keys: ["keysTitle", "keysSubtitle", "createKey"],
    hosts: ["hostsTitle", "hostsSubtitle", "verifyHost"],
    activity: ["activityTitle", "activitySubtitle", null],
    settings: ["settingsTitle", "settingsSubtitle", null],
  };
  const [title, subtitle, primary] = titleKeys[view];
  $("#title").textContent = t(title);
  $("#subtitle").textContent = t(subtitle);
  $("#primary").textContent = primary ? "＋ " + t(primary) : "";
  $("#primary").hidden = !primary;
  document.querySelectorAll("[data-view]").forEach((node) => {
    node.classList.toggle("active", node.dataset.view === view);
    node.setAttribute(
      "aria-current",
      node.dataset.view === view ? "page" : "false",
    );
  });
  if (!state) return;
  $("#repo-count").textContent = Object.keys(state.repos).length;
  $("#key-count").textContent = Object.keys(state.keys).length;
  $("#app-count").textContent = Object.keys(state.deployments).length;
  $("#app-version").textContent = "v" + state.version;
  $("#environment").textContent = environmentText();
  $("#connection").textContent = environmentText();
  $("#connection").classList.toggle("pending", !supervisor?.connected);
  const pending = Object.values(state.jobs).filter(
    (j) => !terminal.has(j.status),
  );
  $("#active-count").hidden = !pending.length;
  $("#active-count").textContent = pending.length;
  $("#active-jobs").hidden = !pending.length || view === "activity";
  $("#active-jobs").innerHTML = pending.length
    ? `<div class="section-title"><h2>${esc(t("jobs"))}</h2>${button("activity", t("activity"))}</div>${pending.slice(0, 3).map(jobCard).join("")}`
    : "";
  const signature = JSON.stringify([
    view,
    state.repos,
    state.keys,
    state.hosts,
    state.deployments,
    state.transactions,
    state.events,
    view === "activity" ? state.jobs : null,
    supervisor,
    preferences,
    repoSearch,
    logSearch,
    logLevel,
  ]);
  if (signature === lastRender) return;
  lastRender = signature;
  const focused = document.activeElement,
    focus =
      focused?.id && $("#view-content").contains(focused)
        ? {
            id: focused.id,
            start: focused.selectionStart,
            end: focused.selectionEnd,
          }
        : null;
  $("#view-content").innerHTML = {
    repos: renderRepos,
    keys: renderKeys,
    hosts: renderHosts,
    activity: renderActivity,
    settings: renderSettings,
  }[view]();
  if (focus) {
    const node = document.getElementById(focus.id);
    node?.focus();
    if (node?.setSelectionRange && focus.start !== null)
      node.setSelectionRange(focus.start, focus.end);
  }
}
function renderRepos() {
  const repos = Object.values(state.repos),
    filtered = repos.filter((r) =>
      (r.name + " " + r.url + " " + r.ref)
        .toLowerCase()
        .includes(repoSearch.toLowerCase()),
    );
  let html = `<div class="section-title"><h2>${esc(t("yourRepos"))}</h2><label class="sr-only" for="repo-search">${esc(t("searchRepos"))}</label><input class="search" id="repo-search" type="search" placeholder="${esc(t("searchRepos"))}" value="${esc(repoSearch)}"></div>`;
  if (!repos.length)
    html += empty(
      t("emptyRepos"),
      t("emptyReposText"),
      button("add-repo", t("connectRepo"), "", "primary"),
    );
  else if (!filtered.length) html += empty(t("emptySearch"), "");
  else
    html += filtered
      .map((r) => {
        const managed = r.apps.some(
          (a) =>
            state.deployments[a.slug]?.repo_id === r.id &&
            state.deployments[a.slug].commit !== r.commit,
        );
        const busy = Object.values(state.jobs).some(
          (j) => j.resource === "repo:" + r.id && !terminal.has(j.status),
        );
        return `<article class="card"><div class="repo-head"><div class="repo-icon" aria-hidden="true">⑂</div><div class="repo-main"><h3 class="repo-name">${esc(r.name)}</h3><div class="repo-url">${esc(r.url)}</div><div class="repo-meta"><span>⑂ ${esc(r.ref)}</span><span>${r.url.startsWith("https:") ? "HTTPS" : "SSH"}</span><span>${esc(short(r.commit))}</span><span>${esc(r.sync_interval ? t("every", { minutes: r.sync_interval / 60 }) : t("manual"))}</span></div></div>${badge(busy ? t("running") : managed ? t("changes") : r.commit ? t("synced") : t("pending"), busy || managed ? "pending" : "")}<div class="repo-actions">${button("sync", "↻ " + t("sync"), controls(r.id) + (busy ? " disabled" : ""))}${button("edit-repo", t("edit"), controls(r.id))}${button("credentials", t("credentials"), controls(r.id))}${button("delete-repo", t("remove"), controls(r.id), "subtle danger")}</div></div><div class="sync-time">${esc(t("lastSync"))}: ${esc(date(r.synced_at))}</div>${r.apps.map((a) => appRow(r, a, busy)).join("")}${r.commit && !r.apps.length ? `<div class="app-row"><div><strong>${esc(t("noApps"))}</strong><p>${esc(t("noAppsHelp"))}</p></div></div>` : ""}</article>`;
      })
      .join("");
  const detached = Object.values(state.deployments).filter(
    (d) => !state.repos[d.repo_id]?.apps.some((a) => a.slug === d.slug),
  );
  if (detached.length)
    html +=
      `<div class="section-title spaced"><h2>${esc(t("appCount"))}</h2></div>` +
      detached
        .map((d) =>
          appRow(state.repos[d.repo_id], {
            slug: d.slug,
            name: d.slug,
            version: d.version,
            arch: [],
            path: "",
            description: "",
          }),
        )
        .join("");
  return (
    html +
    `<div class="info-box"><span aria-hidden="true">◇</span><div><strong>${esc(t("privateTitle"))}</strong><p>${esc(t("privateText"))}</p></div></div>`
  );
}
function appRow(repo, app, busy = false) {
  const deployment = state.deployments[app.slug],
    managed = deployment?.repo_id === repo?.id,
    transaction = state.transactions[app.slug];
  const changed = managed && deployment.commit !== repo.commit;
  const runtime = supervisor?.addons?.find(
    (a) => a.slug === "local_" + app.slug,
  );
  let label = transaction
    ? t("recovery")
    : managed
      ? deployment.status === "installed"
        ? changed
          ? t("changes")
          : t("installed")
        : t(deployment.status)
      : deployment
        ? t("otherSource")
        : t("available");
  const metadata = `${esc(t("version"))} ${esc(app.version)}${app.arch.length ? " · " + esc(app.arch.join(", ")) : ""}${app.path ? " · " + esc(app.path) : ""}`;
  const disabled = busy || !state.supervisor || Boolean(deployment && !managed);
  const data = controls(repo?.id || "") + ` data-slug="${esc(app.slug)}"`;
  let buttons = transaction
    ? button(
        "recover",
        t("reviewRecovery"),
        `data-slug="${esc(app.slug)}"`,
        "warning-button",
      )
    : button(
        "deploy",
        managed ? t("update") : t("install"),
        data + (disabled ? " disabled" : ""),
        managed ? "" : "primary",
      );
  if (managed && !transaction) {
    if (state.supervisor) {
      buttons += button(
        "runtime",
        t(runtime?.state === "started" ? "stop" : "start"),
        `data-slug="${esc(app.slug)}" data-runtime="${runtime?.state === "started" ? "stop" : "start"}"`,
      );
      if (runtime?.state === "started")
        buttons += button(
          "runtime",
          t("restart"),
          `data-slug="${esc(app.slug)}" data-runtime="restart"`,
        );
    }
    buttons += button(
      "release",
      t("release"),
      `data-slug="${esc(app.slug)}"`,
      "subtle",
    );
  }
  return `<div class="app-row"><div class="app-description"><strong>${esc(app.name)}</strong> ${badge(label, transaction || deployment?.status === "error" ? "error" : changed ? "pending" : "")}<p>${metadata}</p><p>${esc(app.description)}</p>${managed ? `<p>${esc(t("appliedCommit"))}: <code>${esc(short(deployment.commit))}</code> · ${esc(t(runtime?.state || "unknown"))}</p>` : ""}</div><div class="app-actions">${buttons}</div></div>`;
}
function renderKeys() {
  const keys = Object.values(state.keys);
  return (
    (keys.length
      ? keys
          .map((key) => {
            const used = Object.values(state.repos).filter(
              (r) => r.key_id === key.id,
            ).length;
            return `<article class="card key-card"><div class="section-title"><h2>${esc(key.name)}</h2>${badge("Ed25519")}</div><p class="muted">${esc(t("keyInstructions"))}</p><label class="sr-only" for="key-${key.id}">${esc(t("publicKey"))}</label><textarea id="key-${key.id}" class="public-key" readonly rows="3" spellcheck="false">${esc(key.public)}</textarea><div class="key-actions">${button("copy-key", t("copyPublic"), `data-key="${key.id}"`)}${button("download-key", t("downloadPublic"), `data-key="${key.id}"`)}${button("delete-key", t("remove"), `data-key="${key.id}"` + (used ? " disabled" : ""), "subtle danger")}<small>${esc(used ? t("keyUsed", { count: used }) : t("keyUnused"))}</small></div></article>`;
          })
          .join("")
      : empty(
          t("emptyKeys"),
          t("emptyKeysText"),
          button("new-key", t("createKey"), "", "primary"),
        )) +
    `<div class="info-box"><span aria-hidden="true">↻</span><p>${esc(t("rotateKey"))}</p></div>`
  );
}
function renderHosts() {
  const hosts = Object.entries(state.hosts);
  return hosts.length
    ? hosts
        .map(
          ([id, host]) =>
            `<article class="card host-card"><div class="section-title"><h2>${esc(id)}</h2>${badge(t("verified"))}</div><code class="fingerprint">${esc(host.fingerprint)}</code><div class="host-actions">${button("delete-host", t("remove"), `data-host="${esc(id)}"`, "subtle danger")}</div></article>`,
        )
        .join("")
    : empty(
        t("emptyHosts"),
        t("emptyHostsText"),
        button("verify-host", t("verifyHost"), "", "primary"),
      );
}
function renderActivity() {
  const jobs = Object.values(state.jobs).sort(
    (a, b) => b.created_at - a.created_at,
  );
  const events = state.events
    .map((e) => ({ ...e, message: dictionary.events[e.code] || e.message }))
    .filter(
      (e) =>
        (!logLevel || (e.level || "info") === logLevel) &&
        JSON.stringify(e).toLowerCase().includes(logSearch.toLowerCase()),
    );
  return `<div class="section-title"><h2>${esc(t("jobs"))}</h2>${button("refresh", t("refresh"))}</div><div class="jobs-list">${jobs.length ? jobs.slice(0, 20).map(jobCard).join("") : `<p class="muted">${esc(t("noJobs"))}</p>`}</div><div class="section-title spaced"><h2>${esc(t("logs"))}</h2><a class="button" download href="api/logs?download=true&amp;language=${preferences.language}&amp;level=${encodeURIComponent(logLevel)}&amp;query=${encodeURIComponent(logSearch)}">${esc(t("exportLogs"))}</a></div><div class="log-filters"><label class="sr-only" for="log-search">${esc(t("searchLogs"))}</label><input type="search" id="log-search" value="${esc(logSearch)}" placeholder="${esc(t("searchLogs"))}"><label class="sr-only" for="log-level">${esc(t("all"))}</label><select id="log-level">${["", "info", "warning", "error"].map((level) => `<option value="${level}" ${logLevel === level ? "selected" : ""}>${esc(t(level || "all"))}</option>`).join("")}</select></div><div class="card log-list">${
    events.length
      ? events
          .map(
            (e) =>
              `<div class="event"><time>${esc(date(e.time))}</time><div>${badge(t(e.level || "info"), e.level === "error" ? "error" : "")} <span>${esc(e.message)}</span>${
                e.context && Object.keys(e.context).length
                  ? `<pre>${esc(
                      Object.entries(e.context)
                        .map(
                          ([k, v]) =>
                            k +
                            ": " +
                            (k === "error" && preferences.language === "en"
                              ? t(e.context.error_code || "operation_failed")
                              : v),
                        )
                        .join("\n"),
                    )}</pre>`
                  : ""
              }</div></div>`,
          )
          .join("")
      : `<div class="empty">${esc(t("emptyLogs"))}</div>`
  }</div>`;
}
function renderSettings() {
  return `<div class="settings-grid"><article class="card settings-card"><h2>${esc(t("settings"))}</h2><label>${esc(t("language"))}<select id="setting-language"><option value="es" ${preferences.language === "es" ? "selected" : ""}>Español</option><option value="en" ${preferences.language === "en" ? "selected" : ""}>English</option></select></label><label>${esc(t("appearance"))}<select id="setting-theme">${["system", "light", "dark"].map((theme) => `<option value="${theme}" ${preferences.theme === theme ? "selected" : ""}>${esc(t(theme))}</option>`).join("")}</select></label><p class="muted">${esc(t("preferencesHelp"))}</p></article><article class="card settings-card"><div class="section-title"><h2>${esc(t("environment"))}</h2>${button("refresh", t("refresh"))}</div><dl><dt>Supervisor</dt><dd>${esc(environmentText())}</dd><dt>${esc(t("version"))}</dt><dd>${esc(state.version)}</dd><dt>${esc(t("dataFree"))}</dt><dd>${bytes(state.disk.data_free)}</dd><dt>${esc(t("addonsFree"))}</dt><dd>${bytes(state.disk.addons_free)}</dd><dt>Ingress</dt><dd>172.30.32.2 · :8099</dd></dl></article></div><article class="card settings-card"><h2>${esc(t("securityTitle"))}</h2><p>${esc(t("securityText"))}</p><p class="muted">${esc(t("scopeText"))}</p></article>`;
}
function showView(next) {
  view = next;
  lastRender = "";
  render();
}
function modal(type, title, body, footer = actions(), context = {}) {
  modalContext = { type, ...context };
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = body;
  $("#modal-actions").innerHTML = footer;
  $("#modal-notice").hidden = true;
  if (context.safeFocus) {
    $("#modal-actions [data-action=close-modal]").autofocus = true;
  }
  if (!$("#modal").open) $("#modal").showModal();
  if (!context.safeFocus)
    requestAnimationFrame(() =>
      $(
        "#modal-form input:not([type=hidden]), #modal-form select, #modal-actions button",
      )?.focus(),
    );
}
function keyOptions(selected) {
  return (
    `<option value="">${esc(t("selectKey"))}</option>` +
    Object.values(state.keys)
      .map(
        (k) =>
          `<option value="${k.id}" ${k.id === selected ? "selected" : ""}>${esc(k.name)}</option>`,
      )
      .join("")
  );
}
function openRepo(draft = {}) {
  modal(
    "repo",
    t("addRepo"),
    `<p>${esc(t("repoIntro"))}</p>${field("name", "name", draft.name || "", 'required maxlength="80" placeholder="Pivigia"')}${field("repoUrl", "url", draft.url || "", 'required maxlength="2048" placeholder="ssh://forgejo@servidor:2233/usuario/repo.git"')}${field("branch", "ref", draft.ref || "main", 'required maxlength="200"')}<label>${esc(t("sshKey"))}<select name="key_id">${keyOptions(draft.key_id)}</select></label><div class="form-inline">${button("repo-new-key", t("newKey"))}${button("repo-verify-host", t("verifyHost"))}</div><p class="form-note">${esc(t("sshHelp"))}</p><details ${draft.url?.startsWith("https:") ? "open" : ""}><summary>${esc(t("httpsCredentials"))}</summary>${field("username", "username", draft.username || "git", 'autocomplete="off"')}${field("token", "token", draft.token || "", 'type="password" autocomplete="new-password" maxlength="4096"')}<small>${esc(t("tokenHelp"))}</small></details>`,
  );
}
function openKey(draft) {
  modal(
    "key",
    t("createKey"),
    `<p>${esc(t("keyIntro"))}</p>${field("keyName", "name", "", 'required maxlength="80" placeholder="Forgejo · Home Assistant"')}`,
    actions("createKey"),
    { draft },
  );
}
function openTrust(draft) {
  modal(
    "trust",
    t("verifyHost"),
    `${field("hostUrl", "url", draft?.url || "", 'required placeholder="ssh://git@servidor/usuario/repo.git"')}${button("scan-host", t("scanHost"))}<div id="fingerprint-result"></div>`,
    button("close-modal", t("close")),
    { draft, scan: null },
  );
}
function confirm(title, text, callback, queued = false) {
  modal("confirm", title, `<p>${esc(text)}</p>`, actions("confirm"), {
    callback,
    queued,
  });
}
function closeModal() {
  if (loadingModal) return;
  if (modalContext.draft) {
    openRepo(modalContext.draft);
  } else {
    $("#modal").close();
    modalContext = {};
  }
}
async function quick(label, callback) {
  try {
    await callback();
    notice(t(label));
    await refresh();
  } catch (error) {
    notice(errorText(error), true);
  }
}
async function queue(path, data = {}) {
  const id = Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  await api(path, "POST", data, id);
  notice(t("accepted"));
  await refresh();
}
async function submitModal(event) {
  event.preventDefault();
  if (loadingModal) return;
  loadingModal = true;
  const submits = $("#modal").querySelectorAll("button");
  submits.forEach((b) => (b.disabled = true));
  const data = Object.fromEntries(new FormData(event.target)),
    context = modalContext;
  try {
    if (context.type === "repo") {
      data.key_id = data.key_id || null;
      data.token = data.token || null;
      await api("repos", "POST", data);
    }
    if (context.type === "key") {
      const result = await api("keys", "POST", data);
      await refresh();
      if (context.draft) {
        openRepo({ ...context.draft, key_id: result.id });
        notice(t("saved"));
        return;
      }
      showView("keys");
    }
    if (context.type === "trust") {
      if (!context.scan || data.url !== context.scan.url)
        throw Object.assign(new Error(t("scanAgain")), { code: "scanAgain" });
      await api("hosts/trust", "POST", {
        url: data.url,
        line: context.scan.line,
        fingerprint: data.fingerprint,
      });
      await refresh();
      if (context.draft) {
        openRepo(context.draft);
        notice(t("saved"));
        return;
      }
    }
    if (context.type === "credentials") {
      data.key_id = data.key_id || null;
      data.token = data.token || null;
      await api(`repos/${context.repo}/credentials`, "POST", data);
    }
    if (context.type === "edit") {
      data.sync_interval = Number(data.sync_interval) * 60;
      await api(`repos/${context.repo}`, "PATCH", data);
    }
    if (context.type === "deploy") {
      await queue(`repos/${context.repo}/deploy`, {
        slug: context.slug,
        update: context.update,
        confirmed: true,
        expected_commit: context.commit,
        adopt_existing: data.adopt_existing === "true",
        expected_local_digest:
          context.inspection.exists && !context.inspection.managed
            ? context.inspection.local_digest
            : null,
      });
    }
    if (context.type === "confirm") await context.callback();
    if (context.type === "recover")
      await queue(`apps/${context.slug}/recover`, {
        confirmed: true,
        accept_current: data.accept_current === "true",
      });
    $("#modal").close();
    notice(
      t(context.queued || context.type === "recover" ? "accepted" : "saved"),
    );
    await refresh();
  } catch (error) {
    $("#modal-notice").textContent = errorText(error);
    $("#modal-notice").hidden = false;
  } finally {
    loadingModal = false;
    $("#modal")
      .querySelectorAll("button")
      .forEach((b) => (b.disabled = false));
  }
}
$("#modal-form").addEventListener("submit", submitModal);
$("#modal").addEventListener("cancel", (event) => {
  event.preventDefault();
  closeModal();
});
$("#notice-close").onclick = () => ($("#notice").hidden = true);
$("#primary").onclick = () =>
  view === "repos" ? openRepo() : view === "keys" ? openKey() : openTrust();
document.addEventListener("click", async (event) => {
  const node = event.target.closest("button");
  if (!node) return;
  if (node.dataset.view) {
    showView(node.dataset.view);
    return;
  }
  const action = node.dataset.action,
    id = node.dataset.repo,
    slug = node.dataset.slug,
    key = node.dataset.key;
  if (!action) return;
  if (action === "close-modal") {
    closeModal();
    return;
  }
  if (action === "activity") {
    showView("activity");
    return;
  }
  if (action === "add-repo") openRepo();
  if (action === "new-key") openKey();
  if (action === "verify-host") openTrust();
  if (action === "repo-new-key")
    openKey(Object.fromEntries(new FormData($("#modal-form"))));
  if (action === "repo-verify-host")
    openTrust(Object.fromEntries(new FormData($("#modal-form"))));
  if (action === "scan-host") {
    if (loadingModal) return;
    loadingModal = true;
    node.disabled = true;
    try {
      const url = $("#modal-form [name=url]").value,
        result = await api("hosts/scan", "POST", { url });
      modalContext.scan = { ...result, url };
      $("#fingerprint-result").innerHTML =
        `<h3>${esc(t("presentedFingerprint"))}</h3><code class="fingerprint">${esc(result.fingerprint)}</code><p>${esc(t("fingerprintHelp"))}</p>${field("expectedFingerprint", "fingerprint", "", 'required pattern="SHA256:.+" autocomplete="off"')}`;
      $("#modal-actions").innerHTML = actions("trustHost");
      $("#modal-notice").hidden = true;
    } catch (error) {
      $("#modal-notice").textContent = errorText(error);
      $("#modal-notice").hidden = false;
    } finally {
      loadingModal = false;
      node.disabled = false;
    }
  }
  if (action === "sync") quick("accepted", () => queue(`repos/${id}/sync`));
  if (action === "refresh") {
    await quick("saved", async () => {
      await refresh();
      await checkSupervisor();
    });
  }
  if (action === "edit-repo") {
    const repo = state.repos[id];
    modal(
      "edit",
      t("editRepo"),
      `${field("name", "name", repo.name, 'required maxlength="80"')}${field("branch", "ref", repo.ref, 'required maxlength="200"')}<p class="form-note">${esc(t("refHelp"))}</p>${field("intervalMinutes", "sync_interval", (repo.sync_interval || 0) / 60, 'type="number" min="0" max="10080" step="5" required')}<p class="form-note">${esc(t("intervalHelp"))}</p>`,
      actions(),
      { repo: id },
    );
  }
  if (action === "credentials")
    modal(
      "credentials",
      t("credentials"),
      `<p>${esc(t("credentialsHelp"))}</p><label>${esc(t("sshKey"))}<select name="key_id">${keyOptions(state.repos[id].key_id)}</select></label>${field("username", "username", state.repos[id].username || "git", 'maxlength="128"')}${field("token", "token", "", 'type="password" autocomplete="new-password" maxlength="4096"')}`,
      actions(),
      { repo: id },
    );
  if (action === "delete-repo")
    confirm(t("deleteRepoTitle"), t("deleteRepoText"), () =>
      api(`repos/${id}`, "DELETE"),
    );
  if (action === "delete-key")
    confirm(t("deleteKeyTitle"), t("deleteKeyText"), () =>
      api(`keys/${key}`, "DELETE"),
    );
  if (action === "delete-host")
    confirm(t("remove"), t("deleteHostText"), () =>
      api(`hosts/${encodeURIComponent(node.dataset.host)}`, "DELETE"),
    );
  if (action === "copy-key") {
    try {
      await navigator.clipboard.writeText(state.keys[key].public);
      notice(t("copyOk"));
    } catch (_) {
      notice(t("copyFallback"), true);
    }
  }
  if (action === "download-key") {
    const url = URL.createObjectURL(
        new Blob([state.keys[key].public + "\n"], { type: "text/plain" }),
      ),
      anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "ha-private-git.pub";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  if (action === "deploy") {
    if (checkingDeployment) return;
    checkingDeployment = true;
    node.setAttribute("aria-busy", "true");
    try {
      const repo = state.repos[id],
        app = repo.apps.find((a) => a.slug === slug);
      const inspection = await api(`repos/${id}/preflight`, "POST", { slug });
      let body = `<p>${esc(t("deployText", { name: app.name, version: app.version, commit: short(inspection.commit) }))}</p>`;
      if (inspection.exists && !inspection.managed) {
        body += `<fieldset><legend>${esc(t("existingFolderTitle"))}</legend><p><code>${esc(inspection.path)}</code></p><p>${esc(t(inspection.installed ? "existingInstalled" : "existingNotInstalled"))}</p>`;
        if (inspection.local_version)
          body += `<p>${esc(t("existingVersion"))}: ${esc(inspection.local_version)}</p>`;
        body += `<p id="adoption-help">${esc(t(inspection.empty ? "existingEmptyHelp" : "existingFolderHelp"))}</p>`;
        if (inspection.requires_adoption)
          body += `<label class="radio" for="adoption-consent"><input id="adoption-consent" type="checkbox" name="adopt_existing" value="true" required aria-describedby="adoption-help">${esc(t("adoptionConsent"))}</label>`;
        body += "</fieldset>";
      }
      body += `<p>${esc(t("longOperation"))}</p>`;
      modal(
        "deploy",
        t(inspection.requires_adoption ? "adoptAndInstall" : "deployTitle"),
        body,
        actions(inspection.requires_adoption ? "adoptAndInstall" : "confirm"),
        {
          repo: id,
          slug,
          commit: inspection.commit,
          update: Boolean(state.deployments[slug]),
          inspection,
          queued: true,
          safeFocus: true,
        },
      );
    } catch (error) {
      notice(errorText(error), true);
    } finally {
      checkingDeployment = false;
      node.removeAttribute("aria-busy");
    }
  }
  if (action === "runtime")
    confirm(
      t(node.dataset.runtime),
      t("confirmRuntime", { action: t(node.dataset.runtime) }),
      () => queue(`apps/${slug}/${node.dataset.runtime}`, { confirmed: true }),
      true,
    );
  if (action === "release")
    confirm(t("release"), t("releaseText"), () =>
      api(`apps/${slug}/release`, "POST", { confirmed: true }),
    );
  if (action === "recover")
    modal(
      "recover",
      t("reviewRecovery"),
      `<p>${esc(t("recoveryIntro"))}</p><div class="warning-box">${esc(t("recoveryHelp"))}</div><label class="radio"><input name="accept_current" type="radio" value="false" checked> ${esc(t("recoverySource"))}</label><label class="radio"><input name="accept_current" type="radio" value="true"> ${esc(t("recoveryAccept"))}</label><label class="radio"><input type="checkbox" required> ${esc(t("recoveryChecked"))}</label>`,
      actions("confirm"),
      { slug },
    );
});
document.addEventListener("input", (event) => {
  if (event.target.id === "repo-search") {
    repoSearch = event.target.value;
    render();
  }
  if (event.target.id === "log-search") {
    logSearch = event.target.value;
    render();
  }
});
document.addEventListener("change", (event) => {
  if (["header-language", "setting-language"].includes(event.target.id))
    setLanguage(event.target.value).catch(() =>
      notice(t("connectionLost"), true),
    );
  if (event.target.id === "setting-theme") {
    setTheme(event.target.value);
    lastRender = "";
    render();
  }
  if (event.target.id === "log-level") {
    logLevel = event.target.value;
    render();
  }
});
async function poll() {
  clearTimeout(pollTimer);
  if (document.hidden) {
    pollTimer = setTimeout(poll, 10000);
    return;
  }
  try {
    await refresh();
  } catch (error) {
    disconnected = true;
    notice(t("connectionLost"), true);
  }
  const active =
    state && Object.values(state.jobs).some((j) => !terminal.has(j.status));
  pollTimer = setTimeout(poll, active ? 1500 : 10000);
}
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    clearTimeout(pollTimer);
    poll();
  }
});
setTheme(preferences.theme);
await setLanguage(preferences.language);
await poll();
await checkSupervisor();
setInterval(() => {
  if (!document.hidden) checkSupervisor();
}, 30000);
