const state = {
  selectedJobId: null,
  jobNodes: new Map(),
  queue: [],
  nextQueueId: 1,
  currentProbe: null,
  currentProbeUrl: "",
  updates: {},
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || data.message || "API error");
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

function fillSelect(select, values, valueKey = null, labelKey = null) {
  const current = select.value;
  select.innerHTML = "";
  values.forEach((item) => {
    const option = document.createElement("option");
    option.value = valueKey ? item[valueKey] : item.value ?? item;
    option.textContent = labelKey ? item[labelKey] : item.label ?? item;
    option.dataset.raw = JSON.stringify(item);
    select.appendChild(option);
  });
  if ([...select.options].some((option) => option.value === current)) {
    select.value = current;
  }
}

async function loadConfig() {
  const data = await api("/api/config");
  const config = data.config;
  $("appRoot").textContent = data.app_root;
  $("outputDir").value = config.download_dir;
  $("container").value = ["mp4", "mkv", "webm"].includes(config.default_container) ? config.default_container : "mp4";
  setMode(config.default_mode || "video");
  $("parallel").value = config.max_parallel_downloads || 2;
  $("cookiesPath").value = config.cookies_path || "";
  syncMode();
}

async function fetchFormats() {
  const url = inputUrl();
  if (!url) {
    setProbeState("URLを入力してください。");
    return;
  }
  if (!dependenciesReady()) {
    setProbeState("yt-dlp と ffmpeg を先に取得してください。");
    return;
  }
  $("fetchFormatsButton").disabled = true;
  $("urlInput").disabled = true;
  resetProbeResult();
  setProbeState("形式を確認中...");
  try {
    const probe = await probeUrl(url);
    state.currentProbe = probe.result;
    state.currentProbeUrl = url;
    renderFormatOptions(probe.result);
    setProbeState("形式を取得しました。URLは変更できます。");
    $("formatSummary").textContent = probe.result.title || url;
  } catch (error) {
    setProbeState(error.message);
  } finally {
    $("urlInput").disabled = false;
    $("fetchFormatsButton").disabled = false;
    syncClearUrlButton();
    syncMode();
  }
}

async function probeUrl(url) {
  return api("/api/probe", {
    method: "POST",
    body: JSON.stringify({
      url,
      cookies_path: $("cookiesPath").value,
      use_browser_cookies: $("browserCookies").checked,
    }),
  });
}

function addToQueue() {
  const url = inputUrl();
  if (!state.currentProbe || url !== state.currentProbeUrl) {
    setProbeState("現在のURLで形式取得してからキューに追加してください。");
    return;
  }
  const payload = currentPayload(url, state.currentProbe);
  if (!payload.selected_format) {
    setProbeState("DLする形式を選択してください。");
    return;
  }
  const queueItem = {
    id: state.nextQueueId++,
    title: state.currentProbe.title || url,
    url,
    mode: payload.mode,
    container: payload.container,
    thumbnail_url: payload.thumbnail_url,
    payload,
    started: false,
  };
  state.queue.push(queueItem);
  renderQueue();
  clearUrlWorkflow();
  setProbeState("キューに追加しました。");
}

async function startQueuedItem(id) {
  const item = state.queue.find((entry) => entry.id === id);
  if (!item || item.started) {
    return;
  }
  item.started = true;
  item.payload.parallel = Number($("parallel").value || 2);
  renderQueue();
  try {
    const data = await api("/api/downloads", {
      method: "POST",
      body: JSON.stringify(item.payload),
    });
    state.selectedJobId = data.jobs[0]?.id || state.selectedJobId;
    state.queue = state.queue.filter((entry) => entry.id !== id);
    renderQueue();
    await refreshJobs();
  } catch (error) {
    item.started = false;
    setProbeState(error.message);
    renderQueue();
  }
}

