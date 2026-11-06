"""Typeset the formal project brief from its accompanying measured evidence."""
from __future__ import annotations
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
OUT.mkdir(exist_ok=True)
DEST = OUT / "芯界BoundaryLab_参赛作品说明.pdf"
FIG = OUT / "figures"
FEATURED = json.loads((ROOT / "artifacts/featured.json").read_text(encoding="utf-8"))["id"]
STUDY = json.loads((ROOT / "artifacts/studies" / FEATURED / "study.json").read_text(encoding="utf-8"))
BENCH = json.loads((ROOT / "artifacts/benchmark/results.json").read_text(encoding="utf-8"))
FIG_SOURCE = json.loads((FIG / "source_runs.json").read_text(encoding="utf-8"))
WB = json.loads((ROOT / "artifacts/runs" / FIG_SOURCE["waveform_comparison"]["before"] / "measurement.json").read_text(encoding="utf-8"))
WA = json.loads((ROOT / "artifacts/runs" / FIG_SOURCE["waveform_comparison"]["after"] / "measurement.json").read_text(encoding="utf-8"))
for name, file in [("CN", "msyh.ttc"), ("CNB", "msyhbd.ttc"), ("EN", "arial.ttf"), ("ENB", "arialbd.ttf")]:
    pdfmetrics.registerFont(TTFont(name, "C:/Windows/Fonts/" + file))
pdfmetrics.registerFontFamily("CN", normal="CN", bold="CNB", italic="CN", boldItalic="CNB")
W, H = A4
M = 44
CW = W - 2 * M
TOTAL = 8
INK = "#15313A"
MUTED = "#607780"
TEAL = "#087F70"
MINT = "#8EE6CB"
LINE = "#DCE5E4"
PALE = "#F0F5F3"
PAPER = "#FAFBF8"
NAVY = "#102A32"
AMBER = "#B87643"
LAYOUT = []
C = canvas.Canvas(str(DEST), pagesize=A4, pageCompression=1)
C.setTitle("芯界 BoundaryLab | 自主电路科研智能体 · 参赛作品说明")
C.setAuthor("芯界 BoundaryLab")
C.setSubject("智绘芯生，AI赋能 · 赛道一：AI智能体（Agent）开发")
C.setCreator("BoundaryLab")
C._doc.info.producer = "BoundaryLab"
C.setKeywords("芯界,BoundaryLab,电路科研,AI智能体,自主实验,ngspice,失效边界")

def color(value):
    return colors.HexColor(value)

def rect(x, top, width, height, fill, radius=0, stroke=None):
    C.setFillColor(color(fill))
    C.setStrokeColor(color(stroke or fill))
    C.setLineWidth(0.6)
    if radius:
        C.roundRect(x, H - top - height, width, height, radius, fill=1, stroke=bool(stroke))
    else:
        C.rect(x, H - top - height, width, height, fill=1, stroke=bool(stroke))

def line(x, top, x2, top2, stroke=LINE, thickness=0.65):
    C.setStrokeColor(color(stroke))
    C.setLineWidth(thickness)
    C.line(x, H - top, x2, H - top2)

def text(value, x, top, size=10, font="CN", fill=INK, align="left"):
    C.setFont(font, size)
    C.setFillColor(color(fill))
    fn = C.drawRightString if align == "right" else C.drawCentredString if align == "center" else C.drawString
    fn(x, H - top - size, str(value))

def p(value, x=M, top=0, width=CW, size=10.2, leading=17.2, fill=INK, bold=False, markup=False):
    content = str(value) if markup else escape(str(value)).replace("\n", "<br/>")
    st = ParagraphStyle("paragraph", fontName="CNB" if bold else "CN", fontSize=size,
                        leading=leading, textColor=color(fill), wordWrap="CJK",
                        splitLongWords=True, allowWidows=0, allowOrphans=0)
    para = Paragraph(content, st)
    _, height = para.wrap(width, 2000)
    if top + height > H - 65:
        raise ValueError(f"Page {C.getPageNumber()} exceeds content area: {content[:80]}")
    para.drawOn(C, x, H - top - height)
    LAYOUT.append({"page": C.getPageNumber(), "top": round(top, 2), "bottom": round(top + height, 2), "text": str(value)[:90]})
    return top + height

