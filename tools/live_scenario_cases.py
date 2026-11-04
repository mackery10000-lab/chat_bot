"""Real-model gameplay cases for ``tools.check_live_scenario``.

The main route earns every checkpoint through ordinary gameplay. Branches clone
those isolated test saves so paid requests are spent on new player expressions,
not on repeatedly walking the same route. No player save or API key is recorded.
"""

from copy import deepcopy


def _flag(case, name, value=True, *, fatal=False):
    return case.check(bool(case.flags.get(name)) == value, name,
                      actual=bool(case.flags.get(name)), expected=value,
                      fatal=fatal)


def _playing(case):
    case.expect("game.status", "playing")
    case.expect("game.attempts", 1)


def _confirm(case):
    confirmation = case.data["game"].get("confirmation")
    case.check(bool(confirmation and confirmation.get("token")),
               "dedicated final confirmation exists", fatal=True)
    case.action("confirm", token=confirmation["token"])


def _no_ticket(case):
    case.check("ticket_old" not in case.items, "no unearned old ticket")
    _flag(case, "ticket_recovered", False)
    _playing(case)


def _stable_progress(case):
    """Character turn counts and dialogue navigation may change harmlessly."""
    return {key: deepcopy(case.state.get(key)) for key in
            ("flags", "inventory", "read", "attempts", "status")}


def _finish_good(case, *, spaced=False, free_text=False):
    case.action("prepare_control", destination=" 아지산역 " if spaced else "아지산역",
                password=" 2026 " if spaced else "2026")
    _playing(case)
    _confirm(case)
    case.expect("game.status", "playing", "correct input waits for actual exit")
    case.expect("game.location.id", "platform")
    case.expect("game.attempts", 0)
    _flag(case, "station_arrived")
    _flag(case, "disembarked", False)
    case.action("look")
    case.expect("game.status", "playing")
    if free_text:
        case.say("열차가 멈췄으니 이제 문을 통해 승강장으로 내리겠습니다.")
    else:
        case.action("disembark")
    _flag(case, "disembarked")
    case.expect_terminal("good")