async function startAllQueued() {
  const pending = state.queue.filter((entry) => !entry.started);
  if (!pending.length) {
    return;
  }
  pending.forEach((item) => {
    item.started = true;
    item.payload.parallel = Number($("parallel").value || 2);
  });
  renderQueue();
  try {
    const pendingIds = new Set(pending.map((item) => item.id));
    const data = await api("/api/download-batch", {
      method: "POST",
      body: JSON.stringify({
        parallel: Number($("parallel").value || 2),
        items: pending.map((item) => item.payload),
      }),
    });
    state.selectedJobId = data.jobs[0]?.id || state.selectedJobId;
    state.queue = state.queue.filter((entry) => !pendingIds.has(entry.id));
    renderQueue();
    await refreshJobs();
  } catch (error) {
    pending.forEach((item) => {
      item.started = false;
    });
    setProbeState(error.message);
    renderQueue();
  }
}

function removeQueuedItem(id) {
  state.queue = state.queue.filter((entry) => entry.id !== id);
  renderQueue();
}

function renderQueue() {
  $("queueSummary").textContent = `${state.queue.length}件`;
  const root = $("queueItems");
  if (!state.queue.length) {
    root.innerHTML = '<div class="empty">キューは空です。</div>';
    return;
  }
  root.innerHTML = "";
  state.queue.forEach((item) => {
    const el = document.createElement("article");
    el.className = "queue-item";
    applyCardThumbnail(el, item.thumbnail_url);
    el.innerHTML = `
      <div class="queue-title" title="${escapeHtml(item.url)}">${escapeHtml(item.title)}</div>
      <div class="queue-meta">
        <span>${item.mode === "audio" ? "音声" : "動画"}</span>
        <span>${escapeHtml(item.container)}</span>
        <span>${item.started ? "開始済み" : "未開始"}</span>
      </div>
      <div class="queue-actions">
        <button class="secondary" type="button" data-action="start" ${item.started ? "disabled" : ""}>DL開始</button>
        <button class="secondary" type="button" data-action="remove" ${item.started ? "disabled" : ""}>削除</button>
      </div>
    `;
    el.querySelector('[data-action="start"]').addEventListener("click", () => startQueuedItem(item.id));
    el.querySelector('[data-action="remove"]').addEventListener("click", () => removeQueuedItem(item.id));
    root.appendChild(el);
  });
  syncDependencyGate();
}

function currentPayload(url, probe) {
  const mode = getMode();
  const selected = selectedFormatPayload(mode, probe);
  return {
    urls: url,
    title: probe.title || url,
    mode,
    output_dir: $("outputDir").value,
    container: mode === "audio" ? $("audioContainer").value : $("container").value,
    quality: "最高",
    video_codec: "自動",
    audio_codec: "auto",
    video_encoder: "auto",
    parallel: Number($("parallel").value || 2),
    cookies_path: $("cookiesPath").value,
    use_browser_cookies: $("browserCookies").checked,
    playlist: false,
    artist_metadata: $("artistMetadata").checked,
    metadata: $("metadata").checked,
    thumbnail: $("thumbnail").checked,
    thumbnail_url: probe.thumbnail_url || "",
    subtitles: $("subtitles").checked,
    selected_format: selected,
    extractor_args: probe.extractor_args || "",
    steps: buildSteps(mode, selected),
  };
}

function selectedFormatPayload(mode, probe) {
  const audio = selectedOptionData($("audioFormat"));
  if (mode === "audio") {
    return audio ? {
      audio_format_id: audio.format_id,
      output_ext: $("audioContainer").value,
      extractor_args: probe.extractor_args || "",
    } : null;
  }
  const video = selectedOptionData($("videoFormat"));
  if (!video) {
    return null;
  }
  const outputExt = $("container").value;
  const useSeparateAudio = video.kind !== "muxed" && audio;
  const selected = {
    video_format_id: video.format_id,
    audio_format_id: useSeparateAudio ? audio.format_id : "",
    output_ext: outputExt,
    needs_recode: outputExt === "mp4" && video.ext && video.ext !== "mp4",
    extractor_args: probe.extractor_args || "",
  };
  syncConversionNotice(selected.needs_recode);
  return selected;
}

