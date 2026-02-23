/* robot.js — Robot Inference Dashboard */

// ── State ─────────────────────────────────────────────────────────────────────

const DEFAULT_BROKER = "wss://broker.hivemq.com:8884/mqtt";

const state = {
  client:    null,
  connected: false,
  robotId:   localStorage.getItem("ri-robot-id") || "go2_0",
  brokerUrl: localStorage.getItem("ri-broker-url") || DEFAULT_BROKER,
  policy:    { running: false, step: 0 },
  telemetry: null,
  chatHistory: [],
  chatStreaming: false,
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function prefix() { return `robot/${state.robotId}`; }

function toast(msg, kind = "default", ms = 3000) {
  const el = document.createElement("div");
  el.className = `toast${kind !== "default" ? " " + kind : ""}`;
  el.textContent = msg;
  document.getElementById("toast-container").appendChild(el);
  setTimeout(() => el.remove(), ms);
}

function fmt(n) { return typeof n === "number" ? n.toFixed(3) : "—"; }

// ── Theme ─────────────────────────────────────────────────────────────────────

(function initTheme() {
  const pref = localStorage.getItem("ri-theme") || "system";
  const dark  = pref === "dark" || (pref === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
})();

// ── MQTT ──────────────────────────────────────────────────────────────────────

function setStatus(label, cls) {
  const dot  = document.getElementById("status-dot");
  const text = document.getElementById("status-text");
  dot.className  = "status-dot" + (cls ? " " + cls : "");
  text.textContent = label;
}

function connect() {
  const url = document.getElementById("url-input").value.trim();
  state.brokerUrl = url;
  localStorage.setItem("ri-broker-url", url);

  setStatus("Connecting…", "connecting");
  document.getElementById("connect-btn").textContent = "Connecting…";
  document.getElementById("connect-btn").disabled = true;

  if (state.client) {
    state.client.end(true);
    state.client = null;
  }

  const client = mqtt.connect(url, { keepalive: 30, reconnectPeriod: 3000 });
  state.client = client;

  client.on("connect", () => {
    state.connected = true;
    setStatus("Connected", "connected");
    document.getElementById("connect-btn").textContent = "Disconnect";
    document.getElementById("connect-btn").disabled = false;
    setCommandsEnabled(true);

    client.subscribe(`${prefix()}/state`);
    client.subscribe(`${prefix()}/policy`);
    toast("Connected to broker", "ok");
  });

  client.on("message", (topic, payload) => {
    let data;
    try { data = JSON.parse(payload.toString()); } catch { return; }

    if (topic === `${prefix()}/state`) {
      state.telemetry = data;
      renderTelemetry(data);
    } else if (topic === `${prefix()}/policy`) {
      state.policy = data;
      renderPolicyBadge(data);
    }
  });

  client.on("error",    e  => { setStatus("Error: " + e.message, "error"); });
  client.on("offline",  () => { setStatus("Offline", "error"); setCommandsEnabled(false); });
  client.on("close",    () => {
    state.connected = false;
    if (!state.client?.reconnecting) {
      setStatus("Disconnected", "");
      document.getElementById("connect-btn").textContent = "Connect";
      document.getElementById("connect-btn").disabled = false;
    }
    setCommandsEnabled(false);
  });
}

function disconnect() {
  if (state.client) {
    state.client.end();
    state.client = null;
  }
  state.connected = false;
  setStatus("Disconnected", "");
  document.getElementById("connect-btn").textContent = "Connect";
  setCommandsEnabled(false);
}

function publish(subtopic, payload) {
  if (!state.client || !state.connected) {
    toast("Not connected", "error");
    return;
  }
  state.client.publish(`${prefix()}/${subtopic}`, JSON.stringify(payload));
}

function publishRaw(subtopic, payload) {
  if (!state.client || !state.connected) {
    toast("Not connected", "error");
    return;
  }
  state.client.publish(`${prefix()}/${subtopic}`, payload);
}

// ── Robot ID ──────────────────────────────────────────────────────────────────

function applyRobotId() {
  const newId = document.getElementById("robot-id-input").value.trim();
  if (!newId) return;
  if (state.connected) {
    state.client.unsubscribe(`robot/${state.robotId}/state`);
    state.client.unsubscribe(`robot/${state.robotId}/policy`);
  }
  state.robotId = newId;
  localStorage.setItem("ri-robot-id", newId);
  if (state.connected) {
    state.client.subscribe(`${prefix()}/state`);
    state.client.subscribe(`${prefix()}/policy`);
  }
  toast(`Robot ID set to ${newId}`, "ok");
}

// ── Velocity ──────────────────────────────────────────────────────────────────

function getVel() {
  return {
    vx:   parseFloat(document.getElementById("vx-slider").value),
    vy:   parseFloat(document.getElementById("vy-slider").value),
    vyaw: parseFloat(document.getElementById("vyaw-slider").value),
  };
}

function sendVelocity() {
  publish("command/velocity", getVel());
}

function zeroVelocity() {
  ["vx", "vy", "vyaw"].forEach(k => {
    document.getElementById(`${k}-slider`).value = 0;
    document.getElementById(`${k}-val`).textContent = "0.00";
  });
  sendVelocity();
}

["vx", "vy", "vyaw"].forEach(k => {
  const slider = document.getElementById(`${k}-slider`);
  const label  = document.getElementById(`${k}-val`);
  slider.addEventListener("input", () => {
    label.textContent = parseFloat(slider.value).toFixed(2);
    if (document.getElementById("vel-auto-send").checked && state.connected) {
      sendVelocity();
    }
  });
});

// ── Commands ──────────────────────────────────────────────────────────────────

function sendState(cmd) {
  publishRaw("command/state", cmd);
}

function setCommandsEnabled(on) {
  const ids = [
    "vel-send-btn", "cmd-stand-up", "cmd-stand-down", "cmd-damping",
    "cmd-policy-start", "cmd-policy-stop", "cmd-estop",
  ];
  ids.forEach(id => { document.getElementById(id).disabled = !on; });
}

// ── Telemetry rendering ───────────────────────────────────────────────────────

const JOINT_NAMES = [
  "FL_hip", "FL_thigh", "FL_calf",
  "FR_hip", "FR_thigh", "FR_calf",
  "RL_hip", "RL_thigh", "RL_calf",
  "RR_hip", "RR_thigh", "RR_calf",
];

function renderTelemetry(data) {
  const ts = new Date(data.ts * 1000).toLocaleTimeString();
  document.getElementById("telemetry-ts").textContent = ts;
  document.getElementById("policy-ts").textContent    = `Last: ${ts}`;

  const joints = data.joints || [];

  // IMU: first 9 values (rpy[2] + gyro[3] + accel[3])
  const imuRow = document.getElementById("imu-row");
  const imuLabels = ["Roll", "Pitch", "ωx", "ωy", "ωz", "ax", "ay", "az"];
  imuRow.innerHTML = imuLabels.map((l, i) => `
    <div class="imu-cell">
      <div class="imu-label">${l}</div>
      <div class="imu-val">${fmt(joints[i])}</div>
    </div>`).join("");

  // Joints: next 12
  const jointGrid = document.getElementById("joint-grid");
  const JOINT_START = 8;
  jointGrid.innerHTML = JOINT_NAMES.map((n, i) => `
    <div class="joint-cell">
      <div class="joint-name">${n}</div>
      <div class="joint-val">${fmt(joints[JOINT_START + i])}</div>
    </div>`).join("");
}

function renderPolicyBadge(data) {
  const badge = document.getElementById("policy-badge");
  const label = document.getElementById("policy-badge-label");
  const step  = document.getElementById("policy-step");

  if (data.running) {
    badge.className = "policy-badge running";
    label.textContent = "Running";
  } else {
    badge.className = "policy-badge stopped";
    label.textContent = "Stopped";
  }
  step.textContent = `Step ${data.step ?? "—"}`;
}

// ── AI Chat ───────────────────────────────────────────────────────────────────

const ROBOT_TOOLS = [
  {
    name: "move",
    description: "Set robot velocity command. Call this to make the robot walk in a direction.",
    input_schema: {
      type: "object",
      properties: {
        vx:   { type: "number", description: "Forward velocity in m/s. Range: -1.0 to 1.0" },
        vy:   { type: "number", description: "Lateral velocity in m/s. Range: -0.5 to 0.5" },
        vyaw: { type: "number", description: "Yaw (turn) rate in rad/s. Range: -1.0 to 1.0" },
      },
      required: ["vx", "vy", "vyaw"],
    },
  },
  {
    name: "set_state",
    description: "Send a state command to the robot.",
    input_schema: {
      type: "object",
      properties: {
        state: {
          type: "string",
          enum: ["stand_up", "stand_down", "damping", "policy_start", "policy_stop"],
          description: "stand_up: rise to standing. stand_down: crouch. damping: low-gain safe mode. policy_start/stop: start or stop the RL policy loop.",
        },
      },
      required: ["state"],
    },
  },
  {
    name: "stop",
    description: "Immediately zero all velocity commands (emergency stop).",
    input_schema: { type: "object", properties: {} },
  },
];

function execTool(name, input) {
  if (name === "move") {
    const vx   = Math.max(-1.0, Math.min(1.0, input.vx   ?? 0));
    const vy   = Math.max(-0.5, Math.min(0.5, input.vy   ?? 0));
    const vyaw = Math.max(-1.0, Math.min(1.0, input.vyaw ?? 0));
    document.getElementById("vx-slider").value   = vx;
    document.getElementById("vy-slider").value   = vy;
    document.getElementById("vyaw-slider").value = vyaw;
    document.getElementById("vx-val").textContent   = vx.toFixed(2);
    document.getElementById("vy-val").textContent   = vy.toFixed(2);
    document.getElementById("vyaw-val").textContent = vyaw.toFixed(2);
    publish("command/velocity", { vx, vy, vyaw });
    return `Velocity set: vx=${vx}, vy=${vy}, vyaw=${vyaw}`;
  }
  if (name === "set_state") {
    publishRaw("command/state", input.state);
    return `State command sent: ${input.state}`;
  }
  if (name === "stop") {
    zeroVelocity();
    return "Velocity zeroed.";
  }
  return `Unknown tool: ${name}`;
}

function systemPrompt() {
  const vel = getVel();
  return `You are an AI assistant controlling a robot via MQTT.
Current robot ID: ${state.robotId}
Policy running: ${state.policy.running}
Current velocity command: vx=${vel.vx}, vy=${vel.vy}, vyaw=${vel.vyaw}

You have tools to move the robot and send state commands.
Be precise and safe. Only send commands when the user explicitly asks.
If the policy is not running, tell the user to start it before sending velocity commands.`;
}

function getApiKey()   { return localStorage.getItem("ri-api-key") || ""; }
function getModel()    { return document.getElementById("chat-model-select").value; }

function appendChatMsg(role, html, cls = "") {
  const msgs = document.getElementById("chat-messages");
  const el   = document.createElement("div");
  el.className = `chat-msg ${role === "user" ? "chat-msg-user" : "chat-msg-assistant"}${cls ? " " + cls : ""}`;
  el.innerHTML = html;
  msgs.appendChild(el);
  msgs.scrollTop = msgs.scrollHeight;
  return el;
}

function chatMsgMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text));
}

