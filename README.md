# 校园智能失物招领匹配系统 · V3.0

《人工智能技术与应用》第 3 组

用户发布失物或招领信息后，系统自动在对向信息中检索候选：先用类别、地点、时间窗做硬过滤，再用字面相似度或大模型语义排序，给出相似度与匹配理由。最终归属由**管理员人工确认**，不交给 AI 判定。

**技术栈**：Vue 3 + FastAPI + SQLite + OpenAI 兼容大模型接口

---

## 一、快速开始

### 本地运行（Windows）

1. 安装 Python 3.9+，安装时勾选 **Add Python to PATH**
2. 双击 `启动.bat`
3. 浏览器自动打开 `http://localhost:8000`

首次运行会自动装依赖、建数据库并构建前端，约 2—4 分钟；之后秒开。

> `启动.bat` 会在缺少 `frontend/dist` 时自动执行 `npm install && npm run build`，因此本机需要 **Node.js 20+**。若只打算部署到云端，本地不必装 Node。

### 预置演示数据（可选）

先启动服务，再另开一个命令行窗口：

```bash
cd backend
python seed.py
```

写入 15 条演示信息（6 组配对 + 3 条干扰项），自动产生匹配候选。可重复执行，会清空旧数据。

### 默认账号

| 角色 | 账号 | 密码 | 可用功能 |
|---|---|---|---|
| 普通用户 | `user` | `user123` | 广场浏览、发布失物/招领、查看 AI 匹配结果（只读）、申请认领 |
| 管理员 | `admin` | `admin123` | 信息管理、确认/忽略匹配、认领审核 |

登录页底部「去注册」点开可看到这两个演示账号，点击自动填入。

### 同一 WiFi 下让别人访问

启动时控制台会打印局域网地址，形如 `http://192.168.1.5:8000`，同一网络的设备直接打开即可。
若打不开，通常是 Windows 防火墙拦截，第一次弹窗时选「允许访问」。

---

## 二、云端部署

云端部署后，别人只需要一个网址，Key 也只存在服务器上，不随代码外传。

### 方式一：Railway（当前使用）

**前置条件**：仓库根目录必须有 `Dockerfile`，且只上传源码。

1. **上传代码到 GitHub**
   仓库根目录应直接是 `ai/`、`backend/`、`frontend/`、`Dockerfile`、`README.md` 等，**不要多套一层文件夹**。
   `frontend/dist/` 不需要上传，`Dockerfile` 会在服务器上自动构建前端。

2. **Railway 新建项目**
   项目 → New → GitHub Repository → 选这个仓库。Railway 会自动识别根目录的 `Dockerfile`。

3. **配置环境变量**（服务 → Variables）

   | 变量名 | 值 | 说明 |
   |---|---|---|
   | `LLM_API_KEY` | 你的大模型 Key | 不填则降级为字面匹配 |
   | `LLM_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` | 默认智谱，可换任意兼容厂商 |
   | `LLM_MODEL` | `glm-5.3-flash` | 模型名 |
   | `DB_PATH` | `/app/data/lost_found.db` | 数据库位置 |
   | `MIN_SCORE` | `0.35` | 候选最低分阈值 |

4. **挂载持久磁盘（必须）**
   服务 → Settings → Volumes → 新建，挂载路径填 `/app/data`。
   数据库和用户上传的图片都在这个目录下（图片在 `/app/data/uploads`）。**不挂的话，每次重新部署数据和图片都会清空。**

5. **首次构建约 3—6 分钟**，因为要在服务器上装前端依赖并编译。
   构建完成会得到一个 `https://xxx.up.railway.app` 地址。

> 免费实例闲置一段时间会休眠，第一次打开需要等几十秒，属正常现象。

### 方式二：Railway CLI（不经 GitHub）

```bash
npm i -g @railway/cli
railway login          # 浏览器里点一下授权
railway link           # 选择已有项目
railway up             # 把当前目录打包上传并立即构建部署
```

`railway up` 每次以本地目录为准完整覆盖，不会残留上一版文件。改完代码重跑一次即可。

### 方式三：任意支持 Docker 的平台

Zeabur、Render、云服务器等，只要平台支持 Docker 或能读到根目录的 `Dockerfile`，步骤与方式一第 3—4 步相同。

手动构建：

```bash
docker build -t lostfound:v3.0 .
docker run -d -p 8000:8000 \
  -e LLM_API_KEY=你的Key \
  -e LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4 \
  -e LLM_MODEL=glm-5.3-flash \
  -e DB_PATH=/app/data/lost_found.db \
  -v $(pwd)/data:/app/data \
  --name lostfound lostfound:v3.0
```

---

## 三、AI 配置

Key 按优先级从高到低取：系统环境变量 → `ai/.env` → 代码默认值。
**云端只能用环境变量**，因为 `ai/.env` 不进仓库，服务器上不存在这个文件。

支持任何 OpenAI 兼容接口，换厂商只改两个值：

