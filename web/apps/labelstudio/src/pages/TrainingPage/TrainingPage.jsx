import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useHistory, useParams as useRouterParams } from "react-router";
import { Button, Select } from "@humansignal/ui";
import { Modal } from "../../components/Modal/ModalPopup";
import { Space } from "../../components/Space/Space";
import { Spinner } from "../../components/Spinner/Spinner";
import { SidebarMenu } from "../../components/SidebarMenu/SidebarMenu";
import { useAPI } from "../../providers/ApiProvider";
import { Block, Elem } from "../../utils/bem";
import "./TrainingPage.scss";

const STATUS_LABEL = {
  none: "无任务",
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

const TrainingLayout = ({ children, ...routeProps }) => (
  <SidebarMenu
    menuItems={[
      { title: "启动训练", path: "/" },
      { title: "任务", path: "/tasks" },
    ]}
    path={routeProps.match.url}
  >
    {children}
  </SidebarMenu>
);

const ConfigModal = ({ visible, onClose, onSaved }) => {
  const api = useAPI();
  const [configs, setConfigs] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "",
    task_type: "obb",
    model_yaml: "yolov8x-obb",
    model_pt: "yolov8x-obb",
    classes: "",
    epochs: 1000,
    batch: 16,
    patience: 200,
    imgsz: 640,
    device: "0",
  });

  const applyConfig = (config) => {
    setSelectedId(config?.id ?? null);
    setError("");
    setForm({
      name: config?.name || "",
      task_type: config?.task_type || "obb",
      model_yaml: config?.model_yaml || "yolov8x-obb",
      model_pt: config?.model_pt || "yolov8x-obb",
      classes: (config?.classes || []).join(", "),
      epochs: config?.epochs || 1000,
      batch: config?.batch || 16,
      patience: config?.patience || 200,
      imgsz: config?.imgsz || 640,
      device: config?.device || "0",
    });
  };

  const load = useCallback(() => {
    api.callApi("trainConfigs", {}).then((res) => {
      const list = Array.isArray(res) ? res : res?.data || res?.results || [];
      setConfigs(list);
      setSelectedId((prev) => {
        if (prev != null && list.some((c) => c.id === prev)) return prev;
        if (list.length) {
          const first = list[0];
          setForm({
            name: first.name || "",
            task_type: first.task_type || "obb",
            model_yaml: first.model_yaml || "yolov8x-obb",
            model_pt: first.model_pt || "yolov8x-obb",
            classes: (first.classes || []).join(", "),
            epochs: first.epochs || 1000,
            batch: first.batch || 16,
            patience: first.patience || 200,
            imgsz: first.imgsz || 640,
            device: first.device || "0",
          });
          return first.id;
        }
        return null;
      });
    }).catch(() => {});
  }, [api]);

  useEffect(() => {
    if (visible) load();
  }, [visible, load]);

  const selectConfig = (config) => applyConfig(config);

  const newConfig = () => {
    setSelectedId(null);
    setError("");
    setForm({
      name: "",
      task_type: "obb",
      model_yaml: "yolov8x-obb",
      model_pt: "yolov8x-obb",
      classes: "",
      epochs: 1000,
      batch: 16,
      patience: 200,
      imgsz: 640,
      device: "0",
    });
  };

  const saveConfig = async () => {
    setSaving(true);
    setError("");
    const body = {
      ...form,
      classes: form.classes.split(",").map((c) => c.trim()).filter(Boolean),
    };
    try {
      if (selectedId) {
        await api.callApi("updateTrainConfig", { params: { config_id: selectedId }, body });
      } else {
        await api.callApi("createTrainConfig", { body });
      }
      onSaved?.();
      load();
    } catch (e) {
      setError(e?.response?.detail || e?.detail || e?.error || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const deleteConfig = async () => {
    if (!selectedId || !confirm("确定删除该配置？")) return;
    await api.callApi("deleteTrainConfig", { params: { config_id: selectedId } });
    setSelectedId(null);
    onSaved?.();
    load();
  };

  if (!visible) return null;

  return (
    <Modal visible bare allowClose onHide={onClose} width={820}>
      <Block name="training-page">
        <Elem name="modal">
          <Elem name="modal-header">
            <Elem name="panel-title" style={{ marginBottom: 0 }}>配置管理</Elem>
            <Button size="small" look="outlined" onClick={onClose}>关闭</Button>
          </Elem>
          <Elem name="modal-body">
            <Elem name="config-sidebar">
              <Button size="small" look="primary" onClick={newConfig} style={{ width: "100%", marginBottom: 12 }}>
                + 新建配置
              </Button>
              <Elem name="config-list">
                {configs.map((c) => (
                  <Elem
                    key={c.id}
                    name="config-item"
                    mod={{ selected: selectedId === c.id }}
                    onClick={() => selectConfig(c)}
                  >
                    <Elem name="config-name">{c.name}</Elem>
                    <Elem name="config-type">{c.task_type}</Elem>
                    <Elem name="config-classes">{(c.classes || []).join(", ")}</Elem>
                  </Elem>
                ))}
              </Elem>
            </Elem>
            <Elem name="config-detail">
              <Elem name="section">
                <Elem name="label">配置名称</Elem>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </Elem>
              <Elem name="form-row">
                <Elem name="form-item">
                  <Elem name="label">任务类型</Elem>
                  <select value={form.task_type} onChange={(e) => setForm({ ...form, task_type: e.target.value })}>
                    <option value="obb">obb</option>
                    <option value="detect">detect</option>
                    <option value="cls">cls</option>
                    <option value="seg">seg</option>
                  </select>
                </Elem>
                <Elem name="form-item">
                  <Elem name="label">model_yaml</Elem>
                  <input value={form.model_yaml} onChange={(e) => setForm({ ...form, model_yaml: e.target.value })} />
                </Elem>
                <Elem name="form-item">
                  <Elem name="label">model_pt</Elem>
                  <input value={form.model_pt} onChange={(e) => setForm({ ...form, model_pt: e.target.value })} />
                </Elem>
              </Elem>
              <Elem name="section">
                <Elem name="label">类别（逗号分隔，须与所选项目标签一致）</Elem>
                <textarea value={form.classes} onChange={(e) => setForm({ ...form, classes: e.target.value })} />
              </Elem>
              <Elem name="params-grid">
                {[
                  ["epochs", form.epochs],
                  ["batch", form.batch],
                  ["patience", form.patience],
                  ["imgsz", form.imgsz],
                ].map(([key, val]) => (
                  <Elem name="param" key={key}>
                    <Elem name="param-label">{key}</Elem>
                    <Elem name="param-input">
                      <input
                        type="number"
                        value={val}
                        onChange={(e) => setForm({ ...form, [key]: Number(e.target.value) || 0 })}
                      />
                    </Elem>
                  </Elem>
                ))}
                <Elem name="param">
                  <Elem name="param-label">device</Elem>
                  <Elem name="param-input">
                    <input value={form.device} onChange={(e) => setForm({ ...form, device: e.target.value })} />
                  </Elem>
                </Elem>
              </Elem>
              {error && <Elem name="error">{error}</Elem>}
              <Space style={{ marginTop: 16 }}>
                {selectedId && (
                  <Button look="negative" onClick={deleteConfig}>删除</Button>
                )}
                <Button look="primary" waiting={saving} onClick={saveConfig}>保存</Button>
              </Space>
            </Elem>
          </Elem>
        </Elem>
      </Block>
    </Modal>
  );
};

const StartTrain = () => {
  const history = useHistory();
  const api = useAPI();
  const [configs, setConfigs] = useState([]);
  const [projects, setProjects] = useState([]);
  const [configName, setConfigName] = useState("");
  const [selectedProjectIds, setSelectedProjectIds] = useState([]);
  const [epochs, setEpochs] = useState(1000);
  const [batch, setBatch] = useState(16);
  const [patience, setPatience] = useState(200);
  const [imgsz, setImgsz] = useState(640);
  const [device, setDevice] = useState("0");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [configModal, setConfigModal] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");

  const loadConfigs = useCallback(() => {
    api.callApi("trainConfigs", {}).then((res) => {
      const list = Array.isArray(res) ? res : res?.data || res?.results || [];
      setConfigs(list);
      if (!configName && list.length) setConfigName(list[0].name);
    }).catch(() => {});
  }, [api, configName]);

  useEffect(() => {
    loadConfigs();
    api.callApi("projects", {
      params: {
        page: 1,
        page_size: 1000,
        include: ["id", "title", "num_tasks_with_annotations", "task_number"].join(","),
      },
    }).then((data) => {
      setProjects(data?.results || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const cfg = configs.find((c) => c.name === configName);
    if (cfg) {
      setEpochs(cfg.epochs || 1000);
      setBatch(cfg.batch || 16);
      setPatience(cfg.patience || 200);
      setImgsz(cfg.imgsz || 640);
      setDevice(cfg.device || "0");
    }
  }, [configName, configs]);

  const filteredProjects = useMemo(() => {
    const q = projectSearch.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter((p) => String(p.title || "").toLowerCase().includes(q) || String(p.id).includes(q));
  }, [projects, projectSearch]);

  const toggleProject = (id) => {
    setSelectedProjectIds((prev) => (
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    ));
  };

  const startTraining = async () => {
    if (!configName || !selectedProjectIds.length) return;
    setStarting(true);
    setError("");
    try {
      const job = await api.callApi("startTrain", {
        body: {
          config_name: configName,
          project_ids: selectedProjectIds,
          epochs,
          batch,
          patience,
          imgsz,
          device,
        },
        suppressError: true,
        errorFilter: () => true,
      });
      if (!job || job.error) {
        const msg = job?.response?.error || job?.error || "启动失败";
        setError(typeof msg === "string" ? msg : JSON.stringify(msg));
        return;
      }
      const jobId = job?.id;
      if (jobId) history.push(`/projects/train/tasks/${jobId}`);
      else history.push("/projects/train/tasks");
    } catch (e) {
      setError(e?.response?.error || e?.error || e?.detail || e?.message || "启动失败");
    } finally {
      setStarting(false);
    }
  };

  const configOptions = configs.map((c) => ({
    label: `${c.name} (${c.task_type}, ${(c.classes || []).join("/")})`,
    value: c.name,
  }));

  return (
    <Block name="training-page">
      <Elem name="panel">
        <Elem name="panel-title">启动训练</Elem>
        <Elem name="hint">
          可选择一个或多个项目，标注数据将合并为同一训练集。所选项目的标签类别必须与配置 classes 完全一致，否则会报错。
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
              options={configOptions}
            />
            <Button size="small" look="outlined" onClick={() => setConfigModal(true)}>
              管理配置
            </Button>
          </Elem>
        </Elem>

        <Elem name="section">
          <Elem name="label">
            训练项目（已选 {selectedProjectIds.length}）
          </Elem>
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
                <Elem
                  tag="label"
                  key={p.id}
                  name="project-option"
                >
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

        <Elem name="section">
          <Elem name="label">训练参数</Elem>
          <Elem name="params-grid">
            {[
              ["Epochs", epochs, setEpochs, "number"],
              ["Batch", batch, setBatch, "number"],
              ["Patience", patience, setPatience, "number"],
              ["Img Size", imgsz, setImgsz, "number"],
              ["Device", device, setDevice, "text"],
            ].map(([label, val, setter, type]) => (
              <Elem name="param" key={label}>
                <Elem name="param-label">{label}</Elem>
                <Elem name="param-input">
                  <input
                    type={type}
                    value={val}
                    onChange={(e) => setter(type === "number" ? Number(e.target.value) || 0 : e.target.value)}
                  />
                </Elem>
              </Elem>
            ))}
          </Elem>
        </Elem>

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

      <ConfigModal
        visible={configModal}
        onClose={() => setConfigModal(false)}
        onSaved={loadConfigs}
      />
    </Block>
  );
};

const TaskList = () => {
  const history = useHistory();
  const api = useAPI();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    const params = { page: 1, page_size: 50 };
    if (statusFilter) params.status = statusFilter;
    api.callApi("trainJobs", { params }).then((data) => {
      setJobs(data?.results || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [api, statusFilter]);

  useEffect(() => {
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, [load]);

  return (
    <Block name="training-page">
      <Elem name="panel">
        <Elem name="panel-header">
          <Elem name="panel-title" style={{ marginBottom: 0 }}>训练任务</Elem>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">全部状态</option>
            {Object.entries(STATUS_LABEL).filter(([k]) => k !== "none").map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
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
                  <Elem name="status-badge" mod={{ [job.status]: true }}>
                    {STATUS_LABEL[job.status] || job.status}
                  </Elem>
                </Elem>
                <Elem name="job-meta">
                  项目：{(job.project_titles || []).join("、") || "—"}
                </Elem>
                <Elem name="job-meta">
                  {job.created_by || "—"} · {job.created_at}
                  {isRunningStatus(job.status) ? ` · Epoch ${job.current_epoch}/${job.total_epochs} (${job.progress}%)` : ""}
                  {job.model_count ? ` · 模型 ${job.model_count}` : ""}
                </Elem>
                {job.error_message && (
                  <Elem name="job-error">{job.error_message}</Elem>
                )}
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
    const id = setInterval(() => {
      loadJob();
      loadLogs();
    }, 2500);
    return () => clearInterval(id);
  }, [jobId, loadJob, loadLogs]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const stopJob = async () => {
    if (!jobId || !confirm("确定停止该训练任务？")) return;
    setStopping(true);
    try {
      await api.callApi("stopTrainJob", { params: { job_id: jobId } });
      loadJob();
    } finally {
      setStopping(false);
    }
  };

  const clearLogs = async () => {
    await api.callApi("clearTrainJobLogs", { params: { job_id: jobId } });
    sinceRef.current = 0;
    setLogs([]);
  };

  const downloadModel = (model) => {
    window.open(`/api/train/models/${model.id}/download`, "_blank");
  };

  const deleteModel = async (modelId) => {
    if (!confirm("确定删除该模型文件？")) return;
    await api.callApi("deleteModel", { params: { mid: modelId } });
    loadJob();
  };

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

  return (
    <Block name="training-page">
      <Elem name="panel">
        <Elem name="panel-header">
          <Space>
            <Button size="small" look="outlined" onClick={() => history.push("/projects/train/tasks")}>
              ← 返回列表
            </Button>
            <Elem name="panel-title" style={{ marginBottom: 0 }}>
              任务 #{job.id}
            </Elem>
          </Space>
          {running && (
            <Button look="negative" size="small" waiting={stopping} onClick={stopJob}>
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
          <Elem name="detail-item" style={{ gridColumn: "1 / -1" }}>
            <Elem name="detail-label">训练参数</Elem>
            <Elem name="detail-value">
              <code>{JSON.stringify(job.params || {}, null, 0)}</code>
            </Elem>
          </Elem>
        </Elem>

        {running && (
          <Elem name="progress-section">
            <Elem name="progress-bar">
              <Elem name="progress-fill" style={{ width: `${job.progress || 0}%` }} />
            </Elem>
            <Elem name="progress-text">{job.progress || 0}%</Elem>
            <Elem name="epoch-text">
              Epoch {job.current_epoch}/{job.total_epochs}
            </Elem>
          </Elem>
        )}

        {job.error_message && (
          <Elem name="error-box">
            <Elem name="label">错误信息</Elem>
            <pre>{job.error_message}</pre>
          </Elem>
        )}

        {job.result && Object.keys(job.result).length > 0 && (
          <Elem name="section">
            <Elem name="label">评估指标</Elem>
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

        <Elem name="section">
          <Elem name="label">产出模型</Elem>
          {(job.models || []).length === 0 ? (
            <Elem name="empty">暂无模型</Elem>
          ) : (
            <Elem name="model-list">
              {job.models.map((model) => (
                <Elem name="model-card" key={model.id}>
                  <Elem name="model-name">{model.name}</Elem>
                  <Elem name="model-meta">
                    {model.created_at} · {formatSize(model.file_size)}
                  </Elem>
                  <Space>
                    <Button size="small" look="outlined" onClick={() => downloadModel(model)}>下载</Button>
                    <Button size="small" look="negative" onClick={() => deleteModel(model.id)}>删除</Button>
                  </Space>
                </Elem>
              ))}
            </Elem>
          )}
        </Elem>

        <Elem name="section">
          <Elem name="panel-header">
            <Elem name="label" style={{ marginBottom: 0 }}>训练日志</Elem>
            <Space>
              <input
                type="text"
                placeholder="搜索日志..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <Button size="small" look="outlined" onClick={clearLogs}>清空</Button>
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
  layout: TrainingLayout,
  component: StartTrain,
  pages: {
    tasks: { title: "任务", path: "/tasks", component: TaskList, exact: true },
    taskDetail: { path: "/tasks/:jobId", component: TaskDetail, exact: true },
  },
};