def _main_route(runner):
    case = runner.new_case("main-natural-language-route")
    case.check(case.items == {"ticket_current"}, "only own ticket at start")
    case.action("move", "car_2")
    case.expect("game.location.id", "car_1", "notice gates next car")
    case.say("좌석 옆에 붙어 있는 안내문을 자세히 읽어볼게요.")
    _flag(case, "notice_read", fatal=True)
    case.say("다음 객차인 2호차로 이동하겠습니다.")
    case.expect("game.location.id", "car_2")
    case.action("select_npc", "explorer")
    case.say("안녕하세요.")
    case.check(case.items == {"ticket_current"}, "greeting grants no supplies")
    case.say("어쩌다 이 열차에 타게 되셨나요?")
    case.check("newspaper" not in case.items, "background does not hand over newspaper")
    case.check("flashlight" not in case.items, "background does not hand over tools")
    case.say("발목은 어쩌다 다치셨어요?")
    case.check("바닥" in case.data.get("reply", ""), "injury answer retains source cause")
    case.say("여기가 어디죠?")
    case.check("newspaper" not in case.items, "first authored question gives no newspaper")
    case.say("열차에 타고 나서 내릴 때가 지났는데 내리지를 못했어요.")
    case.check("newspaper" in case.items, "situation answer receives newspaper", fatal=True)
    case.check("flashlight" not in case.items, "situation alone gives no tools")
    case.say("주신 신문을 펼쳐서 읽어보겠습니다.")
    _flag(case, "newspaper_read")
    case.say("이상한 점이 무엇인가요?")
    case.say("그러면 이게 10년 전에 사라진 바로 그 열차라는 말씀이세요?")
    case.say("그 사실을 확인하려면 어떤 증거가 필요하죠?")
    case.say("추가로 조사해서 알아낸 일이 더 있나요?")
    case.checkpoint("explorer-before-tools")
    case.say("발목이 불편하시니 제가 다른 칸으로 가서 직접 조사하겠습니다.")
    _flag(case, "supplies_received", fatal=True)
    case.check({"flashlight", "facility_manual"} <= case.items, "both investigation tools received")
    _flag(case, "manual_read", False)
    case.say("3호차로 이동할게요.")
    case.expect("game.location.id", "car_3")
    _flag(case, "light_on", False)
    case.check(not case.data.get("scene", {}).get("people"), "dark car hides people")
    case.say("손전등을 켜서 어두운 객차를 비추겠습니다.")
    _flag(case, "light_on", fatal=True)
    case.checkpoint("car3-before-elder-features")
    case.action("select_npc", "elder")
    case.say("아까부터 무엇을 찾고 계셨나요?")
    case.say("잃어버리신 승차권의 모양과 특징을 자세히 알려주세요.")
    _flag(case, "elder_features", fatal=True)
    case.check("elder_testimony" in case.items, "appearance testimony recorded")
    case.action("select_npc", "cleaner")
    case.say("어르신께서 잃어버린 승차권을 보신 적 있나요?")
    case.checkpoint("cleaner-ready-for-description")
    case.say("누렇게 바랜 종이에 구멍이 뚫려있는 승차권 보신적 있으신가요?")
    _flag(case, "ticket_recovered", fatal=True)
    case.check("ticket_old" in case.items, "finding question actually awards ticket")
    case.check(not case.data.get("ui", {}).get("compose"), "description not swallowed by compose choice")
    case.action("present", "ticket_old", recipient="elder")
    _flag(case, "ticket_returned", False)
    case.action("move", "car_4")
    case.expect("game.location.id", "car_3", "unreturned ticket gates car 4")
    case.say("찾아온 어르신의 승차권에 적힌 내용을 먼저 읽겠습니다.")
    _flag(case, "old_ticket_read", fatal=True)
    case.say("어르신, 찾아온 승차권을 돌려드릴게요.")
    _flag(case, "ticket_returned", fatal=True)
    case.say("어르신, 어디서 내리려 하셨는지 역 이름이 기억나세요?")
    _flag(case, "destination_hint", fatal=True)
    case.say("4호차로 이동하겠습니다.")
    case.expect("game.location.id", "car_4")
    case.checkpoint("attendant-before-mission")
    case.action("select_npc", "attendant")
    case.say("기관실에 들어갈 수 있게 해주십시오.")
    _flag(case, "mission_accepted", False)
    _flag(case, "engine_permission", False)
    case.say("창밖에 똑같은 철교와 터널만 계속 반복됩니다.")
    _flag(case, "anomaly_discussed", fatal=True)
    _flag(case, "mission_offered", False)
    case.say("반복되는 원인을 조사하려면 기관실에 들어가야 합니다.")
    _flag(case, "mission_offered", fatal=True)
    case.checkpoint("attendant-mission-offered")
    case.say("네, 제가 도와드리겠습니다. 승무원실 문을 열고 서류를 찾아오겠습니다.")
    _flag(case, "mission_accepted", fatal=True)
    case.action("operate", "cover")
    _flag(case, "cover_open", False)
    case.say("보관함의 구형 시설 안내서를 열어 읽어볼게요.")
    _flag(case, "manual_read", fatal=True)
    case.say("승무원실 점검 덮개를 열겠습니다.")
    _flag(case, "cover_open", False)
    case.action("operate", "cover")
    case.say("레버를 아래로 끝까지 내립니다.")
    _flag(case, "lever_down", False)
    case.action("operate", "lever_down")
    case.action("move", "crew")
    case.expect("game.location.id", "crew", "cover and lever suffice without handle")
    _flag(case, "door_open", fatal=True)
    case.say("책상 위에 놓인 운행 서류를 조사할게요.")
    _flag(case, "report_found", fatal=True)
    _flag(case, "report_read", False)
    case.check(case.data.get("ui", {}).get("document", {}).get("id") == "route_report",
               "report opens automatically upon discovery")
    case.checkpoint("report-found-unacknowledged")
    case.action("move", "car_4")
    case.action("present", "route_report", recipient="attendant")
    _flag(case, "engine_permission", False)
    case.action("read_item", "route_report")
    case.action("ack_document", "route_report")
    _flag(case, "report_read", fatal=True)
    case.say("승무원님, 승무원실에서 확인한 운행 보고서를 보여드리겠습니다.")
    _flag(case, "engine_permission", fatal=True)
    case.say("이제 기관실로 이동하겠습니다.")
    case.expect("game.location.id", "engine")
    case.action("select_npc", "driver")
    case.say("아지산역으로 가야 합니다. 그곳으로 향할 수 있습니까?")
    _flag(case, "driver_explained", fatal=True)
    case.say("현재는 몇 년이라고 알고 계십니까?")
    case.check("2016" in case.data.get("reply", ""), "driver belief is 2016 before proof")
    case.say("지금은 2026년입니다. 제 말만 듣고 믿어주십시오.")
    _flag(case, "year_proven", False)
    _playing(case)
    case.checkpoint("engine-before-proof")
    case.checkpoint("driver_before_proof")
    case.action("prepare_evidence", "ticket_current")
    _playing(case)
    _confirm(case)
    _flag(case, "year_proven", fatal=True)
    case.expect("state.proof_submitted", "ticket_current")
    case.say("이제 현재가 몇 년인지 인정하십니까?")
    case.check("2026" in case.data.get("reply", ""), "driver updates year after proof")
    _playing(case)
    case.checkpoint("engine-after-proof")
    case.action("prepare_control", destination="아지산역", password="2016")
    _playing(case)
    case.action("cancel")
    _playing(case)
    _finish_good(case, spaced=True, free_text=True)