function selectedOptionData(select) {
  const option = select.selectedOptions?.[0];
  if (!option?.dataset.raw) {
    return null;
  }
  try {
    return JSON.parse(option.dataset.raw);
  } catch {
    return null;
  }
}

function renderFormatOptions(probe) {
  const videoOptions = [...(probe.video_options || []), ...(probe.muxed_options || [])]
    .sort((a, b) => (b.height || 0) - (a.height || 0) || (b.fps || 0) - (a.fps || 0) || (b.bitrate || 0) - (a.bitrate || 0));
  fillSelect($("videoFormat"), videoOptions, "format_id", "label");
  fillSelect($("audioFormat"), probe.audio_options || [], "format_id", "label");
  $("videoFormat").disabled = videoOptions.length === 0;
  $("audioFormat").disabled = (probe.audio_options || []).length === 0;
  $("addQueueButton").disabled = (!videoOptions.length && !(probe.audio_options || []).length) || !dependenciesReady();
  syncConversionNotice(false);
}

function resetProbeResult() {
  state.currentProbe = null;
  state.currentProbeUrl = "";
  $("formatSummary").textContent = "形式取得後に選択できます。";
  fillSelect($("videoFormat"), [{ value: "", label: "形式取得後に表示" }]);
  fillSelect($("audioFormat"), [{ value: "", label: "形式取得後に表示" }]);
  $("videoFormat").disabled = true;
  $("audioFormat").disabled = true;
  $("addQueueButton").disabled = true;
  syncConversionNotice(false);
}

function buildSteps(mode, selected) {
  if (mode === "audio") {
    const steps = ["音声ダウンロード", "音声変換"];
    if ($("artistMetadata").checked) {
      steps.push("メタデータ埋め込み");
    }
    return steps;
  }
  const steps = ["映像ダウンロード", "音声ダウンロード"];
  if (selected?.needs_recode) {
    steps.push("mp4変換");
  } else {
    steps.push("結合");
  }
  if ($("artistMetadata").checked) {
    steps.push("メタデータ埋め込み");
  }
  if ($("thumbnail").checked || $("metadata").checked) {
    steps.push("サムネイル処理");
  }
  if ($("subtitles").checked) {
    steps.push("字幕処理");
  }
  return steps;
}

function inputUrl() {
  return $("urlInput").value.trim();
}

function clearUrlWorkflow() {
  $("urlInput").value = "";
  resetProbeResult();
  syncClearUrlButton();
}

function syncClearUrlButton() {
  $("clearUrlButton").disabled = !$("urlInput").value;
}

async function selectOutputDir() {
  const button = $("selectOutputDir");
  button.disabled = true;
  try {
    const data = await api("/api/select-output-dir", {
      method: "POST",
      body: JSON.stringify({ initial_dir: $("outputDir").value }),
    });
    if (!data.cancelled && data.path) {
      $("outputDir").value = data.path;
    }
  } catch (error) {
    setProbeState(error.message);
  } finally {
    button.disabled = false;
  }
}

async function selectCookiesFile() {
  const button = $("selectCookiesFile");
  button.disabled = true;
  try {
    const data = await api("/api/select-cookies-file", {
      method: "POST",
      body: JSON.stringify({ initial_path: $("cookiesPath").value }),
    });
    if (!data.cancelled && data.path) {
      $("cookiesPath").value = data.path;
      $("browserCookies").checked = false;
    }
  } catch (error) {
    setProbeState(error.message);
  } finally {
    button.disabled = false;
  }
}

async function refreshJobs() {
  const data = await api("/api/jobs");
  renderJobs(data.jobs);
}

