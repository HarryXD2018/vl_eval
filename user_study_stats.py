#!/usr/bin/env python3
"""汇总 user_study.ipynb 落盘的所有评分 CSV。

输出（终端打印 + 落盘到 <log-dir>/../stats/<YYYYMMDD_HHMMSS>_*.csv）：
  overall     方法级 MOS：均值 / 标准差 / 95% 置信区间，按两维平均排名
  by_clip     片段 × 方法 的均分
  by_session  每个会话（评价者）的方法均分，以及与其他人均值的相关系数（筛查异常评价者）
  vs_ref      参考方法（默认 ours）与其它方法逐对比较：胜 / 平 / 负、平均分差、符号检验 p 值

用法：
    python user_study_stats.py
    python user_study_stats.py --exclude 20261112_125813      # 剔除某个会话
    python user_study_stats.py --log-dir path/to/logs --no-save

只依赖标准库（volia_viewer 环境里没有 numpy / scipy / pandas）。
统计文件写在 logs/ 之外，不会被 user_study.ipynb 的汇总格当成评分会话读进去。
"""
import argparse
import csv
import datetime
import glob
import json
import math
import os
import statistics
import sys
import unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_DIR = os.path.join(HERE, "v1112_compare", "logs")
DEFAULT_ATTR = os.path.join(HERE, "v1112_compare", "attr.json")

SCORE_MIN, SCORE_MAX = 1, 5
RAW_DIMS = ("naturalness", "timing")
DIMS = RAW_DIMS + ("avg",)          # avg = 每条评分两维的均值，与 CSV 里的 avg 列一致
DIM_NAMES = {"naturalness": "自然程度", "timing": "时机恰当", "avg": "两维平均"}
REQUIRED_COLS = {"clip_id", "method", "naturalness", "timing"}

# 95% 双侧 t 分位数。df > 30 时取区间下端的值，略偏保守；df > 120 退到 1.98。
T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
    15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080,
    22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048,
    29: 2.045, 30: 2.042,
}


def t95(df):
    if df <= 0:
        return math.nan
    if df in T95:
        return T95[df]
    for upper, t in ((40, 2.042), (60, 2.021), (120, 2.000)):
        if df <= upper:
            return t
    return 1.980


def describe(vals):
    """n / 均值 / 样本标准差 / 95% CI 半宽。n < 2 时标准差记 0、CI 记 nan。"""
    n = len(vals)
    if n == 0:
        return {"n": 0, "mean": math.nan, "std": math.nan, "ci95": math.nan}
    mean = statistics.fmean(vals)
    std = statistics.stdev(vals) if n > 1 else 0.0
    ci = t95(n - 1) * std / math.sqrt(n) if n > 1 else math.nan
    return {"n": n, "mean": mean, "std": std, "ci95": ci}


def pearson(xs, ys):
    """少于 3 对或某一侧全是同一个分时相关系数没有意义，返回 nan。"""
    if len(xs) < 3:
        return math.nan
    try:
        return statistics.correlation(xs, ys)
    except statistics.StatisticsError:
        return math.nan


def sign_test_p(wins, losses):
    """双侧精确符号检验（平局不计入）。"""
    n = wins + losses
    if n == 0:
        return math.nan
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


# ============================== 读取 ==============================

def load_sessions(log_dir, exclude):
    """读 log_dir 下所有会话 CSV（跳过 *_summary.csv），返回 (sessions, warnings)。

    每个文件算一个会话；subject 留空时用文件名当评价者标识。
    坏行只跳过该行并记一条警告，不连坐整份文件。
    """
    sessions, warnings = [], []
    paths = sorted(p for p in glob.glob(os.path.join(log_dir, "*.csv"))
                   if not p.endswith("_summary.csv"))
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        if name in exclude:
            continue
        rows, seen, subject = [], set(), ""
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                missing = REQUIRED_COLS - set(reader.fieldnames or [])
                if missing:
                    warnings.append(f"{name}: 缺少列 {sorted(missing)}，整份跳过")
                    continue
                for line_no, r in enumerate(reader, start=2):
                    try:
                        nat, tim = int(r["naturalness"]), int(r["timing"])
                    except (TypeError, ValueError):
                        warnings.append(f"{name} 第 {line_no} 行: 分数为空或不是整数，跳过")
                        continue
                    if not all(SCORE_MIN <= s <= SCORE_MAX for s in (nat, tim)):
                        warnings.append(f"{name} 第 {line_no} 行: 分数超出 "
                                        f"{SCORE_MIN}-{SCORE_MAX}，跳过")
                        continue
                    key = (r["clip_id"].strip(), r["method"].strip())
                    if key in seen:
                        warnings.append(f"{name}: 片段 {key[0]} / {key[1]} 重复，只保留第一条")
                        continue
                    seen.add(key)
                    subject = subject or (r.get("subject") or "").strip()
                    rows.append({"clip_id": key[0], "method": key[1],
                                 "naturalness": nat, "timing": tim, "avg": (nat + tim) / 2})
        except OSError as e:
            warnings.append(f"{name}: 读取失败 {e}")
            continue
        if rows:
            sessions.append({"name": name, "subject": subject or name, "rows": rows})
        else:
            warnings.append(f"{name}: 没有有效评分，跳过")
    return sessions, warnings


