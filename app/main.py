"""直流配电树压降校核 API。"""

from fastapi import FastAPI, HTTPException

from .models import EvaluateRequest, EvaluateResponse
from .solver import TreeError, evaluate

app = FastAPI(
    title="DC Distribution Tree Voltage-Drop Evaluator",
    description=(
        "直流配电树压降校核：自叶向根累计各段下游电流，"
        "自根向叶计算压降与节点电压，报告超额定电流线段与欠压节点。"
    ),
    version="1.0.0",
)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.post(
    "/evaluate",
    response_model=EvaluateResponse,
    responses={
        400: {"description": "树结构非法（不连通、有环、多父节点、未知节点等）"},
        422: {"description": "参数校验失败（非正电源电压、负电阻、负负载等）"},
    },
    tags=["evaluate"],
)
def evaluate_endpoint(payload: EvaluateRequest):
    try:
        return evaluate(
            source_voltage=payload.source_voltage,
            min_voltage=payload.min_voltage,
            segments=[s.model_dump() for s in payload.segments],
            loads=[load.model_dump() for load in payload.loads],
        )
    except TreeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
