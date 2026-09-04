# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# snake.py —— 贪吃蛇（Snake）
#
# MIT License
#
# Copyright (c) 2026 Your Name
#
# 使用本项目前，请把上面的 "Your Name" 改成你自己的名字或组织名称。
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# ---------------------------------------------------------------------------
"""
贪吃蛇（Snake）游戏 —— 仅使用 Python 标准库（tkinter / winsound），
无需安装任何第三方库。

运行方式：
    python snake.py

操作说明：
    - 方向键 / WASD ：控制移动方向
    - 空格          ：暂停 / 继续（游戏结束后按空格重新开始）
    - R             ：重新开始
    - H             ：查看排行榜（前 10 名，本地持久保存）
    - M             ：开关音效
    - Esc           ：退出游戏

玩法说明：
    - 每吃满 6 个食物升入下一关，速度变快，且逐步出现紫色障碍墙
    - 撞墙、撞障碍墙或撞到自己则游戏结束
    - 游戏结束后若进入前十，会询问姓名并记录分数、关卡与日期
"""

import datetime
import io
import json
import math
import os
import random
import struct
import wave
from collections import deque

import tkinter as tk
from tkinter import simpledialog

# ---------------- 配置 ----------------
CELL_SIZE = 20            # 每个格子的像素大小
GRID_WIDTH = 30           # 横向格子数
GRID_HEIGHT = 20          # 纵向格子数
INIT_SPEED = 150          # 初始每步间隔（毫秒），越小越快
MIN_SPEED = 60            # 最快速度
SPEED_STEP = 8            # 每升一关速度减少的毫秒数
FOODS_PER_LEVEL = 6       # 每关需要吃的食物数
MAX_OBSTACLES = 8         # 障碍墙数量上限
OBSTACLE_GAP = 3          # 障碍墙之间的最小间距（切比雪夫距离）
SCORE_FILE = "snake_highscores.json"
MAX_SCORES = 10           # 排行榜保留条数

# 颜色
COLOR_BG = "#1e1e2e"
COLOR_GRID = "#28283a"
COLOR_SNAKE_HEAD = "#a6e3a1"
COLOR_SNAKE_BODY = "#94e2d5"
COLOR_FOOD = "#f38ba8"
COLOR_OBSTACLE = "#cba6f7"
COLOR_TEXT = "#cdd6f4"
COLOR_HINT = "#6c7086"
COLOR_BANNER = "#f9e2af"
FONT = "Microsoft YaHei"

DIRECTIONS = {
    "Up": (0, -1),
    "Down": (0, 1),
    "Left": (-1, 0),
    "Right": (1, 0),
}
WASD = {
    "w": (0, -1),
    "a": (-1, 0),
    "s": (0, 1),
    "d": (1, 0),
}

# ---------------- 纯函数工具（便于测试） ----------------