def method_order(sessions, attr_path):
    """方法按 attr.json 中的顺序排列，attr.json 里没有的追加在后面。"""
    order = []
    try:
        with open(attr_path, "r", encoding="utf-8") as f:
            for rec in json.load(f):
                order += [k for k in rec if k != "id" and k not in order]
    except (OSError, ValueError, TypeError):
        pass
    for s in sessions:
        order += [r["method"] for r in s["rows"] if r["method"] not in order]
    present = {r["method"] for s in sessions for r in s["rows"]}
    return [m for m in order if m in present]


def clip_order(sessions):
    clips = {r["clip_id"] for s in sessions for r in s["rows"]}
    return sorted(clips, key=lambda c: (0, int(c)) if c.isdigit() else (1, c))


def coverage_warnings(sessions):
    """所有会话评过的 (片段, 方法) 取并集，各会话缺哪些就报出来。"""
    universe = {(r["clip_id"], r["method"]) for s in sessions for r in s["rows"]}
    out = []
    for s in sessions:
        lack = universe - {(r["clip_id"], r["method"]) for r in s["rows"]}
        if lack:
            out.append(f"{s['name']}: 比其它会话少 {len(lack)} 条评分（未评完或方法集不同）")
    return out


# ============================== 统计 ==============================

def aggregate(sessions, methods, clips):
    by_method = defaultdict(lambda: defaultdict(list))
    by_clip = defaultdict(lambda: defaultdict(list))
    by_session = defaultdict(lambda: defaultdict(list))
    for s in sessions:
        for r in s["rows"]:
            for d in DIMS:
                by_method[r["method"]][d].append(r[d])
                by_clip[(r["clip_id"], r["method"])][d].append(r[d])
                by_session[(s["name"], r["method"])][d].append(r[d])

    overall = {}
    for m in methods:
        overall[m] = {d: describe(by_method[m][d]) for d in DIMS}
        overall[m]["n_sessions"] = sum(
            1 for s in sessions if any(r["method"] == m for r in s["rows"]))
        overall[m]["n_clips"] = len({c for (c, mm) in by_clip if mm == m})
    clip_stats = {k: {d: describe(v[d]) for d in DIMS} for k, v in by_clip.items()}
    session_stats = {k: {d: describe(v[d]) for d in DIMS} for k, v in by_session.items()}
    return overall, clip_stats, session_stats


def leave_one_out_corr(sessions):
    """每个会话 vs 其余会话均值的 Pearson 相关，按维度分别算。

    明显偏低（甚至为负）的会话说明此人打分标准和大家不一致，可考虑 --exclude。
    只有一个会话时没有可比对象，全部为 nan。
    """
    table = defaultdict(lambda: defaultdict(dict))   # dim -> (clip, method) -> {session: score}
    for s in sessions:
        for r in s["rows"]:
            for d in RAW_DIMS:
                table[d][(r["clip_id"], r["method"])][s["name"]] = r[d]
    out = {}
    for s in sessions:
        out[s["name"]] = {}
        for d in RAW_DIMS:
            xs, ys = [], []
            for by_s in table[d].values():
                if s["name"] in by_s and len(by_s) > 1:
                    others = [v for k, v in by_s.items() if k != s["name"]]
                    xs.append(by_s[s["name"]])
                    ys.append(statistics.fmean(others))
            out[s["name"]][d] = pearson(xs, ys)
    return out


def compare_to_ref(sessions, methods, ref):
    """同一会话、同一片段内，参考方法与其它方法逐对比较。

    配对单位是 (会话, 片段)：同一个人看同一段内容给两种方法打的分，
    比混在一起比均值更能排除"片段本身难"或"这个人打分偏严"的影响。
    """
    result = {}
    if ref not in methods:
        return result
    for m in methods:
        if m == ref:
            continue
        result[m] = {}
        for d in DIMS:
            wins = ties = losses = 0
            diffs = []
            for s in sessions:
                score = defaultdict(dict)
                for r in s["rows"]:
                    score[r["clip_id"]][r["method"]] = r[d]
                for per_clip in score.values():
                    if ref in per_clip and m in per_clip:
                        diff = per_clip[ref] - per_clip[m]
                        diffs.append(diff)
                        wins += diff > 0
                        ties += diff == 0
                        losses += diff < 0
            result[m][d] = {
                "n_pairs": len(diffs), "wins": wins, "ties": ties, "losses": losses,
                "mean_diff": statistics.fmean(diffs) if diffs else math.nan,
                "p": sign_test_p(wins, losses),
            }
    return result


