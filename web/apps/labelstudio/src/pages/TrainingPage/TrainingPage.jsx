import { useCallback, useEffect, useRef, useState } from "react";
import { useHistory, useParams } from "react-router";
import { Button, Select } from "@humansignal/ui";
import { Space } from "../../components/Space/Space";
import { SidebarMenu } from "../../components/SidebarMenu/SidebarMenu";
import { useAPI } from "../../providers/ApiProvider";
import { Block, Elem } from "../../utils/bem";
import "./TrainingPage.scss";

const TABS = [
  { key: "start", label: "启动训练" },
  { key: "progress", label: "训练进度" },
  { key: "logs", label: "训练日志" },
  { key: "models", label: "模型管理" },
  { key: "configs", label: "配置管理" },
];

const TrainingLayout = ({ children, ...routeProps }) => {
  const params = useParams();
  return (
    <SidebarMenu
      menuItems={TABS.map((t) => ({
        title: t.label,
        path: `/train/${t.key}`,
      }))}
      path={`/projects/${params.id}/train`}
      children={children}
    />
  );
};

const StartTrain = () => {
  const history = useHistory();
  const pageParams = useParams();
  const api = useAPI();

  const [configs, setConfigs] = useState([]);
  const [configName, setConfigName] = useState("");
  const [epochs, setEpochs] = useState(1000);
  const [batch, setBatch] = useState(16);
  const [patience, setPatience] = useState(200);
  const [imgsz, setImgsz] = useState(640);
  const [device, setDevice] = useState("0");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [jobStatus, setJobStatus] = useState("none");

  const isRunning = jobStatus === "building" || jobStatus === "training" || jobStatus === "pending";

  useEffect(() => {
    api.callApi("trainConfigs", {}).then((res) => {
      setConfigs(Array.isArray(res) ? res : (res?.data || res?.results || []));
    }).catch(() => {});
    api.callApi("trainStatus", { params: { pk: pageParams.id } }).then((data) => {
      setJobStatus(data?.status || "none");
    }).catch(() => {});
  }, [api, pageParams.id]);

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

  const startTraining = async () => {
    if (!configName) return;
    setStarting(true);
    setError("");
    try {
      await api.callApi("startTrain", {
        params: { pk: pageParams.id },
        body: { config_name: configName, epochs, batch, patience, imgsz, device },
      });
      history.push(`/projects/${pageParams.id}/train/progress`);
    } catch (e) {
      setError(e?.response?.detail || e?.detail || "启动失败");
    } finally {
      setStarting(false);
    }
  };

  const configOptions = configs.map((c) => ({
    label: `${c.name} (${c.task_type}, ${c.classes.join("/")})`,
    value: c.name,
  }));

  return (
    <Block name="training-page">
      <Elem name="panel">
        <Elem name="panel-title">启动新训练</Elem>

        <Elem name="section">
          <Elem name="label">模型配置</Elem>
          <Elem name="select-row">
            <Select
              value={configName}
              onChange={(val) => setConfigName(val)}
              disabled={isRunning}
              searchable={true}
              searchPlaceholder="搜索模型..."
              placeholder="-- 请选择 --"
              options={configOptions}
            />
            <Button size="small" look="outlined" onClick={() => history.push(`/projects/${pageParams.id}/train/configs`)}>
              + 新建
            </Button>
          </Elem>
        </Elem>

        <Elem name="section">
          <Elem name="label">训练参数（留空使用默认值）</Elem>
          <Elem name="params-grid">
            {[
              ["Epochs", epochs, setEpochs],
              ["Batch", batch, setBatch],
              ["Patience", patience, setPatience],
              ["Img Size", imgsz, setImgsz],
              ["Device", device, setDevice],
            ].map(([label, val, setter]) => (
              <Elem name="param" key={label}>
                <Elem name="param-label">{label}</Elem>
                <Elem name="param-input">
                  <input
                    type={typeof val === "number" ? "number" : "text"}
                    value={val}
                    onChange={(e) => setter(typeof val === "number" ? Number(e.target.value) || 0 : e.target.value)}
                    disabled={isRunning}
                  />
                </Elem>
              </Elem>
            ))}
          </Elem>
        </Elem>

        {error && <Elem name="error">{error}</Elem>}

        <Space style={{ marginTop: 20 }}>
          <Button look="primary" onClick={startTraining} waiting={starting} disabled={!configName || isRunning}>
            开始训练
          </Button>
        </Space>
      </Elem>
    </Block>
  );
};

