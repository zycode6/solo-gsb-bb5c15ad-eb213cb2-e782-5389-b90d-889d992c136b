# 直流配电树压降校核 API

基于 FastAPI 的直流配电树压降校核服务：输入以 `source` 为根的配电树（线段电阻/额定电流、各节点恒定负载电流），自叶向根累计每段承载的全部下游电流，再自根向叶计算压降与节点电压，返回各段电流、各节点电压以及超额定电流、欠压位置。

## 启动

单条命令（需 Docker 与 Docker Compose）：

```bash
docker compose up --build
```

容器启动时会先安装 `requirements.txt` 中的依赖，再启动服务。

## 配置

| 环境变量 | 默认值 | 说明 |
| -------- | ------ | ---- |
| `PORT`   | `8000` | 宿主机映射端口，如 `PORT=9000 docker compose up --build` |

## API 地址

- 服务地址：`http://localhost:8000`
- 校核接口：`POST http://localhost:8000/evaluate`
- 交互式文档（Swagger UI）：`http://localhost:8000/docs`
- 健康检查：`GET http://localhost:8000/health`

## 请求格式

```json
{
  "source_voltage": 48.0,
  "min_voltage": 40.0,
  "segments": [
    {"id": "s1", "parent": "source", "child": "a", "resistance": 0.1,  "rated_current": 30.0},
    {"id": "s2", "parent": "a",      "child": "b", "resistance": 0.05, "rated_current": 10.0}
  ],
  "loads": [
    {"node": "a", "current": 5.0},
    {"node": "b", "current": 10.0, "min_voltage": 42.0}
  ]
}
```

- `source_voltage`：电源电压（V），必须为正。
- `min_voltage`：全局最低允许电压（V）；`loads[].min_voltage` 可对单个节点覆盖。
- `segments[]`：线段的父子节点、电阻（Ω，≥0）、额定电流（A，≥0）。全部线段必须构成以 `source` 为根的连通树（每节点恰有一个父节点、无环、无孤立子树）。
- `loads[]`：各节点恒定负载电流（A，≥0），节点必须存在于树中且不可重复定义。

## 响应示例

```json
{
  "ok": true,
  "source_voltage": 48.0,
  "min_voltage": 40.0,
  "segments": [
    {"id": "s1", "parent": "source", "child": "a", "current": 15.0, "rated_current": 30.0, "voltage_drop": 1.5, "over_rated": false},
    {"id": "s2", "parent": "a", "child": "b", "current": 10.0, "rated_current": 10.0, "voltage_drop": 0.5, "over_rated": false}
  ],
  "nodes": [
    {"node": "source", "voltage": 48.0, "min_voltage": 40.0, "under_voltage": false},
    {"node": "a", "voltage": 46.5, "min_voltage": 40.0, "under_voltage": false},
    {"node": "b", "voltage": 46.0, "min_voltage": 42.0, "under_voltage": false}
  ],
  "violations": {
    "over_rated_segments": [],
    "under_voltage_nodes": []
  }
}
```

`violations.over_rated_segments` 列出电流超过额定值的线段，`violations.under_voltage_nodes` 列出电压低于允许值的节点；两者均为空时 `ok` 为 `true`。

## 错误说明

| 状态码 | 场景 |
| ------ | ---- |
| `400`  | 树结构非法：不连通、有环、节点多父、`source` 作为子节点、线段 id 重复、负载引用未知节点、负载重复定义 |
| `422`  | 参数校验失败：电源电压非正、电阻为负、负载电流为负、额定电流为负、字段缺失或含未知字段 |

错误响应示例：

```json
{"detail": "tree is not connected: node(s) ['b'] are not reachable from 'source' (disconnected subtree or cycle)"}
```

## 本地开发与测试

```bash
pip install -r requirements-dev.txt
pytest                 # 全部测试（含 API 集成测试）
python -m unittest discover tests -v   # 仅核心算法测试（无需第三方依赖）
```
