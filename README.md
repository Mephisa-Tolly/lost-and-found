# 校园智能失物招领匹配系统 v3.1

> **V3.1 更新（2026-11-20）**：
> 1. **匹配结果用户可见**：广场 / 详情页点「匹配」不再被路由拦回，普通用户可以查看完整候选、相似度与匹配理由；「确认匹配 / 忽略」仅管理员可见，后端接口同步校验管理员身份，普通用户调用返回 403。
> 2. **图片真正落库**：此前发布页的 `images` 被写死为空数组，选的图从未提交。现在图片经浏览器压缩后上传，后端解码存成文件（`/api/v1/media/xxx.jpg`），详情页、广场卡片、管理端表格均可查看并点击放大。
> 3. **非图片文件禁止提交**：前端在加入列表时就校验类型与大小并移除非法文件，后端再按 data URL 的 MIME 与解码体积二次校验，伪造 pdf/exe 会被 400 拒绝。
> 4. **构建产物不再进仓库**：`frontend/dist` 加入 `.gitignore`，改由 `Dockerfile` 在镜像内构建（Node 阶段 + Python 阶段）。仓库里只保留源码，不会再出现每次改版都堆一批带哈希文件名的问题。
> 5. **隐私字段收紧**：公开列表与详情接口不再返回「私密特征」与「联系方式」，认领人无法从接口读取核验答案。
> 6. **管理端可直接查看匹配**：信息管理表格新增「图片」列与「匹配」入口，管理员也能打开帖子详情。

> **V3.0 更新（2026-11-18）**：
> 1. **登录与双角色**：新增登录页，两个演示账号 `user / user123`（普通用户）、`admin / admin123`（管理员）。登录后按角色进入不同界面，路由守卫拦截越权访问；顶部显示当前账号与角色，可退出登录。
> 2. **用户端**：只有「广场」和「信息发布（失物/招领）」。「广场」即原信息池，展示全部用户发布的帖子，默认最新在前；顶部支持**类别多选、地点多选、失物/招领、时间正倒序**四类筛选。
> 3. **管理端**：信息管理（统计总览、全量列表、单条删除、批量删除、搜索筛选）。删除会级联清理关联的匹配记录与认领申请，操作前二次确认。
> 4. **安全加固**：所有用户输入统一 HTML 转义，修复存储型 XSS；发布时间禁止选择未来；上传图片限 5MB 且仅接受图片格式。
> 5. **AI 匹配优化**：新增「细节提取与冲突判定」——从描述中抽取绳结、贴纸、充电功率等判别细节，一方肯定一方否认时判定为**细节冲突**并大幅扣分，避免「高度疑似」误导；徽标改为如实反映语义通道是否真的可用。
> 6. **移动端**：标题区竖向堆叠、筛选控件整行铺开、卡片标题完整换行，修复窄屏文字被挤压成一列的问题。

> **V2.3 更新（2026-11-17）**：移动端适配修复——窄屏（≤768px）侧边栏自动改为顶部横排导航、统计卡片改两列、弹窗与表格适配小屏、按钮与文字尺寸适配触屏；桌面端布局不受影响。

《人工智能技术与应用》第 3 组 · EXP04 / EXP05

发布丢失/招领信息后，系统自动在对向信息中检索候选，先用规则和字面相似度粗筛，
再用大模型做语义精排，给出相似度、等级和可读的匹配理由，由人工确认后完成闭环。

技术栈：Vue 3 + FastAPI + SQLite + OpenAI 兼容大模型接口（默认智谱 GLM，可换任意厂商）

---

## 一、本地运行（Windows，一键）

1. 装 Python 3.9+（安装时勾选 **Add Python to PATH**）
2. 双击 `启动.bat`
3. 浏览器自动打开 `http://localhost:8000`

首次运行会自动装依赖、建数据库，约 1—3 分钟；之后秒开。

想预置演示数据：先启动服务，再**另开一个**命令行窗口执行

```
cd backend
python seed.py
```

会写入 15 条演示数据（6 组配对 + 3 条干扰项），自动产生 12 条匹配候选，可重复执行。

### 让别人访问（同一 WiFi）

启动时控制台会打印本机局域网地址，形如 `http://192.168.1.5:8000`，同一网络的电脑/手机直接打开即可。
若打不开，通常是 Windows 防火墙拦了，第一次弹窗时选「允许访问」。

---

## 二、云端部署（推荐，给别人测试用这个）

部署在云端后，**别人只需要一个网址，不用装任何东西**，Key 也只存在服务器上，不会随代码外传。

### 路线 A：免登录 PaaS（最省事）

以 Zeabur / Render / Railway 这类平台为例，步骤基本一致：

1. 把本项目推到 GitHub（`.gitignore` 已排除 `ai/.env`、`*.db`、`frontend/dist`、`uploads/`）
   - **只需要上传源码**，不用再上传 `frontend/dist`：`Dockerfile` 会在服务器上先跑 `npm run build` 再打包，仓库里不会堆积带哈希文件名的构建产物
2. 在平台新建项目 → 选择「从 GitHub 部署」→ 选这个仓库
3. 平台会自动识别根目录的 `Dockerfile` 并构建（首次构建多 1~2 分钟，因为要装前端依赖）
4. 在平台的**环境变量**里加五项：

   | 变量名 | 值 |
   |---|---|
   | `LLM_API_KEY` | 你的大模型 Key |
   | `LLM_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` |
   | `LLM_MODEL` | `glm-5.3-flash` |
   | `DB_PATH` | `/app/data/lost_found.db` |
   | `MIN_SCORE` | `0.35` |