const TrainProgress = () => {
  const pageParams = useParams();
  const api = useAPI();

  const [jobStatus, setJobStatus] = useState("none");
  const [jobProgress, setJobProgress] = useState(0);
  const [jobCurrentEpoch, setJobCurrentEpoch] = useState(0);
  const [jobTotalEpochs, setJobTotalEpochs] = useState(0);
  const [jobResult, setJobResult] = useState(null);
  const pollingRef = useRef(null);

  const isRunning = jobStatus === "building" || jobStatus === "training" || jobStatus === "pending";

  const pollStatus = useCallback(() => {
    api.callApi("trainStatus", { params: { pk: pageParams.id } }).then((data) => {
      if (!data || data.status === "none") {
        setJobStatus("none");
        return;
      }
      setJobStatus(data.status);
      setJobProgress(data.progress || 0);
      setJobCurrentEpoch(data.current_epoch || 0);
      setJobTotalEpochs(data.total_epochs || 0);
      setJobResult(data.result || null);
    }).catch(() => {});
  }, [api, pageParams.id]);

  useEffect(() => {
    pollStatus();
    if (isRunning) {
      const id = setInterval(pollStatus, 2000);
      pollingRef.current = id;
      return () => clearInterval(id);
    }
  }, [jobStatus, pollStatus]);

  const stopTraining = async () => {
    await api.callApi("stopTrain", { params: { pk: pageParams.id } });
    pollStatus();
  };

  const getStatusClass = () => {
    if (jobStatus === "completed") return "completed";
    if (jobStatus === "failed") return "failed";
    if (jobStatus === "stopped") return "stopped";
    return "training";
  };

  const getStatusText = () => {
    if (jobStatus === "none") return "无训练任务";
    if (jobStatus === "completed") return "训练完成";
    if (jobStatus === "failed") return "训练失败";
    if (jobStatus === "stopped") return "训练已停止";
    return `训练中 - Epoch ${jobCurrentEpoch}/${jobTotalEpochs}`;
  };

  return (
    <Block name="training-page">
      <Elem name="panel">
        <Elem name="panel-title">训练进度</Elem>

        <Elem name={`status-badge status-badge_${getStatusClass()}`}>{getStatusText()}</Elem>

        {isRunning && (
          <>
            <Elem name="progress-section">
              <Elem name="progress-bar">
                <Elem name="progress-fill" style={{ width: `${jobProgress}%` }} />
              </Elem>
              <Elem name="progress-text">{jobProgress}%</Elem>
            </Elem>
            <Elem name="epoch-text">
              当前进度：第 {jobCurrentEpoch} 轮 / 共 {jobTotalEpochs} 轮
            </Elem>
          </>
        )}

        {jobResult && (
          <Elem name="metrics">
            {Object.entries(jobResult).map(([key, val]) => (
              <Elem name="metric-row" key={key}>
                <Elem name="metric-key">{key}</Elem>
                <Elem name="metric-val">{typeof val === "number" ? val.toFixed(4) : val}</Elem>
              </Elem>
            ))}
          </Elem>
        )}

        {isRunning && (
          <Space style={{ marginTop: 20 }}>
            <Button look="negative" onClick={stopTraining}>
              停止训练
            </Button>
          </Space>
        )}
      </Elem>
    </Block>
  );
};