def section(title, top, x=M, width=CW):
    rect(x, top + 3, 3, 13, TEAL)
    p(title, x + 12, top, width - 12, size=12, leading=20, bold=True)
    return top + 30

def logo(x=M, top=30):
    rect(x, top, 17, 17, TEAL, radius=4)
    for dx in [5, 10]:
        line(x + dx, top + 5, x + dx, top + 12, MINT, 1.5)
    line(x + 5, top + 8, x + 10, top + 8, MINT, 1.4)
    text("芯界", x + 25, top - 1, 10, "CNB")
    text("BOUNDARYLAB", x + 55, top + 3, 7.5, "ENB", MUTED)

def footer(page):
    line(M, 790, W - M, 790)
    text("芯界 BoundaryLab  |  参赛作品说明", M, 801, 7.4, fill=MUTED)
    for i in range(TOTAL):
        rect(W - M - 92 + i * 6.5, 805, 4, 3, TEAL if i < page else LINE)
    text(f"{page:02d} / {TOTAL:02d}", W - M, 800, 8, "EN", MUTED, "right")

def header(page, eyebrow, title, subtitle):
    C.bookmarkPage(f"page-{page}")
    C.addOutlineEntry(title, f"page-{page}")
    logo()
    text("赛道一 · AI智能体（Agent）开发", W - M, 33, 8, fill=MUTED, align="right")
    text(eyebrow, M, 76, 8, "ENB", TEAL)
    p(title, M, 96, CW, size=21, leading=30, bold=True)
    end = p(subtitle, M, 138, CW, size=10, leading=16.5, fill=MUTED)
    footer(page)
    return end + 22

def new_page():
    C.showPage()

def image(name, top, width=CW, max_height=None):
    reader = ImageReader(str(FIG / name))
    iw, ih = reader.getSize()
    height = width * ih / iw
    if max_height and height > max_height:
        height = max_height
        width = height * iw / ih
    x = M + (CW - width) / 2
    C.drawImage(reader, x, H - top - height, width, height, mask="auto")
    return top + height

def caption(value, top):
    return p(value, M + 5, top, CW - 10, size=8, leading=12.5, fill=MUTED)

def table(rows, widths, top, size=9.1, min_height=27):
    assert abs(sum(widths) - CW) < 0.1
    y = top
    for i, row in enumerate(rows):
        paras, heights = [], []
        for value, width in zip(row, widths):
            st = ParagraphStyle("cell", fontName="CNB" if i == 0 else "CN",
                                fontSize=size if i else size - 0.2, leading=13.5,
                                textColor=color("#FFFFFF" if i == 0 else INK), wordWrap="CJK")
            para = Paragraph(escape(str(value)).replace("\n", "<br/>"), st)
            _, ph = para.wrap(width - 20, 1000)
            paras.append(para)
            heights.append(ph)
        rh = max(min_height, max(heights) + 16)
        rect(M, y, CW, rh, NAVY if i == 0 else (PALE if i % 2 else "#FFFFFF"))
        x = M
        for width, para, ph in zip(widths, paras, heights):
            para.drawOn(C, x + 10, H - y - (rh - ph) / 2 - ph)
            x += width
        if i:
            line(M, y + rh, W - M, y + rh, LINE, 0.4)
        y += rh
    return y

def note(title, body, top, height=70):
    rect(M, top, CW, height, PALE, radius=8)
    p(title, M + 16, top + 12, CW - 32, size=10.2, leading=17, bold=True, fill=TEAL)
    p(body, M + 16, top + 35, CW - 32, size=9.1, leading=15.5)
    return top + height

