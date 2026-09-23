/**
 * EPH Ember climate card — On / Boost / Off modes + Schedule / Advance presets.
 *
 * Underlying HA values:
 *   heat → On, fan_only → Boost, off → Off
 *   preset schedule → timetable, preset advance → Advance
 */
const CARD_VERSION = "1.2.0";

const MODE_UI = {
  heat: { label: "On", icon: "mdi:fire" },
  fan_only: { label: "Boost", icon: "mdi:rocket-launch" },
  off: { label: "Off", icon: "mdi:power" },
};

const MODE_ORDER = ["heat", "fan_only", "off"];

const PRESET_UI = {
  schedule: { label: "Schedule", icon: "mdi:calendar-clock" },
  advance: { label: "Advance", icon: "mdi:skip-forward" },
};

class EphEmberClimateCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("ephember-climate-card-editor");
  }

  static getStubConfig(hass, entities) {
    const climate =
      entities.find((e) => e.startsWith("climate.") && e.includes("home")) ||
      entities.find((e) => e.startsWith("climate."));
    return { type: "custom:ephember-climate-card", entity: climate || "" };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Please define a climate entity");
    }
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  _entityState() {
    return this._hass?.states?.[this._config.entity];
  }

  _callService(domain, service, data) {
    this._hass.callService(domain, service, {
      entity_id: this._config.entity,
      ...data,
    });
  }

  _setMode(mode) {
    this._callService("climate", "set_hvac_mode", { hvac_mode: mode });
  }

  _setPreset(preset) {
    this._callService("climate", "set_preset_mode", { preset_mode: preset });
  }

  _adjustTemp(delta) {
    const state = this._entityState();
    if (!state) return;
    const current = state.attributes.temperature;
    if (current == null) return;
    const step = state.attributes.target_temp_step || 0.5;
    const min = state.attributes.min_temp ?? 5;
    const max = state.attributes.max_temp ?? 35;
    const next = Math.min(max, Math.max(min, Math.round((current + delta) / step) * step));
    this._callService("climate", "set_temperature", { temperature: next });
  }

  _render() {
    if (!this._config) return;

    const state = this._entityState();
    if (!this._root) {
      this._root = this.attachShadow({ mode: "open" });
    }

    if (!state) {
      this._root.innerHTML = `
        <ha-card>
          <div class="warn">Entity not found: ${this._escape(this._config.entity)}</div>
        </ha-card>
        <style>${this._styles()}</style>
      `;
      return;
    }

    const attrs = state.attributes;
    const name = this._config.name || attrs.friendly_name || this._config.entity;
    const current = attrs.current_temperature;
    const target = attrs.temperature;
    const action = attrs.hvac_action;
    const modes = attrs.hvac_modes || [];
    const presets = attrs.preset_modes || [];
    const activeMode = state.state;
    const activePreset = attrs.preset_mode;

    const modeButtons = MODE_ORDER.filter((m) => modes.includes(m))
      .map((mode) => {
        const meta = MODE_UI[mode] || { label: mode, icon: "mdi:thermostat" };
        const selected = activeMode === mode ? "selected" : "";
        return `
          <button class="mode ${selected}" data-mode="${mode}" title="${meta.label}">
            <ha-icon icon="${meta.icon}"></ha-icon>
            <span>${meta.label}</span>
          </button>
        `;
      })
      .join("");

    const presetButtons = presets
      .map((preset) => {
        const meta = PRESET_UI[preset] || { label: preset, icon: "mdi:tune" };
        const selected = activePreset === preset ? "selected" : "";
        return `
          <button class="preset ${selected}" data-preset="${preset}" title="${meta.label}">
            <ha-icon icon="${meta.icon}"></ha-icon>
            <span>${meta.label}</span>
          </button>
        `;
      })
      .join("");

    const canSetTemp =
      attrs.supported_features != null &&
      (attrs.supported_features & 1) === 1 &&
      target != null;

    this._root.innerHTML = `
      <ha-card>
        <div class="header">
          <div class="title">${this._escape(name)}</div>
          <div class="action">${this._escape(this._statusLabel(action, activeMode, activePreset))}</div>
        </div>
        <div class="temps">
          <div class="current">
            <span class="value">${current == null ? "—" : current.toFixed(1)}</span>
            <span class="unit">°C</span>
            <span class="label">Current</span>
          </div>
          <div class="target ${canSetTemp ? "" : "disabled"}">
            <button class="step" data-delta="-1" ${canSetTemp ? "" : "disabled"} aria-label="Decrease">−</button>
            <div class="target-mid">
              <span class="value">${target == null ? "—" : Number(target).toFixed(1)}</span>
              <span class="unit">°C</span>
              <span class="label">Target</span>
            </div>
            <button class="step" data-delta="1" ${canSetTemp ? "" : "disabled"} aria-label="Increase">+</button>
          </div>
        </div>
        <div class="modes">${modeButtons}</div>
        ${presetButtons ? `<div class="presets">${presetButtons}</div>` : ""}
      </ha-card>
      <style>${this._styles()}</style>
    `;

    this._root.querySelectorAll("button.mode").forEach((btn) => {
      btn.addEventListener("click", () => this._setMode(btn.dataset.mode));
    });
    this._root.querySelectorAll("button.preset").forEach((btn) => {
      btn.addEventListener("click", () => this._setPreset(btn.dataset.preset));
    });
    this._root.querySelectorAll("button.step").forEach((btn) => {
      btn.addEventListener("click", () => {
        const delta = Number(btn.dataset.delta) * (attrs.target_temp_step || 0.5);
        this._adjustTemp(delta);
      });
    });
  }

  _statusLabel(action, mode, preset) {
    if (action === "heating") return "Heating";
    if (mode === "fan_only") return "Boost";
    if (mode === "off") return "Off";
    if (preset && PRESET_UI[preset]) return PRESET_UI[preset].label;
    if (mode === "heat") return "On";
    return mode;
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  _styles() {
    return `
      :host { display: block; }
      ha-card { padding: 16px; }
      .header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 12px;
        gap: 8px;
      }
      .title {
        font-size: 1.1rem;
        font-weight: 500;
        color: var(--primary-text-color);
      }
      .action {
        font-size: 0.85rem;
        color: var(--secondary-text-color);
      }
      .temps {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin-bottom: 16px;
      }
      .current, .target-mid {
        display: flex;
        flex-direction: column;
        align-items: center;
      }
      .target {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
      }
      .target.disabled { opacity: 0.55; }
      .value {
        font-size: 2rem;
        font-weight: 300;
        line-height: 1.1;
        color: var(--primary-text-color);
      }
      .unit {
        font-size: 0.9rem;
        color: var(--secondary-text-color);
      }
      .label {
        font-size: 0.75rem;
        color: var(--secondary-text-color);
        margin-top: 2px;
      }
      .step {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        border: 1px solid var(--divider-color);
        background: var(--secondary-background-color, transparent);
        color: var(--primary-text-color);
        font-size: 1.4rem;
        line-height: 1;
        cursor: pointer;
      }
      .step:disabled { opacity: 0.4; cursor: default; }
      .modes, .presets {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(72px, 1fr));
        gap: 8px;
      }
      .presets { margin-top: 8px; }
      .mode, .preset {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 4px;
        padding: 10px 6px;
        border-radius: 12px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color, transparent);
        color: var(--secondary-text-color);
        cursor: pointer;
        min-height: 64px;
      }
      .mode ha-icon, .preset ha-icon {
        --mdc-icon-size: 22px;
        color: inherit;
      }
      .mode span, .preset span {
        font-size: 0.75rem;
        font-weight: 500;
      }
      .mode.selected, .preset.selected {
        background: var(--primary-color);
        border-color: var(--primary-color);
        color: var(--text-primary-color, #fff);
      }
      .warn { padding: 16px; color: var(--error-color); }
    `;
  }
}

class EphEmberClimateCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _render() {
    if (!this._config) return;
    if (!this._root) this._root = this.attachShadow({ mode: "open" });
    this._root.innerHTML = `
      <div style="padding:12px;display:flex;flex-direction:column;gap:8px;">
        <label>
          Entity
          <input id="entity" type="text" value="${this._config.entity || ""}"
            style="width:100%;box-sizing:border-box;margin-top:4px;" />
        </label>
        <label>
          Name (optional)
          <input id="name" type="text" value="${this._config.name || ""}"
            style="width:100%;box-sizing:border-box;margin-top:4px;" />
        </label>
      </div>
    `;
    const emit = () => {
      const entity = this._root.getElementById("entity").value.trim();
      const name = this._root.getElementById("name").value.trim();
      const detail = { ...this._config, entity };
      if (name) detail.name = name;
      else delete detail.name;
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: detail } }));
    };
    this._root.getElementById("entity").addEventListener("change", emit);
    this._root.getElementById("name").addEventListener("change", emit);
  }
}

customElements.define("ephember-climate-card", EphEmberClimateCard);
customElements.define("ephember-climate-card-editor", EphEmberClimateCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "ephember-climate-card",
  name: "EPH Ember Climate",
  description: "On / Boost / Off with Schedule and Advance presets for EPH Controls.",
  preview: true,
});

console.info(
  `%c EPH-EMBER-CLIMATE-CARD %c v${CARD_VERSION} `,
  "color:#fff;background:#c45c26;font-weight:bold",
  "color:#c45c26;background:transparent"
);
