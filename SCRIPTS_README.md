# QuantX 启动脚本使用指南

快速启动和停止 QuantX 后端 API 和前端开发服务器的脚本。

## 📋 脚本列表

### Windows (PowerShell)

| 脚本 | 功能 | 用法 |
|------|------|------|
| `start-backend.ps1` | 启动后端 API 服务器 | `.\start-backend.ps1` |
| `start-frontend.ps1` | 启动前端开发服务器 | `.\start-frontend.ps1` |
| `start-all.ps1` | 同时启动后端和前端 | `.\start-all.ps1` |
| `stop-servers.ps1` | 停止所有服务器 | `.\stop-servers.ps1` |

### macOS / Linux (Bash)

| 脚本 | 功能 | 用法 |
|------|------|------|
| `start-backend.sh` | 启动后端 API 服务器 | `./start-backend.sh` |
| `start-frontend.sh` | 启动前端开发服务器 | `./start-frontend.sh` |
| `start-all.sh` | 同时启动后端和前端 | `./start-all.sh` |
| `stop-servers.sh` | 停止所有服务器 | `./stop-servers.sh` |

## 🚀 快速开始

### 方式 1：一键启动所有服务（推荐）

**Windows:**
```powershell
.\start-all.ps1
```

**macOS/Linux:**
```bash
chmod +x start-all.sh
./start-all.sh
```

这会：
- ✅ 启动后端 API 服务器（端口 8000）
- ✅ 启动前端开发服务器（端口 5173）
- ✅ 自动打开浏览器访问 http://127.0.0.1:5173

### 方式 2：分别启动后端和前端

**启动后端（Windows）:**
```powershell
.\start-backend.ps1
```

**启动后端（macOS/Linux）:**
```bash
chmod +x start-backend.sh
./start-backend.sh
```

在另一个终端启动前端：

**启动前端（Windows）:**
```powershell
.\start-frontend.ps1
```

**启动前端（macOS/Linux）:**
```bash
chmod +x start-frontend.sh
./start-frontend.sh
```

## 🛑 停止服务

### 停止所有服务

**Windows:**
```powershell
.\stop-servers.ps1
```

**macOS/Linux:**
```bash
chmod +x stop-servers.sh
./stop-servers.sh
```

### 手动停止

- **后端**：在后端终端按 `Ctrl+C`
- **前端**：在前端终端按 `Ctrl+C`

## 📍 服务地址

启动后，可以访问以下地址：

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端仪表板 | http://127.0.0.1:5173 | React 开发服务器 |
| 后端 API | http://127.0.0.1:8000 | FastAPI 服务器 |
| API 文档 | http://127.0.0.1:8000/docs | Swagger UI |
| API 备选文档 | http://127.0.0.1:8000/redoc | ReDoc |

## ⚙️ 前置要求

### 必需

- **Python 3.8+** — 后端运行环境
- **Node.js 16+** — 前端构建和运行环境
- **npm** — Node.js 包管理器

### 检查安装

```bash
# 检查 Python
python --version

# 检查 Node.js
node --version

# 检查 npm
npm --version
```

### 首次设置

```bash
# 安装 Python 依赖
python -m pip install -r requirements.txt

# 安装前端依赖
cd web
npm install
cd ..
```

## 🔧 脚本详情

### start-backend.ps1 / start-backend.sh

启动 FastAPI 后端服务器，支持热重载。

```
特性：
- 自动重载（代码变更时自动重启）
- 监听 127.0.0.1:8000
- 支持 CORS（跨域请求）
```

### start-frontend.ps1 / start-frontend.sh

启动 Vite 前端开发服务器。

```
特性：
- 快速热模块替换 (HMR)
- 监听 127.0.0.1:5173
- 自动浏览器刷新
```

### start-all.ps1 / start-all.sh

同时启动后端和前端，并自动打开浏览器。

```
特性：
- 在新窗口/标签页启动两个服务
- 自动打开浏览器
- 显示启动信息和 PID
```

### stop-servers.ps1 / stop-servers.sh

停止所有运行的服务器。

```
特性：
- 自动检测并停止后端进程
- 自动检测并停止前端进程
- 释放占用的端口
```

## 🐛 故障排除

### 端口已被占用

如果看到 "Address already in use" 错误：

**Windows:**
```powershell
# 查看占用端口 8000 的进程
Get-NetTCPConnection -LocalPort 8000

# 强制停止
.\stop-servers.ps1
```

**macOS/Linux:**
```bash
# 查看占用端口 8000 的进程
lsof -i :8000

# 强制停止
./stop-servers.sh
```

### npm 依赖问题

```bash
# 清除 npm 缓存
npm cache clean --force

# 重新安装依赖
cd web
rm -rf node_modules package-lock.json
npm install
cd ..
```

### Python 依赖问题

```bash
# 重新安装 Python 依赖
python -m pip install --upgrade -r requirements.txt
```

## 📝 环境变量

### 后端

```bash
# 自定义 API 主机和端口
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000
```

### 前端

```bash
# 自定义 API 基础 URL
VITE_API_BASE=http://127.0.0.1:8000
```

## 🔐 生产部署

对于生产环境，不要使用这些开发脚本。改用：

```bash
# 后端
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000

# 前端
cd web
npm run build
# 使用 nginx 或其他 web 服务器提供 dist/ 目录
```

## 📚 相关文档

- [Web 仪表板文档](docs/web-dashboard.md)
- [API 文档](http://127.0.0.1:8000/docs)
- [项目 README](README.md)

## 💡 提示

- 使用 `start-all.ps1` / `start-all.sh` 是最快的方式
- 前端会自动连接到后端 API
- 修改代码后，两个服务器都会自动重载
- 使用浏览器开发者工具（F12）调试前端
- 查看后端终端输出以调试 API 问题
