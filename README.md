# tech-daily-digest · 技术情报日报

每天自动抓取 4 个高信号技术信息源 → 用 LLM 分析、摘要、重写 → 生成一份**打开就能读**的 HTML 日报。

---

## 一、它抓哪些源（以及为什么是这 4 个）

| # | 源 | 入口 | 它给你什么 |
| --- | --- | --- | --- |
| 1 | 阮一峰 · 科技爱好者周刊 | `ruanyifeng.com/blog/atom.xml` | 每周科技全扫：新工具、新框架、行业变化。中文防茧房最强 |
| 2 | Simon Willison's Weblog | `simonwillison.net/atom/everything/` | 专业工具提前渗透第一名：每天试最新 AI 工具并记录实测结果 |
| 3 | ByteByteGo | `blog.bytebytego.com/feed` | 工程必备技能科普：API、负载均衡、Docker/K8s、模型部署 |
| 4 | Import AI（Jack Clark） | `importai.substack.com/feed.xml` | AI 前沿方向扫描 + 政策视角，前 OpenAI 政策负责人执笔 |

**排序逻辑**：对你只有三件事重要 —— ① 获取信息 ② 判断未来方向 ③ 提前接触专业工具。这 4 个源各自命中其中至少 2 条。

---

## 二、快速开始

### 1. 建环境

```bash
cd D:/course/tech-daily-digest
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`：

```ini
# AI 分析（填了才会做智能摘要；不填则自动降级为抽取式摘要，流程照跑）
AI_BASE_URL=https://api.deepseek.com/v1
AI_MODEL=deepseek-chat
AI_API_KEY=sk-xxxxxxxx

# 本机代理（Clash 类默认就是 7897；不需要就留空）
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897

# 每个来源最多分析几条
MAX_ITEMS_PER_SOURCE=6
```

> `.env` 已写进 `.gitignore`，**不会**被推上 GitHub。

### 3. 跑起来

```bash
./.venv/Scripts/python.exe -m src.main          # 日常：只处理新内容
./.venv/Scripts/python.exe -m src.main --all    # 忽略去重，把当前 feed 全跑一遍
./.venv/Scripts/python.exe -m src.main --limit 3 --no-ai
```

或者直接**双击 `run_daily.bat`**（跑完自动打开日报）。

产物：`output/digest-YYYY-MM-DD.html` 和 `output/latest.html`（永远指向最新一期）。

---

## 三、目录结构

```
tech-daily-digest/
├── config/sources.json      # 四源配置（含备用入口）
├── src/
│   ├── fetch.py             # 抓取层：curl_cffi 伪装浏览器指纹 + 多入口回退
│   ├── store.py             # 去重层：SQLite 记录"已经给你看过的条目"
│   ├── analyze.py           # 分析层：调 LLM 做摘要/价值判断；无 Key 自动降级
│   ├── render.py            # 渲染层：Jinja2 套模板出 HTML
│   └── main.py              # CLI 入口，串起 5 个阶段
├── templates/digest.html.j2 # HTML 模板
├── output/                  # 生成的日报（入库，方便在线阅读）
├── state/seen.sqlite        # 去重状态（入库，换机器也能接着跑）
├── run_daily.bat            # 一键运行
└── .github/workflows/daily.yml  # 可选的云端每日自动运行
```

---

## 四、工程上真正踩过的坑（重要，别改错）

### 1. Cloudflare 会挡普通请求

`requests` 请求阮一峰 / Substack 会拿到 **403 "Just a moment..."**（JS 挑战页）。
本项目用 **`curl_cffi` 伪装 Chrome 的 TLS/JA3 指纹**解决，实测 3/4 的源直接通过。

### 2. Import AI 的 RSS 是特例

- `importai.substack.com/feed` → **403**（Cloudflare 挑战）
- `importai.substack.com/api/v1/archive` → **403**
- `importai.substack.com/feed.xml` → ✅ **200**（注意是 `.xml`！）
- `jack-clark.net/feed/`（作者原站）→ ✅ **200**（备用入口）

配置里两个入口都写了，主入口失败会自动回退。

### 3. 注册新的源时

在 `config/sources.json` 的 `sources` 数组里加一项即可，`url` 为主入口，`fallbacks` 为备用入口（按顺序尝试，第一个成功的胜出）。**顺序很重要**：把最稳的放前面。

---

## 五、每天自动跑（Windows 任务计划程序）

1. `Win + R` → 输入 `taskschd.msc` → 回车
2. 右侧「创建基本任务」→ 名称填 `技术情报日报`
3. 触发器：每天，时间设 `09:00`
4. 操作：启动程序 → 程序填
   `D:\course\tech-daily-digest\run_daily.bat`
   起始于填
   `D:\course\tech-daily-digest`