const TrainLogs = () => {
  const pageParams = useParams();
  const api = useAPI();

  const [logs, setLogs] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const logContainerRef = useRef(null);

  const loadLogs = useCallback(() => {
    api.callApi("trainLogs", { params: { pk: pageParams.id } }).then((data) => {
      setLogs(Array.isArray(data) ? data : (data?.logs || []));
    }).catch(() => {});
  }, [api, pageParams.id]);

  useEffect(() => {
    loadLogs();
    const id = setInterval(loadLogs, 3000);
    return () => clearInterval(id);
  }, [loadLogs]);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const filteredLogs = logs.filter((log) =>
    log.message?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const clearLogs = async () => {
    await api.callApi("clearTrainLogs", { params: { pk: pageParams.id } });
    setLogs([]);
  };

  return (
    <Block name="training-page">
      <Elem name="panel">
        <Elem name="panel-title">训练日志</Elem>

        <Elem name="log-toolbar">
          <input
            type="text"
            placeholder="搜索日志..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ flex: 1 }}
          />
          <Button size="small" look="outlined" onClick={clearLogs}>
            清空日志
          </Button>
        </Elem>

        <Elem name="log-viewer" ref={logContainerRef}>
          {filteredLogs.length === 0 ? (
            <Elem name="empty">暂无日志</Elem>
          ) : (
            filteredLogs.map((log, idx) => (
              <Elem name="log-line" key={idx}>
                <Elem name="log-time">[{log.time}]</Elem>
                <Elem name="log-msg">{log.message}</Elem>
              </Elem>
            ))
          )}
        </Elem>
      </Elem>
    </Block>
  );
};

const ModelManagement = () => {
  const pageParams = useParams();
  const api = useAPI();

  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadModels = useCallback(() => {
    setLoading(true);
    api.callApi("trainModels", { params: { pk: pageParams.id } }).then((res) => {
      setModels(Array.isArray(res) ? res : (res?.data || res?.results || []));
    }).catch(() => {}).finally(() => setLoading(false));
  }, [api, pageParams.id]);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const deleteModel = async (modelId) => {
    if (!confirm("确定要删除这个模型吗？")) return;
    await api.callApi("deleteTrainModel", { params: { pk: pageParams.id, model_id: modelId } });
    loadModels();
  };

  const downloadModel = (model) => {
    window.open(`/api/projects/${pageParams.id}/training/models/${model.id}/download`);
  };

  return (
    <Block name="training-page">
      <Elem name="panel">
        <Elem name="panel-title">模型管理</Elem>

        <Space style={{ marginBottom: 16 }}>
          <Button look="outlined" onClick={() => {}}>
            + 导入模型
          </Button>
        </Space>

        {loading ? (
          <Elem name="empty">加载中...</Elem>
        ) : models.length === 0 ? (
          <Elem name="empty">暂无模型</Elem>
        ) : (
          <Elem name="model-list">
            {models.map((model) => (
              <Elem name="model-card" key={model.id}>
                <Elem name="model-name">{model.name}</Elem>
                <Elem name="model-meta">
                  {model.created_at} | epochs: {model.epochs}
                </Elem>
                {model.metrics && (
                  <Elem name="model-metrics">
                    {Object.entries(model.metrics).slice(0, 3).map(([key, val]) => (
                      <Elem name="metric-tag" key={key}>
                        {key}: {typeof val === "number" ? val.toFixed(3) : val}
                      </Elem>
                    ))}
                  </Elem>
                )}
                <Space>
                  <Button size="small" look="outlined" onClick={() => downloadModel(model)}>
                    下载
                  </Button>
                  <Button size="small" look="negative" onClick={() => deleteModel(model.id)}>
                    删除
                  </Button>
                </Space>
              </Elem>
            ))}
          </Elem>
        )}
      </Elem>
    </Block>
  );
};

const ConfigManagement = () => {
  const pageParams = useParams();
  const api = useAPI();

  const [configs, setConfigs] = useState([]);
  const [selectedConfig, setSelectedConfig] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [formData, setFormData] = useState({
    name: "",
    task_type: "obb",
    pretrained: "",
    classes: "",
    epochs: 1000,
    batch: 16,
    patience: 200,
    imgsz: 640,
    device: "0",
  });

  const loadConfigs = useCallback(() => {
    api.callApi("trainConfigs", {}).then((res) => {
      const list = Array.isArray(res) ? res : (res?.data || res?.results || []);
      setConfigs(list);
      if (list.length > 0 && !selectedConfig) {
        setSelectedConfig(list[0]);
        setFormData({
          name: list[0].name,
          task_type: list[0].task_type,
          pretrained: list[0].pretrained || "",
          classes: list[0].classes?.join(", ") || "",
          epochs: list[0].epochs || 1000,
          batch: list[0].batch || 16,
          patience: list[0].patience || 200,
          imgsz: list[0].imgsz || 640,
          device: list[0].device || "0",
        });
      }
    }).catch(() => {});
  }, [api, selectedConfig]);

  useEffect(() => {
    loadConfigs();
  }, [loadConfigs]);

  const filteredConfigs = configs.filter((c) =>
    c.name?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const selectConfig = (config) => {
    setSelectedConfig(config);
    setFormData({
      name: config.name,
      task_type: config.task_type,
      pretrained: config.pretrained || "",
      classes: config.classes?.join(", ") || "",
      epochs: config.epochs || 1000,
      batch: config.batch || 16,
      patience: config.patience || 200,
      imgsz: config.imgsz || 640,
      device: config.device || "0",
    });
  };

  const saveConfig = async () => {
    await api.callApi("saveTrainConfig", {
      body: {
        ...formData,
        classes: formData.classes.split(",").map((c) => c.trim()).filter(Boolean),
      },
    });
    loadConfigs();
  };

  const deleteConfig = async () => {
    if (!selectedConfig) return;
    if (!confirm("确定要删除这个配置吗？")) return;
    await api.callApi("deleteTrainConfig", { params: { config_name: selectedConfig.name } });
    setSelectedConfig(null);
    loadConfigs();
  };

  return (
    <Block name="training-page">
      <Elem name="panel">
        <Elem name="panel-title">配置管理</Elem>

        <Space style={{ marginBottom: 16 }}>
          <Button look="outlined" onClick={() => {}}>
            + 新建配置
          </Button>
        </Space>

        <input
          type="text"
          placeholder="搜索配置..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{ width: "100%", marginBottom: 16 }}
        />

        <Elem name="config-list">
          {filteredConfigs.map((config) => (
            <Elem
              name="config-item"
              key={config.name}
              mod={{ selected: selectedConfig?.name === config.name }}
              onClick={() => selectConfig(config)}
            >
              <Elem name="config-name">{config.name}</Elem>
              <Elem name="config-type">{config.task_type}</Elem>
              <Elem name="config-classes">{config.classes?.join(", ")}</Elem>
            </Elem>
          ))}
        </Elem>

        {selectedConfig && (
          <Elem name="config-detail">
            <Elem name="panel-title" style={{ fontSize: 16, marginBottom: 16 }}>
              配置详情
            </Elem>

            <Elem name="section">
              <Elem name="label">配置名称</Elem>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                style={{ width: "100%" }}
              />
            </Elem>

            <Elem name="form-row">
              <Elem name="form-item">
                <Elem name="label">任务类型</Elem>
                <select
                  value={formData.task_type}
                  onChange={(e) => setFormData({ ...formData, task_type: e.target.value })}
                  style={{ width: "100%" }}
                >
                  <option value="obb">obb (旋转边界框)</option>
                  <option value="detect">detect (目标检测)</option>
                  <option value="segment">segment (实例分割)</option>
                  <option value="classify">classify (分类)</option>
                </select>
              </Elem>
              <Elem name="form-item">
                <Elem name="label">预训练权重</Elem>
                <input
                  type="text"
                  value={formData.pretrained}
                  onChange={(e) => setFormData({ ...formData, pretrained: e.target.value })}
                  style={{ width: "100%" }}
                />
              </Elem>
            </Elem>

            <Elem name="section">
              <Elem name="label">类别列表（逗号分隔）</Elem>
              <textarea
                value={formData.classes}
                onChange={(e) => setFormData({ ...formData, classes: e.target.value })}
                style={{ width: "100%", height: 80, resize: "vertical" }}
              />
            </Elem>

            <Space style={{ marginTop: 20 }}>
              <Button look="negative" onClick={deleteConfig}>
                删除配置
              </Button>
              <Button look="primary" onClick={saveConfig}>
                保存配置
              </Button>
            </Space>
          </Elem>
        )}
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
    start: StartTrain,
    progress: TrainProgress,
    logs: TrainLogs,
    models: ModelManagement,
    configs: ConfigManagement,
  },
};
