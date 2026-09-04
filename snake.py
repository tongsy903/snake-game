# -*- coding: utf-8 -*-
"""
贪吃蛇（Snake）游戏 —— 使用 Python 标准库 tkinter 实现，无需安装第三方库。

运行方式：
    python snake.py

操作说明：
    - 方向键 / WASD：控制移动方向
    - 空格：暂停 / 继续
    - R：游戏结束后重新开始
    - Esc：退出游戏
"""

import random
import sys
import tkinter as tk

# ---------------- 配置 ----------------
CELL_SIZE = 20          # 每个格子的像素大小
GRID_WIDTH = 30         # 横向格子数
GRID_HEIGHT = 20        # 纵向格子数
INIT_SPEED = 150        # 初始每步间隔（毫秒），越小越快
MIN_SPEED = 60          # 最快速度
SPEEDUP_EVERY = 5       # 每吃多少个食物加速一次
SPEEDUP_STEP = 8        # 每次加速减少的毫秒数

# 颜色
COLOR_BG = "#1e1e2e"
COLOR_GRID = "#28283a"
COLOR_SNAKE_HEAD = "#a6e3a1"
COLOR_SNAKE_BODY = "#94e2d5"
COLOR_FOOD = "#f38ba8"
COLOR_TEXT = "#cdd6f4"
COLOR_TEXT_HINT = "#6c7086"

DIRECTIONS = {
    "Up": (0, -1),
    "Down": (0, 1),
    "Left": (-1, 0),
    "Right": (1, 0),
}


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
            font=("Microsoft YaHei", 12, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        )
        self.status_label.pack(fill="x", pady=4)

        # 键盘绑定
        root.bind("<KeyPress>", self.on_key)
        root.bind("<space>", self.toggle_pause)
        root.bind("<r>", self.reset)
        root.bind("<R>", self.reset)
        root.bind("<Escape>", lambda e: root.destroy())

        # 确保窗口能接收键盘焦点
        self.canvas.focus_set()
        self.reset()

    # ---------------- 游戏状态 ----------------
    def reset(self, event=None):
        """开始新一局游戏。"""
        # 蛇：用 (x, y) 格子坐标的列表表示，头部在列表最前
        cx, cy = GRID_WIDTH // 2, GRID_HEIGHT // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)          # 当前移动方向
        self.pending_direction = (1, 0)  # 待生效的方向（防止一帧内反向）
        self.score = 0
        self.speed = INIT_SPEED
        self.running = True
        self.paused = False
        self.game_over = False

        self.spawn_food()
        self.status_label.config(text=f"分数：0    按 空格 暂停")
        self.draw()
        self.root.after_cancel_safe = self.schedule_tick()

    def schedule_tick(self):
        """安排下一帧移动。"""
        return self.root.after(self.speed, self.tick)

    def spawn_food(self):
        """在空白格子上随机生成一个食物。"""
        while True:
            pos = (
                random.randrange(GRID_WIDTH),
                random.randrange(GRID_HEIGHT),
            )
            if pos not in self.snake:
                self.food = pos
                return

    # ---------------- 主循环 ----------------
    def tick(self):
        """每帧：移动蛇、判断碰撞、更新画面。"""
        if self.game_over or self.paused:
            # 暂停或结束后不再自动推进，等待用户按键
            return

        # 方向只在每帧开始时更新一次，避免同帧内多次转向
        self.direction = self.pending_direction
        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # 撞墙
        if not (0 <= new_head[0] < GRID_WIDTH and 0 <= new_head[1] < GRID_HEIGHT):
            self.end_game()
            return

        # 撞自己（吃到食物时蛇尾会先移动一格，所以不把蛇尾算作碰撞）
        will_grow = new_head == self.food
        collision_body = self.snake[:-1] if will_grow else self.snake
        if new_head in collision_body:
            self.end_game()
            return

        self.snake.insert(0, new_head)

        if will_grow:
            self.score += 1
            # 吃满 SPEEDUP_EVERY 个就加速一次
            if self.score % SPEEDUP_EVERY == 0 and self.speed > MIN_SPEED:
                self.speed = max(MIN_SPEED, self.speed - SPEEDUP_STEP)
            self.spawn_food()
            status = f"分数：{self.score}    长度：{len(self.snake)}    按 空格 暂停"
            self.status_label.config(text=status)
        else:
            self.snake.pop()  # 没吃到食物，尾巴前进一格

        self.draw()
        self.schedule_tick()

    def end_game(self):
        """游戏结束。"""
        self.game_over = True
        self.status_label.config(
            text=f"游戏结束！最终分数：{self.score}    按 R 重新开始"
        )
        self.draw_game_over()

    # ---------------- 输入处理 ----------------
    def on_key(self, event):
        if event.keysym in DIRECTIONS:
            new_dir = DIRECTIONS[event.keysym]
        elif event.char.lower() in ("w", "a", "s", "d"):
            new_dir = {
                "w": (0, -1),
                "a": (-1, 0),
                "s": (0, 1),
                "d": (1, 0),
            }[event.char.lower()]
        else:
            return

        # 不能原地掉头；只记录为待定方向，下一帧生效
        if (new_dir[0] * -1, new_dir[1] * -1) != self.direction:
            self.pending_direction = new_dir

        # 游戏结束后任意方向键也可重新开始
        if self.game_over:
            self.reset()

    def toggle_pause(self, event=None):
        if self.game_over:
            return
        self.paused = not self.paused
        if self.paused:
            self.status_label.config(text="已暂停    按 空格 继续")
            self.draw_overlay("已暂停\n按 空格 继续")
        else:
            self.status_label.config(text=f"分数：{self.score}    按 空格 暂停")
            self.draw()
            self.schedule_tick()

    # ---------------- 绘制 ----------------
    def draw(self):
        self.canvas.delete("all")
        # 网格
        for x in range(0, GRID_WIDTH * CELL_SIZE, CELL_SIZE):
            self.canvas.create_line(x, 0, x, GRID_HEIGHT * CELL_SIZE, fill=COLOR_GRID)
        for y in range(0, GRID_HEIGHT * CELL_SIZE, CELL_SIZE):
            self.canvas.create_line(0, y, GRID_WIDTH * CELL_SIZE, y, fill=COLOR_GRID)

        # 食物
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

    def draw_overlay(self, text):
        """在画布中央绘制半透明提示文字。"""
        self.canvas.create_rectangle(
            0,
            0,
            GRID_WIDTH * CELL_SIZE,
            GRID_HEIGHT * CELL_SIZE,
            fill="#000000",
            stipple="gray50",
            outline="",
        )
        cx = GRID_WIDTH * CELL_SIZE // 2
        cy = GRID_HEIGHT * CELL_SIZE // 2
        self.canvas.create_text(
            cx, cy, text=text, fill=COLOR_TEXT, font=("Microsoft YaHei", 18, "bold"),
            justify="center",
        )

    def draw_game_over(self):
        self.draw_overlay("游戏结束\n按 R 重新开始")


def main():
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
