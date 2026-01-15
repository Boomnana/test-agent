import svgwrite, math, os, textwrap

W, H = 1600, 900
dwg = svgwrite.Drawing("LLM_classroom_tech_route_top.svg", size=(W, H), profile='full')

# ---- defs (gradients, filters, markers) ----
defs = dwg.defs

# background gradient
bg_grad = dwg.linearGradient(start=(0,0), end=(1,1), id="bgGrad")
bg_grad.add_stop_color(0, "#0b1220")
bg_grad.add_stop_color(1, "#0a2a3a")
defs.add(bg_grad)

# card gradient
card_grad = dwg.linearGradient(start=(0,0), end=(0,1), id="cardGrad")
card_grad.add_stop_color(0, "#111b2e")
card_grad.add_stop_color(1, "#0e1726")
defs.add(card_grad)

# accent gradient
acc_grad = dwg.linearGradient(start=(0,0), end=(1,0), id="accGrad")
acc_grad.add_stop_color(0, "#7c3aed")  # purple
acc_grad.add_stop_color(1, "#06b6d4")  # cyan
defs.add(acc_grad)

# soft shadow filter
filt = dwg.filter(id="softShadow", x="-20%", y="-20%", width="140%", height="140%")
filt.feGaussianBlur(in_="SourceAlpha", stdDeviation=6, result="blur")
filt.feOffset(in_="blur", dx=0, dy=6, result="offsetBlur")
filt.feColorMatrix(in_="offsetBlur", type="matrix",
                   values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.45 0",
                   result="shadow")
filt.feMerge(["shadow", "SourceGraphic"])
defs.add(filt)

# arrow marker
marker = dwg.marker(id="arrow", insert=(10,5), size=(12,10), orient="auto")
marker.add(dwg.path(d="M0,0 L12,5 L0,10 Z", fill="#93c5fd", opacity=0.9))
defs.add(marker)

dwg.add(defs)

# ---- background ----
dwg.add(dwg.rect(insert=(0,0), size=(W,H), fill="url(#bgGrad)"))

# subtle grid
grid = dwg.g(opacity=0.12)
step = 80
for x in range(0, W+1, step):
    grid.add(dwg.line(start=(x,0), end=(x,H), stroke="#94a3b8", stroke_width=1))
for y in range(0, H+1, step):
    grid.add(dwg.line(start=(0,y), end=(W,y), stroke="#94a3b8", stroke_width=1))
dwg.add(grid)

# ---- title block ----
title_grp = dwg.g()
title_grp.add(dwg.text("智能时代中小学课堂教学创新样态研究", insert=(70, 85),
                       fill="#e5e7eb", font_size=40, font_family="Noto Sans CJK SC, Microsoft YaHei, PingFang SC, sans-serif",
                       font_weight="700"))
title_grp.add(dwg.text("LLM × 课堂教学结构重构：研究技术路线图", insert=(70, 130),
                       fill="#cbd5e1", font_size=24, font_family="Noto Sans CJK SC, Microsoft YaHei, PingFang SC, sans-serif",
                       font_weight="500"))
# accent underline
title_grp.add(dwg.rect(insert=(70,150), size=(520,6), rx=3, ry=3, fill="url(#accGrad)"))
dwg.add(title_grp)

# ---- layout helpers ----
def add_card(x, y, w, h, title, subtitle, badge=None):
    g = dwg.g(filter="url(#softShadow)")
    # card
    g.add(dwg.rect(insert=(x,y), size=(w,h), rx=18, ry=18, fill="url(#cardGrad)", stroke="#334155", stroke_width=1.2))
    # top accent bar
    g.add(dwg.rect(insert=(x,y), size=(w,5), rx=18, ry=18, fill="url(#accGrad)", opacity=0.95))
    # badge pill
    if badge:
        pill_w = 110
        g.add(dwg.rect(insert=(x+w-pill_w-18, y+16), size=(pill_w, 34), rx=17, ry=17,
                       fill="#0b2a3a", stroke="#0ea5e9", stroke_width=1, opacity=0.95))
        g.add(dwg.text(badge, insert=(x+w-pill_w-18+pill_w/2, y+39),
                       fill="#bae6fd", font_size=16, text_anchor="middle",
                       font_family="Inter, Noto Sans CJK SC, Microsoft YaHei, sans-serif", font_weight="600"))
    # title
    g.add(dwg.text(title, insert=(x+26, y+48),
                   fill="#f8fafc", font_size=22,
                   font_family="Noto Sans CJK SC, Microsoft YaHei, PingFang SC, sans-serif",
                   font_weight="700"))
    # subtitle (wrap)
    max_chars = 18
    lines = []
    for seg in subtitle.split("\n"):
        if len(seg) <= max_chars:
            lines.append(seg)
        else:
            lines.extend(textwrap.wrap(seg, width=max_chars))
    ty = y+82
    for ln in lines[:4]:
        g.add(dwg.text(ln, insert=(x+26, ty),
                       fill="#cbd5e1", font_size=18,
                       font_family="Noto Sans CJK SC, Microsoft YaHei, PingFang SC, sans-serif"))
        ty += 26
    dwg.add(g)
    return (x,y,w,h)