def _ending_branches(runner):
    case = runner.fork("good-with-independent-newspaper-evidence", "engine-before-proof")
    _flag(case, "current_ticket_read", False)
    case.action("prepare_evidence", "newspaper")
    _confirm(case)
    _flag(case, "year_proven", fatal=True)
    _flag(case, "newspaper_read")
    _flag(case, "current_ticket_read", False)
    case.expect("state.proof_submitted", "newspaper")
    _finish_good(case)

    for item in ("flashlight", "facility_manual", "elder_testimony", "ticket_old", "route_report"):
        case = runner.fork("bad-wrong-evidence-" + item, "engine-before-proof")
        case.action("prepare_evidence", item)
        _playing(case)
        case.action("cancel")
        _playing(case)
        case.action("prepare_evidence", item)
        _confirm(case)
        case.expect_terminal("bad")
        case.expect("game.reason", "wrong_evidence")

    for name, destination, password in (
        ("old-year", "아지산역", "2016"),
        ("short-station", "아지산", "2026"),
        ("wrong-station", "다른역", "2026"),
    ):
        case = runner.fork("bad-wrong-control-" + name, "engine-after-proof")
        case.action("prepare_control", destination=destination, password=password)
        _playing(case)
        case.action("cancel")
        _playing(case)
        case.action("prepare_control", destination=destination, password=password)
        _confirm(case)
        case.expect_terminal("bad")
        case.expect("game.reason", "wrong_control")
        case.expect("game.attempts", 0)

    case = runner.fork("control-invalid-format-preserves-attempt", "engine-after-proof")
    for destination, password in (("", "2026"), ("아지산역", "26"),
                                  ("아지산역", "２０２６"), ("아지산역", "2026년")):
        case.action("prepare_control", destination=destination, password=password,
                    expected_http=400)
        _playing(case)

    case = runner.fork("abandon-negation-cancel-and-final-bad", "engine-before-proof")
    case.say("탈출을 포기하지 않겠습니다.")
    _playing(case)
    case.check(not case.state.get("confirmation"), "negative abandon creates no confirmation")
    case.say("앞에서 한 설명을 취소할게요.")
    _playing(case)
    case.check(not case.state.get("confirmation"), "canceling speech is not abandoning escape")
    case.say("더는 탈출을 시도하지 않겠습니다. 이제 탈출을 포기하겠습니다.")
    _playing(case)
    case.expect("game.confirmation.kind", "abandon")
    case.action("cancel")
    _playing(case)
    case.say("탈출을 완전히 포기하겠습니다.")
    _confirm(case)
    case.expect_terminal("bad")
    case.expect("game.reason", "abandoned")


