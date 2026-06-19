import { useState } from "react";
import {
  DnsSection,
  NetworkSection,
  TlsSection,
  type DomainDiagnostic,
  type NetworkDiagnostic,
} from "./DiagnosticResultView";
import type { ToolModule } from "../data/fallbackModules";

const API_BASE = "http://127.0.0.1:8000/api";

interface CaptureEnvironment {
  system: string;
  tools: Record<
    string,
    {
      name: string;
      available: boolean;
      path?: string | null;
      version_output?: string | null;
    }
  >;
  interfaces: Array<{
    index: number;
    name: string;
    flags: string[];
    source: string;
  }>;
  can_list_interfaces: boolean;
  ready_for_capture: boolean;
  interface_error?: string | null;
  warnings: string[];
}

interface CaptureRunResult {
  status: string;
  interface: string;
  bpf_filter?: string | null;
  pcap_path?: string | null;
  packet_count: number;
  summary_lines: string[];
  command: string[];
  returncode?: number | null;
  error?: string | null;
  stderr?: string | null;
}

interface ModuleDetailProps {
  module: ToolModule;
  onBack: () => void;
}

function PlannedModule({ module }: { module: ToolModule }) {
  return (
    <div className="tool-panel">
      <p className="tool-panel__empty">
        该模块已经进入工作台目录，但执行接口还未实现。后续会按模块单独补 agent、任务流和结果模型。
      </p>
      <div className="module-card__caps">
        {module.capabilities.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </div>
    </div>
  );
}

function DomainTool() {
  const [domain, setDomain] = useState("example.com");
  const [includeSsl, setIncludeSsl] = useState(true);
  const [includeWhois, setIncludeWhois] = useState(false);
  const [compareDns, setCompareDns] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DomainDiagnostic | null>(null);

  async function submit() {
    if (!domain.trim()) {
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/tools/domain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain,
          include_ssl: includeSsl,
          include_whois: includeWhois,
          compare_dns: compareDns,
        }),
      });
      const data: DomainDiagnostic = await response.json();
      setResult(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="tool-panel">
      <div className="tool-form">
        <label>
          <span>域名</span>
          <input value={domain} onChange={(event) => setDomain(event.target.value)} />
        </label>
        <label className="check-row">
          <input type="checkbox" checked={includeSsl} onChange={(event) => setIncludeSsl(event.target.checked)} />
          <span>TLS 证书</span>
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={includeWhois}
            onChange={(event) => setIncludeWhois(event.target.checked)}
          />
          <span>WHOIS</span>
        </label>
        <label className="check-row">
          <input type="checkbox" checked={compareDns} onChange={(event) => setCompareDns(event.target.checked)} />
          <span>多 DNS 对比</span>
        </label>
        <button onClick={submit} disabled={loading}>
          {loading ? "检查中..." : "执行检查"}
        </button>
      </div>

      {result ? (
        <div className="result-card">
          <DnsSection diagnostic={result} />
          <TlsSection diagnostic={result} />
          <details className="raw-details">
            <summary>查看原始 JSON</summary>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      ) : null}
    </div>
  );
}

function NetworkTool() {
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState("8000");
  const [timeout, setTimeoutValue] = useState("2");
  const [includePing, setIncludePing] = useState(false);
  const [includeTrace, setIncludeTrace] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<NetworkDiagnostic | null>(null);

  async function submit() {
    if (!host.trim()) {
      return;
    }
    setLoading(true);
    try {
      const parsedPort = Number.parseInt(port, 10);
      const response = await fetch(`${API_BASE}/tools/network`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host,
          port: Number.isFinite(parsedPort) ? parsedPort : null,
          timeout: Number.parseFloat(timeout) || 2,
          include_ping: includePing,
          include_trace: includeTrace,
        }),
      });
      const data: NetworkDiagnostic = await response.json();
      setResult(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="tool-panel">
      <div className="tool-form tool-form--network">
        <label>
          <span>主机 / IP</span>
          <input value={host} onChange={(event) => setHost(event.target.value)} />
        </label>
        <label>
          <span>端口</span>
          <input value={port} onChange={(event) => setPort(event.target.value)} />
        </label>
        <label>
          <span>超时秒数</span>
          <input value={timeout} onChange={(event) => setTimeoutValue(event.target.value)} />
        </label>
        <label className="check-row">
          <input type="checkbox" checked={includePing} onChange={(event) => setIncludePing(event.target.checked)} />
          <span>Ping</span>
        </label>
        <label className="check-row">
          <input type="checkbox" checked={includeTrace} onChange={(event) => setIncludeTrace(event.target.checked)} />
          <span>Traceroute</span>
        </label>
        <button onClick={submit} disabled={loading}>
          {loading ? "检查中..." : "执行检查"}
        </button>
      </div>

      {result ? (
        <div className="result-card">
          <NetworkSection diagnostic={result} />
          <details className="raw-details">
            <summary>查看原始 JSON</summary>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      ) : null}
    </div>
  );
}

