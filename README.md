# Ops Workbench

一个可自部署的本地化运维工作台骨架，支持通过浏览器访问，并为网络诊断、域名接入、抓包分析、服务巡检、日志中心和批量任务预留扩展路径。

## 当前状态

当前版本已提供：

- FastAPI 后端骨架
- React + Vite 前端骨架
- 功能选择区首页
- 快速诊断接口
- 域名检查接口，已接入 `domain_tool.py`
- 网络检查接口，已接入 `ip_check.py`
- Docker Compose 部署入口

## 本地开发

打开两个终端，分别启动后端和前端。

也可以使用脚本启动：

```bash
./scripts/start-backend.sh
./scripts/start-frontend.sh
./scripts/start-capture-agent.sh
```

### 后端

```bash
cd /Users/chenmingtao/script-cmt/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd /Users/chenmingtao/script-cmt/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

访问：

- 前端: http://127.0.0.1:5173
- 后端: http://127.0.0.1:8000/api/health

## 如何验证进展

### 1. 浏览器验证

1. 启动后端和前端
2. 打开 http://127.0.0.1:5173
3. 在“快速诊断”里输入：
   - `example.com`
   - `https://example.com`
   - `127.0.0.1:8000`
4. 点击“开始识别”
5. 页面应展示 DNS、TLS、TCP 或 IP 分类结果

也可以在“功能选择区”直接打开专项模块：

- 点击“网络诊断”，输入主机、端口和超时参数后执行 TCP / Ping / Trace 检查
- 点击“域名与接入”，输入域名后执行 DNS、TLS、WHOIS 或多 DNS 对比
- 点击“抓包分析”，检查 tcpdump/tshark 可用性和本机网卡列表

### 2. 后端接口验证

健康检查：

```bash
curl -s http://127.0.0.1:8000/api/health
```

快速诊断：

```bash
curl -s -X POST http://127.0.0.1:8000/api/diagnostics/quick \
  -H 'Content-Type: application/json' \
  -d '{"target":"example.com","timeout":2}'
```

域名专项检查：

```bash
curl -s -X POST http://127.0.0.1:8000/api/tools/domain \
  -H 'Content-Type: application/json' \
  -d '{"domain":"example.com","include_ssl":true,"compare_dns":false}'
```

网络专项检查：

```bash
curl -s -X POST http://127.0.0.1:8000/api/tools/network \
  -H 'Content-Type: application/json' \
  -d '{"host":"127.0.0.1","port":8000,"timeout":1,"include_ping":false}'
```

抓包环境检查：

```bash
curl -s http://127.0.0.1:8000/api/tools/capture/environment
```

抓包权限检查：

```bash
curl -s http://127.0.0.1:8000/api/tools/capture/permission
```

短时抓包：

```bash
curl -s -X POST http://127.0.0.1:8000/api/tools/capture/run \
  -H 'Content-Type: application/json' \
  -d '{"interface":"lo0","bpf_filter":null,"duration_seconds":3,"packet_count":10}'
```

创建抓包任务记录：

```bash
curl -s -X POST http://127.0.0.1:8000/api/tools/capture/tasks \
  -H 'Content-Type: application/json' \
  -d '{"interface":"lo0","bpf_filter":null,"duration_seconds":3,"packet_count":10}'
```

查看最近抓包任务：

```bash
curl -s http://127.0.0.1:8000/api/tools/capture/tasks
```

查看 pcap 文件：

```bash
curl -s http://127.0.0.1:8000/api/tools/capture/files
```

查看操作日志：

```bash
curl -s 'http://127.0.0.1:8000/api/operation-logs?module=capture&limit=20'
```

下载 pcap 文件：

```bash
curl -OJ http://127.0.0.1:8000/api/tools/capture/files/<filename>.pcap/download
```

说明：抓包通常需要管理员权限。如果接口返回权限错误，说明 Web 后端进程没有抓包权限，后续应通过独立 capture-agent 或管理员权限运行。

### 3. 当前限制

- 网络诊断和域名与接入已有专项模块页
- 抓包分析已有环境检查和网卡列表
- 抓包分析已有短时抓包接口，会生成 pcap 并读取摘要
- 抓包分析已有轻量任务记录，支持创建、列表、详情查询
- 抓包分析已有 pcap 文件列表和下载
- 抓包分析已有操作日志，页面可查看近期操作记录
- 其他模块仍是规划页
- 抓包模块尚未实现后台长任务和停止控制
- 旧脚本仍作为 adapter 被调用，后续会逐步拆成独立 checker

## Docker Compose

```bash
docker compose up --build
```

访问：

- 前端: http://127.0.0.1:5173
- 后端: http://127.0.0.1:8000/api/health
- 抓包 agent: http://127.0.0.1:9000/health

## Capture Agent

抓包能力可以通过独立 agent 执行，避免主 Web 后端长期持有高权限。

### 直接启动 agent

```bash
cd /Users/chenmingtao/script-cmt
sudo backend/.venv/bin/uvicorn agents.capture.app.main:app --host 127.0.0.1 --port 9000
```

### 让后端连接 agent

```bash
cd /Users/chenmingtao/script-cmt/backend
source .venv/bin/activate
CAPTURE_AGENT_URL=http://127.0.0.1:9000 \
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

未设置 `CAPTURE_AGENT_URL` 时，后端会回退到本地执行抓包检查。

权限检查：

```bash
curl -s http://127.0.0.1:8000/api/tools/capture/permission
```

## 目录说明

```text
backend/     FastAPI 后端
frontend/    React 前端
docs/        架构与设计文档
agents/      特权能力代理预留目录
docker/      预留的部署辅助目录
```

## 下一步

1. 将现有 `domain_tool.py` 和 `ip_check.py` 的能力拆到 `backend/app/checkers/`
2. 为抓包能力补充独立 agent 和接口
3. 增加模块详情页和任务历史记录
