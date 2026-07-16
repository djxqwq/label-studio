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
  const [configName, setConfigName] = useState("");
  const [epochs, setEpochs] = useState(1000);
  const [batch, setBatch] = useState(16);
  const [patience, setPatience] = useState(200);
  const [imgsz, setImgsz] = useState(640);
  const [device, setDevice] = useState("0");
  const [training, setTraining] = useState(false);
  const [jobStatus, setJobStatus] = useState("idle");
  const [error, setError] = useState("");

  useEffect(() => {
    if (pageParams.id) {
      api.callApi("trainConfigs", {}).then(setConfigs).catch(() => {});
    }
  }, [pageParams]);

  const startTraining = async () => {
    if (!configName) return;
    setTraining(true);
    setError("");
    try {
      await api.callApi("startTrain", {
        params: { pk: pageParams.id },
        body: {
          config_name: configName,
          epochs: epochs,
          batch: batch,
          patience: patience,
          imgsz: imgsz,
          device: device,
        },
      });
      setJobStatus("training");
    } catch (e) {
      setError(e?.detail || "启动训练失败");
      setTraining(false);
    }
  };

  const close = () => {
    const path = location.pathname.replace(TrainingPage.path, "");
    const search = location.search;
    history.replace(`${path}${search !== "?" ? search : ""}`);
  };

  return (
    <Modal
      onHide={close}
      title="模型训练"
      style={{ width: 560 }}
      visible
      closeOnClickOutside={false}
      allowClose={!training}
    >
      <Block name="training-page">
        <Elem name="section">
          <Elem name="label">模型配置</Elem>
          <Select
            value={configName}
            onChange={(val) => setConfigName(val)}
            disabled={training}
            options={[
              { label: "-- 请选择 --", value: "" },
              ...configs.map((c) => ({ label: c.name, value: c.name })),
            ]}
          />
        </Elem>

        <Elem name="section">
          <Elem name="label">训练参数（可选，留空使用默认值）</Elem>
          <Elem name="params-row">
            <Elem name="param">
              <Elem name="param-label">Epochs</Elem>
              <Elem name="param-input">
                <input type="number" value={epochs} onChange={(e) => setEpochs(Number(e.target.value) || 0)}
                  disabled={training} min={1} placeholder="1000" />
              </Elem>
            </Elem>
            <Elem name="param">
              <Elem name="param-label">Batch</Elem>
              <Elem name="param-input">
                <input type="number" value={batch} onChange={(e) => setBatch(Number(e.target.value) || 0)}
                  disabled={training} min={1} placeholder="16" />
              </Elem>
            </Elem>
            <Elem name="param">
              <Elem name="param-label">Patience</Elem>
              <Elem name="param-input">
                <input type="number" value={patience} onChange={(e) => setPatience(Number(e.target.value) || 0)}
                  disabled={training} min={1} placeholder="200" />
              </Elem>
            </Elem>
          </Elem>
          <Elem name="params-row" style={{ marginTop: 12 }}>
            <Elem name="param">
              <Elem name="param-label">Img Size</Elem>
              <Elem name="param-input">
                <input type="number" value={imgsz} onChange={(e) => setImgsz(Number(e.target.value) || 0)}
                  disabled={training} min={32} placeholder="640" />
              </Elem>
            </Elem>
            <Elem name="param">
              <Elem name="param-label">Device</Elem>
              <Elem name="param-input">
                <input type="text" value={device} onChange={(e) => setDevice(e.target.value)}
                  disabled={training} placeholder="0" />
              </Elem>
            </Elem>
            <Elem name="param" />
          </Elem>
        </Elem>

        {jobStatus === "training" && (
          <Elem name="status">
            <Elem name="status-icon">&#x23F3;</Elem>
            训练已启动，正在后台运行。请稍后查看结果。
          </Elem>
        )}

        {error && (
          <Elem name="error">{error}</Elem>
        )}

        <Elem name="footer">
          <Space spread>
            <div />
            <Space>
              <Button onClick={close} disabled={training}>
                取消
              </Button>
              <Button
                look="primary"
                onClick={startTraining}
                waiting={training}
                disabled={!configName || training}
              >
                开始训练
              </Button>
            </Space>
          </Space>
        </Elem>
      </Block>
    </Modal>
  );
};

TrainingPage.path = "/train";
TrainingPage.modal = true;
