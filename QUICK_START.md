# QuantX 快速启动指南

## 🚀 一键启动（推荐）

### Windows
```cmd
start-all.bat
```

### macOS / Linux
```bash
chmod +x start-all.sh
./start-all.sh
```

**这会自动：**
- ✅ 启动后端 API（http://127.0.0.1:8000）
- ✅ 启动前端开发服务器（http://127.0.0.1:5173）
- ✅ 打开浏览器访问仪表板

---

## 📋 分别启动

### 启动后端

**Windows:**
```cmd
start-backend.bat
```

**macOS/Linux:**
```bash
chmod +x start-backend.sh
./start-backend.sh
```

### 启动前端

**Windows:**
```cmd
start-frontend.bat
```

**macOS/Linux:**
```bash
chmod +x start-frontend.sh
./start-frontend.sh
```

---

## 🛑 停止服务

### Windows
```cmd
stop-servers.bat
```

### macOS/Linux
```bash
chmod +x stop-servers.sh
./stop-servers.sh
```

或在终端按 `Ctrl+C` 手动停止

---

## 📍 服务地址

| 服务 | 地址 |
|------|------|
| 前端仪表板 | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8000 |
| API 文档 | http://127.0.0.1:8000/docs |

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

## 🐛 常见问题

### 端口已被占用

运行停止脚本释放端口：

**Windows:**
```cmd
stop-servers.bat
```

**macOS/Linux:**
```bash
./stop-servers.sh
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

查看 [SCRIPTS_README.md](SCRIPTS_README.md) 了解更多信息。
