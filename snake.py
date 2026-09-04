# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# snake.py —— 贪吃蛇（Snake）
#
# MIT License
#
# Copyright (c) 2026 tongsy903
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
    - 启动后：按 空格 或 方向键 / WASD 开始游戏（窗口会自动获得焦点，
      无需先用鼠标点击窗口）
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
import time
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

ANIM_FPS = 60             # 移动平滑动画的帧率
SNAKE_RADIUS = 0.38       # 蛇身半径（相对格子边长）

# 颜色（Catppuccin Mocha 系配色）
COLOR_BG = "#1e1e2e"            # 窗口底色
COLOR_CHECKER_A = "#1f1f31"     # 棋盘格 A
COLOR_CHECKER_B = "#26263b"     # 棋盘格 B
COLOR_FRAME = "#313244"         # 棋盘外框
COLOR_PANEL = "#181825"         # 顶部状态栏 / 浮层面板
COLOR_TEXT = "#cdd6f4"
COLOR_HINT = "#6c7086"
COLOR_BANNER = "#f9e2af"

# 蛇（头→尾渐变）
SNAKE_HEAD_RGB = (0x8a, 0xe8, 0x9b)
SNAKE_TAIL_RGB = (0x4f, 0xa3, 0x97)
SNAKE_OUTLINE = "#0e0e18"
EYE_WHITE = "#ffffff"
EYE_PUPIL = "#11111b"

# 食物（高光苹果）
FOOD_MAIN = "#f0506e"           # 果身主色
FOOD_SHADE = "#c2255c"          # 果身暗部
FOOD_HILIGHT = "#ffb3c1"        # 高光
FOOD_STEM = "#7f5539"           # 果柄
FOOD_LEAF = "#7bc47f"           # 叶子

# 障碍
OBSTACLE_FILL = "#cba6f7"
OBSTACLE_EDGE = "#8f7ac0"
OBSTACLE_HILIGHT = "#e6dcff"

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

def hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def mix_color(c1, c2, t):
    """在两种 #rrggbb 颜色之间线性插值，返回 #rrggbb。"""
    t = max(0.0, min(1.0, t))
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def lerp(a, b, t):
    return a + (b - a) * t


def cell_center(pos):
    return (pos[0] * CELL_SIZE + CELL_SIZE / 2,
            pos[1] * CELL_SIZE + CELL_SIZE / 2)


