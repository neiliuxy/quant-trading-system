# QuantX 启动指南 - 最简单的方式

## 🚀 推荐方式：在两个不同的终端中分别启动

### 终端 1 - 启动后端 API

```cmd
start-backend.bat
```

或直接运行：
```cmd
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
```

### 终端 2 - 启动前端开发服务器

```cmd
start-frontend.bat
```

或直接运行：
```cmd
cd web
npm run dev
```

---

## 📍 服务地址

启动后访问：

| 服务 | 地址 |
|------|------|
| **前端仪表板** | http://127.0.0.1:5173 |
| **后端 API** | http://127.0.0.1:8000 |
| **API 文档** | http://127.0.0.1:8000/docs |

---

## 🛑 停止服务

在任何终端按 `Ctrl+C` 停止服务

或运行：
```cmd
stop-servers.bat
```

---

## ⚙️ 首次设置

```bash
# 安装 Python 依赖
python -m pip install -r requirements.txt

# 安装前端依赖
cd web
npm install
cd ..
```

---

## 💡 说明

- **`start-backend.bat`** — 启动后端 API 服务器（端口 8000）
- **`start-frontend.bat`** — 启动前端开发服务器（端口 5173）
- **`stop-servers.bat`** — 停止所有服务器

---

## 🐛 常见问题

### 端口已被占用

运行停止脚本释放端口：
```cmd
stop-servers.bat
```

### npm 依赖问题

```bash
cd web
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
cd ..
```

---

## 📚 详细文档

- [SCRIPTS_README.md](SCRIPTS_README.md) — 详细使用指南
- [docs/web-dashboard.md](docs/web-dashboard.md) — Web 仪表板文档
