import { useEffect, useState } from "react";
import { useHistory } from "react-router";
import { Button, Select } from "@humansignal/ui";
import { Modal } from "../../components/Modal/Modal";
import { Space } from "../../components/Space/Space";
import { useAPI } from "../../providers/ApiProvider";
import { useFixedLocation, useParams } from "../../providers/RoutesProvider";
import { BemWithSpecifiContext } from "../../utils/bem";
import "./TrainingPage.scss";

const { Block, Elem } = BemWithSpecifiContext();

export const TrainingPage = () => {
  const history = useHistory();
  const location = useFixedLocation();
  const pageParams = useParams();
  const api = useAPI();

  const [configs, setConfigs] = useState([]);
  const [search, setSearch] = useState("");
  const [configName, setConfigName] = useState("");
  const [epochs, setEpochs] = useState(1000);
  const [batch, setBatch] = useState(16);
  const [patience, setPatience] = useState(200);
  const [imgsz, setImgsz] = useState(640);
  const [device, setDevice] = useState("0");
  const [training, setTraining] = useState(false);
  const [jobStatus, setJobStatus] = useState("idle");
  const [error, setError] = useState("");

  // 新建配置
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newTaskType, setNewTaskType] = useState("obb");
  const [newClasses, setNewClasses] = useState("");
  const [newEpochs, setNewEpochs] = useState(1000);
  const [newBatch, setNewBatch] = useState(16);
  const [newImgsz, setNewImgsz] = useState(640);
  const [newDevice, setNewDevice] = useState("0");
  const [creating, setCreating] = useState(false);

  const loadConfigs = () => {
    api.callApi("trainConfigs", {}).then((res) => {
      const data = Array.isArray(res) ? res : (res?.data || res?.results || []);
      setConfigs(data);
    }).catch(() => {});
  };

  useEffect(() => {
    if (pageParams.id) loadConfigs();
  }, [pageParams]);

  // 选模型时，自动填入默认参数
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
    setTraining(true);
    setError("");
    try {
      await api.callApi("startTrain", {
        params: { pk: pageParams.id },
        body: { config_name: configName, epochs, batch, patience, imgsz, device },
      });
      setJobStatus("training");
    } catch (e) {
      setError(e?.detail || "启动训练失败");
      setTraining(false);
    }
  };

  const createConfig = async () => {
    if (!newName || !newClasses.trim()) return;
    setCreating(true);
    try {
      await api.callApi("createTrainConfig", {
        body: {
          name: newName,
          task_type: newTaskType,
          classes: newClasses.split(",").map((s) => s.trim()).filter(Boolean),
          epochs: newEpochs,
          batch: newBatch,
          imgsz: newImgsz,
          device: newDevice,
        },
      });
      setShowCreate(false);
      setNewName(""); setNewClasses("");
      loadConfigs();
      setConfigName(newName);
    } catch (e) {
      alert(e?.detail || "创建失败");
    } finally {
      setCreating(false);
    }
  };

  const deleteConfig = async () => {
    const cfg = configs.find((c) => c.name === configName);
    if (!cfg || !confirm(`确定删除配置「${cfg.name}」？`)) return;
    await api.callApi("deleteTrainConfig", { params: { pk: cfg.id } });
    setConfigName("");
    loadConfigs();
  };

  const close = () => {
    const path = location.pathname.replace(TrainingPage.path, "");
    history.replace(`${path}${location.search !== "?" ? location.search : ""}`);
  };

  return (
    <Modal onHide={close} title="模型训练" style={{ width: 600 }} visible
      closeOnClickOutside={false} allowClose={!training}>

      <Block name="training-page">

        {/* ---- 选模型 ---- */}
        <Elem name="section">
          <Elem name="label">模型配置</Elem>
          <Elem name="search-box">
            <input type="text" placeholder="搜索模型名或类别..." value={search}
              onChange={(e) => setSearch(e.target.value)} disabled={training} />
          </Elem>
          <Elem name="select-row">
            <Select value={configName} onChange={(val) => setConfigName(val)}
              disabled={training}
              options={[
                { label: "-- 请选择 --", value: "" },
                ...configs
                  .filter((c) => {
                    if (!search) return true;
                    const kw = search.toLowerCase();
                    return c.name.toLowerCase().includes(kw) ||
                      c.classes.some((cls) => cls.toLowerCase().includes(kw)) ||
                      c.task_type.toLowerCase().includes(kw);
                  })
                  .map((c) => ({ label: `${c.name} (${c.task_type}, ${c.classes.join("/")})`, value: c.name })),
              ]}
            />
            <Button size="small" look="outlined" onClick={() => setShowCreate(true)} disabled={training}>
              + 新建
            </Button>
            {configName && (
              <Button size="small" look="outlined" onClick={deleteConfig} disabled={training}>
                删除
              </Button>
            )}
          </Elem>
        </Elem>

        {/* ---- 训练参数 ---- */}
        <Elem name="section">
          <Elem name="label">训练参数（可选，留空使用模型默认值）</Elem>
          <Elem name="params-row">
            {[
              ["Epochs", epochs, setEpochs, 1],
              ["Batch", batch, setBatch, 1],
              ["Patience", patience, setPatience, 1],
            ].map(([label, val, setter, min]) => (
              <Elem name="param" key={label}>
                <Elem name="param-label">{label}</Elem>
                <Elem name="param-input">
                  <input type="number" value={val} onChange={(e) => setter(Number(e.target.value) || 0)}
                    disabled={training} min={min} />
                </Elem>
              </Elem>
            ))}
          </Elem>
          <Elem name="params-row" style={{ marginTop: 10 }}>
            {[
              ["Img Size", imgsz, setImgsz, 32],
              ["Device", device, setDevice, null],
            ].map(([label, val, setter, min]) => (
              <Elem name="param" key={label}>
                <Elem name="param-label">{label}</Elem>
                <Elem name="param-input">
                  {min ? (
                    <input type="number" value={val} onChange={(e) => setter(Number(e.target.value) || 0)}
                      disabled={training} min={min} />
                  ) : (
                    <input type="text" value={val} onChange={(e) => setter(e.target.value)}
                      disabled={training} />
                  )}
                </Elem>
              </Elem>
            ))}
            <Elem name="param" />
          </Elem>
        </Elem>

        {/* ---- 新建配置表单 ---- */}
        {showCreate && (
          <Elem name="create-form">
            <Elem name="label">新建模型配置</Elem>
            <Elem name="form-row">
              <Elem name="form-item">
                <Elem name="param-label">名称</Elem>
                <Elem name="param-input">
                  <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)}
                    placeholder="如 apple-obb" disabled={creating} />
                </Elem>
              </Elem>
              <Elem name="form-item">
                <Elem name="param-label">任务类型</Elem>
                <Select value={newTaskType} onChange={(val) => setNewTaskType(val)}
                  disabled={creating}
                  options={[
                    { label: "OBB 旋转检测", value: "obb" },
                    { label: "目标检测", value: "detect" },
                    { label: "分类", value: "cls" },
                    { label: "分割", value: "seg" },
                  ]}
                />
              </Elem>
            </Elem>
            <Elem name="form-item" style={{ marginTop: 10 }}>
              <Elem name="param-label">类别（逗号分隔）</Elem>
              <Elem name="param-input">
                <input type="text" value={newClasses} onChange={(e) => setNewClasses(e.target.value)}
                  placeholder="如 apple, banana" disabled={creating} />
              </Elem>
            </Elem>
            <Elem name="params-row" style={{ marginTop: 10 }}>
              {[
                ["默认 Epochs", newEpochs, setNewEpochs, 1],
                ["默认 Batch", newBatch, setNewBatch, 1],
                ["默认 ImgSz", newImgsz, setNewImgsz, 32],
                ["默认 Device", newDevice, setNewDevice, null],
              ].map(([label, val, setter, min]) => (
                <Elem name="param" key={label}>
                  <Elem name="param-label">{label}</Elem>
                  <Elem name="param-input">
                    {min ? (
                      <input type="number" value={val} onChange={(e) => setter(Number(e.target.value) || 0)}
                        disabled={creating} min={min} />
                    ) : (
                      <input type="text" value={val} onChange={(e) => setter(e.target.value)}
                        disabled={creating} />
                    )}
                  </Elem>
                </Elem>
              ))}
            </Elem>
            <Space style={{ marginTop: 12 }}>
              <Button size="small" look="primary" onClick={createConfig} waiting={creating}>
                创建
              </Button>
              <Button size="small" onClick={() => setShowCreate(false)} disabled={creating}>
                取消
              </Button>
            </Space>
          </Elem>
        )}

        {jobStatus === "training" && (
          <Elem name="status">
            <Elem name="status-icon">&#x23F3;</Elem> 训练已启动，正在后台运行。
          </Elem>
        )}
        {error && <Elem name="error">{error}</Elem>}

        <Elem name="footer">
          <Space spread>
            <div />
            <Space>
              <Button onClick={close} disabled={training}>取消</Button>
              <Button look="primary" onClick={startTraining} waiting={training}
                disabled={!configName || training}>开始训练</Button>
            </Space>
          </Space>
        </Elem>
      </Block>
    </Modal>
  );
};

TrainingPage.path = "/train";
TrainingPage.modal = true;