async function sendChat() {
  if (state.chatStreaming) return;
  const input = document.getElementById("chat-input");
  const text  = input.value.trim();
  if (!text) return;

  input.value = "";
  state.chatHistory.push({ role: "user", content: text });
  appendChatMsg("user", DOMPurify.sanitize(text));

  const spinnerEl = appendChatMsg("assistant", `<div class="chat-spinner"><span></span><span></span><span></span></div>`);
  state.chatStreaming = true;
  document.getElementById("chat-send-btn").disabled = true;

  try {
    const modelValue = getModel();
    const [provider, model] = modelValue.split(":");

    let response = "";

    if (provider === "local") {
      response = await callLocalProxy(text);
    } else if (provider === "anthropic") {
      response = await callAnthropic(model);
    } else {
      response = "Provider not yet supported in this dashboard. Use Anthropic or Local.";
    }

    spinnerEl.remove();
    appendChatMsg("assistant", chatMsgMarkdown(response));
    state.chatHistory.push({ role: "assistant", content: response });

  } catch (err) {
    spinnerEl.remove();
    appendChatMsg("assistant", `<span class="chat-msg-error">Error: ${DOMPurify.sanitize(err.message)}</span>`);
  } finally {
    state.chatStreaming = false;
    document.getElementById("chat-send-btn").disabled = false;
  }
}