def mini_domain(mp, x, top, width, height):
    contract = STUDY["request"]["contract"]
    left = 7
    pw, ph = width - 14, height - 24
    for k in range(4):
        xx = x + left + k / 3 * pw
        line(xx, top, xx, top + ph, "#28434A", 0.45)
    for k in range(3):
        yy = top + k / 2 * ph
        line(x + left, yy, x + left + pw, yy, "#28434A", 0.45)
    for row in mp["points"]:
        e = row["experiment"]
        u = math.log(e["frequency_hz"] / contract["frequency_min_hz"]) / math.log(contract["frequency_max_hz"] / contract["frequency_min_hz"])
        v = math.log(e["amplitude_v"] / contract["amplitude_min_v"]) / math.log(contract["amplitude_max_v"] / contract["amplitude_min_v"])
        C.setFillColor(color(MINT if row["passed"] else "#DCA06F"))
        C.circle(x + left + u * pw, H - (top + (1 - v) * ph), 2, fill=1, stroke=0)
    text("500 Hz", x + left, top + ph + 8, 6.8, "EN", "#A6C2C7")
    text("200 kHz", x + left + pw, top + ph + 8, 6.8, "EN", "#A6C2C7", "right")

# 01 / Cover
C.bookmarkPage("cover")
C.addOutlineEntry("芯界 BoundaryLab", "cover")
rect(0, 0, W, H, PAPER)
logo()
text("2026", W - M, 31, 9, "ENB", MUTED, "right")
p("上海交通大学集成电路学院（信息与电子工程学院）", M, 84, CW, size=9.4, leading=16, fill=MUTED)
p("“智绘芯生，AI赋能”AI教与学活动周", M, 103, CW, size=10.2, leading=17)
rect(M, 139, 26, 3, TEAL)
text("芯界", M - 1, 167, 56, "CNB")
text("BoundaryLab", M, 239, 32, "ENB")
p("自主电路科研智能体", M, 299, CW, size=23, leading=34, bold=True)
p("让每一个设计结论，都能回到实验。", M, 347, CW, size=13.2, leading=22, fill=TEAL)
p("面向电路专业学习与科研辅助，将研究问题转化为可执行实验，寻找失效反例、审查竞争解释，并用独立复测检验设计修改。", M, 387, CW, size=10.5, leading=18)
hero_top = 455
rect(M, hero_top, CW, 218, NAVY, radius=12)
text("相同合同 · 相同网格 · 独立复测", M + 18, hero_top + 16, 10, "CNB", "#DFEEE9")
text("绿：通过   橙：失效", W - M - 18, hero_top + 18, 7.2, "CN", "#A6C2C7", "right")
smallw = (CW - 56) / 2
text("原始设计", M + 20, hero_top + 49, 9.3, "CN", "#A6C2C7")
text("89 / 165", M + 20 + smallw, hero_top + 44, 16, "ENB", "#FFFFFF", "right")
text("修订候选", M + 36 + smallw, hero_top + 49, 9.3, "CN", "#A6C2C7")
text("135 / 165", W - M - 20, hero_top + 44, 16, "ENB", MINT, "right")
mini_domain(STUDY["map"], M + 14, hero_top + 87, smallw + 12, 113)
mini_domain(STUDY["repair"]["after_map"], M + 30 + smallw, hero_top + 87, smallw + 12, 113)
text("通过点比例 53.9% → 81.8%；图示为通用行为模型的离散仿真结果。", M + 18, hero_top + 199, 7.5, "CN", "#A6C2C7")
for i, (num, label) in enumerate([("10", "次自主搜索实验"), ("6", "个合同失效点"), ("2", "次事先预测被反驳")]):
    xx = M + i * (CW / 3)
    if i:
        line(xx - 12, 704, xx - 12, 746)
    text(num, xx, 698, 26, "ENB")
    text(label, xx + 43, 714, 9.1, fill=MUTED)
text("参赛作品说明", M, 762, 10, "CNB")
text("赛道一：AI智能体（Agent）开发", W - M, 763, 9, fill=MUTED, align="right")
footer(1)
new_page()

# 02 / Problem, value and innovation
y = header(2, "01 / PROBLEM & INNOVATION", "把电路疑问，转化为可检验的研究",
           "适用场景：电路课程实验、专业学习探究与科研初期的设计验证。")
