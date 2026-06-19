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

interface CaptureTask {
  id: string;
  status: string;
  interface: string;
  bpf_filter?: string | null;
  duration_seconds: number;
  packet_count_limit: number;
  captured_packet_count: number;
  pcap_path?: string | null;
  summary_lines: string[];
  command: string[];
  error?: string | null;
  stderr?: string | null;
  source?: string | null;
  created_at: string;
  started_at: string;
  finished_at: string;
}

interface CaptureFile {
  id: string;
  filename: string;
  path: string;
  size_bytes: number;
  created_at: string;
  modified_at: string;
}

interface OperationLog {
  id: string;
  timestamp: string;
  module: string;
  action: string;
  status: string;
  message: string;
  metadata: Record<string, unknown>;
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
  const [captureTask, setCaptureTask] = useState<CaptureTask | null>(null);
  const [tasks, setTasks] = useState<CaptureTask[]>([]);
  const [files, setFiles] = useState<CaptureFile[]>([]);
  const [logs, setLogs] = useState<OperationLog[]>([]);

  async function loadEnvironment() {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/tools/capture/environment`);
      const data: CaptureEnvironment = await response.json();
      setEnvironment(data);
      setSelectedInterface((current) => current || data.interfaces.find((item) => item.name === "en0")?.name || data.interfaces[0]?.name || "");
      await loadLogs();
    } finally {
      setLoading(false);
    }
  }

  async function createTask() {
    if (!selectedInterface) {
      return;
    }
    setCaptureLoading(true);
    try {
      const payload = {
        interface: selectedInterface,
        bpf_filter: bpfFilter.trim() || null,
        duration_seconds: Number.parseInt(durationSeconds, 10) || 5,
        packet_count: Number.parseInt(packetCount, 10) || 50,
      };
      const response = await fetch(`${API_BASE}/tools/capture/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data: CaptureTask = await response.json();
      setCaptureTask(data);
      setCaptureResult({
        status: data.status === "success" ? "success" : "error",
        interface: data.interface,
        bpf_filter: data.bpf_filter,
        pcap_path: data.pcap_path,
        packet_count: data.captured_packet_count,
        summary_lines: data.summary_lines,
        command: data.command,
        error: data.error,
        stderr: data.stderr,
      });
      await loadTasks();
      await loadFiles();
      await loadLogs();
    } finally {
      setCaptureLoading(false);
    }
  }

  async function loadTasks() {
    const response = await fetch(`${API_BASE}/tools/capture/tasks?limit=10`);
    const data: CaptureTask[] = await response.json();
    setTasks(data);
    await loadLogs();
  }

  async function loadFiles() {
    const response = await fetch(`${API_BASE}/tools/capture/files`);
    const data: CaptureFile[] = await response.json();
    setFiles(data);
    await loadLogs();
  }

  async function deleteFile(fileId: string) {
    await fetch(`${API_BASE}/tools/capture/files/${encodeURIComponent(fileId)}`, {
      method: "DELETE",
    });
    await loadFiles();
    await loadLogs();
  }

  async function loadLogs() {
    const response = await fetch(`${API_BASE}/operation-logs?module=capture&limit=20`);
    const data: OperationLog[] = await response.json();
    setLogs(data);
  }

  return (
    <div className="tool-panel">
      <div className="capture-actions">
        <button onClick={loadEnvironment} disabled={loading}>
          {loading ? "检查中..." : "检查抓包环境"}
        </button>
        <button onClick={loadTasks}>刷新任务</button>
        <button onClick={loadFiles}>刷新文件</button>
        <button onClick={loadLogs}>刷新日志</button>
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
              <button onClick={createTask} disabled={captureLoading || !environment.ready_for_capture}>
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
                  <span>任务 ID</span>
                  <strong>{captureTask?.id || "-"}</strong>
                </div>
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

          <div className="result-section">
            <div className="result-section__head">
              <h4>最近抓包任务</h4>
              <span className="status-pill">{tasks.length}</span>
            </div>
            {tasks.length ? (
              <div className="task-table">
                {tasks.map((task) => (
                  <div className="task-row" key={task.id}>
                    <span className={`status-pill status-pill--${task.status}`}>{task.status}</span>
                    <strong>{task.interface}</strong>
                    <code>{task.id}</code>
                    <small>{new Date(task.finished_at).toLocaleString()}</small>
                  </div>
                ))}
              </div>
            ) : (
              <p className="tool-panel__empty">暂无抓包任务记录。</p>
            )}
          </div>

          <div className="result-section">
            <div className="result-section__head">
              <h4>pcap 文件</h4>
              <span className="status-pill">{files.length}</span>
            </div>
            {files.length ? (
              <div className="file-table">
                {files.map((file) => (
                  <div className="file-row" key={file.id}>
                    <strong>{file.filename}</strong>
                    <span>{`${(file.size_bytes / 1024).toFixed(1)} KB`}</span>
                    <small>{new Date(file.modified_at).toLocaleString()}</small>
                    <div className="file-actions">
                      <a href={`${API_BASE}/tools/capture/files/${encodeURIComponent(file.id)}/download`}>下载</a>
                      <button onClick={() => deleteFile(file.id)}>删除</button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="tool-panel__empty">暂无 pcap 文件。</p>
            )}
          </div>

          <div className="result-section">
            <div className="result-section__head">
              <h4>操作日志</h4>
              <span className="status-pill">{logs.length}</span>
            </div>
            {logs.length ? (
              <div className="log-table">
                {logs.map((log) => (
                  <div className="log-row" key={log.id}>
                    <span className={`status-pill status-pill--${log.status}`}>{log.status}</span>
                    <strong>{log.message}</strong>
                    <code>{log.action}</code>
                    <small>{new Date(log.timestamp).toLocaleString()}</small>
                  </div>
                ))}
              </div>
            ) : (
              <p className="tool-panel__empty">暂无操作日志。</p>
            )}
          </div>

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