| 厂商 | `LLM_BASE_URL` | `LLM_MODEL` 示例 |
|---|---|---|
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-5.3-flash` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` |
| 阿里百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen2.5:7b` |

### 未配置 Key 时的行为

系统照常可用：发布、浏览、筛选、认领、人工确认全部正常。匹配降级为**字面相似度**（同义词归一 + TF-IDF + 结构化加减分），结果标记 `source: lexical`，页面右上角显示黄色「字面相似匹配」。

配置成功则标记 `source: semantic`，徽标变绿。Key 错误时徽标变红并提示 `HTTP 401`。

> 做效果评价时，`lexical` 和 `semantic` 必须分开统计，不能混在一起当作「AI 效果」。

---

## 四、匹配流程

```
发布信息
   ↓
① 硬过滤：类别相同、地点相近、时间窗（默认 30 天）内、失物↔招领对向
   ↓
② 细节冲突检测：从描述中抽取判别细节（绳结、贴纸、颜色、充电功率等），
   一方肯定一方否认时判定为「细节冲突」，大幅扣分
   ↓
③ 排序：有 Key 走大模型语义精排；无 Key 走字面相似度（同义词归一 + 2-gram 兜底）
   ↓
④ 输出候选：相似度分数 + 高/中/低分级 + 可读的匹配理由
   ↓
⑤ 人工确认：管理员在匹配结果页点「确认匹配」，两条信息流转为「已确认」；点「忽略」则驳回
```

普通用户可以查看完整候选、相似度与匹配理由，但**没有确认权限**——界面显示「待管理员确认」，后端接口同步校验管理员身份。

---

## 五、目录结构

```
├── 启动.bat                  Windows 一键启动
├── start.sh                  Linux / macOS 启动
├── Dockerfile                云端构建（Node 阶段编译前端 + Python 阶段运行）
├── .dockerignore             构建时排除的文件
├── requirements.txt          根依赖（Docker 用）
├── ai/                       匹配算法（不单独启动，被后端调用）
│   ├── coarse_filter.py        第一层：硬过滤 + 字面粗排
│   ├── llm_ranker.py           第二层：大模型精排 + 降级
│   ├── main.py                 AI 模块独立入口（联调用，可选）
│   ├── test_eval.py            14 条评测用例
│   └── .env.example            配置模板（复制为 .env 使用）
├── backend/                  FastAPI 后端
│   ├── main.py                 路由 + 自动建库 + 匹配触发
│   ├── schema.sql              建表语句
│   ├── seed.py                 演示数据
│   └── requirements.txt
└── frontend/
    └── src/                  Vue 3 源码
        ├── views/              页面
        ├── components/         组件
        ├── api/                接口封装
        ├── store/              状态管理
        └── router/             路由与权限守卫
```

`frontend/dist` 不提交到仓库，由 `Dockerfile` 或 `启动.bat` 在构建时生成。

---

## 六、权限设计

| 功能 | 普通用户 | 管理员 |
|---|---|---|
| 广场浏览、筛选、搜索 | ✅ | ✅ |
| 发布失物 / 招领 | ✅ | ✅ |
| 查看 AI 匹配结果与理由 | ✅ 只读 | ✅ |
| 确认匹配 / 忽略候选 | ❌ | ✅ |
| 信息管理（删除、批量删除） | ❌ | ✅ |
| 认领审核 | ❌ | ✅ |

后端所有管理接口都校验管理员 token，普通用户直接调用返回 403。前端路由守卫同步拦截越权访问。

---

## 七、常见问题

**Q：双击 `启动.bat` 窗口一闪就没了？**
A：没装 Python，或安装时没勾 PATH。脚本会打印中文提示，按提示重装即可。

**Q：启动时提示缺少 `frontend/dist`？**
A：本机需要 Node.js 20+，脚本会自动构建。不想装 Node 就直接部署到云端，`Dockerfile` 会在服务器上构建。

**Q：页面能打开，但右上角是黄色「字面相似匹配」？**
A：没配 Key，或 Key 没生效。确认改的是 `ai/.env`（不是 `.env.example`），且 `LLM_API_KEY=` 后面直接跟 Key，没有引号和空格。改完**必须重启服务**。

**Q：云端重启后数据和图片都没了？**
A：容器文件系统是临时的。需要挂持久磁盘到 `/app/data`，并把 `DB_PATH` 指过去。

**Q：上传图片没反应？**
A：只接受 jpg / png / webp / gif / bmp，单张不超过 5MB，最多 3 张。其他类型会在选择文件时就被拦下。

**Q：想重置演示数据？**
A：重新执行 `python seed.py`，会清空并重新写入，id 从 1 开始。

---

## 八、已知限制

- 匹配只基于文本，不处理图片内容；图片仅用于人工核验
- 同义词表人工维护 12 组，表外说法靠 2-gram 兜底
- 时间窗固定 30 天（可配），跨学期记录会被硬过滤
- 大模型判定存在波动，`temperature=0` 只能降低随机性，不能保证完全可复现
- 单机 SQLite，不支持多实例并发写入
- 用户注册未开放，账号由 `schema.sql` 初始化
