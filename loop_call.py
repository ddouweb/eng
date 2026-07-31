import json
import threading
import time
import urllib.request

# ============ 可配置 ============
URL = "http://192.168.8.105:80/p2/v1/dr/css/proto/patrol/reliability"
HEADERS = {"User-Agent": "192.168.40.135", "Content-Type": "application/json"}
BODY = json.dumps({
    "hostId": "erzz8m3uvdskjk",
    "statsType": "2",
    "beginTime": "2026-07-29 00:00:00",
    "endTime": "2026-07-29 23:59:59",
    "stationCode": "160110102701010000"
}).encode("utf-8")

TOTAL = 100
THREADS = 2

# 校验:$.data.<FIELD> == EXPECT  -> 通过(成功);否则失败
FIELD = "percent"        # 实际带 % 的字段是 percent (statsType 是整数 2)
EXPECT = "1.719%"
# ================================

lock = threading.Lock()
successes = []   # PASS
failures = []    # FAIL


def extract(resp_json):
    """从响应里取出关键字段,容错"""
    data = (resp_json or {}).get("data") or {}
    return {
        "percent": data.get("percent"),
        "statsType": data.get("statsType"),
        "totalNum": data.get("totalNum"),
        "validNum": data.get("validNum"),
        "code": (resp_json or {}).get("code"),
        "message": (resp_json or {}).get("message"),
    }


def call_once(idx):
    req = urllib.request.Request(URL, data=BODY, headers=HEADERS, method="POST")
    start = time.time()
    record = {"idx": idx, "elapsed_ms": 0.0}

    # ---- 1) 发请求 ----
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            http_status = resp.getcode()
            raw = resp.read()
    except Exception as e:
        record.update({"reason": "HTTP_ERROR", "error": str(e)[:200]})
        record["elapsed_ms"] = (time.time() - start) * 1000
        with lock:
            failures.append(record)
            print(f"[{idx:3d}] FAIL  HTTP_ERROR  {record['elapsed_ms']:7.1f}ms  {e}")
        return

    record["elapsed_ms"] = (time.time() - start) * 1000

    # ---- 2) 解析 JSON ----
    try:
        resp_json = json.loads(raw)
    except Exception as e:
        record.update({"reason": "BAD_JSON", "error": str(e)[:200], "raw": raw[:300].decode("utf-8", "ignore")})
        with lock:
            failures.append(record)
            print(f"[{idx:3d}] FAIL  BAD_JSON   {record['elapsed_ms']:7.1f}ms")
        return

    info = extract(resp_json)
    record.update(info)

    # ---- 3) 业务 code 校验 ----
    if info["code"] != 200:
        record["reason"] = "BIZ_CODE_" + str(info["code"])
        with lock:
            failures.append(record)
            print(f"[{idx:3d}] FAIL  code={info['code']}  {record['elapsed_ms']:7.1f}ms")
        return

    # ---- 4) 断言 $.data.<FIELD> == EXPECT ----
    actual = info[FIELD]
    if str(actual) == EXPECT:
        record["reason"] = "PASS"
        with lock:
            successes.append(record)
            print(f"[{idx:3d}] PASS  {FIELD}={actual!r}  {record['elapsed_ms']:7.1f}ms")
    else:
        record["reason"] = "ASSERT_FAIL"
        record["expect"] = EXPECT
        with lock:
            failures.append(record)
            print(f"[{idx:3d}] FAIL  {FIELD}={actual!r}!= {EXPECT!r}  {record['elapsed_ms']:7.1f}ms")


def worker(start_idx, count):
    for i in range(start_idx, start_idx + count):
        call_once(i)


def main():
    per = TOTAL // THREADS
    threads = []
    t0 = time.time()
    for t in range(THREADS):
        start_idx = t * per
        cnt = per if t < THREADS - 1 else TOTAL - start_idx
        th = threading.Thread(target=worker, args=(start_idx, cnt))
        threads.append(th)
        th.start()
    for th in threads:
        th.join()
    total_elapsed = time.time() - t0

    # ---- 落盘明细 ----
    with open("success.json", "w", encoding="utf-8") as f:
        json.dump(successes, f, ensure_ascii=False, indent=2)
    with open("fail.json", "w", encoding="utf-8") as f:
        json.dump(failures, f, ensure_ascii=False, indent=2)

    # ---- 失败原因分布 ----
    from collections import Counter
    fail_by_reason = Counter()
    fail_by_actual = Counter()
    for r in failures:
        fail_by_reason[r["reason"]] += 1
        fail_by_actual[str(r.get(FIELD))] += 1

    print("\n========== SUMMARY ==========")
    print(f"Total        : {TOTAL}")
    print(f"Threads      : {THREADS}")
    print(f"Assert       : $.data.{FIELD} == {EXPECT!r}")
    print(f"PASS (ok)    : {len(successes)}")
    print(f"FAIL (bad)   : {len(failures)}")
    print(f"Wall time    : {total_elapsed:.2f}s")
    if fail_by_reason:
        print("\n-- FAIL by reason --")
        for k, v in fail_by_reason.most_common():
            print(f"  {k:<14} {v}")
    if fail_by_actual:
        print(f"\n-- FAIL by actual $.data.{FIELD} --")
        for k, v in fail_by_actual.most_common():
            print(f"  {k!r:<16} {v}")
    print(f"\nDetail files : success.json ({len(successes)}) , fail.json ({len(failures)})")


if __name__ == "__main__":
    main()
