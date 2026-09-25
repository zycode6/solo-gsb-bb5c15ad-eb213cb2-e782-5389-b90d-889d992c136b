"""直流配电树压降校核核心算法。

纯 Python 实现，不依赖 Web 框架，可独立单元测试。
计算流程：
1. 校验线段构成以 ``source`` 为根的连通树；
2. 自叶向根累计每段承载的全部下游电流；
3. 自根向叶逐段计算压降与各节点电压；
4. 汇总超额定电流线段与欠压节点。
"""

ROOT_NODE = "source"


class TreeError(ValueError):
    """输入线段未构成以 source 为根的合法树时抛出。"""


def _build_tree(segments):
    """校验树结构，返回 (children, seg_by_child, order, nodes)。

    ``order`` 为自根出发的 DFS 先序（父节点一定排在子节点之前）。
    任何结构问题都抛出 TreeError。
    """
    children = {}
    seg_by_child = {}
    nodes = {ROOT_NODE}
    seen_ids = set()

    for seg in segments:
        sid = seg["id"]
        parent = seg["parent"]
        child = seg["child"]

        if sid in seen_ids:
            raise TreeError(f"duplicate segment id '{sid}'")
        seen_ids.add(sid)

        if parent == child:
            raise TreeError(f"segment '{sid}' connects node '{parent}' to itself")
        if child == ROOT_NODE:
            raise TreeError(
                f"segment '{sid}': root node '{ROOT_NODE}' must not appear as a child"
            )
        if child in seg_by_child:
            first = seg_by_child[child]["id"]
            raise TreeError(
                f"node '{child}' has more than one parent "
                f"(segments '{first}' and '{sid}'); "
                "each tree node must have exactly one parent"
            )
        seg_by_child[child] = seg
        nodes.add(child)
        children.setdefault(parent, []).append(child)

    for parent in children:
        if parent not in nodes:
            raise TreeError(
                f"parent node '{parent}' is not defined by any segment "
                f"and is not the root '{ROOT_NODE}'"
            )

    # 连通性 / 环检查：从根出发的 DFS 必须到达全部节点。
    order = []
    visited = set()
    stack = [ROOT_NODE]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        # 逆序入栈，使访问顺序与输入顺序一致，输出更直观。
        stack.extend(reversed(children.get(node, ())))

    unreachable = sorted(nodes - visited)
    if unreachable:
        raise TreeError(
            f"tree is not connected: node(s) {unreachable} are not reachable "
            f"from '{ROOT_NODE}' (disconnected subtree or cycle)"
        )

    return children, seg_by_child, order, nodes


def evaluate(source_voltage, min_voltage, segments, loads):
    """执行压降校核，返回与 EvaluateResponse 对应的字典。

    参数
    ----
    source_voltage : float  电源电压（>0，由 API 层校验）
    min_voltage    : float  全局最低允许电压
    segments       : list[dict]  键：id, parent, child, resistance, rated_current
    loads          : list[dict]  键：node, current，可选 min_voltage（节点级覆盖）
    """
    children, seg_by_child, order, nodes = _build_tree(segments)

    load_current = {}
    node_min_voltage = {}
    for load in loads:
        node = load["node"]
        if node not in nodes:
            raise TreeError(f"load references unknown node '{node}'")
        if node in load_current:
            raise TreeError(f"duplicate load definition for node '{node}'")
        load_current[node] = load["current"]
        override = load.get("min_voltage")
        if override is not None:
            node_min_voltage[node] = override

    # 自叶向根：累计下游电流。order 为先序，逆序遍历保证子先于父。
    subtree_current = {n: load_current.get(n, 0.0) for n in nodes}
    for node in reversed(order):
        for child in children.get(node, ()):
            subtree_current[node] += subtree_current[child]

    # 自根向叶：先序遍历，逐段压降并求节点电压。
    voltage = {ROOT_NODE: float(source_voltage)}
    segment_current = {}
    segment_drop = {}
    for node in order:
        for child in children.get(node, ()):
            seg = seg_by_child[child]
            current = subtree_current[child]
            drop = current * seg["resistance"]
            segment_current[seg["id"]] = current
            segment_drop[seg["id"]] = drop
            voltage[child] = voltage[node] - drop

    segment_results = []
    over_rated = []
    for seg in segments:
        sid = seg["id"]
        current = segment_current[sid]
        is_over = current > seg["rated_current"]
        item = {
            "id": sid,
            "parent": seg["parent"],
            "child": seg["child"],
            "current": round(current, 6),
            "rated_current": seg["rated_current"],
            "voltage_drop": round(segment_drop[sid], 6),
            "over_rated": is_over,
        }
        segment_results.append(item)
        if is_over:
            over_rated.append(item)

    node_results = []
    under_voltage = []
    for node in order:
        threshold = node_min_voltage.get(node, min_voltage)
        v = voltage[node]
        is_under = v < threshold
        item = {
            "node": node,
            "voltage": round(v, 6),
            "min_voltage": threshold,
            "under_voltage": is_under,
        }
        node_results.append(item)
        if is_under:
            under_voltage.append(item)

    return {
        "ok": not over_rated and not under_voltage,
        "source_voltage": source_voltage,
        "min_voltage": min_voltage,
        "segments": segment_results,
        "nodes": node_results,
        "violations": {
            "over_rated_segments": over_rated,
            "under_voltage_nodes": under_voltage,
        },
    }
