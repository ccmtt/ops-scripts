# Capture Agent

独立抓包 agent，用于把需要较高权限的抓包能力从主 Web 后端中拆出去。

## 本地运行

在 macOS/Linux 上，如果需要实际抓包，通常要使用具备抓包权限的方式启动：

```bash
cd /Users/chenmingtao/script-cmt
sudo backend/.venv/bin/uvicorn agents.capture.app.main:app --host 127.0.0.1 --port 9000
```

主后端通过环境变量连接 agent：

```bash
CAPTURE_AGENT_URL=http://127.0.0.1:9000 \
  backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 接口

- `GET /health`
- `GET /environment`
- `POST /run`