def lerp_point(p1, p2, t):
    return (lerp(p1[0], p2[0], t), lerp(p1[1], p2[1], t))


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
        self.root.configure(bg=COLOR_PANEL)

        self.canvas = tk.Canvas(
            root,
            width=GRID_WIDTH * CELL_SIZE,
            height=GRID_HEIGHT * CELL_SIZE,
            bg=COLOR_BG,
            highlightthickness=0,
        )
        self.canvas.pack(padx=6, pady=(6, 0))

        self.status_label = tk.Label(
            root,
            text="",
            font=(FONT, 11, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_PANEL,
        )
        self.status_label.pack(fill="x", padx=10, pady=7)

        self.root.bind("<KeyPress>", self.on_key)

        self.sound = SoundManager()
        self.scores = load_scores()
        self.hi_score = self.scores[0]["score"] if self.scores else 0
        self.after_id = None
        self.anim_after_id = None      # 平滑移动动画定时器
        self._trans = None             # 当前移动过渡信息
        self.banner_after_id = None
        self.banner_text = None
        self.canvas.focus_set()
        self._build_board()            # 静态棋盘背景（只需画一次）
        self.reset(ready=True)
        # 窗口显示后强制获得键盘焦点：否则要先用鼠标点一下窗口按键才生效
        self.root.after(30, self._grab_focus)

    # ---------- 状态管理 ----------

    def reset(self, *args, ready=False):
        """开始新一局；ready=True 时停在“按任意键开始”画面等待玩家。"""
        self.cancel_tick()
        self.cancel_anim()
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
        self.ready = bool(ready)
        self.food = self.spawn_food()
        self.sound.play("start")  # 开局提示音，也便于验证声音是否正常
        if self.ready:
            # 就绪画面：不自动开跑，等玩家按键
            self.cancel_tick()
            self.update_status("按 空格 或 方向键 开始")
            self.draw_ready_overlay()
        else:
            self.update_status("空格 暂停 · H 排行榜 · M 音效")
            self.draw()
            self.schedule_tick()

    def _grab_focus(self):
        """把键盘焦点抢到游戏窗口/画布上，保证按键无需先点窗口。"""
        try:
            self.root.lift()
            self.root.focus_force()
            self.canvas.focus_set()
        except tk.TclError:
            pass  # 窗口已关闭等情况直接忽略

    def begin_play(self):
        """从就绪画面开始游戏。"""
        self.ready = False
        self.game_over = False
        self.paused = False
        self.show_board = False
        self.update_status("空格 暂停 · H 排行榜 · M 音效")
        self.draw()
        self.schedule_tick()

    def cancel_tick(self):
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def cancel_anim(self):
        """停止平滑移动动画。"""
        if self.anim_after_id is not None:
            self.root.after_cancel(self.anim_after_id)
            self.anim_after_id = None
        self._trans = None

    def schedule_tick(self):
        """安排下一帧移动（先取消旧回调，防止叠加导致加速）。"""
        self.cancel_tick()
        self.after_id = self.root.after(self.speed, self.tick)

    def start_transition(self, old_snake, grew):
        """
        开始一次平滑移动：从 old_snake 的各格位置滑动到 self.snake
        的当前位置，动画时长与一次逻辑步进一致。
        """
        self.cancel_anim()
        self._trans = {
            "old": old_snake,
            "grew": grew,
            "t0": time.monotonic(),
            "dur": max(0.03, self.speed) / 1000.0,
        }
        self._anim_frame()

    def _anim_frame(self):
        """平滑动画的一帧（固定帧率，逻辑移动间隔内插值渲染）。"""
        self.anim_after_id = None
        if self._trans is None:
            return
        f = (time.monotonic() - self._trans["t0"]) / self._trans["dur"]
        if f >= 1.0:
            self._trans = None
            self.draw()          # 过渡结束：画最终画面
            return
        self.canvas.delete("dynamic")
        self._paint(self._points_at(f))
        self.anim_after_id = self.root.after(
            int(1000 / ANIM_FPS), self._anim_frame)

    def _points_at(self, f):
        """过渡进度 f∈[0,1] 时蛇身各节点的像素坐标（头→尾）。"""
        old = self._trans["old"]
        pts = [lerp_point(cell_center(old[0]), cell_center(self.snake[0]), f)]
        pts.extend(cell_center(p) for p in self.snake[1:])
        if not self._trans["grew"] and f < 0.999:
            # 未吃食物：尾巴会缩短一格，让尾尖从被弹出的旧尾格滑向新尾格
            tail_from = cell_center(old[-1])
            tail_to = pts[-1]
            if abs(tail_from[0] - tail_to[0]) + abs(tail_from[1] - tail_to[1]) > 0.1:
                pts.append(lerp_point(tail_from, tail_to, f))
        return pts

    def cancel_banner(self):
        if self.banner_after_id is not None:
            self.root.after_cancel(self.banner_after_id)
            self.banner_after_id = None

    def level_speed(self, level):
        return max(MIN_SPEED, INIT_SPEED - (level - 1) * SPEED_STEP)

    def update_status(self, hint=""):
        if self.ready:
            state = "就绪"
        elif self.game_over:
            state = "游戏结束"
        elif self.paused:
            state = "已暂停"
        else:
            state = "进行中"
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
        if self.game_over or self.paused or self.show_board or self.ready:
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

        old_snake = list(self.snake)  # 记录动画起点
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
        self.start_transition(old_snake, will_grow)  # 平滑滑动到新位置
        self.schedule_tick()

    def end_game(self, victory=False):
        """游戏结束（或通关），处理排行榜入库。"""
        self.cancel_tick()
        self.cancel_anim()
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
        # 昵称输入框可能抢走焦点，稍后夺回，保证按 R/空格 直接有效
        self.root.after(30, self._grab_focus)

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

        # 就绪画面：按 空格 / 方向键 / WASD 开始游戏
        if self.ready:
            if key == "space":
                self.begin_play()
                return
            new_dir = DIRECTIONS.get(key) or WASD.get(char)
            if new_dir is not None:
                self.direction = new_dir      # 朝按下的方向开始移动
                self.pending_direction = new_dir
                self.begin_play()
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
            self.cancel_anim()
            self.update_status("空格 继续")
            self.draw_overlay("已暂停\n\n按 空格 继续", size=15)
        else:
            self.update_status()
            self.draw()
            self.schedule_tick()

    def toggle_board(self):
        """显示 / 关闭排行榜（显示期间冻结游戏进程）。"""
        self.show_board = not self.show_board
        if self.show_board:
            self.cancel_tick()
            self.cancel_anim()
            self.draw_board_overlay()
            self.update_status("H 关闭排行榜")
        else:
            self.update_status()
            if self.ready:
                self.draw_ready_overlay()          # 尚未开始，回到就绪画面
            elif self.game_over:
                self.draw()
            elif self.paused:
                self.draw()
                self.draw_overlay("已暂停\n\n按 空格 继续")
            else:
                self.schedule_tick()

    def draw_ready_overlay(self):
        """开始画面。"""
        self.draw()
        self.draw_overlay(
            "贪吃蛇 Snake\n"
            "方向键 / WASD 移动 · 空格 暂停\n\n"
            "按 空格 或 方向键 开始\n"
            "（H 排行榜 · M 音效 · Esc 退出）",
            size=15)

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

    def _build_board(self):
        """一次性绘制静态棋盘背景与边框（标签 'static'，此后不重画）。"""
        w, h = GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE
        self.canvas.create_rectangle(0, 0, w, h, fill=COLOR_BG, outline="",
                                     tags=("static",))
        for cy in range(GRID_HEIGHT):
            for cx in range(GRID_WIDTH):
                fill = COLOR_CHECKER_A if (cx + cy) % 2 == 0 else COLOR_CHECKER_B
                self.canvas.create_rectangle(
                    cx * CELL_SIZE, cy * CELL_SIZE,
                    (cx + 1) * CELL_SIZE, (cy + 1) * CELL_SIZE,
                    fill=fill, outline="", tags=("static",))
        self.canvas.create_rectangle(0.5, 0.5, w - 0.5, h - 0.5,
                                     outline=COLOR_FRAME, width=2,
                                     tags=("static",))

    def draw(self):
        """整帧重绘：逻辑当前位置的静态画面。"""
        self.canvas.delete("dynamic", "overlay")
        self._paint([cell_center(p) for p in self.snake])

    def _paint(self, pts):
        """绘制动态内容（食物 / 障碍 / 蛇 / 过关横幅）。"""
        self._draw_food()
        self._draw_obstacles()
        self._draw_snake(pts)
        if self.banner_text:
            text, color = self.banner_text
            self._dim_board()
            self._center_text(text, color=color, size=26)

    def _dim_board(self, color="#000000", stipple="gray50", tags=("dynamic",)):
        self.canvas.create_rectangle(
            0, 0, GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE,
            fill=color, stipple=stipple, outline="", tags=tags)

    def _center(self):
        return GRID_WIDTH * CELL_SIZE // 2, GRID_HEIGHT * CELL_SIZE // 2

    def _center_text(self, text, color=COLOR_TEXT, size=18, tags=("dynamic",)):
        cx, cy = self._center()
        self.canvas.create_text(
            cx, cy, text=text, fill=color, font=(FONT, size, "bold"),
            justify="center", tags=tags)

    def _round_rect_item(self, x0, y0, x1, y1, r=12, **kw):
        """用平滑多边形近似圆角矩形。"""
        pts = [
            x0 + r, y0, x1 - r, y0,
            x1, y0, x1, y0 + r,
            x1, y1 - r, x1, y1,
            x1 - r, y1, x0 + r, y1,
            x0, y1, x0, y1 - r,
            x0, y0 + r, x0, y0,
        ]
        return self.canvas.create_polygon(
            *pts, smooth=True, splinesteps=24, **kw)

    def _draw_food(self):
        """食物：带高光的小苹果。"""
        if self.food is None:
            return
        tags = ("dynamic",)
        cx, cy = cell_center(self.food)
        r = CELL_SIZE * 0.46
        # 果柄与叶子
        self.canvas.create_oval(
            cx + r * 0.10, cy - r * 1.15, cx + r * 0.52, cy - r * 0.35,
            fill=FOOD_LEAF, outline="", tags=tags)
        self.canvas.create_line(
            cx, cy - r * 0.95, cx + 0.5, cy - r * 1.35,
            fill=FOOD_STEM, width=2, tags=tags)
        # 果身：暗部做底，主色偏左上，形成立体感
        self.canvas.create_oval(
            cx - r, cy - r * 0.94, cx + r, cy + r * 1.06,
            fill=FOOD_SHADE, outline="", tags=tags)
        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill=FOOD_MAIN, outline="", tags=tags)
        # 高光
        self.canvas.create_oval(
            cx - r * 0.62, cy - r * 0.72, cx - r * 0.08, cy - r * 0.16,
            fill=FOOD_HILIGHT, outline="", tags=tags)
        self.canvas.create_oval(
            cx - r * 0.52, cy - r * 0.62, cx - r * 0.30, cy - r * 0.42,
            fill="#ffffff", outline="", tags=tags)

    def _draw_obstacles(self):
        """障碍：圆角水晶块，带高光点。"""
        tags = ("dynamic",)
        pad = CELL_SIZE * 0.10
        for ox, oy in self.obstacles:
            x0 = ox * CELL_SIZE + pad
            y0 = oy * CELL_SIZE + pad
            x1 = (ox + 1) * CELL_SIZE - pad
            y1 = (oy + 1) * CELL_SIZE - pad
            self._round_rect_item(
                x0, y0, x1, y1, r=7,
                fill=OBSTACLE_FILL, outline=OBSTACLE_EDGE, width=2,
                tags=tags)
            # 顶部内侧高光
            self._round_rect_item(
                x0 + 4, y0 + 4, x1 - 4, y0 + (y1 - y0) * 0.34, r=4,
                fill=OBSTACLE_HILIGHT, outline="", tags=tags)

    def _draw_snake(self, pts):
        """蛇：圆头圆尾的胶囊状渐变身体 + 有神的眼睛。"""
        n = len(pts)
        if n == 0:
            return
        tags = ("dynamic",)
        r = CELL_SIZE * SNAKE_RADIUS
        head_hex = "#%02x%02x%02x" % SNAKE_HEAD_RGB
        tail_hex = "#%02x%02x%02x" % SNAKE_TAIL_RGB
        colors = [mix_color(head_hex, tail_hex, i / max(1, n - 1))
                  for i in range(n)]

        def circle(p, radius, fill):
            self.canvas.create_oval(
                p[0] - radius, p[1] - radius, p[0] + radius, p[1] + radius,
                fill=fill, outline="", tags=tags)

        # 1) 深色描边（一条贯通折线，圆角连接）
        coords = [v for p in pts for v in p]
        if n > 1:
            self.canvas.create_line(
                *coords, width=r * 2 + 3, capstyle=tk.ROUND,
                joinstyle=tk.ROUND, fill=SNAKE_OUTLINE, tags=tags)
        # 2) 渐变段
        for i in range(n - 1):
            self.canvas.create_line(
                *pts[i], *pts[i + 1], width=r * 2,
                capstyle=tk.ROUND, fill=colors[i + 1], tags=tags)
        # 3) 每个节点画圆，让转弯处圆润平滑
        for i in range(n):
            circle(pts[i], r, colors[i])
        # 4) 头部稍大 + 眼睛
        head = pts[0]
        hr = r * 1.15
        circle(head, hr + 1.5, SNAKE_OUTLINE)
        circle(head, hr, colors[0])
        dx, dy = self.direction
        px, py = -dy, dx
        for side in (1.0, -1.0):
            eye = (head[0] + dx * r * 0.35 + px * r * 0.55 * side,
                   head[1] + dy * r * 0.35 + py * r * 0.55 * side)
            circle(eye, r * 0.38, EYE_WHITE)
            pupil = (eye[0] + dx * r * 0.16, eye[1] + dy * r * 0.16)
            circle(pupil, r * 0.19, EYE_PUPIL)

    def draw_overlay(self, text, size=15, pw=None, ph=None):
        """居中弹层：压暗背景 + 圆角面板 + 文字。"""
        self.canvas.delete("overlay")
        w, h = GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE
        pw = pw or int(w * 0.80)
        ph = ph or int(h * 0.60)
        pw = max(140, min(w - 24, pw))
        ph = max(90, min(h - 24, ph))
        tags = ("overlay",)
        self._dim_board(tags=tags)
        x0, y0 = (w - pw) // 2, (h - ph) // 2
        self._round_rect_item(
            x0, y0, x0 + pw, y0 + ph, r=18,
            fill=COLOR_PANEL, outline="#45475a", width=2, tags=tags)
        self.canvas.create_text(
            w // 2, y0 + ph // 2, text=text, fill=COLOR_TEXT,
            font=(FONT, size, "bold"), justify="center", tags=tags)

    def draw_board_overlay(self):
        """排行榜浮层。"""
        lines = ["── 排行榜 TOP 10 ──"]
        if not self.scores:
            lines.append("（暂无记录，快来创造第一个纪录吧！）")
        else:
            for i, entry in enumerate(self.scores, 1):
                lines.append(f"{i:>2}. {entry['name']}　{entry['score']} 分"
                             f"　· Lv{entry['level']}　{entry['date']}")
        lines += ["", "按 H 关闭"]
        w, h = GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE
        self.draw_overlay("\n".join(lines), size=13,
                          pw=int(w * 0.84), ph=int(h * 0.84))


def main():
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
