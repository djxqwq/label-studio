import { useCallback, useEffect, useRef, useState } from "react";
import { useHistory } from "react-router";
import { Button, Select } from "@humansignal/ui";
import { Space } from "../../components/Space/Space";
import { Modal } from "../../components/Modal/Modal";
import { useAPI } from "../../providers/ApiProvider";
import { useFixedLocation, useParams } from "../../providers/RoutesProvider";
import { BemWithSpecifiContext } from "../../utils/bem";
import "./TrainingPage.scss";

const { Block, Elem } = BemWithSpecifiContext();

const TABS = [
  { key: "train", label: "启动训练" },
  { key: "progress", label: "训练进度" },
  { key: "logs", label: "训练日志" },
  { key: "models", label: "模型管理" },
];

export const TrainingPage = () => {
  const history = useHistory();
  const location = useFixedLocation();
  const pageParams = useParams();
  const api = useAPI();

  const [activeTab, setActiveTab] = useState("train");
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
  const [jobProgress, setJobProgress] = useState(0);
  const [jobCurrentEpoch, setJobCurrentEpoch] = useState(0);
  const [jobTotalEpochs, setJobTotalEpochs] = useState(0);
  const [jobResult, setJobResult] = useState(null);

  const [logs, setLogs] = useState([]);
  const [lastLogId, setLastLogId] = useState(0);
  const logEndRef = useRef(null);
  const pollingRef = useRef(null);

  const [models, setModels] = useState([]);

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newTaskType, setNewTaskType] = useState("obb");
  const [newClasses, setNewClasses] = useState("");
  const [newEpochs, setNewEpochs] = useState(1000);
  const [newBatch, setNewBatch] = useState(16);
  const [newImgsz, setNewImgsz] = useState(640);
  const [newDevice, setNewDevice] = useState("0");
  const [creating, setCreating] = useState(false);

  const isRunning = jobStatus === "building" || jobStatus === "training" || jobStatus === "pending";

  const loadConfigs = () => {
    api.callApi("trainConfigs", {}).then((res) => {
      setConfigs(Array.isArray(res) ? res : (res?.data || res?.results || []));
    }).catch(() => {});
  };

  const loadModels = () => {
    api.callApi("trainModels", { params: { pk: pageParams.id } }).then((res) => {
      setModels(Array.isArray(res) ? res : []);
    }).catch(() => {});
  };

  const pollStatus = useCallback(() => {
    api.callApi("trainStatus", { params: { pk: pageParams.id } }).then((data) => {
      if (!data || data.status === "none") { setJobStatus("none"); return; }
      const prevStatus = jobStatus;
      setJobStatus(data.status);
      setJobProgress(data.progress || 0);
      setJobCurrentEpoch(data.current_epoch || 0);
      setJobTotalEpochs(data.total_epochs || 0);
      setJobResult(data.result || null);
      // 训练完成/失败时，重新加载模型列表
      if ((data.status === "completed" || data.status === "failed") && prevStatus !== data.status) {
        loadModels();
      }
    }).catch(() => {});
  }, [api, pageParams.id, jobStatus]);

  const pollLogs = useCallback(() => {
    api.callApi("trainLogs", { params: { pk: pageParams.id, since: lastLogId } }).then((data) => {
      const entries = data?.logs || [];
      if (entries.length) {
        setLogs((prev) => [...prev, ...entries]);
        setLastLogId(entries[entries.length - 1].id);
      }
    }).catch(() => {});
  }, [api, pageParams.id, lastLogId]);

  useEffect(() => {
    if (!pageParams.id) return;
    loadConfigs(); loadModels(); pollStatus();
  }, [pageParams]);

  useEffect(() => {
    if (isRunning) {
      const id = setInterval(() => { pollStatus(); pollLogs(); }, 2000);
      pollingRef.current = id;
      return () => clearInterval(id);
    }
  }, [jobStatus, pollStatus, pollLogs]);

  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [logs]);

  useEffect(() => {
    const cfg = configs.find((c) => c.name === configName);
    if (cfg) {
      setEpochs(cfg.epochs || 1000); setBatch(cfg.batch || 16);
      setPatience(cfg.patience || 200); setImgsz(cfg.imgsz || 640); setDevice(cfg.device || "0");
    }
  }, [configName, configs]);

  const startTraining = async () => {
    if (!configName) return;
    setStarting(true); setError("");
    try {
      await api.callApi("startTrain", {
        params: { pk: pageParams.id },
        body: { config_name: configName, epochs, batch, patience, imgsz, device },
      });
      await pollStatus();
      setActiveTab("progress");
    } catch (e) {
      setError(e?.response?.detail || e?.detail || "启动失败");
    } finally { setStarting(false); }
  };

  const stopTraining = async () => { await api.callApi("stopTrain", { params: { pk: pageParams.id } }); pollStatus(); };

  const createConfig = async () => {
    if (!newName || !newClasses.trim()) return;
    setCreating(true);
    try {
      await api.callApi("createTrainConfig", {
        body: { name: newName, task_type: newTaskType,
          classes: newClasses.split(",").map((s) => s.trim()).filter(Boolean),
          epochs: newEpochs, batch: newBatch, imgsz: newImgsz, device: newDevice },
      });
      setShowCreate(false); setNewName(""); setNewClasses("");
      loadConfigs(); setConfigName(newName);
    } catch (e) { alert(e?.response?.detail || e?.detail || "创建失败"); }
    finally { setCreating(false); }
  };

  const deleteConfig = async () => {
    const cfg = configs.find((c) => c.name === configName);
    if (!cfg || !confirm(`确定删除「${cfg.name}」？`)) return;
    await api.callApi("deleteTrainConfig", { params: { pk: cfg.id } });
    setConfigName(""); loadConfigs();
  };

  const downloadModel = (m) => {
    const url = `/api/projects/${pageParams.id}/train/models/${m.id}/download`;
    const a = document.createElement("a"); a.href = url; a.download = m.name;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  };

  const deleteModel = async (m) => {
    if (!confirm(`确定删除「${m.name}」？`)) return;
    await api.callApi("deleteModel", { params: { pk: pageParams.id, mid: m.id } }); loadModels();
  };

  const close = () => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    const path = location.pathname.replace("/data/train", "/data");
    history.replace(`${path}${location.search !== "?" ? location.search : ""}`);
  };

  const configOptions = configs.map((c) => ({
    label: `${c.name} (${c.task_type}, ${c.classes.join("/")})`,
    value: c.name,
  }));

  return (
    <Modal onHide={close} title="模型训练" style={{ width: 900 }} visible
      closeOnClickOutside={false} allowClose={!isRunning}>
      <Block name="training-page">
        <Elem name="body">
          <Elem name="sidebar">
            {TABS.map((t) => (
              <Elem name="menu-item" key={t.key} mod={{ active: activeTab === t.key }}
                onClick={() => setActiveTab(t.key)}>
                {t.label}
                {t.key === "progress" && isRunning && <Elem name="menu-badge">运行中</Elem>}
                {t.key === "models" && models.length > 0 && <Elem name="menu-count">{models.length}</Elem>}
              </Elem>
            ))}
          </Elem>

          <Elem name="content">

            {/* ======== 启动训练 ======== */}
            {activeTab === "train" && (
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
                    <Button size="small" look="outlined" onClick={() => setShowCreate(true)} disabled={isRunning}>+ 新建</Button>
                    {configName && <Button size="small" look="outlined" onClick={deleteConfig} disabled={isRunning}>删除</Button>}
                  </Elem>
                </Elem>

                <Elem name="section">
                  <Elem name="label">训练参数（留空使用默认值）</Elem>
                  <Elem name="params-grid">
                    {[["Epochs", epochs, setEpochs],["Batch", batch, setBatch],["Patience", patience, setPatience],["Img Size", imgsz, setImgsz],["Device", device, setDevice]]
                      .map(([label, val, setter]) => (
                        <Elem name="param" key={label}>
                          <Elem name="param-label">{label}</Elem>
                          <Elem name="param-input">
                            <input type={typeof val === "number" ? "number" : "text"} value={val}
                              onChange={(e) => setter(typeof val === "number" ? (Number(e.target.value) || 0) : e.target.value)}
                              disabled={isRunning} />
                          </Elem>
                        </Elem>
                      ))}
                  </Elem>
                </Elem>
                {error && <Elem name="error">{error}</Elem>}
                <Space style={{ marginTop: 20 }}>
                  <Button look="primary" onClick={startTraining} waiting={starting}
                    disabled={!configName || isRunning}>开始训练</Button>
                  {isRunning && <Button look="danger" onClick={stopTraining}>终止训练</Button>}
                </Space>

                {showCreate && (
                  <Elem name="create-form">
                    <Elem name="label">新建模型配置</Elem>
                    <Elem name="form-row">
                      <Elem name="form-item">
                        <Elem name="param-label">名称</Elem>
                        <Elem name="param-input"><input value={newName} onChange={(e) => setNewName(e.target.value)}
                          placeholder="如 apple-obb" disabled={creating} /></Elem>
                      </Elem>
                      <Elem name="form-item">
                        <Elem name="param-label">类型</Elem>
                        <Select value={newTaskType} onChange={(val) => setNewTaskType(val)} disabled={creating}
                          options={[{ label: "OBB", value: "obb" },{ label: "Detect", value: "detect" },{ label: "分类", value: "cls" },{ label: "分割", value: "seg" }]} />
                      </Elem>
                    </Elem>
                    <Elem name="form-item" style={{ marginTop: 10 }}>
                      <Elem name="param-label">类别（逗号分隔）</Elem>
                      <Elem name="param-input"><input value={newClasses} onChange={(e) => setNewClasses(e.target.value)}
                        placeholder="如 apple, banana" disabled={creating} /></Elem>
                    </Elem>
                    <Elem name="params-grid" style={{ marginTop: 10 }}>
                      {[["Epochs", newEpochs, setNewEpochs],["Batch", newBatch, setNewBatch],["ImgSz", newImgsz, setNewImgsz],["Device", newDevice, setNewDevice]]
                        .map(([label, val, setter]) => (
                          <Elem name="param" key={label}>
                            <Elem name="param-label">{label}</Elem>
                            <Elem name="param-input">
                              <input type={typeof val === "number" ? "number" : "text"} value={val}
                                onChange={(e) => setter(typeof val === "number" ? (Number(e.target.value) || 0) : e.target.value)}
                                disabled={creating} />
                            </Elem>
                          </Elem>
                        ))}
                    </Elem>
                    <Space style={{ marginTop: 12 }}>
                      <Button size="small" look="primary" onClick={createConfig} waiting={creating}>创建</Button>
                      <Button size="small" onClick={() => setShowCreate(false)} disabled={creating}>取消</Button>
                    </Space>
                  </Elem>
                )}
              </Elem>
            )}

            {/* ======== 训练进度 ======== */}
            {activeTab === "progress" && (
              <Elem name="panel">
                <Elem name="panel-title">训练进度</Elem>
                {jobStatus === "none" ? (
                  <Elem name="empty">暂无训练任务，请先在"启动训练"中发起训练</Elem>
                ) : (
                  <>
                    <Elem name="status-badge" mod={{ [jobStatus]: true }}>
                      {jobStatus === "building" && "构建数据集中..."}
                      {jobStatus === "training" && "训练中..."}
                      {jobStatus === "completed" && "已完成"}
                      {jobStatus === "failed" && "失败"}
                      {jobStatus === "stopped" && "已停止"}
                      {jobStatus === "pending" && "排队中..."}
                    </Elem>
                    {(jobStatus === "training" || jobStatus === "completed") && (
                      <Elem name="progress-section">
                        <Elem name="progress-bar"><Elem name="progress-fill" style={{ width: `${jobProgress}%` }} /></Elem>
                        <Elem name="progress-text">{jobProgress}%</Elem>
                      </Elem>
                    )}
                    {jobStatus === "training" && (
                      <Elem name="epoch-text">Epoch {jobCurrentEpoch}/{jobTotalEpochs}</Elem>
                    )}
                    {jobResult && jobStatus === "completed" && (
                      <Elem name="metrics">
                        <Elem name="label">评估指标</Elem>
                        {Object.entries(jobResult).map(([k, v]) => (
                          <Elem name="metric-row" key={k}>
                            <Elem name="metric-key">{k}:</Elem>
                            <Elem name="metric-val">{typeof v === "number" ? v.toFixed(4) : String(v)}</Elem>
                          </Elem>
                        ))}
                      </Elem>
                    )}
                  </>
                )}
              </Elem>
            )}

            {/* ======== 训练日志 ======== */}
            {activeTab === "logs" && (
              <Elem name="panel">
                <Elem name="panel-title">训练日志</Elem>
                <Elem name="log-viewer">
                  {logs.length === 0 && <Elem name="empty" style={{ color: "#888" }}>暂无日志</Elem>}
                  {logs.map((l) => (
                    <Elem name="log-line" key={l.id}>
                      <Elem name="log-time">{l.created_at?.substring(0, 19) || ""}</Elem>
                      <Elem name="log-msg">{l.message}</Elem>
                    </Elem>
                  ))}
                  <div ref={logEndRef} />
                </Elem>
              </Elem>
            )}

            {/* ======== 模型管理 ======== */}
            {activeTab === "models" && (
              <Elem name="panel">
                <Elem name="panel-title">已训练模型</Elem>
                {models.length === 0 ? (
                  <Elem name="empty">暂无已训练的模型</Elem>
                ) : (
                  <Elem name="model-list">
                    {models.map((m) => (
                      <Elem name="model-card" key={m.id}>
                        <Elem name="model-name">{m.name}</Elem>
                        <Elem name="model-meta">{m.created_at} &middot; {(m.file_size / 1024 / 1024).toFixed(1)} MB</Elem>
                        {m.metrics && Object.keys(m.metrics).length > 0 && (
                          <Elem name="model-metrics">
                            {Object.entries(m.metrics).slice(0, 4).map(([k, v]) => (
                              <Elem name="metric-tag" key={k}>
                                {k.replace("metrics/", "").replace(/(B)/, "")}: {typeof v === "number" ? v.toFixed(3) : v}
                              </Elem>
                            ))}
                          </Elem>
                        )}
                        <Space style={{ marginTop: 8 }}>
                          <Button size="small" look="primary" onClick={() => downloadModel(m)}>下载</Button>
                          <Button size="small" look="danger" onClick={() => deleteModel(m)}>删除</Button>
                        </Space>
                      </Elem>
                    ))}
                  </Elem>
                )}
              </Elem>
            )}
          </Elem>
        </Elem>
      </Block>
    </Modal>
  );
};

TrainingPage.path = "/train";
TrainingPage.modal = true;
