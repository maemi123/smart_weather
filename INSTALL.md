# 📦 安装部署指南

本文档将指导您完成"智慧天气"项目的安装和部署。

---

## 1. 环境要求

### 1.1 系统要求

| 项目 | 要求 |
|------|------|
| **操作系统** | Windows 10/11
| **Python** | 3.8 或更高版本（推荐 3.10+） |
| **磁盘空间** | 至少 500MB |
| **网络** | 需要访问 Open-Meteo API、DeepSeek API |

### 1.2 检查 Python 版本

打开终端（Windows: PowerShell / CMD，Mac/Linux: Terminal），输入：

```bash
python --version
# 或
python3 --version
```

如果显示版本号 ≥ 3.8，则可以继续。如果未安装 Python，请前往 [python.org](https://www.python.org/downloads/) 下载安装。

---

## 2. 安装步骤

### 步骤 1：克隆项目

```bash
# 克隆项目到本地
git clone https://github.com/maemi123/smart_weather.git

# 进入项目目录
cd smart_weather
```

> 💡 如果没有安装 Git，可以直接从 GitHub 下载 ZIP 压缩包并解压。

### 步骤 2：创建虚拟环境

虚拟环境可以隔离项目依赖，避免与其他项目冲突。

```bash
# 创建虚拟环境
python -m venv .venv
```

### 步骤 3：激活虚拟环境

**Windows (PowerShell):**
```powershell
.venv\Scripts\activate
```

**Windows (CMD):**
```cmd
.venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

> ✅ 激活成功后，终端前面会显示 `(.venv)` 标识。

### 步骤 4：安装依赖

```bash
# 升级 pip（推荐）
python -m pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt
```

安装过程可能需要几分钟，请耐心等待。

### 步骤 5：配置 API 密钥（可选）

本项目使用 DeepSeek API 提供 AI 农事顾问功能。如果不配置，AI 功能将不可用，但其他功能正常。

#### 5.1 获取 DeepSeek API 密钥

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 注册/登录账号
3. 进入「API Keys」页面
4. 点击「创建 API Key」

#### 5.2 配置密钥

在项目根目录创建 `.env` 文件：

**Windows (PowerShell):**
```powershell
# 创建 .env 文件
New-Item -Name ".env" -ItemType "file"

# 写入密钥（替换为你的实际密钥）
Set-Content -Path ".env" -Value 'DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx'
可能还有些地方秘钥配置没覆盖到，需要手动写入，在ide中使用快捷键shift+ctrl+F，搜索api_key，把不是“api_key = os.getenv······”的地方改为“api_key = “你的秘钥””
```

**macOS / Linux:**
```bash
# 创建并写入 .env 文件
echo "DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx" > .env
```

> ⚠️ **注意**：请将 `sk-xxxxxxxxxxxxxxxx` 替换为你实际的 API 密钥。

---

## 3. 运行项目

### 3.1 启动服务

确保虚拟环境已激活（终端显示 `(.venv)`），然后运行：

```bash
python app.py
```

### 3.2 访问应用

启动成功后，终端会显示：

```
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.x.x:5000
```

打开浏览器，访问 **http://127.0.0.1:5000** 即可使用。

### 3.3 停止服务

在终端按 `Ctrl + C` 即可停止服务。

---

## 4. 验证安装成功

### 4.1 检查首页

访问 http://127.0.0.1:5000，应该能看到项目首页，显示各模块入口。

### 4.2 检查核心功能

| 模块 | 访问地址 | 验证方法 |
|------|----------|----------|
| 多模式预报 | `/advanced-forecast` | 能看到72小时预报图表 |
| 探空分析 | `/upperair` | 能选择日期并显示探空图 |
| 农业气象 | `/agro-dashboard` | 能看到5种作物信息 |
| 历史气候 | `/history` | 能看到历史气温趋势图 |

### 4.3 检查 AI 功能（已配置密钥）

在农业气象模块，点击任意作物的「AI建议」按钮，如果能返回农事建议，说明 AI 功能正常。

---

## 5. 常见问题解决

### 5.1 网络问题：API 访问失败

**症状**：页面显示"获取数据失败"或长时间加载。

**解决方案**：
1. 检查网络连接是否正常
2. 确认能访问 https://api.open-meteo.com
3. 如果在国内，可能需要配置代理：
   ```bash
   # 设置代理（临时）
   set HTTP_PROXY=http://127.0.0.1:7890
   set HTTPS_PROXY=http://127.0.0.1:7890
   ```

### 5.2 依赖安装失败

**症状**：`pip install` 报错，特别是 `cfgrib` 相关错误。

**解决方案**：

`cfgrib` 依赖 `eccodes` 库，安装较为复杂：

**Windows:**
```bash
# 使用 conda 安装（推荐）
conda install -c conda-forge cfgrib

# 或跳过 cfgrib（不影响核心功能）
pip install flask pandas numpy matplotlib plotly requests xarray schedule tqdm openmeteo_requests requests_cache retry_requests
```

**macOS:**
```bash
brew install eccodes
pip install cfgrib
```

**Linux (Ubuntu):**
```bash
sudo apt-get install libeccodes-dev
pip install cfgrib
```

### 5.3 DeepSeek API 密钥问题

**症状**：AI 功能返回"未配置 API 密钥"或调用失败。

**解决方案**：
1. 确认 `.env` 文件在项目根目录
2. 确认密钥格式正确（以 `sk-` 开头）
3. 确认密钥有效且有余额
4. 重启应用使配置生效

### 5.4 端口被占用

**症状**：启动时报错 `Address already in use`。

**解决方案**：

**Windows:**
```powershell
# 查找占用 5000 端口的进程
netstat -ano | findstr :5000

# 结束进程（替换 PID）
taskkill /PID <进程ID> /F
```

**macOS / Linux:**
```bash
# 查找并结束占用端口的进程
lsof -i :5000
kill -9 <PID>
```

或修改 `app.py` 使用其他端口：
```python
app.run(host='0.0.0.0', port=5001, debug=True)
```

### 5.5 Windows 编码问题

**症状**：中文显示乱码或报错 `UnicodeDecodeError`。

**解决方案**：
1. 确保终端编码为 UTF-8：
   ```powershell
   chcp 65001
   ```
2. 或在 `app.py` 开头添加：
   ```python
   import sys
   sys.stdout.reconfigure(encoding='utf-8')
   ```

### 5.6 虚拟环境激活失败

**症状**：Windows PowerShell 报错"无法加载文件，因为在此系统上禁止运行脚本"。

**解决方案**：
```powershell
# 临时允许运行脚本
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# 然后重新激活
.venv\Scripts\activate
```

---

## 6. 目录结构

安装完成后的项目结构：

```
smart_weather/
├── .venv/                      # 虚拟环境（安装后生成）
├── .env                        # API 密钥配置（需手动创建）
├── app.py                      # 主程序入口
├── requirements.txt            # 依赖列表
├── templates/                  # HTML 模板
├── static/                     # 静态资源
├── models/                     # ML 模型文件
├── data/                       # 数据存储
└── ...
```

---

## 7. 获取帮助

如果遇到其他问题：

1. 📖 查看 [README.md](README.md) 了解项目详情
2. 🐛 在 GitHub 提交 [Issue](https://github.com/maemi123/smart_weather/issues)
4. 📧 联系作者：1021389463@qq.com

---

祝您使用愉快！ 🎉
