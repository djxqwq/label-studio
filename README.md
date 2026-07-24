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

## 怎么跑起来（看这一节就够）

先问自己一件事：**你现在是哪种情况？** 只做对应那一块，别全看。

| 我现在… | 看下面第几节 |
|---------|--------------|
| 自己电脑改代码、试训练 | **① 本地开发** |
| 一台有 GPU 的服务器，全装一起 | **② 单机 Docker** |
| 一台给人用网页，另一台有 GPU 专门训练 | **③ 两台机器** |

用的时候都一样：浏览器打开网页 → Projects → **Train** → 选项目开训 → 下载模型。

---

### ① 本地开发（自己电脑）

**放什么文件**

项目克隆下来就行，保证旁边有 `cv-ultralytics` 文件夹。跑起来后会自动出现数据目录，不用先建。

**要改什么（只改这两个）**

```bash
TRAINING_EXECUTOR=local
TRAINING_DATA_MODE=shared
```

意思：训练就在本机跑，不要 SSH、不要第二台机。

**怎么启动（复制执行）**

```bash
# 装依赖（第一次）
pip install poetry
poetry install
pip install torch torchvision ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple

# 建库、建管理员（第一次）
DJANGO_DB=sqlite DJANGO_SETTINGS_MODULE=core.settings.label_studio poetry run python label_studio/manage.py migrate
DJANGO_DB=sqlite DJANGO_SETTINGS_MODULE=core.settings.label_studio poetry run python label_studio/manage.py createsuperuser

# 每次启动
TRAINING_EXECUTOR=local TRAINING_DATA_MODE=shared make run-dev
```

浏览器打开：`http://localhost:8080`

改了前端页面再执行：`cd web && yarn install && yarn run build`

---

### ② 单机 Docker（一台有 GPU 的机器）

**放什么文件**

```text
label-studio/          ← 整个项目
├── cv-ultralytics/    ← 必须有
├── mydata/            ← 不用手建，跑起来会有
└── docker-compose.yml
```

**要改什么**

**不用改。** 默认就能训。

**怎么启动**

```bash
docker compose up --build -d
docker compose run app python3 /label-studio/label_studio/manage.py migrate
docker compose run app python3 /label-studio/label_studio/manage.py createsuperuser
```

浏览器打开：`http://这台机器IP:8080`

机器要装好 NVIDIA 驱动和 Docker 的 GPU 支持。

---

### ③ 两台机器（网页一台 + GPU 一台）

用白话说：

- **A 机**：给人打开网页、存数据（可以没有 GPU）
- **B 机**：只有 GPU，专门训练  
- 两边**各放一份代码**  
- **不要共享盘**；B 用 SSH 去 A 上把数据包拷过来，训完再把 `best.pt` 拷回去  
- 数据库和 Redis 只在 **A** 上；B 连 A 的地址

#### 文件怎么放

**A 机（标注 / 网页）：**

```text
/opt/label-studio/          ← 项目放这里（路径按你实际改）
├── 代码（整个仓库）
├── mydata/                 ← 重要：图片、导出包、最后给人下载的模型都在这
├── postgres-data/
└── redis-data/
```

**B 机（GPU 训练）：**

```text
/opt/label-studio/
├── 代码（同一份仓库）
├── cv-ultralytics/         ← 重要：训练引擎放 B
└── ssh/id_rsa              ← 重要：能 SSH 登录 A 的私钥
```

#### 先做一次：让 B 能 SSH 登录 A

在 A 上允许 B 免密登录（把 B 的公钥放进 A 的 `~/.ssh/authorized_keys`）。  
在 B 上测一下：

```bash
ssh root@A的IP
# 能进去，并且能看到 A 上的 /opt/label-studio/mydata 就对了
```

私钥文件放到 B 的项目里：`ssh/id_rsa`，权限 `chmod 600 ssh/id_rsa`。

还要把 A 的数据库端口 **5432**、Redis 端口 **6379** 对 B 开放（防火墙放行，或在 compose 里给 db/redis 加 ports）。

#### A 机要改什么、怎么启动

只改一行：

```bash
export TRAINING_DATA_MODE=ssh
```

然后：

```bash
cd /opt/label-studio
docker compose up -d --build nginx app db redis
docker compose run app python3 /label-studio/label_studio/manage.py migrate
docker compose run app python3 /label-studio/label_studio/manage.py createsuperuser
```

注意：**不要**在 A 上起 `training-worker`（上面命令已经只起了网页和库）。

#### B 机要改什么、怎么启动

把下面的 `192.168.1.10` 和路径改成你的 A 机真实 IP / 真实 mydata 路径：

```bash
cd /opt/label-studio

export POSTGRE_HOST=192.168.1.10
export REDIS_HOST=192.168.1.10
export TRAINING_DATA_MODE=ssh
export TRAINING_SSH_HOST=192.168.1.10
export TRAINING_SSH_USER=root
export TRAINING_SSH_KEY=/ssh/id_rsa
export TRAINING_SSH_REMOTE_DATA=/opt/label-studio/mydata

docker compose -f docker-compose.training.yml up -d --build
```

`TRAINING_SSH_REMOTE_DATA` = A 机上 **mydata 文件夹在硬盘上的完整路径**（不是容器里的路径）。

#### 然后怎么用

只打开 **A 的网页** `http://A的IP:8080` → Train。  
不用登录 B。B 在后台自己拉数据、训练、把模型传回 A。

---

### 出问题先看这

| 现象 | 怎么办 |
|------|--------|
| 本地点训练没反应 / 报错 | 确认启动时带了 `TRAINING_EXECUTOR=local` |
| 两台机任务一直转圈 | B 没起来，或 `REDIS_HOST` 填错了 |
| 报 scp / SSH 失败 | B 登不上 A，或 `TRAINING_SSH_REMOTE_DATA` 路径不对 |
| 训完下载不了模型 | 看 B 日志里回传是否失败 |

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
