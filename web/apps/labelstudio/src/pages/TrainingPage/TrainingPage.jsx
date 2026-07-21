import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useHistory, useParams as useRouterParams } from "react-router";
import { Button, Select } from "@humansignal/ui";
import { Space } from "../../components/Space/Space";
import { Spinner } from "../../components/Spinner/Spinner";
import { SidebarMenu } from "../../components/SidebarMenu/SidebarMenu";
import { useAPI } from "../../providers/ApiProvider";
import { Block, Elem } from "../../utils/bem";
import "./TrainingPage.scss";

const STATUS_LABEL = {
  pending: "等待中",
  building: "构建数据集",
  training: "训练中",
  completed: "已完成",
  failed: "失败",
  stopped: "已停止",
};

const isRunningStatus = (status) => ["pending", "building", "training"].includes(status);

const formatSize = (bytes) => {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const DEFAULT_TRAIN_PARAMS = {
  epochs: 1000,
  patience: 200,
  batch: 16,
  imgsz: 640,
  device: "0",
  workers: 8,
  seed: 0,
  pretrained: true,
  optimizer: "auto",
  cos_lr: false,
  amp: true,
  close_mosaic: 10,
  fraction: 1.0,
  deterministic: true,
  single_cls: false,
  rect: false,
  multi_scale: false,
  save_period: -1,
  cache: false,
  plots: true,
  val: true,
  lr0: 0.01,
  lrf: 0.01,
  momentum: 0.937,
  weight_decay: 0.0005,
  warmup_epochs: 3.0,
  warmup_momentum: 0.8,
  warmup_bias_lr: 0.1,
  box: 7.5,
  cls: 0.5,
  dfl: 1.5,
  label_smoothing: 0.0,
  nbs: 64,
  dropout: 0.0,
  hsv_h: 0.015,
  hsv_s: 0.7,
  hsv_v: 0.4,
  degrees: 0.0,
  translate: 0.1,
  scale: 0.5,
  shear: 0.0,
  perspective: 0.0,
  flipud: 0.0,
  fliplr: 0.5,
  bgr: 0.0,
  mosaic: 1.0,
  mixup: 0.0,
  copy_paste: 0.0,
  erasing: 0.4,
  crop_fraction: 1.0,
  overlap_mask: true,
  mask_ratio: 4,
};

const PARAM_GROUPS = [
  {
    title: "基础训练参数",
    fields: [
      { key: "epochs", label: "epochs 训练轮数", type: "number" },
      { key: "patience", label: "patience 早停耐心值", type: "number" },
      { key: "batch", label: "batch 批大小", type: "number" },
      { key: "imgsz", label: "imgsz 输入尺寸", type: "number" },
      { key: "device", label: "device 设备(0/cpu/0,1)", type: "text" },
      { key: "workers", label: "workers 数据加载线程", type: "number" },
      { key: "seed", label: "seed 随机种子", type: "number" },
      { key: "optimizer", label: "optimizer 优化器", type: "select", options: ["auto", "SGD", "Adam", "AdamW", "RMSProp", "NAdam", "RAdam", "Adamax"] },
      { key: "pretrained", label: "pretrained 使用预训练", type: "bool" },
      { key: "amp", label: "amp 混合精度", type: "bool" },
      { key: "cos_lr", label: "cos_lr 余弦学习率", type: "bool" },
      { key: "close_mosaic", label: "close_mosaic 末轮关闭马赛克", type: "number" },
      { key: "fraction", label: "fraction 数据使用比例", type: "number", step: 0.01 },
      { key: "save_period", label: "save_period 存档间隔(-1关闭)", type: "number" },
      { key: "cache", label: "cache 缓存数据", type: "bool" },
      { key: "plots", label: "plots 保存图表", type: "bool" },
      { key: "val", label: "val 训练中验证", type: "bool" },
      { key: "deterministic", label: "deterministic 确定性", type: "bool" },
      { key: "single_cls", label: "single_cls 单类模式", type: "bool" },
      { key: "rect", label: "rect 矩形训练", type: "bool" },
      { key: "multi_scale", label: "multi_scale 多尺度", type: "bool" },
    ],
  },
  {
    title: "学习率与损失",
    fields: [
      { key: "lr0", label: "lr0 初始学习率", type: "number", step: 0.0001 },
      { key: "lrf", label: "lrf 最终学习率因子", type: "number", step: 0.0001 },
      { key: "momentum", label: "momentum 动量", type: "number", step: 0.001 },
      { key: "weight_decay", label: "weight_decay 权重衰减", type: "number", step: 0.0001 },
      { key: "warmup_epochs", label: "warmup_epochs 预热轮数", type: "number", step: 0.1 },
      { key: "warmup_momentum", label: "warmup_momentum 预热动量", type: "number", step: 0.01 },
      { key: "warmup_bias_lr", label: "warmup_bias_lr 预热偏置学习率", type: "number", step: 0.01 },
      { key: "box", label: "box 框损失权重", type: "number", step: 0.1 },
      { key: "cls", label: "cls 分类损失权重", type: "number", step: 0.1 },
      { key: "dfl", label: "dfl DFL损失权重", type: "number", step: 0.1 },
      { key: "label_smoothing", label: "label_smoothing 标签平滑", type: "number", step: 0.01 },
      { key: "nbs", label: "nbs 名义批大小", type: "number" },
      { key: "dropout", label: "dropout 分类丢弃率", type: "number", step: 0.01 },
    ],
  },
  {
    title: "数据增强",
    fields: [
      { key: "hsv_h", label: "hsv_h 色调增强", type: "number", step: 0.001 },
      { key: "hsv_s", label: "hsv_s 饱和度增强", type: "number", step: 0.01 },
      { key: "hsv_v", label: "hsv_v 明度增强", type: "number", step: 0.01 },
      { key: "degrees", label: "degrees 旋转角度", type: "number", step: 0.1 },
      { key: "translate", label: "translate 平移", type: "number", step: 0.01 },
      { key: "scale", label: "scale 缩放", type: "number", step: 0.01 },
      { key: "shear", label: "shear 剪切", type: "number", step: 0.1 },
      { key: "perspective", label: "perspective 透视", type: "number", step: 0.0001 },
      { key: "flipud", label: "flipud 上下翻转概率", type: "number", step: 0.01 },
      { key: "fliplr", label: "fliplr 左右翻转概率", type: "number", step: 0.01 },
      { key: "bgr", label: "bgr 通道翻转概率", type: "number", step: 0.01 },
      { key: "mosaic", label: "mosaic 马赛克概率", type: "number", step: 0.01 },
      { key: "mixup", label: "mixup 混合增强概率", type: "number", step: 0.01 },
      { key: "copy_paste", label: "copy_paste 复制粘贴概率", type: "number", step: 0.01 },
      { key: "erasing", label: "erasing 随机擦除概率", type: "number", step: 0.01 },
      { key: "crop_fraction", label: "crop_fraction 裁剪比例", type: "number", step: 0.01 },
    ],
  },
  {
    title: "分割专用",
    fields: [
      { key: "overlap_mask", label: "overlap_mask 掩码重叠", type: "bool" },
      { key: "mask_ratio", label: "mask_ratio 掩码下采样", type: "number" },
    ],
  },
];

const mergeParams = (src = {}) => ({ ...DEFAULT_TRAIN_PARAMS, ...(src || {}) });

const TrainingLayout = ({ children, ...routeProps }) => (
  <SidebarMenu
    menuItems={[
      { title: "启动训练", path: "/" },
      { title: "任务", path: "/tasks" },
      { title: "配置管理", path: "/configs" },
    ]}
    path={routeProps.match.url}
  >
    {children}
  </SidebarMenu>
);

const ParamFields = ({ values, onChange }) => (
  <>
    {PARAM_GROUPS.map((group) => (
      <Elem name="section" key={group.title}>
        <Elem name="label">{group.title}</Elem>
        <Elem name="params-grid">
          {group.fields.map((field) => {
            const val = values[field.key];
            return (
              <Elem name="param" key={field.key}>
                <Elem name="param-label">{field.label}</Elem>
                <Elem name="param-input">
                  {field.type === "bool" ? (
                    <select
                      value={val ? "true" : "false"}
                      onChange={(e) => onChange(field.key, e.target.value === "true")}
                    >
                      <option value="true">true 是</option>
                      <option value="false">false 否</option>
                    </select>
                  ) : field.type === "select" ? (
                    <select value={val} onChange={(e) => onChange(field.key, e.target.value)}>
                      {field.options.map((opt) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={field.type === "number" ? "number" : "text"}
                      step={field.step}
                      value={val ?? ""}
                      onChange={(e) => {
                        if (field.type === "number") {
                          const n = e.target.value === "" ? 0 : Number(e.target.value);
                          onChange(field.key, Number.isNaN(n) ? 0 : n);
                        } else {
                          onChange(field.key, e.target.value);
                        }
                      }}
                    />
                  )}
                </Elem>
              </Elem>
            );
          })}
        </Elem>
      </Elem>
    ))}
  </>
);

const StartTrain = () => {
  const history = useHistory();
  const api = useAPI();
  const [configs, setConfigs] = useState([]);
  const [projects, setProjects] = useState([]);
  const [configName, setConfigName] = useState("");
  const [selectedProjectIds, setSelectedProjectIds] = useState([]);
  const [trainParams, setTrainParams] = useState(mergeParams());
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [projectSearch, setProjectSearch] = useState("");

  useEffect(() => {
    api.callApi("trainConfigs", {}).then((res) => {
      const list = Array.isArray(res) ? res : res?.data || res?.results || [];
      setConfigs(list);
      if (list.length) {
        setConfigName((prev) => prev || list[0].name);
      }
    }).catch(() => {});
    api.callApi("projects", {
      params: {
        page: 1,
        page_size: 1000,
        include: ["id", "title"].join(","),
      },
    }).then((data) => setProjects(data?.results || [])).catch(() => {});
  }, [api]);

  useEffect(() => {
    const cfg = configs.find((c) => c.name === configName);
    if (cfg) setTrainParams(mergeParams(cfg.train_params || cfg));
  }, [configName, configs]);

  const filteredProjects = useMemo(() => {
    const q = projectSearch.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter((p) => String(p.title || "").toLowerCase().includes(q) || String(p.id).includes(q));
  }, [projects, projectSearch]);

  const toggleProject = (id) => {
    setSelectedProjectIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const setParam = (key, value) => setTrainParams((prev) => ({ ...prev, [key]: value }));

  const startTraining = async () => {
    if (!configName || !selectedProjectIds.length) return;
    setStarting(true);
    setError("");
    try {
      const job = await api.callApi("startTrain", {
        body: {
          config_name: configName,
          project_ids: selectedProjectIds,
          train_params: trainParams,
        },
        suppressError: true,
        errorFilter: () => true,
      });
      if (!job || job.error) {
        const msg = job?.response?.error || job?.error || "启动失败";
        setError(typeof msg === "string" ? msg : JSON.stringify(msg));
        return;
      }
      history.push(job?.id ? `/projects/train/tasks/${job.id}` : "/projects/train/tasks");
    } catch (e) {
      setError(e?.message || "启动失败");
    } finally {
      setStarting(false);
    }
  };

  return (
    <Block name="training-page">
      <Elem name="panel">
        <Elem name="panel-title">启动训练</Elem>
        <Elem name="hint">
          选择配置与一个/多个项目合并训练。项目标签类别必须与配置 classes 完全一致，否则会报错。
          支持 obb / detect / seg（PolygonLabels）/ cls（Choices）。提交后请到「任务」页查看进度。
        </Elem>

        <Elem name="section">
          <Elem name="label">模型配置</Elem>
          <Elem name="select-row">
            <Select
              value={configName}
              onChange={setConfigName}
              searchable
              searchPlaceholder="搜索配置..."
              placeholder="请选择配置"
              options={configs.map((c) => ({
                label: `${c.name} (${c.task_type}, ${(c.classes || []).join("/")})`,
                value: c.name,
              }))}
            />
            <Button size="small" look="outlined" onClick={() => history.push("/projects/train/configs")}>
              去配置管理
            </Button>
          </Elem>
        </Elem>

        <Elem name="section">
          <Elem name="label">训练项目（已选 {selectedProjectIds.length}）</Elem>
          <input
            type="text"
            placeholder="搜索项目名称或 ID..."
            value={projectSearch}
            onChange={(e) => setProjectSearch(e.target.value)}
            style={{ width: "100%", marginBottom: 8 }}
          />
          <Elem name="project-picker">
            {filteredProjects.length === 0 ? (
              <Elem name="empty">暂无项目</Elem>
            ) : (
              filteredProjects.map((p) => (
                <Elem tag="label" key={p.id} name="project-option">
                  <input
                    type="checkbox"
                    checked={selectedProjectIds.includes(p.id)}
                    onChange={() => toggleProject(p.id)}
                  />
                  <Elem tag="span" name="project-title">{p.title}</Elem>
                  <Elem tag="span" name="project-meta">#{p.id}</Elem>
                </Elem>
              ))
            )}
          </Elem>
        </Elem>

        <ParamFields values={trainParams} onChange={setParam} />

        {error && <Elem name="error">{String(error)}</Elem>}

        <Space style={{ marginTop: 20 }}>
          <Button
            look="primary"
            waiting={starting}
            disabled={!configName || !selectedProjectIds.length}
            onClick={startTraining}
          >
            开始训练
          </Button>
        </Space>
      </Elem>
    </Block>
  );
};

const DEFAULT_META = {
  name: "",
  task_type: "obb",
  model_yaml: "yolov8x-obb",
  model_pt: "yolov8x-obb",
  data_yaml: "",
  classes: "object",
};

const applyConfigToForm = (config) => ({
  meta: {
    name: config?.name || "",
    task_type: config?.task_type || "obb",
    model_yaml: config?.model_yaml || "yolov8x-obb",
    model_pt: config?.model_pt || "yolov8x-obb",
    data_yaml: config?.data_yaml || "",
    classes: Array.isArray(config?.classes) ? config.classes.join(", ") : (config?.classes || "object"),
  },
  trainParams: mergeParams(config?.train_params || config || {}),
});

const ConfigManagement = () => {
  const api = useAPI();
  const [configs, setConfigs] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [hint, setHint] = useState("");
  const [meta, setMeta] = useState({ ...DEFAULT_META });
  const [trainParams, setTrainParams] = useState(mergeParams());
  const [showAdvanced, setShowAdvanced] = useState(false);

  const fillForm = (config, creating = false, message = "") => {
    const { meta: nextMeta, trainParams: nextParams } = applyConfigToForm(config);
    setMeta(nextMeta);
    setTrainParams(nextParams);
    setIsCreating(creating);
    setSelectedId(creating ? null : (config?.id ?? null));
    setError("");
    setHint(message);
  };

  const load = useCallback(async () => {
    try {
      const res = await api.callApi("trainConfigs", {});
      const list = Array.isArray(res) ? res : res?.data || res?.results || [];
      setConfigs(list);
      if (isCreating) return;
      const keep = list.find((c) => c.id === selectedId);
      const target = keep || list[0];
      if (!target) {
        fillForm({ ...DEFAULT_META, train_params: DEFAULT_TRAIN_PARAMS }, true, "暂无配置，已填入默认参数，请填写名称后保存。");
        return;
      }
      fillForm(target, false, "");
    } catch (e) {
      // ignore
    }
  }, [api, isCreating, selectedId]);

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onSelectChange = (id) => {
    const config = configs.find((c) => String(c.id) === String(id));
    if (!config) return;
    fillForm(config, false, "");
  };

  const startCreate = () => {
    const base = configs.find((c) => c.id === selectedId) || configs[0];
    const stamped = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
    if (base) {
      fillForm(
        {
          ...base,
          id: undefined,
          name: `${base.name}-copy-${stamped}`,
        },
        true,
        "新建模式：已基于当前配置预填全部参数，请修改名称/类别后保存。",
      );
    } else {
      fillForm(
        { ...DEFAULT_META, name: `custom-obb-${stamped}`, train_params: DEFAULT_TRAIN_PARAMS },
        true,
        "新建模式：已填入推荐默认超参，请补全名称与类别后保存。",
      );
    }
    setShowAdvanced(false);
  };

  const saveConfig = async () => {
    setSaving(true);
    setError("");
    const body = {
      ...meta,
      classes: meta.classes.split(",").map((c) => c.trim()).filter(Boolean),
      train_params: trainParams,
    };
    if (!body.name?.trim()) {
      setError("请填写配置名称");
      setSaving(false);
      return;
    }
    if (!body.classes.length) {
      setError("请填写至少一个类别");
      setSaving(false);
      return;
    }
    try {
      const res = isCreating || !selectedId
        ? await api.callApi("createTrainConfig", { body, suppressError: true, errorFilter: () => true })
        : await api.callApi("updateTrainConfig", { params: { config_id: selectedId }, body, suppressError: true, errorFilter: () => true });
      if (!res || res.error) {
        setError(res?.response?.error || res?.error || "保存失败");
        return;
      }
      setIsCreating(false);
      setHint("保存成功");
      const list = await api.callApi("trainConfigs", {});
      const arr = Array.isArray(list) ? list : list?.data || list?.results || [];
      setConfigs(arr);
      const saved = arr.find((c) => c.id === res.id) || arr.find((c) => c.name === body.name) || arr[0];
      if (saved) fillForm(saved, false, "保存成功");
    } catch (e) {
      setError(e?.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const deleteConfig = async () => {
    if (!selectedId || isCreating) return;
    if (!confirm("确定删除该配置？此操作不可恢复。")) return;
    await api.callApi("deleteTrainConfig", { params: { config_id: selectedId } });
    setSelectedId(null);
    setIsCreating(false);
    load();
  };

  return (
    <Block name="training-page">
      <Elem name="panel" mod={{ wide: true }}>
        <Elem name="panel-title">配置管理</Elem>
        <Elem name="hint">
          用下拉框选择已有配置进行编辑；点「新建配置」会预填默认/当前参数，只需改名称和类别即可保存。
        </Elem>

        <Elem name="section">
          <Elem name="label">选择配置</Elem>
          <Elem name="select-row">
            <Select
              value={isCreating ? "" : (selectedId ?? "")}
              onChange={onSelectChange}
              searchable
              searchPlaceholder="搜索配置..."
              placeholder={isCreating ? "新建中（未保存）" : "请选择配置"}
              disabled={isCreating}
              options={configs.map((c) => ({
                label: `${c.name} (${c.task_type})`,
                value: c.id,
              }))}
            />
            <Button size="small" look="primary" onClick={startCreate}>新建配置</Button>
            {!isCreating && selectedId && (
              <Button size="small" look="negative" onClick={deleteConfig}>删除配置</Button>
            )}
            {isCreating && (
              <Button
                size="small"
                look="outlined"
                onClick={() => {
                  const cur = configs.find((c) => c.id === selectedId) || configs[0];
                  if (cur) fillForm(cur, false, "");
                  else load();
                }}
              >
                取消新建
              </Button>
            )}
          </Elem>
          {(hint || isCreating) && (
            <Elem name="mode-banner" mod={{ creating: isCreating }}>
              {hint || (isCreating ? "新建模式" : "")}
            </Elem>
          )}
        </Elem>

        <Elem name="section">
          <Elem name="label">基础信息</Elem>
          <Elem name="form-row">
            <Elem name="form-item">
              <Elem name="param-label">name 配置名称 *</Elem>
              <input
                value={meta.name}
                placeholder="例如 jasmine-obb-v2"
                onChange={(e) => setMeta({ ...meta, name: e.target.value })}
              />
            </Elem>
            <Elem name="form-item">
              <Elem name="param-label">task_type 任务类型</Elem>
              <select
                value={meta.task_type}
                onChange={(e) => {
                  const task_type = e.target.value;
                  const defaults = {
                    obb: { model_yaml: "yolov8x-obb", model_pt: "yolov8x-obb" },
                    detect: { model_yaml: "yolov8x", model_pt: "yolov8x" },
                    seg: { model_yaml: "yolov8-seg", model_pt: "yolov8x-seg" },
                    cls: { model_yaml: "yolov8-cls", model_pt: "yolov8x-cls" },
                  }[task_type] || {};
                  setMeta({ ...meta, task_type, ...defaults });
                }}
              >
                <option value="obb">obb 旋转检测</option>
                <option value="detect">detect 目标检测</option>
                <option value="cls">cls 分类（需 Choices 标注）</option>
                <option value="seg">seg 分割（需 PolygonLabels）</option>
              </select>
            </Elem>
          </Elem>
          <Elem name="form-row">
            <Elem name="form-item">
              <Elem name="param-label">model_yaml 模型结构</Elem>
              <input value={meta.model_yaml} onChange={(e) => setMeta({ ...meta, model_yaml: e.target.value })} />
              <Elem name="hint" style={{ marginTop: 4 }}>
                示例：obb→yolov8x-obb；detect→yolov8x；seg→yolov8-seg；cls→yolov8-cls
              </Elem>
            </Elem>
            <Elem name="form-item">
              <Elem name="param-label">model_pt 预训练权重名</Elem>
              <input value={meta.model_pt} onChange={(e) => setMeta({ ...meta, model_pt: e.target.value })} />
              <Elem name="hint" style={{ marginTop: 4 }}>
                对应 .pt 名，如 yolov8x-seg / yolov8x-cls（不含后缀）
              </Elem>
            </Elem>
            <Elem name="form-item">
              <Elem name="param-label">data_yaml 数据配置名(可空)</Elem>
              <input value={meta.data_yaml} onChange={(e) => setMeta({ ...meta, data_yaml: e.target.value })} />
            </Elem>
          </Elem>
          <Elem name="param-label">classes 类别(逗号分隔，须与项目标签一致) *</Elem>
          <textarea
            value={meta.classes}
            placeholder="例如 blooming, seed"
            onChange={(e) => setMeta({ ...meta, classes: e.target.value })}
          />
          <Elem name="hint" style={{ marginTop: 4 }}>
            seg 项目请用 PolygonLabels；cls 项目请用 Choices，类别名须与这里完全一致。
          </Elem>
        </Elem>

        <Elem name="section">
          <Elem name="panel-header">
            <Elem name="label" style={{ marginBottom: 0 }}>训练超参</Elem>
            <Button size="small" look="outlined" onClick={() => setShowAdvanced((v) => !v)}>
              {showAdvanced ? "收起高级参数" : "展开全部参数"}
            </Button>
          </Elem>
          {!showAdvanced ? (
            <Elem name="params-grid">
              {[
                ["epochs", "epochs 训练轮数"],
                ["batch", "batch 批大小"],
                ["patience", "patience 早停"],
                ["imgsz", "imgsz 输入尺寸"],
                ["device", "device 设备"],
                ["lr0", "lr0 初始学习率"],
              ].map(([key, label]) => (
                <Elem name="param" key={key}>
                  <Elem name="param-label">{label}</Elem>
                  <Elem name="param-input">
                    <input
                      type={key === "device" ? "text" : "number"}
                      step={key === "lr0" ? 0.0001 : 1}
                      value={trainParams[key] ?? ""}
                      onChange={(e) => {
                        const val = key === "device" ? e.target.value : Number(e.target.value);
                        setTrainParams((p) => ({ ...p, [key]: val }));
                      }}
                    />
                  </Elem>
                </Elem>
              ))}
            </Elem>
          ) : (
            <ParamFields values={trainParams} onChange={(k, v) => setTrainParams((p) => ({ ...p, [k]: v }))} />
          )}
        </Elem>

        {error && <Elem name="error">{String(error)}</Elem>}
        <Space style={{ marginTop: 16 }}>
          <Button look="primary" waiting={saving} onClick={saveConfig}>
            {isCreating ? "创建并保存" : "保存修改"}
          </Button>
        </Space>
      </Elem>
    </Block>
  );
};

const TaskList = () => {
  const history = useHistory();
  const api = useAPI();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [projectQuery, setProjectQuery] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    const params = { page: 1, page_size: 50 };
    if (statusFilter) params.status = statusFilter;
    if (projectQuery.trim()) params.project = projectQuery.trim();
    api.callApi("trainJobs", { params }).then((data) => {
      setJobs(data?.results || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [api, statusFilter, projectQuery]);

  useEffect(() => {
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, [load]);

  const deleteJob = async (e, job) => {
    e.stopPropagation();
    if (isRunningStatus(job.status)) {
      alert("任务仍在运行，请先进入详情停止后再删除");
      return;
    }
    if (!confirm(`确定删除任务 #${job.id}？\n将同时删除该任务的日志与全部模型文件，不可恢复。`)) return;
    setDeletingId(job.id);
    try {
      const res = await api.callApi("deleteTrainJob", {
        params: { job_id: job.id },
        suppressError: true,
        errorFilter: () => true,
      });
      if (!res || res.error) {
        alert(res?.response?.error || res?.error || "删除失败");
        return;
      }
      load();
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Block name="training-page">
      <Elem name="panel">
        <Elem name="panel-header">
          <Elem name="panel-title" style={{ marginBottom: 0 }}>训练任务</Elem>
          <Space>
            <input
              type="text"
              placeholder="按项目名称或 ID 搜索..."
              value={projectQuery}
              onChange={(e) => setProjectQuery(e.target.value)}
              style={{ minWidth: 220 }}
            />
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">全部状态</option>
              {Object.entries(STATUS_LABEL).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </Space>
        </Elem>

        {loading && !jobs.length ? (
          <Spinner size={40} />
        ) : jobs.length === 0 ? (
          <Elem name="empty">暂无训练任务</Elem>
        ) : (
          <Elem name="job-list">
            {jobs.map((job) => (
              <Elem
                name="job-card"
                key={job.id}
                onClick={() => history.push(`/projects/train/tasks/${job.id}`)}
              >
                <Elem name="job-card-top">
                  <Elem name="job-name">#{job.id} · {job.config_name}</Elem>
                  <Space>
                    <Elem name="status-badge" mod={{ [job.status]: true }}>
                      {STATUS_LABEL[job.status] || job.status}
                    </Elem>
                    <Button
                      size="small"
                      look="negative"
                      waiting={deletingId === job.id}
                      disabled={isRunningStatus(job.status)}
                      onClick={(e) => deleteJob(e, job)}
                    >
                      删除
                    </Button>
                  </Space>
                </Elem>
                <Elem name="job-meta">项目：{(job.project_titles || []).join("、") || "—"}</Elem>
                <Elem name="job-meta">
                  {job.created_by || "—"} · {job.created_at}
                  {isRunningStatus(job.status) ? ` · Epoch ${job.current_epoch}/${job.total_epochs} (${job.progress}%)` : ""}
                  {job.model_count ? ` · 模型 ${job.model_count}` : ""}
                </Elem>
                {job.error_message && <Elem name="job-error">{job.error_message}</Elem>}
              </Elem>
            ))}
          </Elem>
        )}
      </Elem>
    </Block>
  );
};

const TaskDetail = () => {
  const history = useHistory();
  const api = useAPI();
  const { jobId } = useRouterParams();
  const [job, setJob] = useState(null);
  const [logs, setLogs] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [stopping, setStopping] = useState(false);
  const logRef = useRef(null);
  const sinceRef = useRef(0);

  const loadJob = useCallback(() => {
    if (!jobId) return;
    api.callApi("trainJobDetail", { params: { job_id: jobId } }).then(setJob).catch(() => {});
  }, [api, jobId]);

  const loadLogs = useCallback(() => {
    if (!jobId) return;
    api.callApi("trainJobLogs", {
      params: { job_id: jobId, since: sinceRef.current },
    }).then((data) => {
      const entries = data?.logs || [];
      if (!entries.length) return;
      setLogs((prev) => {
        const merged = sinceRef.current ? [...prev, ...entries] : entries;
        sinceRef.current = entries[entries.length - 1].id;
        return merged;
      });
    }).catch(() => {});
  }, [api, jobId]);

  useEffect(() => {
    sinceRef.current = 0;
    setLogs([]);
    loadJob();
    loadLogs();
    const id = setInterval(() => { loadJob(); loadLogs(); }, 2500);
    return () => clearInterval(id);
  }, [jobId, loadJob, loadLogs]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  if (!job) {
    return (
      <Block name="training-page">
        <Elem name="panel"><Spinner size={40} /></Elem>
      </Block>
    );
  }

  const filteredLogs = logs.filter((log) =>
    (log.message || "").toLowerCase().includes(searchTerm.toLowerCase()),
  );
  const running = isRunningStatus(job.status);
  const params = job.params || {};

  return (
    <Block name="training-page">
      <Elem name="panel" mod={{ wide: true }}>
        <Elem name="panel-header">
          <Space>
            <Button size="small" look="outlined" onClick={() => history.push("/projects/train/tasks")}>
              ← 返回列表
            </Button>
            <Elem name="panel-title" style={{ marginBottom: 0 }}>任务 #{job.id}</Elem>
          </Space>
          {running && (
            <Button
              look="negative"
              size="small"
              waiting={stopping}
              onClick={async () => {
                if (!confirm("确定停止该训练任务？")) return;
                setStopping(true);
                try {
                  await api.callApi("stopTrainJob", { params: { job_id: jobId } });
                  loadJob();
                } finally {
                  setStopping(false);
                }
              }}
            >
              停止训练
            </Button>
          )}
        </Elem>

        <Elem name="status-badge" mod={{ [job.status]: true }}>
          {STATUS_LABEL[job.status] || job.status}
        </Elem>

        <Elem name="detail-grid">
          <Elem name="detail-item">
            <Elem name="detail-label">配置</Elem>
            <Elem name="detail-value">{job.config_name}</Elem>
          </Elem>
          <Elem name="detail-item">
            <Elem name="detail-label">创建人</Elem>
            <Elem name="detail-value">{job.created_by || "—"}</Elem>
          </Elem>
          <Elem name="detail-item">
            <Elem name="detail-label">创建时间</Elem>
            <Elem name="detail-value">{job.created_at}</Elem>
          </Elem>
          <Elem name="detail-item">
            <Elem name="detail-label">更新时间</Elem>
            <Elem name="detail-value">{job.updated_at}</Elem>
          </Elem>
          <Elem name="detail-item" style={{ gridColumn: "1 / -1" }}>
            <Elem name="detail-label">关联项目</Elem>
            <Elem name="detail-value">
              {(job.projects || []).map((p) => `${p.title} (#${p.id})`).join("、") || "—"}
            </Elem>
          </Elem>
        </Elem>

        {running && (
          <Elem name="progress-section">
            <Elem name="progress-bar">
              <Elem name="progress-fill" style={{ width: `${job.progress || 0}%` }} />
            </Elem>
            <Elem name="progress-text">{job.progress || 0}%</Elem>
            <Elem name="epoch-text">Epoch {job.current_epoch}/{job.total_epochs}</Elem>
          </Elem>
        )}

        <Elem name="section">
          <Elem name="label">训练参数明细</Elem>
          <Elem name="params-readonly">
            {Object.entries(params)
              .filter(([k]) => k !== "project_ids")
              .map(([key, val]) => (
                <Elem name="param-chip" key={key}>
                  <strong>{key}</strong>: {String(val)}
                </Elem>
              ))}
          </Elem>
        </Elem>

        {job.error_message && (
          <Elem name="error-box">
            <Elem name="label">错误信息</Elem>
            <pre>{job.error_message}</pre>
          </Elem>
        )}

        {job.result && Object.keys(job.result).length > 0 && (
          <Elem name="section">
            <Elem name="label">评估指标（用于判断模型是否有效）</Elem>
            <Elem name="hint">
              重点看 mAP50 / mAP50-95：数值越高越好。一般 mAP50 &gt; 0.5 可认为有一定检测能力；若接近 0 或训练失败无指标，说明模型基本无效。也可用下载的 .pt 在业务数据上做推理验证。
            </Elem>
            <Elem name="metrics">
              {Object.entries(job.result).map(([key, val]) => (
                <Elem name="metric-row" key={key}>
                  <Elem name="metric-key">{key}</Elem>
                  <Elem name="metric-val">{typeof val === "number" ? val.toFixed(4) : String(val)}</Elem>
                </Elem>
              ))}
            </Elem>
          </Elem>
        )}

        {job.status === "completed" && (!job.result || !Object.keys(job.result).length) && (
          <Elem name="hint">
            训练已完成但缺少评估指标。请查看日志是否评估失败；可下载模型后在实际图片上试推理确认效果。
          </Elem>
        )}

        {job.artifacts?.F1_curve?.url && (
          <Elem name="section">
            <Elem name="label">F1 Curve</Elem>
            <Elem name="hint">训练结束后由 Ultralytics 生成的 F1 曲线，用于查看各类别 F1 与置信度阈值的关系。</Elem>
            <Elem name="artifact-image">
              <img src={job.artifacts.F1_curve.url} alt="F1 Curve" />
            </Elem>
          </Elem>
        )}

        <Elem name="section">
          <Elem name="label">产出模型</Elem>
          {(job.models || []).length === 0 ? (
            <Elem name="empty">暂无模型</Elem>
          ) : (
            <Elem name="model-list">
              {[...(job.models || [])]
                .sort((a, b) => {
                  const rank = (m) => (m.variant === "best" || /best/i.test(m.name || "") ? 0 : m.variant === "last" || /last/i.test(m.name || "") ? 1 : 2);
                  return rank(a) - rank(b);
                })
                .map((model) => {
                  const isBest = model.variant === "best" || /best/i.test(model.name || "");
                  const isLast = model.variant === "last" || /last/i.test(model.name || "");
                  const label = isBest ? "best（验证集最优）" : isLast ? "last（最后一轮）" : model.name;
                  return (
                    <Elem name="model-card" key={model.id}>
                      <Elem name="model-name">{label}</Elem>
                      <Elem name="model-meta">{model.name} · {model.created_at} · {formatSize(model.file_size)}</Elem>
                      {model.metrics && Object.keys(model.metrics).length > 0 && (
                        <Elem name="model-meta">
                          {["metrics/mAP50(B)", "metrics/mAP50-95(B)", "mAP50", "mAP50-95", "metrics/accuracy_top1"]
                            .filter((k) => model.metrics[k] != null)
                            .map((k) => `${k}=${Number(model.metrics[k]).toFixed(4)}`)
                            .join(" · ")}
                        </Elem>
                      )}
                      <Space>
                        <Button
                          size="small"
                          look={isBest ? "primary" : "outlined"}
                          onClick={() => window.open(`/api/train/models/${model.id}/download`, "_blank")}
                        >
                          {isBest ? "下载 best" : isLast ? "下载 last" : "下载"}
                        </Button>
                      </Space>
                    </Elem>
                  );
                })}
            </Elem>
          )}
          <Elem name="hint" style={{ marginTop: 8 }}>
            推理/部署建议优先用 best；last 为训练结束时的权重。删除请回「任务」列表删除整个任务。
          </Elem>
        </Elem>

        <Elem name="section">
          <Elem name="panel-header">
            <Elem name="label" style={{ marginBottom: 0 }}>训练日志</Elem>
            <Space>
              <input type="text" placeholder="搜索日志..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} />
              <Button
                size="small"
                look="outlined"
                onClick={async () => {
                  await api.callApi("clearTrainJobLogs", { params: { job_id: jobId } });
                  sinceRef.current = 0;
                  setLogs([]);
                }}
              >
                清空
              </Button>
            </Space>
          </Elem>
          <Elem name="log-viewer" ref={logRef}>
            {filteredLogs.length === 0 ? (
              <Elem name="empty">暂无日志</Elem>
            ) : (
              filteredLogs.map((log) => (
                <Elem name="log-line" key={log.id}>
                  <Elem name="log-time">[{log.created_at}]</Elem>
                  <Elem name="log-level">{log.level}</Elem>
                  <Elem name="log-msg">{log.message}</Elem>
                </Elem>
              ))
            )}
          </Elem>
        </Elem>
      </Elem>
    </Block>
  );
};

export const TrainingPage = {
  title: "训练",
  path: "/train",
  exact: true,
  layout: TrainingLayout,
  component: StartTrain,
  pages: {
    // 注意：不要再挂 path:"/" 的 StartTrain，否则会与 component 重复渲染
    tasks: { title: "任务", path: "/tasks", component: TaskList, exact: true },
    taskDetail: { path: "/tasks/:jobId", component: TaskDetail, exact: true },
    configs: { title: "配置管理", path: "/configs", component: ConfigManagement, exact: true },
  },
};
