#!/usr/bin/env python3
"""
Đánh giá thực nghiệm hiệu năng của hệ thống giải suy luận Griductive.
Chạy thuật toán trên bộ câu đố chuẩn và xuất kết quả ra file experiment_results.csv.
"""
from __future__ import annotations

import csv
from pathlib import Path
import sys

# Thêm thư mục Source vào đường dẫn tìm kiếm module của Python
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.agent import LogicAgent
from core.cnf import CNFEncoder
from core.engine import GameEngine
from core.puzzle_generator import create_sample_puzzles


def run_experiments() -> None:
    """Chạy thực nghiệm trên các kích thước bảng 3x3, 3x4, 4x4, 5x5 và ghi nhận số liệu."""
    puzzles = create_sample_puzzles()
    rows_data: list[dict[str, object]] = []

    print("=========================================================================================")
    print("                    ĐÁNH GIÁ THỰC NGHIỆM THUẬT TOÁN GRIDUCTIVE SOLVER                   ")
    print("=========================================================================================")

    for puzzle in puzzles:
        engine = GameEngine(puzzle)
        agent = LogicAgent()

        # Thu thập thông số Knowledge Base ban đầu trước khi bắt đầu suy luận
        init_state = engine.public_state()
        init_encoded = CNFEncoder(puzzle.characters).encode_public(init_state)

        # Chạy vòng lặp tự động giải không cần phỏng đoán
        while not engine.is_solved():
            res, deduction = engine.auto_step(agent)
            if res.value != "ACCEPTED":
                print(f"Cảnh báo: Câu đố {puzzle.title} dừng lại tại trạng thái {res.value}")
                break

        # Tổng hợp các chỉ số hoạt động của bộ giải SAT qua từng bước suy luận
        step_stats = [entry.stats for entry in engine.trace]
        total_sat_calls = sum(s.sat_calls for s in step_stats)
        total_decisions = sum(s.decisions for s in step_stats)
        total_props = sum(s.propagations for s in step_stats)
        total_backtracks = sum(s.backtracks for s in step_stats)
        total_runtime_ms = sum(s.runtime_ms for s in step_stats)

        row = {
            "puzzle": puzzle.title,
            "dimensions": f"{puzzle.rows}x{puzzle.columns}",
            "primary_variables": init_encoded.primary_variables,
            "auxiliary_variables": init_encoded.auxiliary_variables,
            "initial_clauses": init_encoded.clause_count,
            "sat_calls": total_sat_calls,
            "decisions": total_decisions,
            "propagations": total_props,
            "backtracks": total_backtracks,
            "deduction_steps": len(engine.trace),
            "total_runtime_ms": round(total_runtime_ms, 3),
            "status": "SOLVED" if engine.is_solved() else "FAILED",
        }
        rows_data.append(row)

        print(
            f"Ván: {row['puzzle']:<20} | Kích thước: {row['dimensions']} | "
            f"Biến: {row['primary_variables']} chính + {row['auxiliary_variables']} phụ | "
            f"Mệnh đề: {row['initial_clauses']:<3} | Lần gọi SAT: {row['sat_calls']:<3} | "
            f"Số bước: {row['deduction_steps']:<2} | Thời gian: {row['total_runtime_ms']:>6.2f} ms"
        )

    # Ghi kết quả vào file CSV phục vụ phân tích và báo cáo
    csv_path = Path(__file__).resolve().parent / "experiment_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows_data[0].keys()))
        writer.writeheader()
        writer.writerows(rows_data)

    print("=========================================================================================")
    print(f"Đã xuất kết quả thực nghiệm thành công vào file: {csv_path.name}")


if __name__ == "__main__":
    run_experiments()