# ============================== 输出 ==============================

def disp_width(s):
    """中文占两格，对齐终端表格用。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def pad(s, width, right):
    s = str(s)
    gap = " " * max(width - disp_width(s), 0)
    return gap + s if right else s + gap


def print_table(title, headers, rows, left_cols=1):
    """前 left_cols 列左对齐，其余右对齐。"""
    cols = list(zip(headers, *rows)) if rows else [(h,) for h in headers]
    widths = [max(disp_width(str(x)) for x in col) for col in cols]

    def line(cells):
        return "  ".join(pad(c, w, i >= left_cols) for i, (c, w) in enumerate(zip(cells, widths)))

    head = line(headers)
    print(f"\n【{title}】")
    print(head)
    print("-" * disp_width(head))
    for r in rows:
        print(line(r))


def fmt(x, nd=2):
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def fmt_ci(st):
    if st["n"] == 0:
        return "–"
    if math.isnan(st["ci95"]):
        return fmt(st["mean"])
    return f"{st['mean']:.2f} ± {st['ci95']:.2f}"


def fmt_p(p):
    if math.isnan(p):
        return "–"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def ranked_methods(overall, methods):
    return sorted(methods, key=lambda m: (-overall[m]["avg"]["mean"], methods.index(m)))


def report(sessions, methods, clips, overall, clip_stats, session_stats, corr, vs, ref):
    n_ratings = sum(len(s["rows"]) for s in sessions)
    subjects = sorted({s["subject"] for s in sessions})
    print(f"会话 {len(sessions)} 个 · 评价者 {len(subjects)} 人 · 评分 {n_ratings} 条 · "
          f"片段 {len(clips)} 个 · 方法 {len(methods)} 种")

    rows = []
    for rank, m in enumerate(ranked_methods(overall, methods), 1):
        o = overall[m]
        rows.append([rank, m, o["avg"]["n"], fmt_ci(o["naturalness"]),
                     fmt_ci(o["timing"]), fmt_ci(o["avg"])])
    print_table("方法 MOS（均值 ± 95% CI）",
                ["名次", "方法", "n", "自然程度", "时机恰当", "两维平均"], rows, left_cols=2)

    for d in DIMS:
        rows = []
        for c in clips:
            rows.append([c] + [fmt(clip_stats[(c, m)][d]["mean"]) if (c, m) in clip_stats
                               else "–" for m in methods])
        print_table(f"各片段均分 · {DIM_NAMES[d]}", ["片段"] + methods, rows)

    rows = []
    for s in sessions:
        cells = [s["name"], s["subject"] if s["subject"] != s["name"] else "", len(s["rows"])]
        for m in methods:
            st = session_stats.get((s["name"], m))
            cells.append(f"{fmt(st['naturalness']['mean'], 1)}/{fmt(st['timing']['mean'], 1)}"
                         if st else "–")
        cells += [fmt(corr[s["name"]]["naturalness"]), fmt(corr[s["name"]]["timing"])]
        rows.append(cells)
    print_table("各会话均分（自然/时机）与一致性",
                ["会话", "评价者", "n"] + methods + ["r_自然", "r_时机"], rows, left_cols=2)
    print("  r_* = 该会话与其余会话均值的 Pearson 相关；明显偏低的会话可用 --exclude 剔除")

    if vs:
        rows = []
        for m, per_dim in vs.items():
            cells = [m]
            for d in DIMS:
                v = per_dim[d]
                cells.append(f"{v['wins']}/{v['ties']}/{v['losses']}  "
                             f"Δ{v['mean_diff']:+.2f}  p={fmt_p(v['p'])}"
                             if v["n_pairs"] else "–")
            rows.append(cells)
        print_table(f"{ref} vs 其它方法（胜/平/负，按会话×片段配对）",
                    ["对比方法"] + [DIM_NAMES[d] for d in DIMS], rows)
        print("  Δ = 参考方法减对比方法的平均分差；p 为双侧符号检验（平局不计）")


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def save(out_dir, stamp, sessions, methods, clips, overall, clip_stats,
         session_stats, corr, vs, ref):
    os.makedirs(out_dir, exist_ok=True)
    written = []

    path = os.path.join(out_dir, f"{stamp}_overall.csv")
    header = ["rank", "method", "n_ratings", "n_sessions", "n_clips"]
    for d in DIMS:
        header += [f"{d}_mean", f"{d}_std", f"{d}_ci95"]
    rows = []
    for rank, m in enumerate(ranked_methods(overall, methods), 1):
        o = overall[m]
        row = [rank, m, o["avg"]["n"], o["n_sessions"], o["n_clips"]]
        for d in DIMS:
            row += [fmt(o[d]["mean"], 4), fmt(o[d]["std"], 4), fmt(o[d]["ci95"], 4)]
        rows.append(row)
    write_csv(path, header, rows)
    written.append(path)

    path = os.path.join(out_dir, f"{stamp}_by_clip.csv")
    header = ["clip_id", "method", "n"] + [f"{d}_{k}" for d in DIMS for k in ("mean", "std")]
    rows = []
    for c in clips:
        for m in methods:
            st = clip_stats.get((c, m))
            if st:
                rows.append([c, m, st["avg"]["n"]]
                            + [fmt(st[d][k], 4) for d in DIMS for k in ("mean", "std")])
    write_csv(path, header, rows)
    written.append(path)

    path = os.path.join(out_dir, f"{stamp}_by_session.csv")
    header = ["session", "subject", "n_ratings", "r_naturalness", "r_timing"]
    header += [f"{m}_{d}" for m in methods for d in RAW_DIMS]
    rows = []
    for s in sessions:
        row = [s["name"], s["subject"], len(s["rows"]),
               fmt(corr[s["name"]]["naturalness"], 4), fmt(corr[s["name"]]["timing"], 4)]
        for m in methods:
            st = session_stats.get((s["name"], m))
            row += [fmt(st[d]["mean"], 4) if st else "" for d in RAW_DIMS]
        rows.append(row)
    write_csv(path, header, rows)
    written.append(path)

    if vs:
        path = os.path.join(out_dir, f"{stamp}_vs_{ref}.csv")
        header = ["reference", "method", "dimension", "n_pairs", "wins", "ties", "losses",
                  "mean_diff", "sign_test_p"]
        rows = [[ref, m, d, v["n_pairs"], v["wins"], v["ties"], v["losses"],
                 fmt(v["mean_diff"], 4), fmt(v["p"], 4)]
                for m, per_dim in vs.items() for d, v in per_dim.items()]
        write_csv(path, header, rows)
        written.append(path)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description="汇总 user_study.ipynb 的所有评分 CSV")
    ap.add_argument("--log-dir", default=DEFAULT_LOG_DIR, help="评分 CSV 所在目录")
    ap.add_argument("--attr", default=DEFAULT_ATTR, help="attr.json，用于固定方法顺序")
    ap.add_argument("--out-dir", default=None,
                    help="统计结果输出目录，默认 <log-dir>/../stats")
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="要剔除的会话（文件名，可带或不带 .csv）")
    ap.add_argument("--ref", default="ours", help="逐对比较的参考方法")
    ap.add_argument("--no-save", action="store_true", help="只打印不落盘")
    args = ap.parse_args(argv)

    log_dir = os.path.abspath(args.log_dir)
    exclude = {os.path.splitext(os.path.basename(e))[0] for e in args.exclude}
    sessions, warnings = load_sessions(log_dir, exclude)
    if not sessions:
        print(f"{log_dir} 下没有可用的评分 CSV", file=sys.stderr)
        for w in warnings:
            print(f"  ! {w}", file=sys.stderr)
        return 1
    warnings += coverage_warnings(sessions)

    methods = method_order(sessions, args.attr)
    clips = clip_order(sessions)
    overall, clip_stats, session_stats = aggregate(sessions, methods, clips)
    corr = leave_one_out_corr(sessions)
    vs = compare_to_ref(sessions, methods, args.ref)

    print(f"日志目录：{log_dir}")
    if exclude:
        print(f"已剔除：{', '.join(sorted(exclude))}")
    for w in warnings:
        print(f"  ! {w}")
    report(sessions, methods, clips, overall, clip_stats, session_stats, corr, vs, args.ref)
    if args.ref not in methods:
        print(f"\n（参考方法 {args.ref} 不在评分里，跳过逐对比较）")

    if not args.no_save:
        out_dir = os.path.abspath(args.out_dir or os.path.join(os.path.dirname(log_dir), "stats"))
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        written = save(out_dir, stamp, sessions, methods, clips, overall, clip_stats,
                       session_stats, corr, vs, args.ref)
        print("\n已写入：")
        for p in written:
            print(f"  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