async function updateYtDlp() {
  const button = $("updateYtDlp");
  button.disabled = true;
  setYtDlpUpdateStatus("更新確認中...", "running");
  const runningTimer = window.setTimeout(() => {
    setYtDlpUpdateStatus("更新中...", "running");
  }, 800);
  try {
    const data = await api("/api/yt-dlp/update", {
      method: "POST",
      body: "{}",
    });
    setYtDlpUpdateStatus(updateResultText(data), data.status);
  } catch (error) {
    setYtDlpUpdateStatus(`更新に失敗しました: ${error.message}`, "failed");
  } finally {
    window.clearTimeout(runningTimer);
    button.disabled = false;
  }
}

function updateResultText(data) {
  if (data.status === "current") {
    return `最新版です: ${data.after_version || data.before_version || "不明"}`;
  }
  if (data.status === "updated") {
    return `更新しました: ${data.before_version || "不明"} → ${data.after_version || "不明"}`;
  }
  return data.message || "更新結果を確認できませんでした。";
}

async function loadJobLog(jobId) {
  const data = await api(`/api/jobs/${jobId}`);
  state.selectedJobId = jobId;
  const node = state.jobNodes.get(jobId);
  if (!node) {
    return;
  }
  node.log.classList.toggle("hidden");
  node.log.textContent = data.job.log.slice(-80).join("\n");
}

async function cancelJob(jobId) {
  await api(`/api/jobs/${jobId}/cancel`, { method: "POST", body: "{}" });
  await refreshJobs();
}

async function shutdownApp(force = false) {
  try {
    await api("/api/shutdown", {
      method: "POST",
      body: JSON.stringify({ force }),
    });
    document.body.innerHTML = '<main class="shell"><section class="section"><h1>終了しました</h1><p>このタブは閉じて構いません。</p></section></main>';
  } catch (error) {
    if (error.status === 409 && confirm("実行中または待機中のジョブがあります。キャンセルして終了しますか？")) {
      await shutdownApp(true);
      return;
    }
    setProbeState(error.message);
  }
}

function renderJobs(jobs) {
  $("progressSummary").textContent = summaryText(jobs);
  const root = $("jobs");
  if (!jobs.length) {
    state.jobNodes.clear();
    root.innerHTML = '<div class="empty">まだ進捗はありません。</div>';
    return;
  }
  const empty = root.querySelector(".empty");
  if (empty) {
    empty.remove();
  }

  const seen = new Set();
  jobs.forEach((job) => {
    seen.add(job.id);
    let nodes = state.jobNodes.get(job.id);
    if (!nodes) {
      nodes = createJobNode(job);
      state.jobNodes.set(job.id, nodes);
      root.appendChild(nodes.root);
    }
    updateJobNode(nodes, job);
  });

  for (const [jobId, nodes] of state.jobNodes.entries()) {
    if (!seen.has(jobId)) {
      nodes.root.remove();
      state.jobNodes.delete(jobId);
    }
  }
}

function createJobNode(job) {
  const root = document.createElement("article");
  root.className = "job";
  root.dataset.jobId = job.id;
  root.innerHTML = `
    <div class="job-head">
      <div class="job-url"></div>
      <span class="status"></span>
    </div>
    <div class="bar"><span></span></div>
    <div class="job-meta">
      <span data-field="message"></span>
      <span class="info-mark" data-field="detail" title="">i</span>
      <span data-field="percent"></span>
      <span data-field="speed"></span>
      <span data-field="eta"></span>
      <span data-field="kind"></span>
    </div>
    <ol class="step-list"></ol>
    <div class="job-actions">
      <button class="secondary" type="button" data-action="log">ログ</button>
      <button class="secondary" type="button" data-action="cancel">キャンセル</button>
    </div>
    <pre class="log hidden"></pre>
  `;
  root.querySelector('[data-action="log"]').addEventListener("click", () => loadJobLog(job.id));
  root.querySelector('[data-action="cancel"]').addEventListener("click", () => cancelJob(job.id));
  return {
    root,
    url: root.querySelector(".job-url"),
    status: root.querySelector(".status"),
    bar: root.querySelector(".bar span"),
    message: root.querySelector('[data-field="message"]'),
    detail: root.querySelector('[data-field="detail"]'),
    percent: root.querySelector('[data-field="percent"]'),
    speed: root.querySelector('[data-field="speed"]'),
    eta: root.querySelector('[data-field="eta"]'),
    kind: root.querySelector('[data-field="kind"]'),
    steps: root.querySelector(".step-list"),
    cancel: root.querySelector('[data-action="cancel"]'),
    log: root.querySelector(".log"),
  };
}

