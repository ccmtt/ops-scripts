export type ModuleStatus = "planned" | "active" | "experimental";

export interface ToolModule {
  key: string;
  name: string;
  category: string;
  summary: string;
  status: ModuleStatus;
  entry: string;
  capabilities: string[];
}

export const fallbackModules: ToolModule[] = [
  {
    key: "network-diagnostics",
    name: "网络诊断",
    category: "诊断",
    summary: "连通性、端口、路由和基础网络检查。",
    status: "active",
    entry: "/modules/network-diagnostics",
    capabilities: ["Ping", "TCP 端口", "Traceroute", "基础扫描"],
  },
  {
    key: "domain-access",
    name: "域名与接入",
    category: "诊断",
    summary: "DNS、WHOIS、TLS 证书和 HTTP 接入检查。",
    status: "active",
    entry: "/modules/domain-access",
    capabilities: ["DNS", "WHOIS", "CDN 判断", "TLS 检查"],
  },
  {
    key: "packet-capture",
    name: "抓包分析",
    category: "流量",
    summary: "网卡选择、过滤表达式、实时抓包和 pcap 管理。",
    status: "experimental",
    entry: "/modules/packet-capture",
    capabilities: ["环境检查", "网卡管理", "过滤器", "pcap 导出"],
  },
  {
    key: "service-inspection",
    name: "服务巡检",
    category: "巡检",
    summary: "面向常见中间件和服务的专项检查入口。",
    status: "planned",
    entry: "/modules/service-inspection",
    capabilities: ["Nginx", "Redis", "MySQL", "Docker/K8s"],
  },
  {
    key: "log-center",
    name: "日志中心",
    category: "分析",
    summary: "按时间窗口和错误模式检索日志。",
    status: "planned",
    entry: "/modules/log-center",
    capabilities: ["日志读取", "筛选", "错误聚合"],
  },
  {
    key: "batch-jobs",
    name: "批量任务",
    category: "效率",
    summary: "批量执行检查并导出汇总结果。",
    status: "planned",
    entry: "/modules/batch-jobs",
    capabilities: ["导入目标", "批量执行", "导出报告"],
  },
];
