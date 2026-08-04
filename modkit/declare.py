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
    my_order = set((mod_card.get("order") or {}).get("after") or ())
    my_order |= set((mod_card.get("order") or {}).get("before") or ())
    warnings = []
    for other in installed_names:
        if other == me:
            continue
        other_card = _card(store, other)
        other_order = set((other_card.get("order") or {}).get("after") or ())
        other_order |= set((other_card.get("order") or {}).get("before") or ())
        theirs_t = other_card.get("touches") or {}
        theirs = set(theirs_t.get("methods") or []) | set(theirs_t.get("files") or [])
        spots = sorted(mine & theirs)
        if other in my_order or me in other_order:
            # 순서를 선언한 겹침은 의도된 층 — 경고 대신 결과를 알리는 한 줄만.
            # 완전 침묵이던 첫 판은 이로치가 한글패치를 부분 상태로 내리는 걸
            # 유저가 알 길이 없었다(2026-08-04 아닐 실기).
            if spots:
                warnings.append(
                    f"`{other}` 위에 얹는 모드예요 — 겹치는 자리 {len(spots)}곳은 이 모드가 "
                    f"이겨요. `{other}`를 나중에 다시 설치하면 그쪽이 다시 이겨요.")
            continue
        if spots:
            # 상대당 한 줄 — 자리마다 부연을 되풀이하면 못 읽는다(2026-08-04 실기).
            heads = ", ".join(f"`{s}`" for s in spots[:4])
            more = f" 외 {len(spots) - 4}곳" if len(spots) > 4 else ""
            warnings.append(f"`{other}`도 건드리는 자리예요 — {heads}{more}")
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
