# 运维工作台架构与 MVP 设计

## 1. 产品定位

本项目定位为一个可自部署的本地化运维工作台，而不是单一的诊断入口或若干脚本的页面包装。

目标特征：

- 可在任意一台电脑或服务器上重新部署
- 以浏览器访问为主，避免桌面平台绑定
- 具备功能选择区，按能力域组织工具
- 支持诊断、巡检、抓包、服务检查、日志分析等运维场景
- 保留插件化扩展空间，便于持续新增能力

## 2. 信息架构

首页应同时提供两类入口：

1. 诊断入口
   - 输入域名 / IP / URL / host:port
   - 自动识别目标类型并执行诊断流

2. 功能选择区
   - 按运维能力域列出可直接进入的工具模块

推荐一级导航：

- 工作台
- 网络诊断
- 域名与接入
- 抓包分析
- 服务巡检
- 日志中心
- 批量任务
- 历史记录
- 系统设置

## 3. 功能域划分

### 3.1 网络诊断

- Ping
- TCP/UDP 端口检测
- Traceroute / MTR
- DNS 查询
- MTU / 路由类检查

### 3.2 域名与接入

- DNS 解析
- 多公共 DNS 对比
- WHOIS
- CDN 判断
- TLS 证书检查
- HTTP/HTTPS 响应检查

### 3.3 抓包分析

- 本机网卡列表
- 启动 / 停止抓包
- BPF 过滤条件
- 实时数据包摘要
- pcap 文件保存与读取
- 会话聚合与基础协议解析

### 3.4 服务巡检

- Nginx / Apache
- MySQL / Redis / PostgreSQL
- SSH
- Docker / Kubernetes
- 常见端口模板巡检

### 3.5 日志中心

- 本地日志文件读取
- 时间窗口过滤
- 关键错误模式搜索
- 多来源结果聚合

### 3.6 批量任务

- 导入域名/IP/URL/主机列表
- 批量执行选定工具
- 汇总结果
- 导出 JSON / CSV

## 4. MVP 范围

第一版只实现能跑通平台架构和扩展路径的能力，避免一开始过度铺开：

### 4.1 已实现的页面骨架

- 工作台首页
- 工具目录页
- 模块概览区
- 快速诊断入口

### 4.2 第一批后端模块

- 模块注册中心
- 诊断入口接口
- 功能目录接口
- 抓包模块占位接口
- 历史任务占位接口

### 4.3 第一批可迁移能力

- 域名工具能力迁移入口
- IP / 端口 / 连通性能力迁移入口

## 5. 系统架构

采用三层结构：

1. Web UI
2. API / Orchestrator
3. Workers / Agents

### 5.1 Web UI

职责：

- 展示功能选择区
- 发起诊断任务
- 展示模块状态与结果
- 展示抓包任务状态

建议技术栈：

- React
- TypeScript
- Vite

### 5.2 API / Orchestrator

职责：

- 统一对外 API
- 模块注册与发现
- 任务编排
- 结果模型统一
- 历史记录与设置管理

建议技术栈：

- FastAPI
- Pydantic

### 5.3 Workers / Agents

职责：

- 执行各类检查器
- 承担抓包这类需要特殊权限的任务
- 将结果回传给 API 层

建议拆分：

- 通用检查 worker
- 抓包 agent

## 6. 模块模型

每个功能模块统一描述为：

- `key`: 模块唯一标识
- `name`: 展示名称
- `category`: 所属能力域
- `summary`: 简述
- `status`: `planned` / `active` / `experimental`
- `entry`: 前端入口路径
- `capabilities`: 支持的能力列表

每个执行结果统一描述为：

- `id`
- `module_key`
- `target`
- `status`
- `summary`
- `raw_data`
- `suggestions`
- `started_at`
- `finished_at`

## 7. 现有脚本迁移策略

现有脚本不应继续作为应用主入口保留，而应逐步拆到后端模块中：

- `domain_tool.py`
  - 迁移到 `backend/app/checkers/domain_*`
  - 拆分为 DNS / WHOIS / TLS / IP 信息等服务

- `ip_check.py`
  - 迁移到 `backend/app/checkers/network_*`
  - 拆分为 ping / traceroute / port / scan / route 等服务

迁移原则：

- 先保留脚本文件，不直接改动用户当前未提交内容
- 新代码通过 adapter 调用旧脚本能力或逐步平移函数
- 待接口稳定后再考虑彻底收敛

## 8. 部署策略

优先采用 `Docker Compose`，提供：

- `backend`
- `frontend`

后续可扩展：

- `worker`
- `capture-agent`
- `postgres`
- `redis`

### 8.1 本地开发

- 后端：`uvicorn`
- 前端：`vite`

### 8.2 可部署环境

- Dockerfile for backend
- Dockerfile for frontend
- `docker-compose.yml`

## 9. 抓包模块设计原则

抓包能力不做 Wireshark 复刻，而聚焦运维排障需要：

- 选择网卡
- 指定过滤表达式
- 启停抓包
- 展示包摘要
- 保存 pcap
- 提供基础会话和协议视图

注意：

- 抓包通常需要高权限
- 应独立为 agent 或受控执行单元
- 需要明确平台兼容与权限要求

## 10. 下一阶段建议

1. 将首页做成真正的功能工作台
2. 补齐模块详情页路由
3. 为抓包模块设计后端执行接口
4. 将现有两个脚本的能力抽象为可复用 checker
5. 为任务结果持久化预留存储层
