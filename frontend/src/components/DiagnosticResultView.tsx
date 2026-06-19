interface CommandResult {
  command?: string[];
  returncode?: number;
  stdout?: string;
  stderr?: string;
  error?: string;
  elapsed_seconds?: number;
}

interface TcpResult {
  target?: string;
  host?: string;
  port?: number;
  ok?: boolean;
  scanner?: string;
  port_state?: string;
  port_reason?: string;
  error?: string;
  elapsed_seconds?: number;
}

export interface DomainDiagnostic {
  status: string;
  dns?: {
    dns_server?: string | null;
    records?: Record<string, string[]>;
    ports?: Record<string, string>;
    errors?: string[];
    response_time?: number | null;
    ttl?: Record<string, number>;
    ip_info?: Record<string, unknown>;
  };
  ssl?: {
    issuer?: string | null;
    subject?: string | null;
    valid_from?: string | null;
    valid_to?: string | null;
    days_remaining?: number | null;
    is_valid?: string | null;
    error?: string | null;
  };
}

export interface NetworkDiagnostic {
  status: string;
  ip_classification?: {
    ip?: string;
    version?: number;
    network_type?: string[];
    reverse_dns?: string | null;
    error?: string;
  };
  ping?: CommandResult;
  tcp?: TcpResult;
  tcp_80?: TcpResult;
  tcp_443?: TcpResult;
  trace?: CommandResult;
}

export interface QuickDiagnosticResult {
  module_key: string;
  target: string;
  status: "success" | "warn" | "error" | "info";
  summary: string;
  suggestions: string[];
  raw_data: {
    target_type: string;
    domain_diagnostic?: DomainDiagnostic;
    network_diagnostic?: NetworkDiagnostic;
  };
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return String(value);
}

function KeyValue({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="kv">
      <span>{label}</span>
      <strong>{formatValue(value)}</strong>
    </div>
  );
}

function StatusPill({ value }: { value?: string | boolean }) {
  const normalized = String(value ?? "unknown");
  return <span className={`status-pill status-pill--${normalized}`}>{normalized}</span>;
}

export function DnsSection({ diagnostic }: { diagnostic: DomainDiagnostic }) {
  const dns = diagnostic.dns;
  if (!dns) {
    return null;
  }

  const records = Object.entries(dns.records ?? {});
  const ports = Object.entries(dns.ports ?? {});
  const ipInfo = dns.ip_info ?? {};

  return (
    <div className="result-section">
      <div className="result-section__head">
        <h4>DNS 与接入</h4>
        <StatusPill value={diagnostic.status} />
      </div>

      <div className="kv-grid">
        <KeyValue label="DNS 服务器" value={dns.dns_server} />
        <KeyValue label="响应耗时" value={dns.response_time ? `${dns.response_time} ms` : null} />
        <KeyValue label="IP 归属" value={[ipInfo.country, ipInfo.isp].filter(Boolean).join(" / ")} />
      </div>

      {dns.errors?.length ? (
        <div className="notice notice--error">{dns.errors.join("; ")}</div>
      ) : null}

      {records.length ? (
        <div className="record-table">
          {records.map(([type, values]) => (
            <div className="record-row" key={type}>
              <span>{type}</span>
              <code>{values.join(" | ")}</code>
            </div>
          ))}
        </div>
      ) : null}

      {ports.length ? (
        <div className="port-grid">
          {ports.map(([port, state]) => (
            <div key={port}>
              <span>{port}</span>
              <strong>{state}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function TlsSection({ diagnostic }: { diagnostic: DomainDiagnostic }) {
  if (!diagnostic.ssl) {
    return null;
  }
  const ssl = diagnostic.ssl;

  return (
    <div className="result-section">
      <div className="result-section__head">
        <h4>TLS 证书</h4>
        <StatusPill value={ssl.is_valid ?? (ssl.error ? "error" : "unknown")} />
      </div>
      {ssl.error ? <div className="notice notice--error">{ssl.error}</div> : null}
      <div className="kv-grid">
        <KeyValue label="主体" value={ssl.subject} />
        <KeyValue label="签发者" value={ssl.issuer} />
        <KeyValue label="生效时间" value={ssl.valid_from} />
        <KeyValue label="过期时间" value={ssl.valid_to} />
        <KeyValue label="剩余天数" value={ssl.days_remaining} />
      </div>
    </div>
  );
}

function TcpBlock({ title, result }: { title: string; result?: TcpResult }) {
  if (!result) {
    return null;
  }

  return (
    <div className="tcp-block">
      <div className="tcp-block__head">
        <strong>{title}</strong>
        <StatusPill value={result.port_state ?? result.ok} />
      </div>
      <div className="kv-grid kv-grid--compact">
        <KeyValue label="目标" value={result.target ?? `${result.host}:${result.port}`} />
        <KeyValue label="扫描器" value={result.scanner} />
        <KeyValue label="耗时" value={result.elapsed_seconds ? `${result.elapsed_seconds}s` : null} />
      </div>
      <p>{result.port_reason ?? result.error}</p>
    </div>
  );
}

export function NetworkSection({ diagnostic }: { diagnostic: NetworkDiagnostic }) {
  return (
    <div className="result-section">
      <div className="result-section__head">
        <h4>网络检查</h4>
        <StatusPill value={diagnostic.status} />
      </div>

      <div className="kv-grid">
        <KeyValue label="IP" value={diagnostic.ip_classification?.ip} />
        <KeyValue label="版本" value={diagnostic.ip_classification?.version} />
        <KeyValue label="类型" value={diagnostic.ip_classification?.network_type} />
        <KeyValue label="反向 DNS" value={diagnostic.ip_classification?.reverse_dns} />
      </div>

      {diagnostic.ip_classification?.error ? (
        <div className="notice">{diagnostic.ip_classification.error}</div>
      ) : null}

      {diagnostic.ping ? (
        <div className="command-block">
          <div className="tcp-block__head">
            <strong>Ping</strong>
            <StatusPill value={diagnostic.ping.returncode === 0 ? "success" : "warn"} />
          </div>
          <pre>{diagnostic.ping.stdout || diagnostic.ping.stderr || diagnostic.ping.error}</pre>
        </div>
      ) : null}

      <div className="tcp-grid">
        <TcpBlock title="TCP" result={diagnostic.tcp} />
        <TcpBlock title="TCP 80" result={diagnostic.tcp_80} />
        <TcpBlock title="TCP 443" result={diagnostic.tcp_443} />
      </div>
    </div>
  );
}

export function DiagnosticResultView({ result }: { result: QuickDiagnosticResult }) {
  const domainDiagnostic = result.raw_data.domain_diagnostic;
  const networkDiagnostic = result.raw_data.network_diagnostic;

  return (
    <div className="result-card">
      <div className="result-card__head">
        <span className="result-card__type">{result.raw_data.target_type}</span>
        <strong>{result.target}</strong>
      </div>
      <p>{result.summary}</p>

      {domainDiagnostic ? (
        <>
          <DnsSection diagnostic={domainDiagnostic} />
          <TlsSection diagnostic={domainDiagnostic} />
        </>
      ) : null}

      {networkDiagnostic ? <NetworkSection diagnostic={networkDiagnostic} /> : null}

      <details className="raw-details">
        <summary>查看原始 JSON</summary>
        <pre>{JSON.stringify(result.raw_data, null, 2)}</pre>
      </details>
    </div>
  );
}
