# 项目提交文件清单

## 必须提交的核心文件

### 源代码 (5 个文件)
```
main.py                 # GUI 主程序 (1034 行)
game_engine.py          # 游戏规则引擎 (965 行)
music_ogg.py           # 音频管理器 (171 行)
leaderboard.py         # 排行榜系统 (86 行)
tests/test_game_engine.py  # 单元测试 (283 行)
```

### 数据文件 (2 个文件)
```
data/questions.json     # 题库（20 道编程题）
data/leaderboard.json   # 排行榜记录（可选：可提交空文件 [] ）
```

### 音频资源 (19 个 .ogg 文件，共约 11 MB)
```
music/Colosseo.ogg          # 主菜单音乐 1
music/kiriko_origin.ogg     # 主菜单音乐 2
music/midtown.ogg           # 主菜单音乐 3
music/select_hero.ogg       # 战斗音乐 1
music/round1.ogg            # 战斗音乐 2/5
music/last30.ogg            # 战斗音乐 3
music/overtime.ogg          # 战斗音乐 4
music/DVA_self_destruct.ogg # 英雄技能音效：自毁程序
music/duplicate.ogg         # 英雄技能音效：改变数字
music/tracer.ogg            # 英雄技能音效：返回上一步
music/meteor_strike.ogg     # 敌方技能音效：裂地重拳
music/reaper.ogg            # 敌方技能音效：暗影吞噬
music/EMP.ogg               # 敌方技能音效：系统骇入
music/sigma.ogg             # 敌方技能音效：重力场（复用于盒子）
music/SSVGG.ogg             # 敌方技能音效：笼中斗（复用于盒子）
music/mercy.ogg             # 盒子音效：Heroes Never Die
music/dragon_blade.ogg      # 盒子音效：龙刃出鞘
music/kitsune_rush.ogg      # 盒子音效：灵狐为我引路
music/moira.ogg             # 盒子音效：生化之球
```

### 字体文件 (1 个文件)
```
fonts/Times New Roman.ttf   # 游戏界面字体
```

### 文档和配置 (5 个文件)
```
README.md               # 项目说明文档（已更新）
GAME_RULES.md          # 完整游戏规则文档（实现依据）
requirements.txt       # Python 依赖声明（新建）
.gitignore             # Git 忽略规则（新建）
run_game.command       # macOS 快速启动脚本
```

---

## 可选文件（测试/开发用）

```
verify_changes.py      # 端到端验证脚本（可选提交）
```

---

## 不应提交的文件

```
__pycache__/           # Python 缓存目录
*.pyc, *.pyo          # Python 编译文件
.DS_Store             # macOS 系统文件
.vscode/, .idea/      # IDE 配置目录
```

---

## 文件统计

| 类别 | 数量 | 总大小 |
|-----|------|--------|
| Python 源代码 | 5 个 | ~2500 行 |
| 数据文件 | 2 个 | ~5 KB |
| 音频文件 | 19 个 | ~11 MB |
| 字体文件 | 1 个 | ~1 MB |
| 文档配置 | 5 个 | ~30 KB |
| **总计** | **32 个文件** | **~12 MB** |

---

## 提交前检查清单

- [ ] 所有 Python 文件可以正常导入（无语法错误）
- [ ] 单元测试通过：`python3 -m unittest discover -s tests -v`
- [ ] 游戏可以正常启动：`python3 main.py`
- [ ] requirements.txt 包含所有依赖
- [ ] README.md 信息准确完整
- [ ] data/questions.json 至少包含 10 道题
- [ ] music/ 目录包含所有 19 个音频文件
- [ ] 没有提交 __pycache__ 或 .DS_Store 等临时文件

---

## 打包提交建议

### 方式 1：Git 仓库
```bash
git init
git add .
git commit -m "Initial commit: Watchpoint Matrix 2048 v1.0"
```

### 方式 2：压缩包
```bash
cd ..
zip -r Final_Project.zip Final_Project/ \
    -x "*.pyc" -x "*__pycache__*" -x "*.DS_Store" -x ".git/*"
```

### 方式 3：云盘上传
直接上传整个 `Final_Project` 文件夹，确保保持目录结构不变。