function updateJobNode(nodes, job) {
  const percent = job.percent == null ? 0 : Math.max(0, Math.min(100, job.percent));
  applyCardThumbnail(nodes.root, job.thumbnail_url);
  setText(nodes.url, job.title || job.url);
  nodes.url.title = job.url;
  setText(nodes.status, job.status);
  nodes.status.className = `status ${job.status}`;
  nodes.bar.style.width = `${percent}%`;
  setText(nodes.message, job.message || "");
  nodes.detail.title = job.detail || job.message || "";
  setText(nodes.percent, `${percent.toFixed(1)}%`);
  setText(nodes.speed, job.speed || "");
  setText(nodes.eta, job.eta ? `ETA ${job.eta}` : "");
  setText(nodes.kind, `${job.mode === "audio" ? "音声" : "動画"} / ${job.container}`);
  renderStepList(nodes.steps, job);
  nodes.cancel.classList.toggle("hidden", !(job.status === "running" || job.status === "queued"));
}

function renderStepList(root, job) {
  const steps = job.steps?.length ? job.steps : defaultSteps(job);
  const current = job.current_step || inferCurrentStep(job);
  const failed = job.failed_step || (job.status === "failed" ? current : "");
  root.innerHTML = steps.map((step) => {
    let cls = "";
    if (failed === step) cls = "failed";
    else if (current === step && job.status === "running") cls = "active";
    else if (stepIsDone(step, current, steps, job)) cls = "done";
    return `<li class="${cls}">${escapeHtml(step)}</li>`;
  }).join("");
}

function defaultSteps(job) {
  return job.mode === "audio"
    ? ["音声ダウンロード", "音声変換", "メタデータ埋め込み"]
    : ["映像ダウンロード", "音声ダウンロード", "結合", "メタデータ埋め込み"];
}

function inferCurrentStep(job) {
  const msg = `${job.message || ""} ${job.detail || ""}`;
  if (msg.includes("mp4") || msg.includes("VideoConvertor")) return "mp4変換";
  if (msg.includes("結合") || msg.includes("Merger")) return "結合";
  if (msg.includes("音声を抽出") || msg.includes("ExtractAudio")) return "音声変換";
  if (msg.includes("サムネイル") || msg.includes("Thumbnail")) return "サムネイル処理";
  if (msg.includes("字幕") || msg.includes("Subtitle")) return "字幕処理";
  if (msg.includes("メタデータ") || msg.includes("Metadata")) return "メタデータ埋め込み";
  if (job.mode === "audio") return "音声ダウンロード";
  return job.percent && job.percent > 50 ? "音声ダウンロード" : "映像ダウンロード";
}

function stepIsDone(step, current, steps, job) {
  if (job.status === "done") return true;
  const currentIndex = steps.indexOf(current);
  const stepIndex = steps.indexOf(step);
  return currentIndex > 0 && stepIndex >= 0 && stepIndex < currentIndex;
}

function summaryText(jobs) {
  if (!jobs.length) return "待機中";
  const running = jobs.filter((job) => job.status === "running").length;
  const queued = jobs.filter((job) => job.status === "queued").length;
  const done = jobs.filter((job) => job.status === "done").length;
  const failed = jobs.filter((job) => job.status === "failed").length;
  return `実行中 ${running} / 待機 ${queued} / 完了 ${done} / 失敗 ${failed}`;
}

