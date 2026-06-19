import type { ToolModule } from "../data/fallbackModules";

interface ModuleCardProps {
  module: ToolModule;
  onOpen?: (module: ToolModule) => void;
}

const statusText: Record<ToolModule["status"], string> = {
  active: "可接入",
  planned: "规划中",
  experimental: "实验性",
};

export function ModuleCard({ module, onOpen }: ModuleCardProps) {
  return (
    <article className="module-card">
      <div className="module-card__header">
        <span className="module-card__category">{module.category}</span>
        <span className={`module-card__status module-card__status--${module.status}`}>
          {statusText[module.status]}
        </span>
      </div>
      <h3>{module.name}</h3>
      <p>{module.summary}</p>
      <ul className="module-card__caps">
        {module.capabilities.map((capability) => (
          <li key={capability}>{capability}</li>
        ))}
      </ul>
      <button className="module-card__action" onClick={() => onOpen?.(module)}>
        打开模块
      </button>
    </article>
  );
}