async function callAnthropic(model) {
  const apiKey = getApiKey();
  if (!apiKey) throw new Error("No API key — enter it in the chat panel.");

  const messages = state.chatHistory.map(m => ({ role: m.role, content: m.content }));

  const resp = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model,
      max_tokens: 1024,
      system: systemPrompt(),
      tools: ROBOT_TOOLS,
      messages,
    }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error?.message || `HTTP ${resp.status}`);
  }

  const data = await resp.json();

  let text = "";
  for (const block of data.content) {
    if (block.type === "text") {
      text += block.text;
    } else if (block.type === "tool_use") {
      const result = execTool(block.name, block.input);
      toast(`Tool: ${block.name} → ${result}`, "ok");
      text += `\n*[Tool: ${block.name}]*\n`;
    }
  }
  return text.trim();
}

async function callLocalProxy(prompt) {
  const resp = await fetch("http://127.0.0.1:7337/claude", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  if (!resp.ok) throw new Error(`Proxy error: HTTP ${resp.status}. Is \`make proxy\` running?`);

  let output = "";
  const reader = resp.body.getReader();
  const dec    = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    for (const line of dec.decode(value).split("\n").filter(Boolean)) {
      try {
        const evt = JSON.parse(line);
        if (evt.type === "result") output = evt.result;
      } catch {}
    }
  }
  return output || "(no response)";
}