5. 完成后右键任务 → 属性 → 勾选「不管用户是否登录都要运行」

**前提**：代理软件要在跑（`.env` 里的 `HTTP_PROXY` 指向它）。如果代理没开，抓取会失败并提示。

---

## 六、推到 GitHub

### 1. 本地已初始化

仓库已在本地初始化完毕（`git init` + 首次提交）。因为 GitHub 直连被墙，**仓库已配好只对本仓库生效的代理**：

```bash
git config --local http.proxy  http://127.0.0.1:7897
git config --local https.proxy http://127.0.0.1:7897
```

### 2. 在 GitHub 上建空仓库

打开 https://github.com/new ，仓库名建议 `tech-daily-digest`，**不要**勾选 README / .gitignore / License（保持空仓库）。

### 3. 关联并推送

```bash
cd D:/course/tech-daily-digest
git branch -M main
git remote add origin https://github.com/<你的用户名>/tech-daily-digest.git
git push -u origin main
```

> 首次推送会让你输密码 —— 现在 GitHub 不支持账号密码，要用 **Personal Access Token**。
> 生成：GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → 勾 `repo` → 生成后当密码粘贴。

### 4. 让日报可以直接在线看（GitHub Pages）

> ⚠️ GitHub 新版界面已不再提供"从分支部署"的下拉框，改为 **GitHub Actions 部署**。
> 本项目已把部署步骤直接写进 `.github/workflows/daily.yml`，你只需要把 Source 设对。

仓库 → `Settings` → `Pages` → **Source 选 `GitHub Actions`**（新版界面默认就是这个，不用改）。

不需要自己建 Pages 工作流，也不需要选 "Static HTML" 模板 —— 我们自己的 workflow 里已经包含了
`configure-pages` → `upload-pages-artifact` → `deploy-pages` 三步。

**部署后的地址**（把 `<用户名>` 换成你的 GitHub 用户名）：

```
https://<用户名>.github.io/<仓库名>/          # 自动跳转到最新一期
https://<用户名>.github.io/<仓库名>/output/latest.html   # 直达最新
```

手机也能随时打开，收藏短的那个即可。

> **注意**：GitHub Pages 在免费账户下**只支持公开仓库**。如果仓库是 private，
> 要么把仓库改成 public（本项目内容全是公开的技术文章摘要，检查过无密钥泄漏），
> 要么升级 GitHub Pro，要么改用 `https://raw.githack.com/<用户名>/<仓库名>/main/output/latest.html`。

### 5. 验收清单

```
□ Settings → Secrets and variables → Actions 里有 Deepseek_Daily_Report（或 AI_API_KEY）
    workflow 两个名字都认，优先 Deepseek_Daily_Report
□ Settings → Actions → General → Workflow permissions 选了 Read and write permissions
□ Settings → Pages → Source 是 GitHub Actions
□ Actions 标签里手动 Run workflow 一次，跑出绿勾
□ 打开 https://<用户名>.github.io/<仓库名>/ 看到日报
```

第 4 步跑绿了就说明整条云端流水线通了；第 5 步只是验证网址。

### 6. 本地跑 vs 云端跑（二选一，不要同时开）

| | 云端（GitHub Actions） | 本地 |
| --- | --- | --- |
| 电脑要开机吗 | 不要 | 要 |
| 要梯子吗 | 不要（服务器在墙外） | 要 |
| 密钥要给 GitHub 吗 | 要给（加密 Secret，日志打码） | 不用 |
| 怎么触发 | 自动，每天北京时间 09:00 | 双击 `run_daily.bat` 或任务计划程序 |

**⚠️ 两边共用同一个 `state/seen.sqlite`，同时跑会造成去重混乱**（该推的没推，或重复推）。

- 选了云端 → 不要建本地任务计划程序
- 选了本地 → 把 `.github/workflows/daily.yml` 里的 `schedule:` 两行注释掉（保留 `workflow_dispatch` 以便手动跑）

---

## 七、每天怎么用（重要）

打开日报后，**不要从头读到尾**。按这个顺序：

1. **先看「今日速览」** —— 5 秒知道今天有没有值得关注的东西
2. **再看「值得深读」** —— 只有 0-3 条，这是当天信息密度最高的
3. **最后扫「全部条目」的标题** —— 只点开你感兴趣的

这样每天 10 分钟内能扫完，不会变成信息负担。

---

## 八、成本

`deepseek-chat` 处理 20 条左右的条目，**每次约几分钱到一毛钱**量级。每天跑一次，一个月成本可以忽略。
