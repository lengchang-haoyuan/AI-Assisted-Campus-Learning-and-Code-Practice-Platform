"""将已完成 S06 原始 JSON 导出为论文可复核 CSV 与独立 SVG，不执行计算作业。"""

import csv
import html
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def graph(summaries, lifecycle, value_key, title, path):
    width, height = 1080, 640
    left, top, chart_width, chart_height = 95, 100, 890, 410
    colors = {"python": "#687687", "spark": "#1a7181"}
    values = [s["medians"][f"{engine}-{lifecycle}"][value_key]
              for s in summaries for engine in ("python", "spark")]
    maximum = max(5, math.ceil(max(values)/5)*5)
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
              '<rect width="100%" height="100%" fill="white"/>',
              '<g font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif" fill="#23323c">',
              f'<text x="{left}" y="43" font-size="24">{html.escape(title)}</text>',
              f'<text x="{left}" y="72" font-size="14">本机 local[2] · driver 2 GiB · shuffle 8 · 三轮中位数 · 单位：秒</text>']
    for i in range(6):
        value = maximum*i/5
        y = top+chart_height-chart_height*i/5
        pieces.extend([f'<path d="M {left} {y:.2f} H {left+chart_width}" stroke="#dce3e8" fill="none"/>',
                       f'<text x="{left-12}" y="{y+5:.2f}" text-anchor="end" font-size="13">{value:g}</text>'])
    for group, summary in enumerate(summaries):
        center = left+chart_width*(group+.5)/2
        for j, engine in enumerate(("python", "spark")):
            value = summary["medians"][f"{engine}-{lifecycle}"][value_key]
            bar_height = chart_height*value/maximum
            x = center-110+j*120
            y = top+chart_height-bar_height
            pieces.extend([f'<rect x="{x:.2f}" y="{y:.2f}" width="95" height="{bar_height:.2f}" fill="{colors[engine]}"/>',
                           f'<text x="{x+47.5:.2f}" y="{y-10:.2f}" text-anchor="middle" font-size="16">{value:.3f}</text>'])
        pieces.append(f'<text x="{center}" y="{top+chart_height+30}" text-anchor="middle" font-size="16">{summary["scale"]:,} 唯一学习记录 / {summary["scale"]//100:,} 合成主体</text>')
    for i, (engine, label) in enumerate((("python", "Python 标准库参考"), ("spark", "PySpark"))):
        x = left+i*250
        pieces.extend([f'<rect x="{x}" y="567" width="18" height="18" fill="{colors[engine]}"/>',
                       f'<text x="{x+28}" y="581" font-size="14">{label}</text>'])
    pieces.extend([f'<text x="{left}" y="617" font-size="12">参考实现每主体重复全表去重与关系校验；非优化 SQL 基线。未清 OS 缓存，无通用加速结论。</text>',
                   '</g></svg>'])
    path.write_text("\n".join(pieces)+"\n", encoding="utf-8")


def main():
    summaries = [json.loads((HERE/f"n{n}-summary.json").read_text(encoding="utf-8")) for n in (10000, 100000)]
    fields = ["scale", "engine", "lifecycle", "label", "measured", "input_load_seconds", "compute_seconds",
              "output_seconds", "validation_seconds", "round_total_seconds", "peak_process_tree_rss_bytes",
              "rss_samples", "equal_reference_leaf_assertions", "process_name", "external_process_seconds", "session_startup_seconds"]
    with (HERE/"all-rounds.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for summary in summaries:
            for process in summary["runs"]:
                worker = process["worker"]
                for sample in worker["rounds"]:
                    row = {field: sample.get(field) for field in fields}
                    row.update(scale=summary["scale"], engine=worker["engine"], lifecycle=worker["lifecycle"],
                               peak_process_tree_rss_bytes=sample["memory"]["peak_process_tree_rss_bytes"],
                               rss_samples=sample["memory"]["samples"], process_name=process["name"],
                               external_process_seconds=process["external_process_seconds"],
                               session_startup_seconds=worker["session_startup_seconds"])
                    writer.writerow(row)
    graph(summaries, "process_cold", "external_process_seconds", "进程冷启动：完整进程墙钟时间", HERE/"process-cold-median.svg")
    graph(summaries, "hot", "round_total_seconds", "同进程预热后：完整作业与结果核对时间", HERE/"hot-round-median.svg")
    print(json.dumps({"exported": ["all-rounds.csv", "process-cold-median.svg", "hot-round-median.svg"],
                      "rounds": sum(len(p["worker"]["rounds"]) for s in summaries for p in s["runs"])}))


if __name__ == "__main__":
    main()
