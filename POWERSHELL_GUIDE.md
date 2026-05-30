# QuantX PowerShell 启动指南

## 🚀 快速开始

### 方式 1：在两个不同的 PowerShell 终端中分别启动（推荐）

**PowerShell 终端 1 - 启动后端 API：**
```powershell
.\start-backend.ps1
```

**PowerShell 终端 2 - 启动前端开发服务器：**
```powershell
.\start-frontend.ps1
```

### 方式 2：一键启动所有服务（自动打开两个新窗口）

```powershell
.\start-all.ps1
```

这会自动：
- ✅ 启动后端 API 服务器（http://127.0.0.1:8000）
- ✅ 启动前端开发服务器（http://127.0.0.1:5173）
- ✅ 打开浏览器访问仪表板

---

## 📍 服务地址

启动后可以访问：

| 服务 | 地址 | 说明 |
|------|------|------|
| **前端仪表板** | http://127.0.0.1:5173 | React 开发服务器 |
| **后端 API** | http://127.0.0.1:8000 | FastAPI 服务器 |
| **API 文档** | http://127.0.0.1:8000/docs | Swagger UI |
| **API 备选文档** | http://127.0.0.1:8000/redoc | ReDoc |

---

## 🛑 停止服务

### 方式 1：运行停止脚本

```powershell
.\stop-servers.ps1
```

### 方式 2：手动停止

在任何 PowerShell 终端按 `Ctrl+C` 停止服务

---

## 📋 所有可用的 PowerShell 脚本

| 脚本 | 功能 | 用法 |
|------|------|------|
| **`start-backend.ps1`** | 启动后端 API 服务器 | `.\start-backend.ps1` |
| **`start-frontend.ps1`** | 启动前端开发服务器 | `.\start-frontend.ps1` |
| **`start-all.ps1`** | 同时启动后端和前端 | `.\start-all.ps1` |
| **`stop-servers.ps1`** | 停止所有服务器 | `.\stop-servers.ps1` |

---

## ⚙️ 首次设置

```powershell
# 安装 Python 依赖
python -m pip install -r requirements.txt

# 安装前端依赖
cd web
npm install
cd ..
```

---

## 🔧 脚本详情

### start-backend.ps1

启动 FastAPI 后端服务器，支持热重载。

**特性：**
- 自动重载（代码变更时自动重启）
- 监听 127.0.0.1:8000
- 支持 CORS（跨域请求）
- 彩色输出

**输出示例：**
```
Starting QuantX Backend API Server...
API will be available at http://127.0.0.1:8000
Press Ctrl+C to stop the server

INFO:     Uvicorn running on http://127.0.0.1:8000
```

### start-frontend.ps1

启动 Vite 前端开发服务器。

**特性：**
- 快速热模块替换 (HMR)
- 监听 127.0.0.1:5173
- 自动浏览器刷新
- 彩色输出

**输出示例：**
```
Starting QuantX Frontend Development Server...
Frontend will be available at http://127.0.0.1:5173
Press Ctrl+C to stop the server

VITE v8.0.14 ready in 279 ms
➜  Local:   http://127.0.0.1:5173/
```

### start-all.ps1

同时启动后端和前端，并自动打开浏览器。

**特性：**
- 在新 PowerShell 窗口启动两个服务
- 自动打开浏览器
- 显示启动信息和服务地址
- 依赖检查（Python、npm）
- 彩色输出

**输出示例：**
```
============================================================
          QuantX Backtest Dashboard - Start All
============================================================

Starting Backend API Server in new window...
  - http://127.0.0.1:8000

Starting Frontend Development Server in new window...
  - http://127.0.0.1:5173

============================================================
                    Servers Started!
============================================================
Backend:  http://127.0.0.1:8000
Frontend: http://127.0.0.1:5173

To stop all servers, run: .\stop-servers.ps1
============================================================

Dashboard opened in browser.
```

### stop-servers.ps1

停止所有运行的服务器。

**特性：**
- 自动检测并停止后端进程
- 自动检测并停止前端进程
- 释放占用的端口
- 彩色输出

**输出示例：**
```
Stopping QuantX Servers...

Stopping backend API server (port 8000)...
✓ Backend stopped
Stopping frontend dev server (port 5173)...
✓ Frontend stopped

Cleaning up ports...
✓ Port 8000 released
✓ Port 5173 released

All servers stopped.
```

---

## 🐛 常见问题

### 问题 1：PowerShell 执行策略限制

如果看到错误：`cannot be loaded because running scripts is disabled on this system`

**解决方案：**
```powershell
# 临时允许执行脚本（仅当前 PowerShell 会话）
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process

# 然后运行脚本
.\start-all.ps1
```

### 问题 2：端口已被占用

如果看到错误：`Address already in use`

**解决方案：**
```powershell
# 运行停止脚本释放端口
.\stop-servers.ps1

# 或手动停止
Get-Process | Where-Object { $_.ProcessName -eq "python" } | Stop-Process -Force
Get-Process | Where-Object { $_.ProcessName -eq "node" } | Stop-Process -Force
```

### 问题 3：npm 依赖问题

```powershell
# 清除 npm 缓存
npm cache clean --force

# 重新安装依赖
cd web
Remove-Item -Recurse -Force node_modules
Remove-Item package-lock.json
npm install
cd ..
```

### 问题 4：Python 依赖问题

```powershell
# 重新安装 Python 依赖
python -m pip install --upgrade -r requirements.txt
```

---

## 📝 环境变量

### 后端

```powershell
# 自定义 API 主机和端口
$env:UVICORN_HOST = "0.0.0.0"
$env:UVICORN_PORT = "8000"
```

### 前端

```powershell
# 自定义 API 基础 URL
$env:VITE_API_BASE = "http://127.0.0.1:8000"
```

---

## 🔐 生产部署

对于生产环境，不要使用这些开发脚本。改用：

```powershell
# 后端
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000

# 前端
cd web
npm run build
# 使用 nginx 或其他 web 服务器提供 dist/ 目录
```

---

## 💡 提示

- 使用 `.\start-all.ps1` 是最快的方式
- 前端会自动连接到后端 API
- 修改代码后，两个服务器都会自动重载
- 使用浏览器开发者工具（F12）调试前端
- 查看 PowerShell 终端输出以调试 API 问题
- 如果脚本无法执行，检查 PowerShell 执行策略

---

## 📚 相关文档

- [QUICK_START.md](QUICK_START.md) — 一页快速参考
- [SCRIPTS_README.md](SCRIPTS_README.md) — 详细使用指南
- [docs/web-dashboard.md](docs/web-dashboard.md) — Web 仪表板文档
- [API 文档](http://127.0.0.1:8000/docs) — Swagger UI