function syncMode() {
  const audio = getMode() === "audio";
  document.querySelectorAll(".video-field").forEach((node) => {
    node.classList.toggle("hidden", audio);
  });
  document.querySelectorAll(".audio-field").forEach((node) => {
    node.classList.toggle("hidden", !audio);
  });
  if ($("audioFormat")) {
    $("audioFormat").disabled = !state.currentProbe || !(state.currentProbe.audio_options || []).length;
  }
  if ($("videoFormat")) {
    $("videoFormat").disabled = audio || !state.currentProbe || !((state.currentProbe.video_options || []).length || (state.currentProbe.muxed_options || []).length);
  }
}

function getMode() {
  return document.querySelector('input[name="modeSelect"]:checked')?.value || "video";
}

function setMode(mode) {
  const input = document.querySelector(`input[name="modeSelect"][value="${mode === "audio" ? "audio" : "video"}"]`);
  if (input) {
    input.checked = true;
  }
}

function syncConversionNotice(willRecode = false) {
  const notice = $("conversionNotice");
  notice.classList.toggle("hidden", !willRecode);
  if (willRecode) {
    notice.textContent = "mp4へ変換します。GPUエンコーダを使用しますが、結合ではなく再エンコードなので動画の長さと解像度で処理時間が変わります。";
  }
}

function setProbeState(text) {
  $("probeState").textContent = text;
}

function setYtDlpUpdateStatus(text, status = "") {
  const node = $("ytDlpUpdateStatus");
  node.textContent = text;
  node.className = `update-status ${status}`.trim();
}

function setText(node, value) {
  const text = String(value ?? "");
  if (node.textContent !== text) node.textContent = text;
}

function applyCardThumbnail(node, thumbnailUrl) {
  if (!thumbnailUrl) {
    node.classList.remove("has-thumbnail");
    node.style.removeProperty("--thumb-url");
    return;
  }
  node.classList.add("has-thumbnail");
  node.style.setProperty("--thumb-url", `url("${cssUrl(thumbnailUrl)}")`);
}

function cssUrl(value) {
  return String(value).replaceAll("\\", "\\\\").replaceAll('"', '\\"');
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

$("fetchFormatsButton").addEventListener("click", fetchFormats);
$("clearUrlButton").addEventListener("click", () => {
  clearUrlWorkflow();
  setProbeState("URLをクリアしました。");
});
$("addQueueButton").addEventListener("click", addToQueue);
$("startAllButton").addEventListener("click", startAllQueued);
$("shutdownButton").addEventListener("click", () => shutdownApp(false));
$("selectOutputDir").addEventListener("click", selectOutputDir);
$("selectCookiesFile").addEventListener("click", selectCookiesFile);
$("refreshJobs").addEventListener("click", refreshJobs);
$("checkUpdates").addEventListener("click", () => loadUpdates(true));
$("updateYtDlp").addEventListener("click", updateYtDlp);
$("updateFfmpeg").addEventListener("click", updateFfmpeg);
$("updateApp").addEventListener("click", updateApp);
document.querySelectorAll('input[name="modeSelect"]').forEach((input) => {
  input.addEventListener("change", syncMode);
});
$("urlInput").addEventListener("input", () => {
  syncClearUrlButton();
  if (inputUrl() !== state.currentProbeUrl) {
    resetProbeResult();
  }
});
$("container").addEventListener("change", () => {
  if (state.currentProbe) {
    selectedFormatPayload(getMode(), state.currentProbe);
  }
});
$("videoFormat").addEventListener("change", () => {
  if (state.currentProbe) {
    selectedFormatPayload(getMode(), state.currentProbe);
  }
});
$("urlInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    fetchFormats();
  }
});

