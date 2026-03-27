import { useState, useEffect } from "react";
import styles from "./SettingsModal.module.css";

function SvgIcon({ d, size = 16 }: { d: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

const ICONS = {
  eye: "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M1 12a11 11 0 0 1 18 0 M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  eyeOff: "M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24 M1 1l22 22",
  copy: "M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2 M8 2h8v4H8z",
  check: "M20 6 9 17l-5-5",
  close: "M18 6 6 18 M6 6l12 12",
};

interface PlatformInfo {
  provider: string;
  base_url: string;
  timeout: number;
  max_retries: number;
  temperature: number;
  max_tokens: number | null;
  models?: string[];
  capability_overrides?: Record<string, unknown>;
  api_key?: string;
}

interface PlatformsData {
  [id: string]: PlatformInfo;
}

const PROVIDERS = ["deepseek", "dashscope", "ollama"] as const;

const PROVIDER_LABELS: Record<string, string> = {
  deepseek: "DeepSeek",
  dashscope: "DashScope",
  ollama: "Ollama",
};

type NavItem = "platforms" | "models";

interface Props {
  open: boolean;
  onClose: () => void;
}

function generatePlatformId(provider: string, existing: string[]): string {
  let n = 1;
  while (existing.includes(`${provider}_${n}`)) n++;
  return `${provider}_${n}`;
}

const maskApiKey = (key: string) => {
  if (!key) return "";
  if (key.length <= 6) return "*".repeat(key.length);
  return key.slice(0, 3) + "*".repeat(key.length - 6) + key.slice(-3);
};

export default function SettingsModal({ open, onClose }: Props) {
  const [nav, setNav] = useState<NavItem>("platforms");
  const [platforms, setPlatforms] = useState<PlatformsData>({});

  const [overlay, setOverlay] = useState<string | null>(null);

  const [editForm, setEditForm] = useState<PlatformInfo>({
    provider: "deepseek",
    base_url: "",
    timeout: 30,
    max_retries: 3,
    temperature: 0.7,
    max_tokens: 0,
    models: [],
  });
  const [editApiKey, setEditApiKey] = useState("");
  const [editHasKey, setEditHasKey] = useState(false);
  const [editingKey, setEditingKey] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [apiKeyCopied, setApiKeyCopied] = useState(false);
  const [platformIdInput, setPlatformIdInput] = useState("");
  const [saving, setSaving] = useState(false);

  // settings save feedback
  const [settingsMsg, setSettingsMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [modelSearch, setModelSearch] = useState("");

  // connection test
  const [testingConn, setTestingConn] = useState(false);
  const [connResult, setConnResult] = useState<{ success: boolean; error?: string } | null>(null);

  // fetch models
  const [fetchingModels, setFetchingModels] = useState(false);
  const [fetchedModels, setFetchedModels] = useState<string[]>([]);

  const [defaultPlatform, setDefaultPlatform] = useState("");
  const [defaultModels, setDefaultModels] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open) return;
    loadAll();
  }, [open]);

  const loadAll = async () => {
    try {
      const [pRes, sRes] = await Promise.all([
        fetch("/api/platforms"),
        fetch("/api/settings"),
      ]);
      const pData: PlatformsData = await pRes.json();
      const sData = await sRes.json();
      setPlatforms(pData);
      setDefaultPlatform(sData.default_platform || "");
      setDefaultModels(sData.default_model || {});
    } catch { /* ignore */ }
  };

  const openEdit = async (platformId: string) => {
    const data = platforms[platformId];
    let base: PlatformInfo = {
      provider: data.provider,
      base_url: data.base_url || "",
      timeout: data.timeout ?? 30,
      max_retries: data.max_retries ?? 3,
      temperature: data.temperature ?? 0.7,
      max_tokens: data.max_tokens,
      models: data.models || [],
      capability_overrides: data.capability_overrides,
    };
    // Merge in latest provider defaults (fixes stale base_url etc.)
    try {
      const res = await fetch(`/api/providers/defaults?provider=${encodeURIComponent(data.provider)}`);
      const def = await res.json();
      if (def.success) {
        base = {
          provider: def.provider,
          base_url: data.base_url || def.base_url,
          timeout: data.timeout ?? def.timeout,
          max_retries: data.max_retries ?? def.max_retries,
          temperature: data.temperature ?? def.temperature,
          max_tokens: data.max_tokens ?? def.max_tokens ?? 0,
          models: data.models?.length ? data.models : [],
          capability_overrides: data.capability_overrides || def.capability,
        };
      }
    } catch { /* keep saved config */ }
    setEditForm(base);
    setEditApiKey("");
    setEditHasKey(!!data.api_key);
    setEditingKey(false);
    setShowApiKey(false);
    setApiKeyCopied(false);
    setConnResult(null);
    setFetchedModels(base.models || []);
    setOverlay(platformId);
  };

  const fetchProviderDefaults = async (provider: string) => {
    try {
      const res = await fetch(`/api/providers/defaults?provider=${encodeURIComponent(provider)}`);
      const data = await res.json();
      if (data.success) {
        setEditForm((prev) => ({
          ...prev,
          provider: data.provider,
          base_url: data.base_url,
          timeout: data.timeout,
          max_retries: data.max_retries,
          temperature: data.temperature,
          max_tokens: data.max_tokens,
          capability_overrides: data.capability,
        }));
      }
    } catch { /* ignore */ }
  };

  const openAdd = () => {
    const nextProvider = "deepseek";
    setEditForm({
      provider: nextProvider,
      base_url: "",
      timeout: 30,
      max_retries: 3,
      temperature: 0.7,
      max_tokens: 0,
      models: [],
    });
    setEditApiKey("");
    setEditHasKey(false);
    setEditingKey(true);
    setPlatformIdInput(generatePlatformId(nextProvider, Object.keys(platforms)));
    setShowApiKey(false);
    setApiKeyCopied(false);
    setConnResult(null);
    setFetchedModels([]);
    setOverlay("add");
    fetchProviderDefaults(nextProvider);
  };

  const closeOverlay = () => {
    setOverlay(null);
    loadAll();
  };

  const getTestPayload = () => {
    if (overlay !== "add") {
      return { platform_id: overlay };
    }
    return { provider: editForm.provider, base_url: editForm.base_url, api_key: editApiKey };
  };

  const handleTestConnection = async () => {
    setTestingConn(true);
    setConnResult(null);
    try {
      const res = await fetch("/api/platforms/connection-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(getTestPayload()),
      });
      if (!res.ok) {
        const text = await res.text();
        let msg = `HTTP ${res.status}`;
        try { const err = JSON.parse(text); msg = err.detail || err.error || msg; } catch { /* */ }
        setConnResult({ success: false, error: msg });
      } else {
        setConnResult(await res.json());
      }
    } catch {
      setConnResult({ success: false, error: "Network error" });
    } finally {
      setTestingConn(false);
    }
  };

  const handleFetchModels = async () => {
    setFetchingModels(true);
    setFetchedModels([]);
    try {
      const res = await fetch("/api/platforms/fetch-models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(getTestPayload()),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.models) {
          setFetchedModels(data.models);
          setEditForm((prev) => ({ ...prev, models: data.models }));
        }
      }
    } catch { /* ignore */ }
    finally { setFetchingModels(false); }
  };

  const handleSave = async () => {
    setSaving(true);
    const platformId = overlay === "add" ? platformIdInput.trim() || generatePlatformId(editForm.provider, Object.keys(platforms)) : overlay!;

    const payload = { ...editForm, api_key: editApiKey || editForm.api_key || "", models: editForm.models?.length ? editForm.models : fetchedModels };

    await fetch(`/api/platforms/${encodeURIComponent(platformId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setSaving(false);
    closeOverlay();
  };

  const handleDelete = async () => {
    if (!confirm(`Remove platform "${overlay}"?`)) return;
    await fetch(`/api/platforms/${encodeURIComponent(overlay!)}`, { method: "DELETE" });
    closeOverlay();
  };

  const saveSettings = async () => {
    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ default_platform: defaultPlatform, default_model: defaultModels }),
      });
      if (res.ok) {
        setSettingsMsg({ ok: true, text: "Settings saved." });
      } else {
        setSettingsMsg({ ok: false, text: "Failed to save settings." });
      }
    } catch {
      setSettingsMsg({ ok: false, text: "Network error." });
    }
    setTimeout(() => setSettingsMsg(null), 3000);
  };

  if (!open) return null;

  const platformEntries = Object.entries(platforms);
  const enabledProviders = Object.keys(platforms);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.sidebar}>
          <div className={styles.sidebarTitle}>Settings</div>
          <button className={`${styles.navItem} ${nav === "platforms" ? styles.navActive : ""}`} onClick={() => { setNav("platforms"); setOverlay(null); }}>Platforms</button>
          <button className={`${styles.navItem} ${nav === "models" ? styles.navActive : ""}`} onClick={() => { setNav("models"); setOverlay(null); }}>Model Assignment</button>
          <div className={styles.sidebarFooter}>
            <button className={styles.closeBtn} onClick={onClose}>Close</button>
          </div>
        </div>

        <div className={styles.content}>
          {nav === "platforms" && (
            <div className={styles.contentInner}>
              {!overlay && (
                <>
                  <h3>Platforms</h3>
                  <p className={styles.hint}>Click a card to configure, or add a new platform.</p>
                  <div className={styles.cardGrid}>
                    {platformEntries.map(([pid, info]) => (
                      <div key={pid} className={styles.squareCard} onClick={() => openEdit(pid)}>
                        <div className={styles.cardIcon}>
                          {info.provider.charAt(0).toUpperCase()}
                        </div>
                        <div className={styles.cardLabel}>{pid}</div>
                        <div className={styles.cardState}>
                          {info.api_key ? "Active" : "No API key"}
                        </div>
                      </div>
                    ))}
                    <div className={`${styles.squareCard} ${styles.addCard}`} onClick={openAdd}>
                      <div className={styles.addIcon}>+</div>
                      <div className={styles.cardLabel}>Add Platform</div>
                    </div>
                  </div>
                </>
              )}

              {overlay && (
                <div className={styles.configPanel}>
                  <div className={styles.panelHeader}>
                    <button className={styles.backBtn} onClick={closeOverlay}>← Back</button>
                    <h3>{overlay === "add" ? "Add Platform" : `Configure ${overlay}`}</h3>
                  </div>

                  <div className={styles.panelBody}>
                    <div className={styles.panelScrollOverflow}>
                    <div className={styles.field}>
                      <label>Provider</label>
                      <select value={editForm.provider} onChange={(e) => {
                        const p = e.target.value;
                        setEditForm({ ...editForm, provider: p });
                        if (overlay === "add") setPlatformIdInput(generatePlatformId(p, Object.keys(platforms)));
                        fetchProviderDefaults(p);
                      }}>
                        {PROVIDERS.map((p) => (
                          <option key={p} value={p}>{PROVIDER_LABELS[p]}</option>
                        ))}
                      </select>
                    </div>
                    {overlay === "add" && (
                      <div className={styles.field}>
                        <label>Platform ID</label>
                        <input value={platformIdInput} onChange={(e) => setPlatformIdInput(e.target.value)}
                          placeholder={generatePlatformId(editForm.provider, Object.keys(platforms))} />
                      </div>
                    )}
                    <div className={styles.field}>
                      <label>Base URL</label>
                      <input value={editForm.base_url} onChange={(e) => setEditForm({ ...editForm, base_url: e.target.value })}
                        placeholder={editForm.provider === "ollama" ? "http://localhost:11434" : `https://api.${editForm.provider}.com/v1`} />
                    </div>
                    <div className={styles.fieldRow}>
                      <div className={styles.field}>
                        <label>Timeout (s)</label>
                        <input type="number" value={editForm.timeout} onChange={(e) => setEditForm({ ...editForm, timeout: +e.target.value })} />
                      </div>
                      <div className={styles.field}>
                        <label>Max Retries</label>
                        <input type="number" value={editForm.max_retries} onChange={(e) => setEditForm({ ...editForm, max_retries: +e.target.value })} />
                      </div>
                    </div>
                    <div className={styles.fieldRow}>
                      <div className={styles.field}>
                        <label>Temperature</label>
                        <input type="number" step="0.1" min="0" max="2" value={editForm.temperature} onChange={(e) => setEditForm({ ...editForm, temperature: +e.target.value })} />
                      </div>
                      <div className={styles.field}>
                        <label>Max Tokens</label>
                        <input type="number" value={editForm.max_tokens ?? ""} placeholder="unlimited" onChange={(e) => setEditForm({ ...editForm, max_tokens: e.target.value ? +e.target.value : null })} />
                      </div>
                    </div>

                    <div className={styles.apikeySection}>
                      <label>API Key</label>
                      {editHasKey && !editingKey ? (
                        <div className={styles.apikeyMasked}>
                          <code className={styles.apikeyMaskedText}>{maskApiKey(editForm.api_key || "")}</code>
                          <button className={styles.iconBtn} onClick={() => { setEditingKey(true); setEditApiKey(""); }} title="Edit">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z M15 5l4 4"/></svg>
                          </button>
                          <button className={styles.iconBtn} onClick={async (e) => {
                            e.stopPropagation();
                            await navigator.clipboard.writeText(editForm.api_key || "");
                            setApiKeyCopied(true);
                            setTimeout(() => setApiKeyCopied(false), 2000);
                          }} title="Copy">
                            {apiKeyCopied ? <SvgIcon d={ICONS.check} /> : <SvgIcon d={ICONS.copy} />}
                          </button>
                        </div>
                      ) : (
                        <div className={styles.apikeyInput}>
                          <input type={showApiKey ? "text" : "password"} autoComplete="off" data-lpignore="true" data-form-type="other"
                            value={editApiKey} onChange={(e) => setEditApiKey(e.target.value)}
                            placeholder="Enter API key" />
                          <button className={styles.iconBtn} onClick={() => setShowApiKey(!showApiKey)} title={showApiKey ? "Hide" : "Show"}>
                            <SvgIcon d={showApiKey ? ICONS.eyeOff : ICONS.eye} />
                          </button>
                          {editHasKey && (
                            <button className={styles.iconBtn} onClick={() => {
                              setEditingKey(false);
                              setEditApiKey("");
                              setShowApiKey(false);
                            }} title="Cancel">
                              <SvgIcon d={ICONS.close} />
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                      {connResult && (
                        <div className={`${styles.resultBox} ${connResult.success ? styles.resultSuccess : styles.resultFail}`}>
                          {connResult.success ? "Connection successful!" : `Connection failed: ${connResult.error}`}
                        </div>
                      )}

                      {fetchedModels.length > 0 && (
                        <div className={styles.modelSection}>
                          <div className={styles.modelSectionTitle}>Available Models ({fetchedModels.length})</div>
                          <div className={styles.modelList}>
                            {fetchedModels.map((m) => <span key={m} className={styles.modelTag}>{m}</span>)}
                          </div>
                        </div>
                      )}
                    </div>

                    <div className={styles.panelFooter}>
                      <button className={styles.testBtn} onClick={handleTestConnection} disabled={testingConn}>
                        {testingConn ? "Testing..." : "Test Connection"}
                      </button>
                      <button className={styles.fetchBtn} onClick={handleFetchModels} disabled={fetchingModels}>
                        {fetchingModels ? "Fetching..." : "Fetch Models"}
                      </button>
                      <div style={{ flex: 1 }} />
                      {overlay !== "add" && (
                        <button className={styles.deleteBtn} onClick={handleDelete}>Delete</button>
                      )}
                      <button className={styles.cancelBtn} onClick={closeOverlay}>Cancel</button>
                      <button className={styles.saveBtn} onClick={handleSave} disabled={saving}>
                        {saving ? "Saving..." : "Save"}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {nav === "models" && (
            <div className={styles.contentInner}>
              {!overlay ? (
                <>
                  <h3>Model Assignment</h3>
                  <p className={styles.hint}>Assign models to each agent. Click a card to configure.</p>

                  <div className={styles.agentCards}>
                    <div className={styles.agentCard} onClick={() => { setOverlay("main_chat"); setModelSearch(""); }}>
                      <div className={styles.agentCardIcon}>C</div>
                      <div className={styles.agentCardBody}>
                        <div className={styles.agentCardName}>Main Chat</div>
                        <div className={styles.agentCardAssignment}>
                          {defaultPlatform && defaultModels[defaultPlatform]
                            ? `${defaultPlatform} / ${defaultModels[defaultPlatform]}`
                            : "Not configured"}
                        </div>
                      </div>
                      <div className={styles.agentCardArrow}>→</div>
                    </div>
                  </div>

                  <div className={styles.saveRow} style={{ marginTop: 16 }}>
                    <button className={styles.saveBtn} onClick={saveSettings}>Save Settings</button>
                    {settingsMsg && (
                      <span className={settingsMsg.ok ? styles.msgOk : styles.msgErr}>{settingsMsg.text}</span>
                    )}
                  </div>
                </>
              ) : (
                <div className={styles.configPanel}>
                  <div className={styles.panelHeader}>
                    <button className={styles.backBtn} onClick={() => setOverlay(null)}>← Back</button>
                    <h3>Main Chat</h3>
                  </div>
                  <div className={styles.panelBody}>
                    <p className={styles.hint}>Select the platform and model for the main chat agent.</p>

                    <div className={styles.section}>
                      <h4>Platform</h4>
                      <div className={styles.platformGrid}>
                        {enabledProviders.map((p) => (
                          <div
                            key={p}
                            className={`${styles.platformOption} ${defaultPlatform === p ? styles.platformActive : ""}`}
                            onClick={() => { setDefaultPlatform(p); setModelSearch(""); }}
                          >
                            <div className={styles.platformOptionIcon}>{p.charAt(0).toUpperCase()}</div>
                            <div className={styles.platformOptionLabel}>{p}</div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className={styles.panelScroll}>
                      {defaultPlatform && (
                        <div className={styles.section}>
                          <h4>Model</h4>
                          <div className={styles.searchInput}>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                            <input
                              value={modelSearch}
                              onChange={(e) => setModelSearch(e.target.value)}
                              placeholder="Filter models..."
                            />
                          </div>
                          <div className={styles.modelScroll}>
                            <div className={styles.modelGrid}>
                              {(platforms[defaultPlatform]?.models || [])
                                .filter((m) => !modelSearch || m.toLowerCase().includes(modelSearch.toLowerCase()))
                                .map((m) => (
                                  <div
                                    key={m}
                                    className={`${styles.modelOption} ${defaultModels[defaultPlatform] === m ? styles.modelOptionActive : ""}`}
                                    onClick={() => setDefaultModels({ ...defaultModels, [defaultPlatform]: m })}
                                  >
                                    <span className={styles.modelOptionName}>{m}</span>
                                    {defaultModels[defaultPlatform] === m && (
                                      <span className={styles.modelOptionCheck}>
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
                                      </span>
                                    )}
                                  </div>
                                ))}
                              {(!platforms[defaultPlatform]?.models || platforms[defaultPlatform]!.models!.length === 0) && (
                                <p className={styles.hint}>No models fetched. Go to Platforms → click the platform → Fetch Models.</p>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className={styles.panelFooter}>
                      <button className={styles.cancelBtn} onClick={() => setOverlay(null)}>Cancel</button>
                      <button className={styles.saveBtn} onClick={() => { saveSettings(); setOverlay(null); }}>Save</button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