def arrow(p1, p2, bend=0.0):
    # p1,p2 are (x,y)
    x1,y1 = p1
    x2,y2 = p2
    if bend == 0:
        dwg.add(dwg.line(start=p1, end=p2, stroke="#93c5fd", stroke_width=3,
                         marker_end="url(#arrow)", opacity=0.9))
    else:
        # quadratic bezier
        cx = (x1+x2)/2 + bend
        cy = (y1+y2)/2 - bend
        path = f"M{x1},{y1} Q{cx},{cy} {x2},{y2}"
        dwg.add(dwg.path(d=path, fill="none", stroke="#93c5fd", stroke_width=3,
                         marker_end="url(#arrow)", opacity=0.9))

# ---- cards positions ----
# Top row (3)
card_w, card_h = 430, 150
top_y = 220
x1, x2, x3 = 80, 585, 1090

c1 = add_card(x1, top_y, card_w, card_h,
              "政策与理论基础",
              "国家“人工智能+”行动\n课堂教学结构理论\n智能教育治理与伦理", badge="输入")

c2 = add_card(x2, top_y, card_w, card_h,
              "课堂现实问题诊断",
              "LLM进入课堂的现状\n结构性风险与痛点\n（秩序、真实性、可控性）", badge="诊断")

c3 = add_card(x3, top_y, card_w, card_h,
              "课堂结构要素拆解",
              "角色 · 流程 · 互动 · 评价\n要素—关系—机制图谱化",
              badge="解析")

# Middle (2) big
mid_y = 420
mid_w, mid_h = 680, 170
m1 = add_card(150, mid_y, mid_w, mid_h,
              "人机协同课堂结构模型构建",
              "教师主导｜学生主体｜LLM支持\n目标结构—流程结构—评价结构一体化",
              badge="建模")

m2 = add_card(770, mid_y, mid_w, mid_h,
              "课堂实践嵌入与验证",
              "多学段 × 多学科 × 多类型课堂\n行动研究：实施—观察—反思—迭代",
              badge="验证")

# Bottom (2) big
bot_y = 645
b_w, b_h = 680, 170
b1 = add_card(150, bot_y, b_w, b_h,
              "创新样态提炼（类型化）",
              "问题生成型｜人机协作型｜反思提升型\n形成“结构样态谱系”与适用条件",
              badge="归纳")

b2 = add_card(770, bot_y, b_w, b_h,
              "路径与规范策略形成",
              "课堂结构重构路径（可复制）\n规范边界、风险防控、教师支持\n输出指南与决策建议",
              badge="输出")

# ---- arrows between cards ----
def right_mid(c): x,y,w,h=c; return (x+w, y+h/2)
def left_mid(c): x,y,w,h=c; return (x, y+h/2)
def bottom_mid(c): x,y,w,h=c; return (x+w/2, y+h)
def top_mid(c): x,y,w,h=c; return (x+w/2, y)

# top row sequential
arrow(right_mid(c1), left_mid(c2))
arrow(right_mid(c2), left_mid(c3))

# top -> middle
arrow((c3[0]+c3[2]*0.55, c3[1]+c3[3]), (m1[0]+m1[2]*0.35, m1[1]), bend=-140)

# middle sequential
arrow(right_mid(m1), left_mid(m2))

# middle -> bottom
arrow((m2[0]+m2[2]*0.55, m2[1]+m2[3]), (b1[0]+b1[2]*0.35, b1[1]), bend=-140)
arrow(right_mid(b1), left_mid(b2))

# feedback loop arrow (iteration)
# from b2 back to m2 (dashed curved)
x1,y1 = (b2[0]+b2[2]*0.85, b2[1]+20)
x2,y2 = (m2[0]+m2[2]*0.85, m2[1]+m2[3]-10)
path = f"M{x1},{y1} C{(x1+120)},{(y1-160)} {(x2+120)},{(y2-160)} {x2},{y2}"
dwg.add(dwg.path(d=path, fill="none", stroke="#67e8f9", stroke_width=3,
                 stroke_dasharray="10 8", marker_end="url(#arrow)", opacity=0.85))
dwg.add(dwg.text("迭代优化", insert=(1415, 565),
                 fill="#a5f3fc", font_size=16,
                 font_family="Noto Sans CJK SC, Microsoft YaHei, sans-serif",
                 font_weight="600", text_anchor="middle"))

# ---- footer legend ----
legend = dwg.g()
legend.add(dwg.rect(insert=(70, 835), size=(1460, 44), rx=14, ry=14, fill="#0b1726", stroke="#334155", stroke_width=1))
legend.add(dwg.text("研究方法组合：文献分析｜调查研究｜课堂观察｜案例研究｜比较研究｜行动研究（循环验证）",
                    insert=(100, 865), fill="#cbd5e1", font_size=18,
                    font_family="Noto Sans CJK SC, Microsoft YaHei, PingFang SC, sans-serif"))
legend.add(dwg.rect(insert=(1220, 848), size=(290, 18), rx=9, ry=9, fill="url(#accGrad)", opacity=0.85))
legend.add(dwg.text("输出：研究报告｜案例集｜实践指南｜决策建议",
                    insert=(1365, 865), fill="#0b1220", font_size=16,
                    font_family="Noto Sans CJK SC, Microsoft YaHei, PingFang SC, sans-serif",
                    font_weight="800", text_anchor="middle"))
dwg.add(legend)

dwg.save()

print("LLM_classroom_tech_route_top.svg", os.path.getsize("LLM_classroom_tech_route_top.svg"))

