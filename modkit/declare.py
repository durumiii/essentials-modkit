"""제작자 선언을 적용 시점에 검사한다 — 차단, 배치, 경고 세 겹.

선언은 전부 선택이다. 선언 없는 옛 모드는 기계 감지(touches 겹침 경고)만 받는다.
"""


class Blocked(Exception):
    def __init__(self, reasons):
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


def _card(store, name):
    from . import modstore
    try:
        mod = modstore.read_mod(store, name)
    except modstore.ModMissing:
        return {}
    import json
    return json.loads((mod.folder / "mod.json").read_text(encoding="utf-8"))


def gate(mod_card: dict, installed_names: list, store) -> list:
    """requires·conflicts를 검사하고, 통과하면 touches 겹침 경고 목록을 준다."""
    me = mod_card.get("name", "")
    blocks = []
    for need in mod_card.get("requires") or []:
        if need not in installed_names:
            blocks.append(f"`{me}`에는 `{need}`가 먼저 필요해요")
    for enemy, why in (mod_card.get("conflicts") or {}).items():
        if enemy in installed_names:
            blocks.append(f"`{enemy}`와 공존할 수 없어요 — {why}")
    for other in installed_names:
        other_card = _card(store, other)
        why = (other_card.get("conflicts") or {}).get(me)
        if why:
            blocks.append(f"`{other}`가 `{me}`를 거부해요 — {why}")
    if blocks:
        raise Blocked(blocks)

    mine = set((mod_card.get("touches") or {}).get("methods") or [])
    mine |= set((mod_card.get("touches") or {}).get("files") or [])
    warnings = []
    for other in installed_names:
        if other == me:
            continue
        theirs_t = _card(store, other).get("touches") or {}
        theirs = set(theirs_t.get("methods") or []) | set(theirs_t.get("files") or [])
        for spot in sorted(mine & theirs):
            warnings.append(
                f"`{me}`와 `{other}`가 모두 `{spot}`를 건드려요 — "
                "순서 선언이 없으면 나중 것이 이겨요")
    return warnings


def place(mod_card: dict, installed_names: list) -> int:
    """order 제약을 만족하는 삽입 인덱스. 모순이면 Blocked."""
    order = mod_card.get("order") or {}
    lo = max((installed_names.index(n) + 1 for n in order.get("after") or []
              if n in installed_names), default=0)
    hi = min((installed_names.index(n) for n in order.get("before") or []
              if n in installed_names), default=len(installed_names))
    if lo > hi:
        raise Blocked([f"order 제약이 모순이에요 — after {order.get('after')} / "
                       f"before {order.get('before')} (현재 {installed_names})"])
    return hi