y = section("从“某个条件能工作”，走向“哪些条件仍然有效”", y)
y = p("以目标增益为10的放大器为例，低频小信号下通过验收后，频率或输入幅值增大仍可能引发增益压缩、波形失真或输出饱和。系统将输入范围与性能阈值约定为“验收合同”，之后不随模型解释改变。判断有效范围，需要选择实验、比较解释，并检查修改是否带来新的问题。", top=y)
y += 18
p("自主研究闭环", M, y, CW, size=12, leading=19, bold=True)
y += 31
gap = 12
cardw = (CW - 2 * gap) / 3
stages = [
    ("01", "约定验收", "固定电路、输入域\n与性能阈值"),
    ("02", "登记预测", "记录假设、预期结果\n与实验条件"),
    ("03", "执行仿真", "调用ngspice\n获得波形与测量"),
    ("04", "审查机制", "比较竞争解释\n补充对照证据"),
    ("05", "提出修改", "模型选择GBW、SR\n候选参数"),
    ("06", "独立复测", "原实验回归与网格验证\n残余失败反馈给模型"),
]
for i, (num, title, body) in enumerate(stages):
    xx = M + (i % 3) * (cardw + gap)
    tt = y + (i // 3) * 99
    rect(xx, tt, cardw, 86, PALE, radius=8)
    text(num, xx + 12, tt + 12, 9, "ENB", TEAL)
    p(title, xx + 36, tt + 10, cardw - 48, size=11, leading=18, bold=True)
    p(body, xx + 12, tt + 39, cardw - 24, size=8.7, leading=14.5, fill=MUTED)
y += 211
for num, title, body in [
    ("A", "预测发生在测量之前", "保留模型原先的通过或失败判断；测量不符时显式标记反驳，避免结论只在事后成立。"),
    ("B", "解释需要能区分机制的实验", "结合小信号频响、同频幅值对照和输出触轨等证据，区分带宽、压摆率与摆幅约束。"),
    ("C", "修改必须接受同一套验收", "保持原目标与阈值，对原实验回归，再在相同网格复测；未解决的失败继续保留。"),
]:
    rect(M, y + 3, 25, 25, TEAL, radius=6)
    text(num, M + 12.5, y + 8, 11, "ENB", "#FFFFFF", "center")
    p(title, M + 39, y, CW - 39, size=11, leading=18, bold=True)
    end = p(body, M + 39, y + 24, CW - 39, size=9.6, leading=16)
    y = end + 17
p("职责分工：DeepSeek负责提出行动与解释，ngspice执行仿真，冻结的确定性验收器计算指标。", M, y + 2, CW, size=9, leading=15, fill=MUTED)
new_page()

# 03 / Product
y = header(3, "02 / PRODUCT & FUNCTIONS", "一页工作台，串起实验与证据",
           "研究设置、工作域、原始波形、实验轨迹与研究报告在同一套界面中完成。")
half = (CW - 14) / 2
for xx, title, desc in [(M, "精密放大器", "检验不同频率与幅值下的增益和线性工作范围。"),
                        (M + half + 14, "有源低通滤波器", "区分预期RC滚降与器件非理想造成的额外失效。")]:
    rect(xx, y, half, 58, PALE, radius=7)
    p(title, xx + 12, y + 10, half - 24, size=10.8, leading=17, bold=True)
    p(desc, xx + 12, y + 34, half - 24, size=8.6, leading=14, fill=MUTED)
y += 72
y = image("工作台地图.png", y, max_height=240)
y = caption("① 工作域地图：每个点对应一次真实仿真，颜色表示冻结合同下的通过或失效；点击即可追溯到波形和网表。", y + 8)
y += 14
y = image("工作台波形.png", y, max_height=188)
y = caption("② 波形证据：并列显示输入、实测输出与理想参考，给出频率、幅值、增益误差和残差失真；数据可追溯至原始网表、瞬态表与日志。", y + 8)
new_page()

# 04 / Operating-domain case
y = header(4, "03 / MEASURED CASE", "让设计修改，经得起同一把尺子的检验",
           "精选研究：目标增益10，输出摆幅、负载与验收阈值在候选修改中保持一致。")
iterations = STUDY["repair"]["iterations"]
rows = [["设计阶段", "GBW", "SR", "独立网格通过点"],
        ["原始模型", "0.8 MHz", "0.3 V/µs", "89 / 165"]]
for i, it in enumerate(iterations, 1):
    rows.append([f"第{i}轮候选", f'{it["device"]["gbw_hz"] / 1e6:g} MHz',
                 f'{it["device"]["slew_v_us"]:g} V/µs', f'{it["pass_count"]} / 165'])
y = table(rows, [135, 110, 117, CW - 362], y)
y = caption("GBW为增益带宽积，SR为压摆率（输出电压变化速率上限）。验收域为500 Hz至200 kHz、输入峰值5至800 mV；增益误差不超过5%，残差失真不超过3%。", y + 8)
y += 19
y = image("工作域对比.png", y)
y = caption("图1  原始设计与第二轮候选的独立工作域测量。两图采用相同的165个对数网格点，通过点比例由53.9%提高至81.8%，增加27.9个百分点。", y + 8)
y += 19
for num, title, body in [
    ("01", "搜索先发现问题", "10次搜索实验发现6个不符合合同的点；9次模型通过或失败预测中，2次被实测反驳。"),
    ("02", "独立验证推动再次修订", "首轮候选通过134/165点。系统将残余失效返回模型，第二轮候选通过135/165点。"),
    ("03", "改善范围与剩余问题一并呈现", "原搜索中的3个失败点得到修复，原先通过的点保持通过；输出摆幅相关的失败仍然保留。"),
]:
    text(num, M, y, 13, "ENB", TEAL)
    p(title, M + 37, y - 1, CW - 37, size=10.5, leading=17, bold=True)
    end = p(body, M + 37, y + 21, CW - 37, size=9.4, leading=16)
    y = end + 15
p("本结果仅适用于所附通用行为模型与固定离散采样，不等同于连续工作域证明、器件良率或真实芯片性能。", M, y + 2, CW, size=8.6, leading=14.5, fill=MUTED)
new_page()

# 05 / Waveforms and mechanism evidence
y = header(5, "04 / WAVEFORMS & REASONING", "从一条失真波形，追问背后的限制",
           "补充对照条件：50 kHz输入，输入正弦峰值0.2 V，目标增益与验收条件一致。")
rect(M, y, CW, 64, PALE, radius=8)
text(f'{WB["gain_error"]:.2%}', M + 18, y + 10, 23, "ENB", AMBER)
text("原始设计增益误差", M + 18, y + 42, 8.5, fill=MUTED)
text("→", M + CW / 2, y + 18, 20, "CN", TEAL, "center")
text(f'{WA["gain_error"]:.2%}', W - M - 18, y + 10, 23, "ENB", TEAL, "right")
text("修订候选增益误差", W - M - 18, y + 42, 8.5, fill=MUTED, align="right")
y += 83
y = image("波形修复对比.png", y)
y = caption("图2  真实ngspice输出与理想参考对照。原设计出现增益压缩，候选更接近目标正弦。该补充实验不计入Agent的10次搜索预算，原始运行编号见第8页。", y + 8)
y = section("机制审查：保留证据的强弱", y + 21)
for title, tag, body in [
    ("带宽限制", "观测支持", "小信号下增益下降并伴随相位滞后，与有限增益带宽的预期相符。"),
    ("压摆率限制", "对照支持", "检查输出斜率与失真，并在同一频率下降低幅值，观察非线性影响是否减弱。"),
    ("输出摆幅限制", "观测支持", "低频大幅值下出现输出触轨；提高GBW或SR不能消除既定摆幅约束。"),
]:
    rect(M, y, CW, 62, PALE, radius=6)
    p(title, M + 12, y + 10, 110, size=10.2, leading=17, bold=True)
    p(tag, M + 12, y + 34, 110, size=8.1, leading=13, fill=TEAL)
    p(body, M + 133, y + 12, CW - 147, size=9.4, leading=16)
    y += 73
p("这些标签表示当前证据的支持程度。多个机制可以共存，观测特征不被当成唯一因果证明；对照不足时保留“证据不足”。", M, y + 2, CW, size=8.8, leading=15, fill=MUTED)
new_page()

# 06 / Benchmark
y = header(6, "05 / FROZEN EVALUATION", "用固定任务与共同验收，检查系统表现",
           "8个预先固定的合成任务；每次最多8次搜索仿真，均包含同一标称基线。")
name_map = {"bandwidth": "带宽限制", "slew": "压摆率限制", "saturation": "输出饱和",
            "combined": "组合失效", "normal_amplifier": "正常放大域", "lowpass": "低通非理想",
            "normal_lowpass": "正常低通域", "high_gain": "高增益设计"}
rows = [["任务", "Agent\n首反例序号", "固定测试\n首反例序号", "本地策略\n首反例序号", "随机搜索\n检出次数"]]
for name, label in name_map.items():
    rr = [r for r in BENCH["results"] if r["task"] == name]
    def first(method):
        r = next(v for v in rr if v["method"] == method)
        return str(r["first_failure_index"]) if r["first_failure_index"] is not None else f'未发现({r["simulations"]}/8)'
    random = [r for r in rr if r["method"] == "random"]
    rows.append([label, first("deepseek"), first("fixed"), first("local"),
                 f'{sum(r["failure_found_within_budget"] for r in random)} / 3'])
y = table(rows, [105, 99, 99, 99, CW - 402], y, size=8.6, min_height=25)
y = caption("表1  首反例序号包含标称基线；未发现时保留实际使用预算。模型每任务运行1次，随机搜索使用17、42、93三个种子。地图与设计修订不参与本项评测。", y + 9)
y += 14
y = image("冻结评测.png", y, width=430)
y = caption("图3  仅统计6个含失效预设任务。Agent、固定测试与本地策略均检出6/6，随机搜索检出14/18；两个正常预设域的各方法均未发现反例。", y + 5)
note("结果说明", "固定测试在本任务集上同样有效。Agent的附加价值体现在动态实验、事先预测、机制对照与候选修订。任务数和模型重复次数有限，结果不足以支持统计显著性或广泛泛化结论。", y + 14, height=76)
new_page()

# 07 / Guide
y = header(7, "06 / GETTING STARTED", "解压后，即可检查记录与运行实验",
           "Windows x64 · Python 3.12或更新版本 · 已附ngspice 47，无需安装商业EDA。")
steps = [
    ("01", "启动工作台", "解压作品，双击“启动芯界.cmd”。首次启动需要联网安装Python依赖；浏览器入口为 http://127.0.0.1:8765/ 。"),
    ("02", "先审阅已有研究", "首页载入精选记录。点击地图点查看波形与网表，展开实验轨迹检查事先预测，再切换候选设计查看变化。"),
    ("03", "发起自己的实验研究", "选择放大器或低通滤波器，填写研究问题、输入域与验收阈值。在线模式需按.env.example在本地配置DeepSeek API；也可选择本地策略。"),
    ("04", "查看报告并导出证据", "运行中可停止并保留已有数据。完成后进入“证据与报告”，检查机制支持、候选差异和回归结果，导出可重跑证据包。"),
]
for num, title, body in steps:
    rect(M, y, CW, 87, PALE, radius=8)
    text(num, M + 14, y + 12, 20, "ENB", TEAL)
    p(title, M + 58, y + 10, CW - 74, size=11, leading=18, bold=True)
    p(body, M + 58, y + 35, CW - 74, size=9.3, leading=16)
    y += 99
y = section("三种使用方式", y + 1)
y = table([["方式", "需要API", "可检查的内容"],
           ["历史研究审阅", "否", "已保存的模型调用、波形、网表和候选修订"],
           ["本地策略运行", "否", "真实仿真与确定性流程，界面明确标为非大模型"],
           ["在线自主研究", "是", "模型根据新观测选择实验并生成新决策"]],
          [116, 72, CW - 188], y, size=9, min_height=25)
p("公开作品包不含API密钥。在线调用产生实际API费用；搜索、独立地图和修改验证分别记录。若8765端口已有服务运行，直接打开现有入口即可。", M, y + 14, CW, size=8.7, leading=15, fill=MUTED)
new_page()

# 08 / Evidence, methods and sources
y = header(8, "07 / EVIDENCE & SCOPE", "让结果有来源，也有清楚的适用范围",
           "作品同时交付执行代码、研究轨迹与原始仿真数据，支持独立检查和离线重跑。")
y = section("可复现资料", y)
y = table([["位置", "内容"],
           ["lab/ 与 web/", "Agent、仿真、冻结验收、中文界面与证据导出源码"],
           ["artifacts/studies/\nartifacts/runs/", "研究快照、原生工具调用、事件轨迹、网表、瞬态表和日志"],
           ["artifacts/benchmark/", "预先固定的任务合同、全部48条评测记录和结果报告"],
           ["docs/ 与 docs/figures/", "作品说明、演示视频、实验图与对应原始运行编号"]],
          [174, CW - 174], y, size=8.8, min_height=25)
y += 16
y = section("测量方法与完成范围", y)
y = p("通用运放模型包含有限开环增益、单主极点、压摆率、输出摆幅和抗积分饱和；低通案例增加输入RC。瞬态仿真14周期，取最后4周期拟合基波。增益误差相对各拓扑的理想响应计算；残差失真为移除直流与基波后的残差RMS与基波RMS之比，包含数值误差。", top=y, size=9.1, leading=15.6)
y = p("已通过18项自动化检查与独立解压验证。当前未进行真实器件、工艺角或仪器测量，候选的功耗、噪声、成本和稳定性仍需后续工程验证。离散地图不构成连续域证明；逐文件SHA-256与事件哈希链用于内部一致性检查。", top=y + 10, size=9.1, leading=15.6)
y = section("方法与工具来源", y + 17)
sources = [
    ("[1] LLM-Falsifier：数值反馈驱动的反例搜索。", "arXiv:2609.20752", "https://arxiv.org/abs/2609.20752"),
    ("[2] LLM-IDEA：以可辨识性审查实验能区分什么。", "arXiv:2610.11253", "https://arxiv.org/abs/2610.11253"),
    ("[3] AnalogAgent：工具反馈驱动的模拟电路设计。", "arXiv:2603.23910", "https://arxiv.org/abs/2603.23910"),
    ("[4] ngspice：开源电路仿真器与官方文档。", "ngspice.sourceforge.io", "https://ngspice.sourceforge.io/"),
]
for label, display, url in sources:
    p(label, M, y, CW - 142, size=8.6, leading=14)
    p(f'<link href="{url}" color="{TEAL}">{escape(display)}</link>', W - M - 138, y, 138, size=8.4, leading=14, markup=True)
    y += 25
y = p("以上为方法启发与执行工具来源，未宣称复现相关论文成绩。项目代码采用MIT许可，第三方文件保留各自许可，详见THIRD_PARTY_NOTICES.md。", top=y + 2, size=8, leading=13.5, fill=MUTED)
line(M, y + 13, W - M, y + 13)
p("精选研究编号：" + FEATURED + "\n补充波形运行：" + FIG_SOURCE["waveform_comparison"]["before"] + " / " + FIG_SOURCE["waveform_comparison"]["after"],
  M, y + 24, CW, size=7.5, leading=13, fill=MUTED)
C.save()
qa = ROOT / "artifacts/pdf-qa"
qa.mkdir(exist_ok=True)
(qa / "layout.json").write_text(json.dumps({"pages": TOTAL, "text_blocks": LAYOUT}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"pdf": str(DEST), "pages": TOTAL, "bytes": DEST.stat().st_size}, ensure_ascii=False))
