# Label Studio (改造版)

基于 [HumanSignal/label-studio](https://github.com/HumanSignal/label-studio) 的二次开发版本，在原有数据标注功能基础上增加了 **超级管理员（Superuser）权限体系**、**多组织管理能力** 和 **YOLO 模型训练集成**。

---

## 改造内容

### 1. 权限体系改造：超级管理员（Superuser）

原版 Label Studio 中所有已登录用户权限一致，任何用户都可以创建组织。改造后引入了 **Superuser** 角色，实现分级权限控制：

| 操作 | Superuser | 普通用户 |
|------|-----------|----------|
| 创建组织 | ✅ | ❌ |
| 查看所有组织 | ✅ | ❌（仅可见自己所属组织） |
| 删除组织 | ✅（仅空组织） | ❌ |
| 查看所有用户 | ✅ | ❌（仅可见本组织成员） |
| 将用户添加到组织 | ✅ | ❌ |
| 将用户从组织移除 | ✅ | ❌ |
| 修改用户的活跃组织 | ✅ | ❌ |

**后端实现：**

- `core/permissions.py` — 新增 `is_superuser` 权限检查函数，将 `organizations_create` 权限覆盖为仅 Superuser 可执行，其余权限保持 `is_authenticated`
- `users/api.py` — Superuser 的 `get_queryset` 返回 `User.objects.all()`，而非仅本组织用户；新增三个 Superuser 专属 API
- `users/serializers.py` — Superuser 可见非本组织成员（不标记为已删除）；新增 `is_superuser` 字段到用户序列化输出

### 2. 新增 Superuser 专属 API

#### 组织管理 API

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/organizations/all` | GET | 获取所有组织列表（含成员数） |
| `/api/organizations/<pk>/delete` | DELETE | 删除空组织（有成员时拒绝） |
| `/api/organizations/user/<pk>/active-organization` | PATCH | 修改用户的活跃组织 |

#### 用户-组织管理 API

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/users/<pk>/organizations/` | GET | 查看用户所属的所有组织 |
| `/api/users/<pk>/organizations/add/` | POST | 将用户添加到指定组织 |
| `/api/users/<pk>/organizations/<org_id>/` | DELETE | 将用户从指定组织移除 |

### 3. 前端改造

#### 新增"组织列表"页面（OrganizationListPage）

- Superuser 可浏览所有组织及其成员数，可创建新组织，可删除无成员的组织
- 普通用户仅可见自己的组织
- 选中组织后右侧展示该组织成员列表

#### 新增"People"页面（PeoplePage）

- 仅 Superuser 可访问（菜单栏中仅 Superuser 可见）
- 全局用户列表（带搜索、分页）
- 选中用户后右侧面板显示：
  - 用户所属组织列表（标记活跃组织）
  - 修改用户活跃组织的下拉选择
  - 将用户添加到新组织 / 从组织移除的操作

#### 新增"创建组织"对话框（CreateOrganizationModal）

- 仅 Superuser 可通过组织列表页触发
- 输入组织名称即可创建

#### 导航栏改造（Menubar）

- 新增 "People" 菜单项，仅 Superuser 可见
- 原有 "Organization" 菜单项改为显示组织列表而非成员列表

### 4. Bug 修复与健壮性增强

多处原版代码依赖 `organization.created_by` 关系访问，当 `created_by_id` 为空时会产生异常。改造后统一添加了安全检查：

- `organizations/models.py` — `is_owner` 判断改用 `created_by_id` 而非 `created_by.id`，避免无创建者时的 `NoneType` 错误
- `core/feature_flags/utils.py` — 安全获取 `created_by.email`
- `data_export/mixins.py` / `data_export/models.py` — 导出功能中 `access_token` 获取增加异常保护
- `jwt_auth/models.py` — JWT 权限判断改用 `created_by_id`
- `organizations/serializers.py` — `OrganizationIdSerializer` 新增 `member_count` 字段

### 5. 组织删除功能完善

`organizations/functions.py` 中的 `destroy_organization` 函数从仅删除项目扩展为完整清理：

- 删除组织成员（OrganizationMember）
- 删除项目（Project）
- 删除转换格式（ConvertedFormat）
- 删除标签（Label / LabelLink）
- 删除 Webhook
- 删除 ML 相关对象（ModelInterface / ThirdPartyModelVersion / ModelRun / ModelProviderConnection）
- 删除会话策略（SessionTimeoutPolicy）
- 删除 SAML / JWT 配置
- 置空指向该组织的用户的 `active_organization`
- 最终删除组织本身

### 6. YOLO 模型训练集成

集成 `cv-ultralytics` 训练引擎，在标注平台内直接训练 YOLO 模型：

- **入口**：Projects 列表页 **Train** → `/projects/train`（全局训练，不挂在单个项目内）
- **多项目训练集**：可勾选多个项目合并导出后一起训练（各类别须与配置 `classes` 一致）
- **任务驱动**：每次启动产生一条训练任务，进度 / 日志 / 报错 / 模型下载均在任务详情中查看
- **配置管理**：独立「配置管理」页，支持完整 YOLO 超参；启动时可选择 YOLO 版本（v5/v8/v9/v10）与尺寸档位（任务类型由配置自动带出）
- **自动数据流转**：导出 YOLO 格式 → 划分数据集 → 生成 `data.yaml` → 训练
- **数据划分**：与 `cv-ultralytics` 原仓库一致 — **训练集 80% / 验证集 15% / 测试集 5%**
- **预训练权重**：本地 `cv-ultralytics/.../models/` 有对应 `.pt` 则直接用，否则走国内镜像竞速下载
- **产物**：可下载 `best.pt` / `last.pt`，并展示 F1 等训练曲线（若生成）
- **训练调度**：标注服导出后入队 Redis `training` 队列；GPU 机上的 RQ Worker 执行训练（也可单机同 compose 跑 `training-worker`）
- **GPU 支持**：`training-worker` 服务透传 NVIDIA GPU（标注服 `app` 无需 GPU）

支持的训练任务类型：
- `obb`：旋转边界框检测（Oriented Bounding Box）
- `detect`：标准目标检测
- `cls`：图像分类（需 Choices 标注）
- `seg`：实例分割（需 PolygonLabels）

---

## 如何启动

下面按场景说明：**文件怎么放**、**本地开发怎么跑**、**双机要改什么**。

### 0. 三种用法对照（先选一种）

| 场景 | 机器 | 数据怎么到训练进程 | 你要改/设的 |
|------|------|-------------------|-------------|
| **本地开发** | 你自己电脑 | 本机目录直读 | `TRAINING_EXECUTOR=local`（最简单） |
| **单机 Docker** | 一台有 GPU 的机 | compose 同机挂 `mydata` + `cv-ultralytics` | 基本不用改，`docker compose up` |
| **双机（标注 + GPU）** | A 标注、B 训练 | **SSH/SCP** 拉包/回传（不搞共享盘） | A/B 各一份仓库；B 配 SSH + DB/Redis 地址 |

业务使用始终一样：浏览器打开标注服 → Projects → **Train**。

---

### 1. 文件怎么分配

#### 仓库里始终要有的

```text
label-studio/                 ← git clone 下来的项目根
├── label_studio/             ← 后端（两边都要）
├── web/                      ← 前端源码（改 UI 才需要）
├── cv-ultralytics/           ← 训练引擎（有 GPU 训练的机器必须有）
├── docker-compose.yml        ← 标注服 / 单机全栈
├── docker-compose.training.yml  ← 仅训练服 Worker
├── docker-compose.dev.yml    ← 本地/开发挂载代码
└── mydata/                   ← 运行后产生（标注服数据，勿提交）
```

#### 本地开发 / 单机 Docker（一份目录即可）

```text
/你的路径/label-studio/
├── mydata/                   ← 上传、导出、训练回传的 zip/pt
│   └── media/training_xfer/  ← SSH 模式下的导出包与回传模型
├── cv-ultralytics/           ← 权重、runs、trained_models
├── postgres-data/            ← 仅 Docker
└── redis-data/               ← 仅 Docker
```

单机时 app 与 `training-worker` **共用**上面这些目录，路径不用对两台机器。

#### 双机（A 标注服 + B GPU 训练服，SSH，无共享盘）

**标注服 A**（放网页数据，可无 GPU、可不放完整训练权重）：

```text
/opt/label-studio/            ← 建议绝对路径，后面填进 TRAINING_SSH_REMOTE_DATA
├── label_studio/ …           ← 代码
├── docker-compose.yml
├── mydata/                   ← 必须；导出 zip、回传 best.pt 都落这里
│   └── media/training_xfer/job_<id>/
│       ├── export.zip        ← 启动训练后由 A 打好
│       └── artifacts/        ← B scp 回来的 best.pt 等
├── postgres-data/
├── redis-data/
└── cv-ultralytics/           ← 可选（A 不训练可很瘦）
```

**训练服 B**（只跑 Worker + GPU）：

```text
/opt/label-studio/            ← 同一份代码仓库（或同镜像）
├── docker-compose.training.yml
├── cv-ultralytics/           ← 必须；本机训练 runs/权重（不必和 A 同步）
├── ssh/
│   └── id_rsa                ← 私钥，chmod 600；公钥已放到 A 的 authorized_keys
└── （不必有 mydata；数据靠 scp 临时拉取）
```

| 东西 | 放哪 | 说明 |
|------|------|------|
| 用户上传 / 标注数据 | **仅 A** `mydata/` | 浏览器只打 A |
| 导出 zip | **A** `mydata/media/training_xfer/` | B 用 scp 拉 |
| `best.pt` 下载用 | **最终在 A** 同目录 `artifacts/` | B 训完 scp 回去 |
| YOLO 训练过程文件 | **B** `cv-ultralytics/` | runs 可只留在 B |
| Postgres / Redis | **A**（或独立机） | B 只连过去，不另起库 |
| SSH 私钥 | **仅 B** `ssh/id_rsa` | 不要提交 git |

`TRAINING_SSH_REMOTE_DATA` = A 宿主机上 **mydata 的绝对路径**，例如 `/opt/label-studio/mydata`（不要填容器内路径）。

---

### 2. 本地开发模式（推荐调试时用）

目标：改代码立刻生效；训练可用本机线程，不必先搭 Redis/双机。

> 需要 **Python 3.10+**、**Node 22+**、**GCC 9.3+**。CentOS 7 请用 Docker。

#### 2.1 你要改什么（环境变量）

本地**最少**这样（写进 shell 或项目根 `.env`，按你们 `make run-dev` 是否自动加载为准）：

```bash
# 必改/建议
export DJANGO_DB=sqlite
export DJANGO_SETTINGS_MODULE=core.settings.label_studio
export TRAINING_EXECUTOR=local          # ← 关键：不入队，本机线程直接训
export TRAINING_DATA_MODE=shared        # 本地同盘，不要设 ssh
# 可选
export CV_ULTRA_PATH=/你的路径/label-studio/cv-ultralytics
export DEBUG=1
```

若要用 RQ（本机 Redis + Worker）而不是 `local`：

```bash
export TRAINING_EXECUTOR=rq
export TRAINING_DATA_MODE=shared
export REDIS_HOST=127.0.0.1
export REDIS_PORT=6379
# 另开终端：redis-server
# 再开终端：poetry run python label_studio/manage.py rqworker training
```

本地开发**不要**设 `TRAINING_DATA_MODE=ssh`（没有第二台机 scp）。

#### 2.2 后端安装与启动

`poetry` **不含** `torch`/`ultralytics`，须额外 pip：

```bash
pip install poetry
poetry install

# GPU
pip install torch torchvision --index-url https://mirror.sjtu.edu.cn/pytorch-wheels/cu118
pip install ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple
# 或 CPU：pip install torch torchvision ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple

DJANGO_DB=sqlite DJANGO_SETTINGS_MODULE=core.settings.label_studio \
  poetry run python label_studio/manage.py migrate
DJANGO_DB=sqlite DJANGO_SETTINGS_MODULE=core.settings.label_studio \
  poetry run python label_studio/manage.py createsuperuser

# 本机线程训练（最省事）
TRAINING_EXECUTOR=local TRAINING_DATA_MODE=shared make run-dev
# 或：
# TRAINING_EXECUTOR=local DJANGO_DB=sqlite DJANGO_SETTINGS_MODULE=core.settings.label_studio \
#   poetry run python label_studio/manage.py runserver 0.0.0.0:8080
```

Makefile 常用：

```bash
make env-dev-setup   # 生成 .env
make migrate-dev
make run-dev
```

#### 2.3 前端

```bash
cd web && yarn install
cd web && yarn run build          # 改完 Train 页等必须 build，或
cd web && yarn run dev            # HMR；后端需在 8080
```

#### 2.4 Docker 开发挂载（可选）

代码挂进容器、改 Python 不用重建镜像：

```bash
make docker-dev-setup
# 默认 TRAINING_DATA_MODE=shared；单机调试可：
# export TRAINING_EXECUTOR=local
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

---

### 3. 单机 Docker（生产形态、一台有 GPU）

文件：仓库旁 `./mydata`、`./cv-ultralytics` 即可，**一般不用改环境变量**。

```bash
docker compose up --build -d
docker compose run app python3 /label-studio/label_studio/manage.py migrate
docker compose run app python3 /label-studio/label_studio/manage.py createsuperuser
```

访问 `http://localhost:8080`。会起 nginx、app、db、redis、`training-worker`（GPU）。

| 目录 | 作用 |
|------|------|
| `./mydata` | 上传、导出临时目录 |
| `./postgres-data` | 库 |
| `./redis-data` | 训练队列 |
| `./cv-ultralytics` | 训练引擎与权重 |

- 镜像已含 torch（CUDA 11.8）+ ultralytics  
- 宿主机需 NVIDIA 驱动 + [Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)  
- 无 Worker / 无 Redis 时入队失败会回退本机线程；调试可 `TRAINING_EXECUTOR=local`

---

### 4. 双机部署（标注服 A + 训练服 B，SSH）

```text
浏览器 → A:8080 (nginx+app+db+redis) → 入队 Redis
GPU 机 B (rqworker) --scp 拉 export.zip→ 训练 --scp 回 best.pt→ A
```

#### 4.1 使用前要改什么

**标注服 A**（`.env` 或 export）：

```bash
TRAINING_EXECUTOR=rq
TRAINING_DATA_MODE=ssh          # ← 启动训练时打 zip，供 B 拉取
# 不要起 training-worker
```

并把 **Postgres 5432、Redis 6379** 暴露给 B（compose 给 `db`/`redis` 加 `ports`，或独立部署）。  
训练服公钥写入 A：`~/.ssh/authorized_keys`，且能读 A 的 `mydata`。

**训练服 B**：

```bash
POSTGRE_HOST=192.168.1.10       # A 的库
REDIS_HOST=192.168.1.10
TRAINING_DATA_MODE=ssh
TRAINING_SSH_HOST=192.168.1.10  # A 的 SSH
TRAINING_SSH_USER=root
TRAINING_SSH_PORT=22
TRAINING_SSH_KEY=/ssh/id_rsa
TRAINING_SSH_REMOTE_DATA=/opt/label-studio/mydata   # ← A 宿主机 mydata 绝对路径
TRAINING_ANNOTATION_DATA_DIR=/label-studio/data     # A 容器内路径，一般不用改
```

#### 4.2 启动命令

**A：**

```bash
cd /opt/label-studio
export TRAINING_DATA_MODE=ssh
docker compose up -d --build nginx app db redis
docker compose run app python3 /label-studio/label_studio/manage.py migrate
```

**B：**

```bash
cd /opt/label-studio
mkdir -p ssh && chmod 700 ssh
# 放入私钥 ./ssh/id_rsa && chmod 600 ./ssh/id_rsa

export POSTGRE_HOST=192.168.1.10
export REDIS_HOST=192.168.1.10
export TRAINING_DATA_MODE=ssh
export TRAINING_SSH_HOST=192.168.1.10
export TRAINING_SSH_USER=root
export TRAINING_SSH_KEY=/ssh/id_rsa
export TRAINING_SSH_REMOTE_DATA=/opt/label-studio/mydata

docker compose -f docker-compose.training.yml up -d --build
```

改过 Dockerfile（含 `openssh-client`）后 B 需重新 `--build`。

#### 4.3 SSH 路径对照

| 位置 | 路径 |
|------|------|
| A 宿主机导出包 | `{TRAINING_SSH_REMOTE_DATA}/media/training_xfer/job_<id>/export.zip` |
| A 容器内（网页下载） | `/label-studio/data/media/training_xfer/job_<id>/artifacts/best.pt` |
| B | `./cv-ultralytics`（本地训练，可不与 A 同步） |

#### 4.4 环境变量一览

| 变量 | 默认 | 谁要设 | 说明 |
|------|------|--------|------|
| `TRAINING_EXECUTOR` | `rq` | 本地调试改 `local` | `rq` 入队；`local` 本机线程 |
| `TRAINING_QUEUE` | `training` | 一般不改 | RQ 队列名 |
| `TRAINING_DATA_MODE` | `shared` | 双机改 **`ssh`** | `shared` / `ssh` / `http` |
| `TRAINING_SSH_HOST` | 空 | **B** | 标注服 SSH |
| `TRAINING_SSH_USER` | `root` | B | SSH 用户 |
| `TRAINING_SSH_PORT` | `22` | B | 端口 |
| `TRAINING_SSH_KEY` | 空 | **B** | 容器内私钥，如 `/ssh/id_rsa` |
| `TRAINING_SSH_REMOTE_DATA` | 空 | **B** | A 宿主机 `mydata` 绝对路径 |
| `TRAINING_ANNOTATION_DATA_DIR` | `/label-studio/data` | B | A 容器数据根（写 DB） |
| `REDIS_HOST` / `PORT` | localhost | 双机 B 填 A | 共用队列 |
| `POSTGRE_HOST` 等 | — | 双机 B 填 A | 共用库 |
| `CV_ULTRA_PATH` | 仓库内路径 | 有训练的机器 | 训练引擎根目录 |

---

### 5. 日常使用（网页）

与部署方式无关，只访问**标注服**：

1. 登录 → Projects → **Train**
2. 选配置、项目、YOLO 版本/尺寸 → 启动  
3. 任务里看日志 / 停止 / 下载 `best.pt`、`last.pt`

| 现象 | 先查 |
|------|------|
| 任务一直不动 | B 的 worker 没起，或 Redis 地址错 |
| 失败「导出目录不可读」/ scp 失败 | `TRAINING_SSH_*`、A 上 `mydata` 路径、SSH 免密 |
| 训完下不了模型 | 回传 scp 失败；看 B 日志 |
| 本地想省事 | `TRAINING_EXECUTOR=local` |

---

### 6. Docker 单容器（极简）

```bash
docker build -t label-studio:latest .
docker run -it -p 8080:8080 \
  -v $(pwd)/mydata:/label-studio/data \
  -v $(pwd)/cv-ultralytics:/label-studio/cv-ultralytics \
  --gpus all \
  label-studio:latest
```

此时建议容器内 `TRAINING_EXECUTOR=local`（没有单独 worker 时）。

---

## 更新项目

当仓库有新代码推送后，按以下步骤更新：

```bash
# 1. 拉取最新代码
git pull

# 2. Docker Compose 部署：重新构建并启动（前端变更会在镜像构建时打包）
docker compose up --build

# 3. 运行数据库迁移（training 等新表/字段变更时必须执行）
docker compose run app python3 /label-studio/label_studio/manage.py migrate
```

**本地开发 / 非 Docker 更新：**

```bash
# 1. 拉取最新代码
git pull

# 2. 更新 Python 依赖（如果 pyproject.toml 有变化）
poetry install
# 若训练依赖有变，再确认 torch / ultralytics：
# pip install torch torchvision --index-url https://mirror.sjtu.edu.cn/pytorch-wheels/cu118
# pip install ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 更新并构建前端（TrainingPage / ApiConfig 等变更后必须 build）
cd web && yarn install && yarn run build && cd ..

# 4. 运行数据库迁移
poetry run python label_studio/manage.py migrate

# 5. 重启后端服务
make run-dev
```

> **注意**：每次更新后务必执行迁移；有前端改动时务必 `yarn build`，否则训练页/配置保存等新功能不会生效。

---

## 生产打包 / 发布

推荐把 **Docker 镜像** 作为生产环境交付物。这个仓库根目录下的 `Dockerfile` 已经包含前端生产构建、Python 依赖安装、`collectstatic` 和最终运行镜像封装，因此生产打包命令直接使用：

```bash
docker build -t <registry>/label-studio:<tag> .
```

例如：

```bash
docker build -t registry.example.com/label-studio:2026.05.06 .
docker push registry.example.com/label-studio:2026.05.06
```

如果只是想单独验证构建产物，也可以使用下面两个子命令：

```bash
# 仅构建前端生产包
make frontend-build

# 仅构建 Python 分发包（wheel / sdist）
poetry build
```

---

## 创建 Superuser

首次部署后需通过 Django 管理命令创建 Superuser：

```bash
# Docker Compose 环境
docker compose run app python3 /label-studio/label_studio/manage.py createsuperuser

# 本地开发环境
poetry run python label_studio/manage.py createsuperuser
```

创建的 Superuser 即可使用上述所有管理功能。

---

## 新增 API 快速参考

### 获取所有组织

```bash
curl -H "Authorization: Token <superuser_token>" \
  http://localhost:8080/api/organizations/all
```

### 创建组织

```bash
curl -X POST -H "Authorization: Token <superuser_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "New Org"}' \
  http://localhost:8080/api/organizations
```

### 删除空组织

```bash
curl -X DELETE -H "Authorization: Token <superuser_token>" \
  http://localhost:8080/api/organizations/1/delete
```

### 查看用户所属组织

```bash
curl -H "Authorization: Token <superuser_token>" \
  http://localhost:8080/api/users/3/organizations/
```

### 将用户添加到组织

```bash
curl -X POST -H "Authorization: Token <superuser_token>" \
  -H "Content-Type: application/json" \
  -d '{"organization_id": 2}' \
  http://localhost:8080/api/users/3/organizations/add/
```

### 将用户从组织移除

```bash
curl -X DELETE -H "Authorization: Token <superuser_token>" \
  http://localhost:8080/api/users/3/organizations/2/
```

### 修改用户活跃组织

```bash
curl -X PATCH -H "Authorization: Token <superuser_token>" \
  -H "Content-Type: application/json" \
  -d '{"active_organization": 2}' \
  http://localhost:8080/api/organizations/user/3/active-organization
```

### 获取训练模型配置列表

```bash
curl -H "Authorization: Token <token>" \
  http://localhost:8080/api/train/configs
```

### 查询可选预训练权重（按任务类型 / YOLO 版本）

```bash
curl -H "Authorization: Token <token>" \
  "http://localhost:8080/api/train/weights?task_type=obb&version=8"
```

### 启动训练（多项目）

```bash
curl -X POST -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "config_name": "tree-obb",
    "project_ids": [1, 2],
    "yolo_version": "8",
    "yolo_scale": "x",
    "train_params": {"epochs": 1000, "batch": 16}
  }' \
  http://localhost:8080/api/train
```

### 训练任务列表 / 详情

```bash
curl -H "Authorization: Token <token>" \
  http://localhost:8080/api/train/jobs

curl -H "Authorization: Token <token>" \
  http://localhost:8080/api/train/jobs/1
```

---

## 项目结构

```
label-studio/
├── cv-ultralytics/                # ✨ YOLO 训练引擎（仅保留平台用到的子集）
│   ├── datasets_process/utils/group_img.py  # ✨ 数据集划分
│   └── ultralytics/               # YOLO 框架源码
├── label_studio/                  # Django 后端
│   ├── core/
│   │   ├── permissions.py         # ✏️ 权限体系改造（Superuser 权限）
│   │   └── feature_flags/utils.py # ✏️ 安全修复
│   ├── organizations/
│   │   ├── api.py                 # ✏️ 新增 3 个 Superuser API
│   │   ├── urls.py                # ✏️ 新增路由
│   │   ├── serializers.py         # ✏️ 新增 member_count 字段
│   │   ├── models.py              # ✏️ is_owner 修复
│   │   ├── functions.py           # ✏️ destroy_organization 完整清理
│   │   └── views.py               # ✏️ 使用 react_page.html
│   │   └── templates/             # ✨ 新增 react_page.html
│   ├── users/
│   │   ├── api.py                 # ✏️ 新增 3 个 Superuser API + queryset 扩展
│   │   ├── urls.py                # ✏️ 新增路由
│   │   └── serializers.py         # ✏️ is_superuser 字段 + Superuser 可见性
│   ├── data_export/
│   │   ├── mixins.py              # ✏️ access_token 安全获取
│   │   ├── models.py              # ✏️ access_token 安全获取
│   ├── jwt_auth/models.py         # ✏️ created_by_id 修复
│   ├── training/                  # ✨ 训练模块
│   │   ├── api.py                 # ✨ 训练 API（导出后 RQ 入队 / 本机回退）
│   │   ├── rq_jobs.py             # ✨ RQ Worker 入口（build_dataset + run_training）
│   │   ├── jobs.py                # ✨ rq_jobs 别名（分机方案）
│   │   ├── transfer.py            # ✨ 共享盘 / 内网拉包与产物回传
│   │   ├── paths.py               # ✨ 共享盘路径约定（DATA_ROOT / CV_ULTRA）
│   │   ├── models.py              # ✨ 训练任务、模型配置、训练日志、训练模型
│   │   ├── tasks.py               # ✨ 数据集划分 + YOLO 训练执行
│   │   ├── weights.py             # ✨ 预训练权重命名 / 国内镜像下载
│   │   ├── urls.py                # ✨ 训练模块路由
│   │   └── migrations/            # ✨ 数据库迁移（0001–0006）
│   └── ...
├── web/                            # React 前端
│   ├── apps/labelstudio/src/
│   │   ├── components/Menubar/    # ✏️ 新增 People 菜单项（Superuser 限定）
│   │   ├── config/ApiConfig.js    # ✏️ 新增 API 路由配置
│   │   ├── pages/
│   │   │   ├── Organization/
│   │   │   │   ├── OrganizationListPage/  # ✨ 新增组织列表页
│   │   │   │   └── PeoplePage/
│   │   │   │       ├── CreateOrganizationModal.tsx  # ✨ 新增创建组织对话框
│   │   │   │       ├── PeopleListTable.jsx  # ✨ 新增全局用户列表
│   │   │   │       ├── SelectedUserPanel.jsx # ✨ 新增用户组织管理面板
│   │   │   │       ├── PeopleList.jsx       # ✏️ 改造为支持 organizationId
│   │   │   │       └── PeoplePage.jsx       # ✏️ 改造为 Superuser 限定
│   │   │   └── index.js           # ✏️ 注册 PeoplePage、TrainingPage 路由
│   │   │   └── TrainingPage/      # ✨ 训练页面
│   │   │       ├── TrainingPage.jsx # ✨ 训练页面组件
│   │   │       └── TrainingPage.scss # ✨ 训练页面样式
│   ├── libs/core/src/types/user.ts # ✏️ 新增 is_superuser 类型
│   └── ...
├── docker-compose.yml              # app + redis + training-worker（GPU）
├── docker-compose.training.yml     # ✨ 仅 GPU 训练服 RQ Worker
├── Dockerfile                      # 生产镜像构建（已包含 YOLO 训练依赖）
├── Dockerfile.development          # 开发镜像构建
├── Makefile                        # 开发快捷命令
├── pyproject.toml                  # Python 项目配置（训练用 torch/ultralytics 需额外 pip）
└── ...
```

标注说明：✏️ = 修改已有文件，✨ = 新增文件

---

## 与原版的差异总结

| 维度 | 原版 Label Studio | 本改造版 |
|------|-------------------|----------|
| 组织创建 | 任何用户可创建 | 仅 Superuser 可创建 |
| 组织删除 | 不支持 | Superuser 可删除空组织 |
| 组织列表 | 仅见自己所属 | Superuser 可见全部（含成员数） |
| 用户管理 | 仅管理本组织成员 | Superuser 可管理所有用户 |
| 用户-组织关系 | 无法跨组织操作 | Superuser 可添加/移除用户到任意组织 |
| 活跃组织切换 | 仅用户自己 | Superuser 可为任意用户切换 |
| 导航菜单 | Organization = 成员列表 | Organization = 组织列表 + People（Superuser） |
| YOLO 训练 | 无 | Projects 级多项目训练 + 任务/配置/权重管理 |

---

## License

基于原版 [Apache 2.0 LICENSE](/LICENSE) © [Heartex](https://www.heartex.com/)。2020-2025