5. 若平台支持挂载持久磁盘（Volume），挂到 `/app/data`。数据库与上传的图片都放在这个目录下（图片在 `/app/data/uploads`），不挂也能跑，但**重新部署后数据与图片会清空**。
6. 部署完成会得到一个 `https://xxx.zeabur.app` 这样的地址，发给测试组即可。

> 免费实例闲置一段时间会休眠，第一次打开需要等几十秒，属正常现象。

### 路线 A+：连 GitHub 都不用时（Railway CLI 直传）

GitHub 打不开、或者不想再跟仓库里的历史文件纠缠时，可以把本地代码**直接推给 Railway**，全程绕开 GitHub：

```bash
npm i -g @railway/cli
railway login          # 浏览器里点一下授权
railway link           # 选择已有项目（或 railway init 新建）
railway up             # 把当前目录打包上传并立即构建部署
```

`railway up` 每次都是"以本地目录为准"的完整覆盖，不会残留上一版的文件，也不需要在平台上手动清仓库。改完代码重跑一次 `railway up` 就是最新版本。

### 路线 B：云服务器（阿里云/腾讯云学生机）

```bash
# 1. 上传代码（或 git clone）
# 2. 装依赖
pip3 install -r requirements.txt
# 3. 配置 Key（写进环境变量，不要写进代码）
export LLM_API_KEY=你的Key
export LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
export LLM_MODEL=glm-5.3-flash
# 4. 启动
python3 backend/main.py
```

访问 `http://服务器公网IP:8000`。记得在安全组放行 8000 端口。
长期运行建议用 `nohup python3 backend/main.py &` 或配置 systemd。

### 路线 C：Docker（两种环境都通用）

```bash
docker build -t lostfound:v3.0 .
docker run -d -p 8000:8000 \
  -e LLM_API_KEY=你的Key \
  -e LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4 \
  -e LLM_MODEL=glm-5.3-flash \
  -v $(pwd)/data:/app/data \
  -e DB_PATH=/app/data/lost_found.db \
  --name lostfound lostfound:v3.0
```

---

## 三、AI 配置说明

Key 有三种给法，优先级从高到低：系统环境变量 → `ai/.env` → 代码默认值。
**云端只能用环境变量**（`ai/.env` 不进仓库，上传后服务器上不存在）。

支持任何 OpenAI 兼容接口，换厂商只改两个值：

| 厂商 | LLM_BASE_URL | LLM_MODEL 示例 |
|---|---|---|
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-5.3-flash` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` |
| 阿里百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen2.5:7b` |

### 没配 Key 会怎样

系统照常能用：发布、浏览、搜索、认领、人工确认全部正常，匹配走**字面相似度**
（同义词归一 + TF-IDF + 结构化加减分），结果标记为 `source: lexical`，
页面右上角徽标显示黄色「字面相似匹配」。

配了 Key 且调用成功，结果标记为 `source: semantic`，徽标变绿。
Key 错误时徽标变红并提示 `HTTP 401`。

**注意**：`lexical` 和 `semantic` 是两种强度不同的结果，做效果评价时要分开统计，
不能混在一起当作「AI 效果」。

---

## 四、目录结构

```
lost-and-found-v3.0/
├── 启动.bat                  Windows 一键启动
├── start.sh                  Linux/macOS 启动
├── Dockerfile                云端构建
├── requirements.txt          根依赖（Docker 用）
├── ai/                       匹配算法（不单独启动，被后端调用）
│   ├── coarse_filter.py        第一层：硬过滤 + 字面粗排
│   ├── llm_ranker.py           第二层：大模型精排 + 降级
│   ├── main.py                 AI 模块独立入口（联调用，可选）
│   ├── test_eval.py            14 条评测用例
│   ├── .env.example            配置模板
│   └── .env                    本机配置（不入库）
├── backend/                  FastAPI 后端
│   ├── main.py                 路由 + 自动建库 + 匹配触发
│   ├── schema.sql              建表语句
│   ├── seed.py                 演示数据
│   └── requirements.txt
└── frontend/
    ├── dist/                 构建产物（由 Dockerfile 构建，不入库）
    └── src/                  Vue 3 源码
```

---

## 五、常见问题

**Q：双击 `启动.bat` 窗口一闪就没了？**
A：没装 Python，或装的时候没勾 PATH。脚本会打印中文提示，看提示重装即可。

**Q：页面能打开，但右上角是黄色「字面相似匹配」？**
A：没配 Key。填好后**必须重启服务**，配置只在启动时读取。

**Q：改了 Key 但徽标还是黄色？**
A：确认改的是 `ai/.env`（不是 `.env.example`），且文件里 `LLM_API_KEY=` 后面直接跟 Key，没有引号和空格。

**Q：想重置演示数据？**
A：重新执行 `python seed.py`，会清空并重新写入，id 从 1 开始。

**Q：云端重启后数据没了？**
A：容器文件系统是临时的，需要挂持久磁盘并把 `DB_PATH` 指过去（见部署章节第 5 步）。

---

## 六、已知限制

- 匹配只基于文本，不处理图片；`items.images` 字段已预留但当前不使用
- 同义词表人工维护 12 组，表外说法靠 2-gram 兜底
- 时间窗固定 30 天（可配），跨学期记录会被硬过滤
- 大模型判定存在波动，`temperature=0` 只能降低随机性，不能保证完全可复现
- 目前只有用户端，管理端（核验队列、封禁、统计）计划在 EXP05 实现
- 无账号体系，`created_by` 固定为 1
