# Label Studio (改造版)

基于 [HumanSignal/label-studio](https://github.com/HumanSignal/label-studio) 的二次开发版本，在原有数据标注功能基础上增加了 **超级管理员（Superuser）权限体系** 和 **多组织管理能力**。

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

---

## 如何启动

### 方式一：Docker Compose（推荐）

使用 Docker Compose 启动完整的生产级栈（Label Studio + Nginx + PostgreSQL）：

```bash
# 1. 构建并启动所有服务
docker compose up --build

# 2.（可选）首次启动后运行数据库迁移
docker compose run app python3 /label-studio/label_studio/manage.py migrate

# 3.（可选）收集静态文件
docker compose run app python3 /label-studio/label_studio/manage.py collectstatic
```

启动后访问 `http://localhost:8080`。

数据持久化目录为 `./mydata`（SQLite 数据库、上传文件等）。PostgreSQL 数据存储在 `./postgres-data`。

**开发模式（支持前端 HMR 热更新）：**

```bash
# 1. 设置开发环境配置
make docker-dev-setup

# 2. 构建并启动
docker compose up --build
```

这将自动创建 `.env` 和 `docker-compose.override.yml`，启用前端热模块替换（HMR），前端开发服务器运行在 `http://localhost:8081`。

### 方式二：本地开发（不使用 Docker）

#### 后端

```bash
# 1. 安装 Poetry
pip install poetry

# 2. 安装项目依赖
poetry install

# 3. 运行数据库迁移
DJANGO_DB=sqlite DJANGO_SETTINGS_MODULE=core.settings.label_studio \
  poetry run python label_studio/manage.py migrate

# 4. 收集静态文件
DJANGO_DB=sqlite DJANGO_SETTINGS_MODULE=core.settings.label_studio \
  poetry run python label_studio/manage.py collectstatic

# 5. 启动开发服务器（SQLite 模式）
make run-dev
```

或使用 Makefile 快捷命令：

```bash
make env-dev-setup   # 创建 .env 文件
make run-dev          # 启动 Django 开发服务器（SQLite）
make migrate-dev      # 运行迁移（SQLite）
make shell-dev        # Django shell
```

#### 前端

```bash
# 1. 安装前端依赖
cd web && yarn install --frozen-lockfile

# 2. 启动前端开发服务器（HMR 模式）
cd web && yarn run dev

# 3.（或）构建生产前端包
cd web && yarn run build
```

前端开发模式下，后端需在 `http://localhost:8080` 运行，前端 HMR 服务在 `http://localhost:8010`。

### 方式三：Docker 单容器

```bash
# 构建镜像
docker build -t label-studio:latest .

# 运行
docker run -it -p 8080:8080 -v $(pwd)/mydata:/label-studio/data label-studio:latest
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

---

## 项目结构

```
label-studio/
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
│   │   │   └── index.js           # ✏️ 注册 PeoplePage 路由
│   ├── libs/core/src/types/user.ts # ✏️ 新增 is_superuser 类型
│   └── ...
├── docker-compose.yml              # 生产部署配置
├── Dockerfile                      # 生产镜像构建
├── Dockerfile.development          # 开发镜像构建
├── Makefile                        # 开发快捷命令
├── pyproject.toml                  # Python 项目配置
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

---

## License

基于原版 [Apache 2.0 LICENSE](/LICENSE) © [Heartex](https://www.heartex.com/)。2020-2025