function CaptureTool() {
  const [loading, setLoading] = useState(false);
  const [captureLoading, setCaptureLoading] = useState(false);
  const [environment, setEnvironment] = useState<CaptureEnvironment | null>(null);
  const [selectedInterface, setSelectedInterface] = useState("");
  const [bpfFilter, setBpfFilter] = useState("");
  const [durationSeconds, setDurationSeconds] = useState("5");
  const [packetCount, setPacketCount] = useState("50");
  const [captureResult, setCaptureResult] = useState<CaptureRunResult | null>(null);

  async function loadEnvironment() {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/tools/capture/environment`);
      const data: CaptureEnvironment = await response.json();
      setEnvironment(data);
      setSelectedInterface((current) => current || data.interfaces.find((item) => item.name === "en0")?.name || data.interfaces[0]?.name || "");
    } finally {
      setLoading(false);
    }
  }

  async function runCapture() {
    if (!selectedInterface) {
      return;
    }
    setCaptureLoading(true);
    try {
      const response = await fetch(`${API_BASE}/tools/capture/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          interface: selectedInterface,
          bpf_filter: bpfFilter.trim() || null,
          duration_seconds: Number.parseInt(durationSeconds, 10) || 5,
          packet_count: Number.parseInt(packetCount, 10) || 50,
        }),
      });
      const data: CaptureRunResult = await response.json();
      setCaptureResult(data);
    } finally {
      setCaptureLoading(false);
    }
  }

  return (
    <div className="tool-panel">
      <div className="capture-actions">
        <button onClick={loadEnvironment} disabled={loading}>
          {loading ? "检查中..." : "检查抓包环境"}
        </button>
      </div>

      {environment ? (
        <div className="result-card">
          <div className="result-section">
            <div className="result-section__head">
              <h4>环境状态</h4>
              <span className={`status-pill status-pill--${environment.ready_for_capture ? "success" : "warn"}`}>
                {environment.ready_for_capture ? "可进入下一阶段" : "能力不完整"}
              </span>
            </div>
            <div className="kv-grid">
              <div className="kv">
                <span>系统</span>
                <strong>{environment.system}</strong>
              </div>
              <div className="kv">
                <span>可列出网卡</span>
                <strong>{environment.can_list_interfaces ? "是" : "否"}</strong>
              </div>
              <div className="kv">
                <span>抓包准备度</span>
                <strong>{environment.ready_for_capture ? "基础可用" : "待补依赖"}</strong>
              </div>
            </div>
            {environment.warnings.length ? (
              <div className="notice">{environment.warnings.join(" ")}</div>
            ) : null}
            {environment.interface_error ? (
              <div className="notice notice--error">{environment.interface_error}</div>
            ) : null}
          </div>

          <div className="result-section">
            <div className="result-section__head">
              <h4>工具检测</h4>
            </div>
            <div className="tool-status-grid">
              {Object.values(environment.tools).map((tool) => (
                <div key={tool.name} className="tool-status">
                  <div className="tcp-block__head">
                    <strong>{tool.name}</strong>
                    <span className={`status-pill status-pill--${tool.available ? "success" : "error"}`}>
                      {tool.available ? "available" : "missing"}
                    </span>
                  </div>
                  <p>{tool.path || "未找到可执行文件"}</p>
                  {tool.version_output ? <pre>{tool.version_output}</pre> : null}
                </div>
              ))}
            </div>
          </div>

          <div className="result-section">
            <div className="result-section__head">
              <h4>网卡列表</h4>
              <span className="status-pill">{environment.interfaces.length}</span>
            </div>
            <div className="interface-table">
              {environment.interfaces.map((item) => (
                <div className="interface-row" key={`${item.source}-${item.index}-${item.name}`}>
                  <span>{item.index}</span>
                  <strong>{item.name}</strong>
                  <code>{item.flags.length ? item.flags.join(", ") : "-"}</code>
                </div>
              ))}
            </div>
          </div>

          <div className="result-section">
            <div className="result-section__head">
              <h4>短时抓包</h4>
              <span className="status-pill">受控执行</span>
            </div>
            <div className="capture-form">
              <label>
                <span>网卡</span>
                <select value={selectedInterface} onChange={(event) => setSelectedInterface(event.target.value)}>
                  {environment.interfaces.map((item) => (
                    <option key={`${item.source}-${item.index}-${item.name}`} value={item.name}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>BPF 过滤</span>
                <input
                  value={bpfFilter}
                  onChange={(event) => setBpfFilter(event.target.value)}
                  placeholder="host 1.1.1.1 or port 443"
                />
              </label>
              <label>
                <span>时长秒</span>
                <input value={durationSeconds} onChange={(event) => setDurationSeconds(event.target.value)} />
              </label>
              <label>
                <span>包数上限</span>
                <input value={packetCount} onChange={(event) => setPacketCount(event.target.value)} />
              </label>
              <button onClick={runCapture} disabled={captureLoading || !environment.ready_for_capture}>
                {captureLoading ? "抓包中..." : "开始短时抓包"}
              </button>
            </div>
            <div className="notice">
              建议先用较小包数和短时长验证权限。macOS/Linux 上抓包通常需要管理员权限或特定能力授权。
            </div>
          </div>

          {captureResult ? (
            <div className="result-section">
              <div className="result-section__head">
                <h4>抓包结果</h4>
                <span className={`status-pill status-pill--${captureResult.status}`}>
                  {captureResult.status}
                </span>
              </div>
              <div className="kv-grid">
                <div className="kv">
                  <span>网卡</span>
                  <strong>{captureResult.interface}</strong>
                </div>
                <div className="kv">
                  <span>pcap 路径</span>
                  <strong>{captureResult.pcap_path || "-"}</strong>
                </div>
                <div className="kv">
                  <span>摘要行数</span>
                  <strong>{captureResult.packet_count}</strong>
                </div>
              </div>
              {captureResult.error ? <div className="notice notice--error">{captureResult.error}</div> : null}
              {captureResult.summary_lines.length ? (
                <pre className="packet-summary">{captureResult.summary_lines.join("\n")}</pre>
              ) : null}
              <details className="raw-details">
                <summary>查看命令与原始结果</summary>
                <pre>{JSON.stringify(captureResult, null, 2)}</pre>
              </details>
            </div>
          ) : null}

          <details className="raw-details">
            <summary>查看原始 JSON</summary>
            <pre>{JSON.stringify(environment, null, 2)}</pre>
          </details>
        </div>
      ) : null}
    </div>
  );
}

export function ModuleDetail({ module, onBack }: ModuleDetailProps) {
  return (
    <section className="section module-detail">
      <button className="back-button" onClick={onBack}>
        返回功能选择
      </button>
      <div className="section-head">
        <div>
          <p className="section-label">{module.category}</p>
          <h2>{module.name}</h2>
          <p>{module.summary}</p>
        </div>
      </div>

      {module.key === "domain-access" ? <DomainTool /> : null}
      {module.key === "network-diagnostics" ? <NetworkTool /> : null}
      {module.key === "packet-capture" ? <CaptureTool /> : null}
      {module.key !== "domain-access" && module.key !== "network-diagnostics" && module.key !== "packet-capture" ? (
        <PlannedModule module={module} />
      ) : null}
    </section>
  );
}