// ── Event wiring ──────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {

  // Restore persisted state
  document.getElementById("url-input").value     = state.brokerUrl;
  document.getElementById("robot-id-input").value = state.robotId;

  const savedKey = localStorage.getItem("ri-api-key");
  if (savedKey) document.getElementById("chat-api-key").value = savedKey;

  const savedModel = localStorage.getItem("ri-chat-model");
  if (savedModel) document.getElementById("chat-model-select").value = savedModel;

  // Connect / disconnect
  document.getElementById("connect-btn").addEventListener("click", () => {
    state.connected ? disconnect() : connect();
  });

  // Broker URL — save on change
  document.getElementById("url-input").addEventListener("change", e => {
    localStorage.setItem("ri-broker-url", e.target.value.trim());
  });

  // Broker presets
  const presetsBtn     = document.getElementById("url-presets-btn");
  const presetsPopover = document.getElementById("url-presets-popover");
  presetsBtn.addEventListener("click", e => {
    e.stopPropagation();
    presetsPopover.hidden = !presetsPopover.hidden;
  });
  presetsPopover.querySelectorAll(".url-preset-item").forEach(btn => {
    btn.addEventListener("click", () => {
      document.getElementById("url-input").value = btn.dataset.url;
      presetsPopover.hidden = true;
    });
  });
  document.addEventListener("click", () => { presetsPopover.hidden = true; });

  // Robot ID
  document.getElementById("robot-id-save").addEventListener("click", applyRobotId);
  document.getElementById("robot-id-input").addEventListener("keydown", e => {
    if (e.key === "Enter") applyRobotId();
  });

  // Velocity
  document.getElementById("vel-send-btn").addEventListener("click", sendVelocity);
  document.getElementById("vel-zero-btn").addEventListener("click", zeroVelocity);

  // Commands
  document.getElementById("cmd-stand-up").addEventListener("click",    () => sendState("stand_up"));
  document.getElementById("cmd-stand-down").addEventListener("click",  () => sendState("stand_down"));
  document.getElementById("cmd-damping").addEventListener("click",     () => sendState("damping"));
  document.getElementById("cmd-policy-start").addEventListener("click",() => sendState("policy_start"));
  document.getElementById("cmd-policy-stop").addEventListener("click", () => sendState("policy_stop"));
  document.getElementById("cmd-estop").addEventListener("click",       () => { sendState("policy_stop"); zeroVelocity(); toast("E-STOP sent", "error"); });

  // Chat panel toggle
  const chatToggle = document.getElementById("chat-panel-toggle");
  const chatPanel  = document.getElementById("chat-panel");
  chatToggle.addEventListener("click", () => {
    const isHidden = chatPanel.hidden;
    chatPanel.hidden = !isHidden;
    chatToggle.setAttribute("aria-expanded", isHidden ? "true" : "false");
    chatToggle.classList.toggle("active", isHidden);
  });

  // Chat: API key
  document.getElementById("chat-key-save").addEventListener("click", () => {
    const key = document.getElementById("chat-api-key").value.trim();
    localStorage.setItem("ri-api-key", key);
    toast("API key saved", "ok");
  });

  // Chat: model
  document.getElementById("chat-model-select").addEventListener("change", e => {
    localStorage.setItem("ri-chat-model", e.target.value);
  });

  // Chat: send
  document.getElementById("chat-send-btn").addEventListener("click", sendChat);
  document.getElementById("chat-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  });

});
