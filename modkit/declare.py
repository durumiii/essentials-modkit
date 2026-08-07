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


def _provided(store, installed_names: list) -> set:
    """설치된 모드들이 `provides`로 선언한 능력의 합집합."""
    out = set()
    for one in installed_names:
        out |= set(_card(store, one).get("provides") or ())
    return out


def gate(mod_card: dict, installed_names: list, store) -> list:
    """requires·conflicts를 검사하고, 통과하면 touches 겹침 경고 목록을 준다."""
    me = mod_card.get("name", "")
    blocks = []
    # requires는 모드 이름이거나 능력 이름이다 — 「한글 폰트를 제공하는 모드
    # 아무거나」를 이름으로는 적을 수 없다. 이름으로 먼저 보고, 없으면 설치된
    # 모드들의 provides에서 찾는다.
    unmet = [n for n in mod_card.get("requires") or [] if n not in installed_names]
    if unmet:
        provided = _provided(store, installed_names)
        for need in unmet:
            if need not in provided:
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


def arrange(names: list, store) -> tuple:
    """설치된 이름들을 order 선언대로 다시 늘어놓는다 — (새 순서, 경고 목록).

    선언이 없는 모드끼리는 지금 순서를 그대로 지킨다(안정 정렬). 선언 없는 옛 모드가
    설치할 때마다 자리를 옮기면, 무엇이 왜 움직였는지 아무도 설명할 수 없다.

    순환(모순)이면 설치를 무르지 않고 지금 순서를 그대로 두고 경고만 준다.
    `place`가 Blocked를 던지는 것과 다른 판단인 이유: `place`는 쓰기 **전**이라
    막으면 아무 일도 안 일어나지만, 여기는 이미 얹힌 뒤에 도는 마무리라 막아 봐야
    설치는 이미 끝나 있다. 늘어놓기를 포기하는 편이 반쪽 상태보다 낫다.
    """
    order_by = {n: _card(store, n).get("order") or {} for n in names}
    need = {n: set() for n in names}            # n보다 먼저 서야 하는 이름들
    for name, order in order_by.items():
        for other in order.get("after") or ():
            if other in need:
                need[name].add(other)
        for other in order.get("before") or ():
            if other in need:
                need[other].add(name)
    # ponytail: O(n²) 안정 위상정렬 — 한 설치본의 모드는 수십 개다. 커지면 Kahn 큐로.
    left, out = list(names), []
    while left:
        pick = next((n for n in left if not (need[n] - set(out))), None)
        if pick is None:
            return list(names), [
                f"order 제약이 순환이에요 — {', '.join(f'`{n}`' for n in left)} 사이의 "
                "선언이 서로를 앞세워요. 순서를 지금 그대로 뒀어요."]
        out.append(pick)
        left.remove(pick)
    return out, []


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
