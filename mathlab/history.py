# -*- coding: utf-8 -*-
"""计算历史: 本地持久化 (JSON), 支持搜索 / 删除 / 导出

存储位置: %LOCALAPPDATA%\\MathLab\\history.json  (非 Windows 回落到 ~/.mathlab)
"""
from __future__ import annotations

import csv
import json
import os
import time
import uuid
from datetime import datetime


def default_dir():
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return os.path.join(base, "MathLab")
    return os.path.join(os.path.expanduser("~"), ".mathlab")


class History:
    def __init__(self, path=None, limit=800):
        self.dir = default_dir()
        self.path = path or os.path.join(self.dir, "history.json")
        self.limit = limit
        self.items = []
        self.load()

    # ---------------- 持久化 ----------------
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                data = data.get("items", [])
            self.items = [it for it in data if isinstance(it, dict)]
        except FileNotFoundError:
            self.items = []
        except Exception:
            self.items = []

    def save(self):
        try:
            os.makedirs(self.dir, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "items": self.items}, fh,
                          ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except Exception:
            pass

    # ---------------- 增删查 ----------------
    def add(self, kind, expr, result, note=""):
        item = {
            "id": uuid.uuid4().hex[:12],
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "kind": kind,
            "expr": (expr or "").strip(),
            "result": (result or "").strip(),
            "note": note,
            "fav": False,
        }
        self.items.insert(0, item)
        if len(self.items) > self.limit:
            self.items = self.items[:self.limit]
        self.save()
        return item

    def search(self, q=""):
        if not q:
            return list(self.items)
        q = q.strip().lower()
        out = []
        for it in self.items:
            hay = " ".join([it.get("kind", ""), it.get("expr", ""),
                            it.get("result", ""), it.get("note", "")]).lower()
            if q in hay:
                out.append(it)
        return out

    def get(self, iid):
        for it in self.items:
            if it.get("id") == iid:
                return it
        return None

    def delete(self, iid):
        before = len(self.items)
        self.items = [it for it in self.items if it.get("id") != iid]
        if len(self.items) != before:
            self.save()
            return True
        return False

    def toggle_fav(self, iid):
        it = self.get(iid)
        if it:
            it["fav"] = not it.get("fav", False)
            self.save()
            return it["fav"]
        return False

    def clear(self, keep_fav=True):
        self.items = [it for it in self.items if it.get("fav")] if keep_fav else []
        self.save()

    def count(self):
        return len(self.items)

    # ---------------- 导出 ----------------
    def export_csv(self, path):
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["时间", "类别", "输入", "结果", "备注"])
            for it in self.items:
                w.writerow([it.get("ts", ""), it.get("kind", ""), it.get("expr", ""),
                            it.get("result", ""), it.get("note", "")])
        return path

    def export_txt(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            for it in reversed(self.items):
                fh.write("[%s] %s\n  %s\n  = %s\n\n" % (
                    it.get("ts", ""), it.get("kind", ""), it.get("expr", ""),
                    it.get("result", "")))
        return path
