import { useEffect, useMemo, useState } from "react";
import { DiagnosticResultView, type QuickDiagnosticResult } from "./components/DiagnosticResultView";
import { ModuleCard } from "./components/ModuleCard";
import { ModuleDetail } from "./components/ModuleDetail";
import { fallbackModules, type ToolModule } from "./data/fallbackModules";

const API_BASE = "http://127.0.0.1:8000/api";

function App() {
  const [modules, setModules] = useState<ToolModule[]>(fallbackModules);
  const [target, setTarget] = useState("");
  const [result, setResult] = useState<QuickDiagnosticResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedModule, setSelectedModule] = useState<ToolModule | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/modules`)
      .then((response) => response.json())
      .then((data: ToolModule[]) => setModules(data))
      .catch(() => setModules(fallbackModules));
  }, []);

  const groupedModules = useMemo(() => {
    return modules.reduce<Record<string, ToolModule[]>>((acc, item) => {
      acc[item.category] ||= [];
      acc[item.category].push(item);
      return acc;
    }, {});
  }, [modules]);

  async function runDiagnostic() {
    if (!target.trim()) {
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/diagnostics/quick`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target }),
      });
      const data: QuickDiagnosticResult = await response.json();
      setResult(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__eyebrow">Ops Platform</span>
          <h1>运维工作台</h1>
        </div>
        <nav className="nav">
          <a href="#overview">工作台</a>
          <a href="#catalog">功能选择</a>
          <a href="#diagnostics">快速诊断</a>
          <a href="#roadmap">模块路线</a>
        </nav>
      </aside>

      <main className="content">
        {selectedModule ? (
          <ModuleDetail module={selectedModule} onBack={() => setSelectedModule(null)} />
        ) : (
          <>
        <section id="overview" className="hero">
          <div>
            <p className="section-label">统一入口</p>
            <h2>不是脚本列表，而是可部署的运维工作台</h2>
            <p className="hero__copy">
              首页同时提供功能选择区和快速诊断入口。诊断只是其中一类能力，后续可继续接入抓包、
              服务巡检、日志分析、批量任务等模块。
            </p>
          </div>
          <div className="hero__panel">
            <div className="hero__metric">
              <span>模块数</span>
              <strong>{modules.length}</strong>
            </div>
            <div className="hero__metric">
              <span>当前状态</span>
              <strong>骨架已就绪</strong>
            </div>
          </div>
        </section>

        <section id="catalog" className="section">
          <div className="section-head">
            <div>
              <p className="section-label">功能选择区</p>
              <h2>按运维能力域组织模块</h2>
            </div>
          </div>

          {Object.entries(groupedModules).map(([category, items]) => (
            <div key={category} className="module-group">
              <h3>{category}</h3>
              <div className="module-grid">
                {items.map((module) => (
                  <ModuleCard key={module.key} module={module} onOpen={setSelectedModule} />
                ))}
              </div>
            </div>
          ))}
        </section>

        <section id="diagnostics" className="section">
          <div className="section-head">
            <div>
              <p className="section-label">快速诊断</p>
              <h2>保留统一输入，但不绑死首页形态</h2>
            </div>
          </div>

          <div className="diagnostic-panel">
            <input
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              placeholder="输入域名、IP、URL 或 host:port"
            />
            <button onClick={runDiagnostic} disabled={loading}>
              {loading ? "识别中..." : "开始识别"}
            </button>
          </div>

          {result ? <DiagnosticResultView result={result} /> : null}
        </section>

        <section id="roadmap" className="section roadmap">
          <div className="section-head">
            <div>
              <p className="section-label">路线</p>
              <h2>后续扩展方向</h2>
            </div>
          </div>

          <div className="roadmap-grid">
            <div>
              <h3>第一阶段</h3>
              <p>迁移现有 IP 和域名脚本能力，统一为后端 checker。</p>
            </div>
            <div>
              <h3>第二阶段</h3>
              <p>补抓包 agent、实时任务流和 pcap 管理。</p>
            </div>
            <div>
              <h3>第三阶段</h3>
              <p>加入服务巡检、日志检索和批量任务执行。</p>
            </div>
          </div>
        </section>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