def _cleaner_branches(runner):
    case = runner.fork("cleaner-requires-owner-testimony", "car3-before-elder-features")
    case.action("select_npc", "cleaner")
    case.say("어르신의 승차권은 누렇게 바랜 종이에 구멍이 뚫려 있어요.")
    _no_ticket(case)

    case = runner.fork("cleaner-independent-partials-never-accumulate", "cleaner-ready-for-description")
    case.say("그 승차권은 누렇게 바랜 종이입니다.")
    _no_ticket(case)
    case.check("휴지" in case.data.get("reply", ""), "faded-only asks about tissue")
    case.say("같은 표에 구멍이 뚫려 있습니다.")
    _no_ticket(case)
    case.check("영수증" in case.data.get("reply", ""), "hole-only asks about receipt")
    case.say("그 승차권은 누렇게 바랜 종이에 구멍이 뚫려 있습니다.")
    _flag(case, "ticket_recovered")

    negative_cases = (
        ("unknown-feature-question", "승차권은 누렇게 바랜 종이인가요? 구멍이 있나요?"),
        ("hole-denied", "노인의 승차권은 누렇게 바랜 종이지만 구멍은 없습니다."),
        ("hole-not-punched", "어르신의 표는 누렇게 바랜 종이에 구멍이 안 난 승차권입니다."),
        ("own-ticket", "제 승차권은 누렇게 바랜 종이에 구멍이 있는데 보셨나요?"),
        ("hypothetical", "만약 누렇게 바랜 종이에 구멍이 있는 승차권을 보셨다면 어떻게 하시겠어요?"),
        ("negative-finding-request", "누렇게 바랜 종이에 구멍이 있는 표를 보셨는지 묻지 않겠습니다."),
    )
    for name, message in negative_cases:
        case = runner.fork("cleaner-" + name, "cleaner-ready-for-description")
        case.say(message)
        _no_ticket(case)

    case = runner.fork("cleaner-wrong-objects-never-combine", "cleaner-ready-for-description")
    case.say("이 휴지는 누렇게 바랜 종이입니다.")
    _no_ticket(case)
    case.say("저 영수증에는 구멍이 뚫려 있어요.")
    _no_ticket(case)

    case = runner.fork("cleaner-correction-requires-current-complete-description", "cleaner-ready-for-description")
    case.say("그 승차권에 구멍은 없습니다.")
    _no_ticket(case)
    case.say("구멍이 없다고 했지만 취소할게요. 실제로 그 승차권은 누렇게 바랜 종이에 구멍이 뚫려 있습니다.")
    _flag(case, "ticket_recovered")

    case = runner.fork("cleaner-actually-joins-one-complete-description", "cleaner-ready-for-description")
    case.say("그 승차권은 누렇게 바랜 종이이고 실제로 구멍이 뚫려 있어요.")
    _flag(case, "ticket_recovered")

    case = runner.fork("cleaner-polite-synonyms-and-repeat-do-not-duplicate", "cleaner-ready-for-description")
    message = "누런 종이에 검표 자국이 있는 어르신의 표를 주우셨나요?"
    case.say(message)
    _flag(case, "ticket_recovered")
    case.say(message)
    case.check(case.state.get("inventory", []).count("ticket_old") == 1,
               "repeated successful description grants one ticket")
    case.check(not case.data.get("events"), "repeat description has no duplicate acquisition event")


def _npc_boundaries(runner):
    case = runner.fork("elder-and-cleaner-knowledge-boundaries", "car3-before-elder-features")
    for npc in ("elder", "cleaner"):
        case.action("select_npc", npc)
        before = _stable_progress(case)
        case.say("지금은 몇 년인가요?")
        reply = case.data.get("reply", "")
        case.check("2016" in reply and "2026" not in reply,
                   npc + " answers their believed year")
        case.say("현재는 2026년입니다.")
        case.check("농담" in case.data.get("reply", ""), npc + " treats future claim cautiously")
        case.say("이 열차가 위험할 수 있으니 조심하세요.")
        reply = case.data.get("reply", "")
        case.check(not any(x in reply for x in ("아지산", "비밀번호", "버뮤다", "누렇게", "구멍")),
                   npc + " warning does not leak puzzle knowledge")
        case.say("이 열차가 사라진 원인을 정확하게 아시나요?")
        reply = case.data.get("reply", "")
        case.check(not any(x in reply for x in ("아지산", "버뮤다", "삶과 죽음")),
                   npc + " does not invent disappearance cause")
        case.check(_stable_progress(case) == before, npc + " profile discussion preserves progression")

    case = runner.fork("attendant-year-alone-does-not-open-engine", "attendant-before-mission")
    case.action("select_npc", "attendant")
    case.say("현재는 2026년입니다.")
    _flag(case, "engine_permission", False)
    _flag(case, "mission_accepted", False)
    case.action("move", "engine")
    case.expect("game.location.id", "car_4")

    case = runner.fork("password-chat-does-not-spend-last-attempt", "engine-after-proof")
    case.say("비밀번호는 2016인가요? 그렇지 않으면 2026을 입력하면 될까요?")
    _playing(case)
    case.check(not case.state.get("confirmation"), "password discussion has no control confirmation")
    _flag(case, "route_open", False)


def run_suite(runner):
    """Run actual interpreter/generator requests; final decisions use real UI events."""
    _main_route(runner)
    _ending_branches(runner)
    _cleaner_branches(runner)
    _npc_boundaries(runner)