syncClearUrlButton();
renderQueue();
Promise.all([loadConfig(), loadUpdates(false)]).then(refreshJobs).catch((error) => {
  $("appRoot").textContent = error.message;
});
setInterval(refreshJobs, 1500);

async function loadUpdates(refresh = false) {
  try {
    const data = await api(`/api/updates${refresh ? "?refresh=1" : ""}`);
    state.updates = data.updates || {};
    renderUpdates();
    syncDependencyGate();
  } catch (error) {
    $("updateSummary").textContent = `更新確認に失敗しました: ${error.message}`;
  }
}

function renderUpdates() {
  const updates = state.updates || {};
  const items = [updates.app, updates.yt_dlp, updates.ffmpeg].filter(Boolean);
  const missingTools = [updates.yt_dlp, updates.ffmpeg].filter((item) => item && !item.installed).length;
  const available = items.filter((item) => item.available).length;
  if (missingTools) {
    $("updateSummary").textContent = "初回セットアップが必要です。yt-dlp と ffmpeg を取得してください。";
  } else if (available) {
    $("updateSummary").textContent = `${available} 件の更新があります。`;
  } else if (items.length) {
    $("updateSummary").textContent = "更新確認が完了しました。";
  }
  renderUpdateCard("app", updates.app);
  renderUpdateCard("yt_dlp", updates.yt_dlp);
  renderUpdateCard("ffmpeg", updates.ffmpeg);
}

function renderUpdateCard(key, item) {
  const card = document.querySelector(`[data-update-card="${key}"]`);
  if (!card || !item) return;
  const status = card.querySelector('[data-update-field="status"]');
  const version = card.querySelector('[data-update-field="version"]');
  const button = card.querySelector("button");
  status.textContent = item.message || "確認済み";
  version.textContent = `現在: ${item.current || "未導入"} / 最新: ${item.latest || "不明"}`;
  card.classList.toggle("missing", !item.installed);
  card.classList.toggle("available", !!item.available);
  if (button) {
    button.disabled = key === "app" ? !item.available : false;
  }
}

function dependenciesReady() {
  const updates = state.updates || {};
  return !!(updates.yt_dlp?.installed && updates.ffmpeg?.installed);
}

function syncDependencyGate() {
  const ready = dependenciesReady();
  if ($("fetchFormatsButton")) $("fetchFormatsButton").disabled = !ready;
  if ($("startAllButton")) $("startAllButton").disabled = !ready || state.queue.every((entry) => entry.started);
  if ($("addQueueButton") && !state.currentProbe) $("addQueueButton").disabled = true;
  if ($("addQueueButton") && state.currentProbe) {
    const hasFormats = (state.currentProbe.video_options || []).length || (state.currentProbe.audio_options || []).length || (state.currentProbe.muxed_options || []).length;
    $("addQueueButton").disabled = !ready || !hasFormats;
  }
}

async function runUpdate(endpoint, buttonId) {
  const button = $(buttonId);
  if (button) button.disabled = true;
  $("updateSummary").textContent = "更新処理中...";
  try {
    const data = await api(endpoint, { method: "POST", body: "{}" });
    $("updateSummary").textContent = data.message || "更新処理が完了しました。";
    if (data.shutdown) {
      document.body.innerHTML = '<main class="shell"><section class="section"><h1>更新を適用しています</h1><p>アプリが自動的に再起動するまでお待ちください。</p></section></main>';
      return;
    }
    await loadUpdates(true);
  } catch (error) {
    $("updateSummary").textContent = `更新に失敗しました: ${error.message}`;
  } finally {
    if (button) button.disabled = false;
  }
}

async function updateYtDlp() {
  await runUpdate("/api/updates/yt-dlp", "updateYtDlp");
}

async function updateFfmpeg() {
  await runUpdate("/api/updates/ffmpeg", "updateFfmpeg");
}

async function updateApp() {
  await runUpdate("/api/updates/app", "updateApp");
}