def default_scores_path():
    """排行榜文件默认保存在本脚本同目录下。"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), SCORE_FILE)


def load_scores(path=None):
    """读取排行榜，返回 [{name, score, level, date}, ...]（按分数降序）。"""
    path = path or default_scores_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        scores = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("score"), int):
                scores.append({
                    "name": str(item.get("name", "玩家")),
                    "score": item["score"],
                    "level": int(item.get("level", 1)),
                    "date": str(item.get("date", "")),
                })
        scores.sort(key=lambda e: e["score"], reverse=True)
        return scores[:MAX_SCORES]
    except (OSError, ValueError):
        return []


def save_scores(scores, path=None):
    """保存排行榜（截断到 MAX_SCORES 条）。"""
    path = path or default_scores_path()
    scores = sorted(scores, key=lambda e: e["score"], reverse=True)[:MAX_SCORES]
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(scores, f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # 写失败（如目录只读）不阻塞游戏


def qualifies(scores, score):
    """分数能否进入排行榜。"""
    return score > 0 and (len(scores) < MAX_SCORES or score > scores[-1]["score"])


def reachable_cells(head, blocked, width=GRID_WIDTH, height=GRID_HEIGHT):
    """从 head 出发，4 方向 BFS 求所有可达空格（避开 blocked 集合）。"""
    seen = {head}
    queue = deque([head])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            pos = (nx, ny)
            if (0 <= nx < width and 0 <= ny < height
                    and pos not in seen and pos not in blocked):
                seen.add(pos)
                queue.append(pos)
    return seen


def gen_obstacles(count, occupied, width=GRID_WIDTH, height=GRID_HEIGHT,
                  gap=OBSTACLE_GAP, tries=800):
    """
    生成 count 个障碍墙：互不重叠、与 occupied 集合不冲突，
    彼此切比雪夫距离 >= gap。尽量多放，放不下则少放（返回实际列表）。
    """
    obstacles = []
    for _ in range(tries):
        if len(obstacles) >= count:
            break
        pos = (random.randrange(width), random.randrange(height))
        if pos in occupied or pos in obstacles:
            continue
        if all(max(abs(pos[0] - o[0]), abs(pos[1] - o[1])) >= gap
               for o in obstacles):
            obstacles.append(pos)
    return obstacles


def build_wav(notes, rate=22050, amp=11000):
    """
    把 [(频率Hz, 时长ms), ...] 合成一段 16bit 单声道 WAV（字节串），
    每段带 4ms 淡入淡出以避免爆音。返回 bytes。
    """
    samples = []
    fade_ms = 4
    for freq, dur_ms in notes:
        n = max(1, int(rate * dur_ms / 1000))
        fade = min(int(rate * fade_ms / 1000), n // 2)
        for i in range(n):
            if i < fade:
                env = i / fade
            elif i >= n - fade:
                env = (n - 1 - i) / max(1, fade - 1)
            else:
                env = 1.0
            samples.append(int(amp * env * math.sin(2 * math.pi * freq * i / rate)))
        samples.extend([0] * int(rate * 0.02))  # 音段之间 20ms 静音
    if not samples:
        return b""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))
    return buf.getvalue()


# ---------------- 音效 ----------------

class SoundManager:
    """
    Windows 下用 winsound 播放音效；其他平台自动静音。

    注意：winsound 不支持“从内存异步播放”（SND_MEMORY + SND_ASYNC 会抛
    RuntimeError），因此这里把合成好的 WAV 写入临时目录，再以文件方式
    异步播放（SND_FILENAME | SND_ASYNC），程序退出时自动清理临时文件。
    """

    def __init__(self):
        self.muted = False
        self._winsound = None
        self._paths = {}
        try:
            import winsound
            self._winsound = winsound
        except ImportError:
            pass  # 非 Windows：自动静音

        self.sounds = {
            "start": build_wav([(523, 60), (784, 90)]),
            "eat": build_wav([(880, 45), (1175, 60)]),
            "levelup": build_wav([(660, 70), (880, 70), (1175, 100)]),
            "gameover": build_wav([(523, 120), (392, 120), (262, 240)]),
            "record": build_wav([(784, 80), (988, 80), (1175, 80), (1568, 180)]),
        }
        if self._winsound is not None:
            self._prepare_files()

    def _prepare_files(self):
        """把内置音效写入临时 WAV 文件，供异步播放。"""
        import atexit
        import tempfile

        prefix = f"snake_sfx_{os.getpid()}_"
        try:
            for name, data in self.sounds.items():
                path = os.path.join(tempfile.gettempdir(), prefix + name + ".wav")
                with open(path, "wb") as f:
                    f.write(data)
                self._paths[name] = path
        except OSError:
            self._paths.clear()  # 临时目录不可写则放弃音效
            return
        atexit.register(self._cleanup)

    def _cleanup(self):
        for path in self._paths.values():
            try:
                os.remove(path)
            except OSError:
                pass
        self._paths.clear()

    def play(self, name):
        if self.muted or self._winsound is None:
            return
        path = self._paths.get(name)
        if not path:
            return
        try:
            # SND_FILENAME(文件) + SND_ASYNC(异步)：不阻塞游戏主循环
            self._winsound.PlaySound(
                path, self._winsound.SND_FILENAME | self._winsound.SND_ASYNC)
        except Exception:
            pass


# ---------------- 游戏 ----------------

class SnakeGame:
    def __init__(self, root):
        self.root = root
        self.root.title("贪吃蛇 Snake")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root,
            width=GRID_WIDTH * CELL_SIZE,
            height=GRID_HEIGHT * CELL_SIZE,
            bg=COLOR_BG,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.status_label = tk.Label(
            root,
            text="",
            font=(FONT, 11, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        )
        self.status_label.pack(fill="x", pady=4)

        self.root.bind("<KeyPress>", self.on_key)

        self.sound = SoundManager()
        self.scores = load_scores()
        self.hi_score = self.scores[0]["score"] if self.scores else 0
        self.after_id = None
        self.banner_after_id = None
        self.banner_text = None
        self.canvas.focus_set()
        self.reset()

    # ---------- 状态管理 ----------

    def reset(self, *args):
        """开始新一局。"""
        self.cancel_tick()
        self.cancel_banner()
        cx, cy = GRID_WIDTH // 2, GRID_HEIGHT // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)
        self.pending_direction = (1, 0)
        self.obstacles = []
        self.level = 1
        self.foods_eaten = 0
        self.score = 0
        self.speed = INIT_SPEED
        self.running = True
        self.paused = False
        self.game_over = False
        self.show_board = False
        self.banner_text = None
        self.food = self.spawn_food()
        self.update_status("空格 暂停 · H 排行榜 · M 音效")
        self.draw()
        self.sound.play("start")  # 开局提示音，也便于验证声音是否正常

    def cancel_tick(self):
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def schedule_tick(self):
        """安排下一帧移动（先取消旧回调，防止叠加导致加速）。"""
        self.cancel_tick()
        self.after_id = self.root.after(self.speed, self.tick)

    def cancel_banner(self):
        if self.banner_after_id is not None:
            self.root.after_cancel(self.banner_after_id)
            self.banner_after_id = None

    def level_speed(self, level):
        return max(MIN_SPEED, INIT_SPEED - (level - 1) * SPEED_STEP)

    def update_status(self, hint=""):
        state = "游戏结束" if self.game_over else ("已暂停" if self.paused else "进行中")
        sound_txt = "开" if not self.sound.muted else "关"
        text = (f"{state}    关卡 {self.level}    分数 {self.score}    "
                f"最高 {self.hi_score}    声音 {sound_txt}")
        if hint:
            text += f"    {hint}"
        self.status_label.config(text=text)

    # ---------- 食物 / 障碍 ----------

    def spawn_food(self):
        """在所有可达空格中随机放食物；无空格可放返回 None（视为通关）。"""
        blocked = set(self.obstacles) | set(self.snake)
        candidates = reachable_cells(self.snake[0], blocked)
        candidates.discard(self.snake[0])
        if not candidates:
            return None
        return random.choice(tuple(candidates))

    def add_obstacles_for_level(self, level):
        """按当前关卡补齐障碍墙（只增不减）。"""
        want = min(MAX_OBSTACLES, max(0, level - 1))
        have = len(self.obstacles)
        if want <= have:
            return
        occupied = set(self.obstacles) | set(self.snake)
        new_ones = gen_obstacles(want - have, occupied)
        self.obstacles.extend(new_ones)
        # 若新障碍盖住了食物或使食物不可达，则重放食物
        if self.food is None or self.food not in reachable_cells(
                self.snake[0], set(self.obstacles) | set(self.snake)):
            self.food = self.spawn_food()

    # ---------- 主循环 ----------

    def tick(self):
        """每帧：移动、碰撞判定、成长、关卡推进。"""
        if self.game_over or self.paused or self.show_board:
            return  # 不重新排程，处于冻结状态

        self.direction = self.pending_direction
        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # 撞墙或障碍墙
        if not (0 <= new_head[0] < GRID_WIDTH and 0 <= new_head[1] < GRID_HEIGHT):
            self.end_game()
            return
        if new_head in self.obstacles:
            self.end_game()
            return

        will_grow = new_head == self.food
        body = self.snake[:-1] if will_grow else self.snake
        if new_head in body:  # 撞到自己
            self.end_game()
            return

        self.snake.insert(0, new_head)
        if will_grow:
            self.food = None  # 占位，稍后重放
            self.score += 1
            self.foods_eaten += 1
            new_level = self.foods_eaten // FOODS_PER_LEVEL + 1
            if new_level > self.level:
                self.level = new_level
                self.speed = self.level_speed(self.level)
                self.add_obstacles_for_level(self.level)
                self.show_banner(f"第 {self.level} 关", COLOR_BANNER)
                self.sound.play("levelup")
            else:
                self.sound.play("eat")
            self.food = self.spawn_food()
            if self.food is None:
                self.end_game(victory=True)
                return
        else:
            self.snake.pop()

        self.update_status()
        self.draw()
        self.schedule_tick()

    def end_game(self, victory=False):
        """游戏结束（或通关），处理排行榜入库。"""
        self.cancel_tick()
        self.game_over = True
        self.sound.play("record" if victory else "gameover")

        is_record = False
        if qualifies(self.scores, self.score):
            name = "玩家"
            try:
                answer = simpledialog.askstring(
                    "进入排行榜",
                    f"你的分数：{self.score}（第 {self.level} 关）\n请输入昵称：",
                    initialvalue=name,
                    parent=self.root,
                )
                if answer is not None and answer.strip():
                    name = answer.strip()[:12]
            except Exception:
                pass
            self.scores.append({
                "name": name,
                "score": self.score,
                "level": self.level,
                "date": datetime.date.today().isoformat(),
            })
            self.scores.sort(key=lambda e: e["score"], reverse=True)
            self.scores = self.scores[:MAX_SCORES]
            save_scores(self.scores)
            if self.score >= self.hi_score:
                is_record = True
                self.hi_score = self.score
        else:
            self.hi_score = max(self.hi_score, self.score)

        # 通关或破纪录播号角声，其余情况播游戏结束音
        self.sound.play("record" if (victory or is_record) else "gameover")

        title = "恭喜通关！" if victory else "游戏结束"
        if is_record:
            title += "　★ 新纪录！"
        self.update_status()
        self.draw_overlay(
            f"{title}\n最终分数：{self.score}（第 {self.level} 关）\n\n"
            "按 空格 或 R 重新开始　·　H 排行榜"
        )

    # ---------- 输入 ----------

    def on_key(self, event):
        key = event.keysym
        char = (event.char or "").lower()

        # Esc 退出
        if key == "Escape":
            self.root.destroy()
            return

        # 声音开关（取消静音时播提示音便于确认）
        if char == "m":
            self.sound.muted = not self.sound.muted
            if not self.sound.muted:
                self.sound.play("start")
            self.update_status()
            return

        # 排行榜
        if char == "h":
            self.toggle_board()
            return

        # 空格：暂停 / 继续 / 重开
        if key == "space":
            if self.game_over:
                self.reset()
            elif self.show_board:
                self.toggle_board()
            else:
                self.toggle_pause()
            return

        # R：重新开始
        if char == "r":
            self.reset()
            return

        # 游戏结束：移动键不再处理
        if self.game_over:
            return

        new_dir = DIRECTIONS.get(key) or WASD.get(char)
        if new_dir is None:
            return
        # 排行榜显示中不移动
        if self.show_board:
            return
        # 禁止原地掉头；记录为待定方向，下一帧生效
        if (new_dir[0] * -1, new_dir[1] * -1) != self.direction:
            self.pending_direction = new_dir

    def toggle_pause(self):
        if self.game_over:
            return
        self.paused = not self.paused
        if self.paused:
            self.cancel_tick()
            self.update_status("空格 继续")
            self.draw_overlay("已暂停\n\n按 空格 继续")
        else:
            self.update_status()
            self.draw()
            self.schedule_tick()

    def toggle_board(self):
        """显示 / 关闭排行榜（显示期间冻结游戏进程）。"""
        self.show_board = not self.show_board
        if self.show_board:
            self.cancel_tick()
            self.draw_board_overlay()
            self.update_status("H 关闭排行榜")
        else:
            self.update_status()
            if not self.game_over and not self.paused:
                self.schedule_tick()
            else:
                self.draw()

    def show_banner(self, text, color):
        self.banner_text = (text, color)
        self.draw()
        self.cancel_banner()
        self.banner_after_id = self.root.after(1600, self.clear_banner)

    def clear_banner(self):
        self.banner_after_id = None
        self.banner_text = None
        if not self.game_over and not self.paused and not self.show_board:
            self.draw()

    # ---------- 绘制 ----------

    def draw(self):
        self.canvas.delete("all")
        # 网格
        for x in range(0, GRID_WIDTH * CELL_SIZE, CELL_SIZE):
            self.canvas.create_line(x, 0, x, GRID_HEIGHT * CELL_SIZE, fill=COLOR_GRID)
        for y in range(0, GRID_HEIGHT * CELL_SIZE, CELL_SIZE):
            self.canvas.create_line(0, y, GRID_WIDTH * CELL_SIZE, y, fill=COLOR_GRID)

        # 食物
        if self.food is not None:
            fx, fy = self.food
            pad = 3
            self.canvas.create_oval(
                fx * CELL_SIZE + pad,
                fy * CELL_SIZE + pad,
                (fx + 1) * CELL_SIZE - pad,
                (fy + 1) * CELL_SIZE - pad,
                fill=COLOR_FOOD,
                outline=COLOR_FOOD,
            )

        # 障碍墙
        for (ox, oy) in self.obstacles:
            self.canvas.create_rectangle(
                ox * CELL_SIZE + 1,
                oy * CELL_SIZE + 1,
                (ox + 1) * CELL_SIZE - 1,
                (oy + 1) * CELL_SIZE - 1,
                fill=COLOR_OBSTACLE,
                outline=COLOR_OBSTACLE,
            )

        # 蛇
        for i, (sx, sy) in enumerate(self.snake):
            color = COLOR_SNAKE_HEAD if i == 0 else COLOR_SNAKE_BODY
            self.canvas.create_rectangle(
                sx * CELL_SIZE,
                sy * CELL_SIZE,
                (sx + 1) * CELL_SIZE,
                (sy + 1) * CELL_SIZE,
                fill=color,
                outline=COLOR_BG,
                width=1,
            )

        # 过关横幅
        if self.banner_text:
            text, color = self.banner_text
            self.draw_center_text(text, color=color, size=24, semi=True)

    def _center(self):
        return GRID_WIDTH * CELL_SIZE // 2, GRID_HEIGHT * CELL_SIZE // 2

    def draw_center_text(self, text, color=COLOR_TEXT, size=18, semi=False):
        """在画布中央绘制多行文本；semi=True 时加半透明底。"""
        if semi:
            self.canvas.create_rectangle(
                0, 0, GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE,
                fill="#000000", stipple="gray50", outline="")
        cx, cy = self._center()
        self.canvas.create_text(
            cx, cy, text=text, fill=color,
            font=(FONT, size, "bold"), justify="center")

    def draw_overlay(self, text):
        self.draw_center_text(text, semi=True)

    def draw_board_overlay(self):
        """排行榜浮层。"""
        lines = ["── 排行榜 TOP 10 ──"]
        if not self.scores:
            lines.append("（暂无记录，快来创造第一个纪录吧！）")
        else:
            for i, entry in enumerate(self.scores, 1):
                rank = f"{i}."
                lines.append(f"{rank:<4}{entry['name']}　{entry['score']} 分"
                             f"　· Lv{entry['level']}　{entry['date']}")
        lines.append("")
        lines.append("按 H 关闭")
        self.draw_center_text("\n".join(lines), size=14, semi=True)


def main():
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
