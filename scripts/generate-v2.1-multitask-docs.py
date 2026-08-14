#!/usr/bin/env python3
"""Generate the V2.1 multi-task scenario and seven-layer DOCX deliverables."""

from pathlib import Path
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "v2.1"
OUT.mkdir(parents=True, exist_ok=True)
DATE = "2026年8月14日"


ROLES = [
    ("张总", "总行经营管理角色", "全机构、对公与零售经营指标；可执行全部八个多任务场景"),
    ("李总", "北京分行负责人", "仅北京分行及下辖机构；可访问授权经营指标"),
    ("王总", "总行零售信贷负责人", "总行范围内仅零售信贷专项指标；对公指标前置拦截"),
]

SCENARIOS = [
    {
        "id": "MT01", "name": "多机构多指标并行查询与综合汇总", "type": "并行任务",
        "question": "对比总行、北京分行和上海分行2026年一季度贷款投放、存款余额和不良率，并给出经营概览。",
        "goal": "将一个综合问句拆为多个机构×指标查询节点，并行执行后按统一口径汇总。",
        "dag": "T1权限与口径确认 → {T2贷款投放、T3存款余额、T4不良率}并行 → T5机构对比汇总",
        "result": "返回授权范围内的机构对比表、完成度和证据引用；无权限机构不进入计划。",
        "roles": ["完整执行三机构对比", "仅保留北京分行节点并提示范围收缩", "贷款/存款若非零售授权则拦截，仅保留零售信贷合法节点"],
        "failure": "任一非关键指标失败则 PARTIAL_SUCCESS；汇总明确缺失指标，不输出完整排名。",
    },
    {
        "id": "MT02", "name": "指标下降的串行下钻归因", "type": "依赖任务",
        "question": "分析2026年一季度对公贷款投放为什么下降，先确认同比，再按客户类型和机构找主要影响项。",
        "goal": "证明前置事实查询成功后，才生成维度下钻及贡献度计算节点。",
        "dag": "T1当期/同期 → T2同比判定 → {T3客户类型拆解、T4机构拆解} → T5贡献度计算 → T6证据化归因",
        "result": "给出下降幅度、主要贡献项、任务证据和未核实项，不把相关性表述为因果。",
        "roles": ["全行全维度归因", "仅北京分行内部维度归因", "对公指标无权，L2前置终止且不生成DAG"],
        "failure": "T1或T2失败为 FAILED；T3/T4之一失败为 PARTIAL_SUCCESS，禁止声称完成全面归因。",
    },
    {
        "id": "MT03", "name": "执行前任务计划预览与调整", "type": "人机协同",
        "question": "生成北京分行一季度经营体检，先让我确认分析步骤再执行。",
        "goal": "展示计划预览、节点删改、影响检查、版本化和确认后执行。",
        "dag": "T1生成Plan v1 → 用户删除低价值节点/增加渠道拆解 → T2校验Plan v2 → 用户确认 → 执行DAG",
        "result": "显示计划版本差异、预计任务数、权限和成本提示，未经确认不查库。",
        "roles": ["可规划任意授权机构", "固定北京分行范围，不能添加其他机构", "只可添加零售信贷节点"],
        "failure": "非法节点或越权调整被拒绝，保留最近合法计划；计划未确认状态为 WAITING_CONFIRMATION。",
    },
    {
        "id": "MT04", "name": "长任务实时进度与主动取消", "type": "运行控制",
        "question": "分析近12个月北京分行贷款投放趋势和机构排名，开始后展示每一步进度。",
        "goal": "展示排队、运行、心跳、节点进度、取消传播和资源释放。",
        "dag": "T1月度趋势 ∥ T2机构明细 → T3排名 → T4汇总；用户运行中取消",
        "result": "已成功节点保留为审计事实，下游未启动节点标记 CANCELLED，不生成最终完整结论。",
        "roles": ["可运行全量任务", "仅北京分行任务", "仅零售信贷指标任务"],
        "failure": "取消必须幂等；执行端确认后进入 CANCELLED，超时则进入 CANCEL_PENDING 并告警。",
    },
    {
        "id": "MT05", "name": "失败节点定点重试与结果复用", "type": "故障恢复",
        "question": "查询北京分行一季度贷款、存款和中收表现；如果某项失败，只重试失败项。",
        "goal": "证明成功结果有版本和有效期，重试不重复查询已成功节点。",
        "dag": "{T1贷款成功、T2存款超时、T3中收成功} → 用户重试T2 → T4重新汇总",
        "result": "展示attempt、错误码、重试原因和复用节点；最终成功后产生新汇总版本。",
        "roles": ["全指标重试", "北京分行授权指标重试", "只允许零售授权节点，越权节点不可借重试绕过"],
        "failure": "超过最大重试次数仍失败则维持 PARTIAL_SUCCESS；禁止换用Fixture静默成功。",
    },
    {
        "id": "MT06", "name": "非关键节点失败与部分成功披露", "type": "完整性治理",
        "question": "生成一季度零售信贷经营摘要，包含投放、余额、不良率和渠道结构。",
        "goal": "验证关键/非关键节点定义、完成度计算和未核实项披露。",
        "dag": "{T1投放关键、T2余额关键、T3不良率关键、T4渠道结构非关键} → T5摘要",
        "result": "T4失败时仍输出核心摘要，但醒目标注渠道结构未核实、完成度3/4。",
        "roles": ["完整全行摘要", "北京分行摘要", "零售信贷指标合法执行"],
        "failure": "任一关键节点失败则不得输出整体正常/异常结论；状态由规则引擎而非LLM裁决。",
    },
    {
        "id": "MT07", "name": "关键节点失败与安全终止", "type": "失败语义",
        "question": "判断北京分行一季度经营是否正常，并列出需要关注的问题。",
        "goal": "证明基础事实或权限等关键节点失败时，系统安全终止并拒绝生成总体判断。",
        "dag": "T1权限快照 → {T2核心指标、T3基准口径} → T4异常规则 → T5结论",
        "result": "核心指标失败时返回 FAILED 和未完成原因，只展示已验证事实，不生成总体判断。",
        "roles": ["按全行基准执行", "按北京分行授权基准执行", "只使用零售授权基准"],
        "failure": "权限、基准或核心事实失败均短路依赖节点；L7不得用历史缓存补出本轮结论。",
    },
    {
        "id": "MT08", "name": "多轮追问继承并扩展多任务计划", "type": "多轮任务",
        "question": "第一轮：对比北京分行近三个月零售贷款投放和不良率。第二轮：再加上去年同期，并找出变化最大的月份。",
        "goal": "继承合法上下文和权限快照，在新计划中复用有效节点并增加同期、差值和极值任务。",
        "dag": "Round1:{T1投放趋势∥T2不良率趋势}→T3汇总；Round2:复用T1/T2→{T4同期、T5差值}→T6极值",
        "result": "展示继承参数、复用证据、计划v1/v2差异以及本轮新增结论。",
        "roles": ["可切换授权机构后重建计划", "机构始终锁定北京分行", "指标始终锁定零售信贷权限域"],
        "failure": "角色切换或权限版本变化必须重新建会话/计划；过期结果不可复用。",
    },
]

LAYERS = [
    ("L1", "交互与任务接入层", "接收问句、身份、会话和控制命令，创建Request与Trace。", "NlqTaskRequest", "InteractionEnvelope / WAITING_INPUT", "不得判定权限或直接生成SQL。"),
    ("L2", "对话理解与权限预检层", "抽取指标、机构、时间、分析目标，补全上下文并执行资产级权限预检。", "InteractionEnvelope + PermissionSnapshot", "UnderstandingResult / Clarification", "模型只提供候选；规则代码裁决必填、字典和权限。"),
    ("L3", "语义规划与任务拆解层", "归一口径，将综合问题拆为子任务，定义关键性、依赖和完整性要求。", "UnderstandingResult", "SemanticTaskPlan", "只引用已发布能力；不得创造跨域关系。"),
    ("L4", "可信资产匹配层", "为每个子任务匹配授权指标、表、字段和数据源，固化资产版本。", "SemanticTaskPlan + PermissionSnapshot", "AssetBindingSet", "所有节点全量授权；无资产节点不得进入执行计划。"),
    ("L5", "查询与任务编排层", "生成受控SQL/计算节点和版本化DAG，校验依赖、参数及风险。", "AssetBindingSet", "ExecutableTaskDAG", "SQL模板/AST门禁；DAG无环；计划变更需新版本。"),
    ("L6", "执行与治理层", "公平准入、串并行调度、限流、重试、取消、事实持久化和状态裁决。", "ExecutableTaskDAG", "ExecutionFactBundle", "只输出执行事实；关键节点失败决定整体不可用。"),
    ("L7", "证据化结果解释层", "只基于L6成功事实组织结论、表格、图表、证据和未核实项。", "ExecutionFactBundle", "EvidenceAnswer", "不查库、不补数、不重算；不能自行把失败改为成功。"),
]


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def configure(doc, title):
    sec = doc.sections[0]
    sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.0)
    sec.left_margin, sec.right_margin = Cm(2.2), Cm(2.0)
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(5)
    for name, size, color in [("Title", 24, "17365D"), ("Heading 1", 17, "17365D"), ("Heading 2", 14, "1F4E78"), ("Heading 3", 12, "2F75B5")]:
        st = styles[name]
        st.font.name = "Microsoft YaHei"
        st._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
        st.font.size = Pt(size)
        st.font.color.rgb = RGBColor.from_string(color)
    p = doc.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(title)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("AskData 产品 V2.1｜单域多任务问数版本").bold = True
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(f"版本：V1.0　编制日期：{DATE}　状态：规划/设计基线")
    doc.add_page_break()
    add_heading(doc, "文档控制", 1)
    add_table(doc, ["项目", "内容"], [
        ["适用版本", "AskData V2.1 Demo、POC、Product；客户交付版按客户映射后复用"],
        ["架构范围", "单业务域；不含多域识别、跨域授权和跨域编排"],
        ["参考材料", "现有多角色权限八场景、七层双场景输入输出案例、七层技术详设、权限全场景演示文档"],
        ["核心铁律", "L1—L6产生和治理事实；L7只解释成功事实。权限、安全、计划状态和完整性由确定性代码裁决"],
    ])
    add_heading(doc, "目录（打开 Word 后更新域）", 1)
    p = doc.add_paragraph()
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), 'TOC \\o "1-3" \\h \\z \\u')
    p._p.append(fld)
    doc.add_page_break()


def add_heading(doc, text, level=1):
    doc.add_heading(text, level=level)


def add_bullets(doc, items, numbered=False):
    style = "List Number" if numbered else "List Bullet"
    for item in items:
        doc.add_paragraph(item, style=style)


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = str(h)
        set_cell_shading(cell, "D9EAF7")
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
            cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    doc.add_paragraph()
    return table


def add_code(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.right_indent = Cm(0.5)
    set_cell = OxmlElement("w:shd")
    set_cell.set(qn("w:fill"), "F2F2F2")
    p._p.get_or_add_pPr().append(set_cell)
    r = p.add_run(text)
    r.font.name = "Consolas"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "等线")
    r.font.size = Pt(8.5)


def add_footer(doc):
    for sec in doc.sections:
        p = sec.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.text = "AskData V2.1 多任务设计基线｜内部规划资料"


def scenario_doc():
    doc = Document()
    configure(doc, "NLQ多任务优化·8大标准演示场景完整清单\n（含多角色差异化演示＋七层任务链路）")
    add_heading(doc, "一、整体说明", 1)
    doc.add_paragraph("本清单在原八大问数场景之外新增八个V2.1多任务演示场景。原S01—S08保持不变用于V2.0回归；本清单使用MT01—MT08独立编号，重点证明综合问题拆解、计划预览、DAG串并行、取消、重试、部分成功、关键失败和多轮计划复用。")
    add_heading(doc, "二、三角色权限基线", 1)
    add_table(doc, ["演示角色", "角色定位", "权限范围"], ROLES)
    add_heading(doc, "三、八场景总览", 1)
    add_table(doc, ["编号", "场景", "任务类型", "核心验收点"], [[s["id"], s["name"], s["type"], s["goal"]] for s in SCENARIOS])
    add_heading(doc, "四、统一演示规范", 1)
    add_bullets(doc, [
        "每次演示先展示用户问句和当前角色，再展开任务计划、执行轨迹和最终结果。",
        "Demo采用内置确定性Fixture并显示“模拟执行”；POC连接真实或显式Mock Provider；Product禁止Fixture进入生产路径。",
        "所有任务节点显示taskId、依赖、关键性、状态、耗时、attempt、证据引用；不得只展示动画而无状态事实。",
        "三个角色权限完全继承V2.0，无需重新确认；角色无权时在L2前置终止，禁止生成越权SQL后再依赖数据库报错。",
        "综合问题包含有权和无权节点时默认整单停止，不静默裁剪；用户确认仅执行授权范围后生成新的范围收缩计划并重新校验。",
        "关键任务失败必须终止完整结论；非关键任务失败可部分成功，但必须披露未核实项。",
    ])
    for idx, s in enumerate(SCENARIOS, 1):
        doc.add_page_break()
        add_heading(doc, f"场景{idx}｜{s['id']} {s['name']}", 1)
        add_table(doc, ["项目", "内容"], [
            ["场景类型", s["type"]], ["标准触发问句", s["question"]], ["核心能力", s["goal"]],
            ["标准任务DAG", s["dag"]], ["标准结果", s["result"]], ["失败/兜底", s["failure"]],
        ])
        add_heading(doc, "分角色差异化演示效果", 2)
        add_table(doc, ["角色", "预期效果"], [[ROLES[i][0], s["roles"][i]] for i in range(3)])
        add_heading(doc, "七层链路行为", 2)
        layer_rows = []
        for lid, name, purpose, inp, out, boundary in LAYERS:
            behavior = purpose
            if lid == "L3": behavior += f" 本场景计划：{s['dag']}。"
            if lid == "L6": behavior += f" 失败语义：{s['failure']}"
            if lid == "L7": behavior += f" 输出：{s['result']}"
            layer_rows.append([lid, name, behavior, boundary])
        add_table(doc, ["层级", "名称", "本场景行为", "强制边界"], layer_rows)
        add_heading(doc, "现场讲解话术", 2)
        doc.add_paragraph(f"“这不是把多个SQL简单拼在一起。系统先把问题形成版本化计划，再按依赖执行。当前展示的是{s['type']}：{s['dag']}。每个节点都有权限、状态和证据；失败时按照关键性决定失败或部分成功，最后一层不能掩盖缺失事实。”")
        add_heading(doc, "验收检查点", 2)
        add_bullets(doc, [
            "问句、角色、权限快照和计划版本可追溯。", "任务节点数量、依赖和关键性符合预期。",
            "执行状态与最终状态一致，取消/重试具有幂等性。", "最终结论逐条引用成功节点，失败节点进入未核实项。",
            "切换角色后重建会话和计划，不复用旧权限域结果。",
        ])
    add_heading(doc, "附录A｜角色×场景预期矩阵", 1)
    add_table(doc, ["场景", "张总", "李总", "王总"], [[s["id"], *s["roles"]] for s in SCENARIOS])
    add_heading(doc, "附录B｜Demo、POC、Product、客户交付映射", 1)
    add_table(doc, ["状态", "场景数据", "执行方式", "验收证据"], [
        ["Demo", "版本化脱敏Fixture", "确定性任务时间线", "离线回归、截图/录屏、SHA256"],
        ["POC", "测试库/批准样例", "真实服务或显式Mock", "API轨迹、SQL、结果对账"],
        ["Product", "隔离准生产数据", "正式运行组件", "安全、容量、恢复、升级回退"],
        ["Customer Delivery", "客户批准数据", "客户环境适配", "客户差异清单、业务对账和签字"],
    ])
    add_footer(doc)
    path = OUT / "01-NLQ产品V2.1多任务优化-8大标准演示场景完整清单.docx"
    doc.save(path)
    return path


def standard_io_doc():
    doc = Document()
    configure(doc, "NLQ产品V2.1七层架构完整输入输出标准案例\n（8大多任务场景）")
    add_heading(doc, "一、统一输入输出铁律", 1)
    add_bullets(doc, [
        "一次用户请求对应一个requestId和一个不可变权限快照；计划调整生成新planVersion。",
        "L2模型输出只是候选理解；L3—L6的口径、依赖、权限、安全、调度和状态由确定性代码裁决。",
        "L6形成唯一执行事实包；L7不得查库、补数、重算、隐藏失败或改变最终状态。",
        "所有层输出均携带schemaVersion、traceId、requestId、sessionId、actor、permissionSnapshotId、configVersion。",
        "V2.1限定单域已发布资产；多域识别、跨域授权和跨域编排不在范围内。",
    ])
    add_heading(doc, "二、七层标准契约总表", 1)
    add_table(doc, ["层级", "名称", "标准输入", "标准输出", "错误/等待状态"], [[l[0], l[1], l[3], l[4], l[5]] for l in LAYERS])
    add_heading(doc, "三、统一请求样例", 1)
    add_code(doc, '''{
  "schemaVersion":"2.1", "requestId":"req-mt02-001", "sessionId":"s-001",
  "actor":{"userId":"u-zhang","roleId":"ROLE_ALL","orgCode":"HQ"},
  "question":"分析2026年一季度对公贷款投放为什么下降，先确认同比，再按客户类型和机构找主要影响项。",
  "mode":"DEMO|POC|PRODUCT", "configVersion":"cfg-2.1.0",
  "control":{"previewPlan":false,"allowPartial":true}
}''')
    for s in SCENARIOS:
        doc.add_page_break()
        add_heading(doc, f"标准案例｜{s['id']} {s['name']}", 1)
        add_table(doc, ["项目", "标准值"], [["用户输入", s["question"]], ["任务DAG", s["dag"]], ["期望结果", s["result"]], ["异常语义", s["failure"]]])
        for lid, name, purpose, inp, out, boundary in LAYERS:
            add_heading(doc, f"{lid} {name}", 2)
            add_table(doc, ["维度", "标准内容"], [
                ["功能目标", purpose], ["输入对象", inp], ["处理规则", boundary], ["输出对象", out],
                ["本场景要点", s["dag"] if lid in ("L3", "L5") else (s["failure"] if lid == "L6" else s["result"] if lid == "L7" else s["goal"])],
            ])
            sample = {
                "L1": f'{{"requestId":"req-{s["id"].lower()}-001","question":"{s["question"]}","command":"SUBMIT"}}',
                "L2": '{"intent":"MULTI_TASK_ANALYSIS","entities":{"period":"2026Q1"},"permissionDecision":"ALLOW|FILTER|DENY","clarification":null}',
                "L3": f'{{"planVersion":1,"scenario":"{s["id"]}","taskGraph":"{s["dag"]}","completenessPolicy":"KEY_TASKS_REQUIRED"}}',
                "L4": '{"bindings":[{"taskId":"T1","metricId":"published_metric","table":"authorized_table","fields":["published_field"],"assetVersion":"v1"}]}',
                "L5": '{"dagId":"dag-001","nodes":[{"taskId":"T1","type":"SQL","dependsOn":[],"critical":true,"timeoutMs":30000}],"validation":"PASSED"}',
                "L6": '{"overallStatus":"SUCCEEDED|PARTIAL_SUCCESS|FAILED|CANCELLED","completion":{"succeeded":3,"total":4},"facts":[],"failedTasks":[],"auditRef":"audit-001"}',
                "L7": '{"status":"PARTIAL_SUCCESS","summary":"仅基于成功事实","evidenceRefs":["fact:T1"],"unverifiedItems":["失败节点对应结论"]}',
            }[lid]
            add_code(doc, sample)
    add_heading(doc, "四、状态机与错误码", 1)
    add_table(doc, ["类别", "代码/状态", "定义", "前端行为"], [
        ["请求", "WAITING_INPUT", "关键参数缺失", "展示澄清选项，不执行DAG"],
        ["计划", "WAITING_CONFIRMATION", "等待用户确认计划", "允许调整/确认/取消"],
        ["执行", "QUEUED/RUNNING", "排队或执行中", "SSE显示节点进度和心跳"],
        ["终态", "SUCCEEDED", "全部必需节点成功", "展示完整证据化结论"],
        ["终态", "PARTIAL_SUCCESS", "关键节点成功、非关键节点失败", "展示可用结论和未核实项"],
        ["终态", "FAILED", "关键节点失败或安全拒绝", "不得展示整体结论"],
        ["终态", "CANCELLED", "取消已传播并确认", "保留已完成事实但不生成完整结论"],
        ["权限", "PERMISSION_DENIED", "指标/机构/资产无权", "L2/L4短路，不生成越权SQL"],
        ["计划", "DAG_INVALID", "循环依赖或非法节点", "拒绝发布计划版本"],
        ["执行", "TASK_TIMEOUT/RETRY_EXHAUSTED", "超时/重试耗尽", "按节点关键性裁决整体状态"],
    ])
    add_footer(doc)
    path = OUT / "02-NLQ产品V2.1七层架构-8大多任务完整输入输出标准案例.docx"
    doc.save(path)
    return path


def technical_doc():
    doc = Document()
    configure(doc, "NLQ产品V2.1七层架构技术实现详设文件\n（完整落地版·多任务DAG·分级分权）")
    add_heading(doc, "一、建设范围与非目标", 1)
    add_table(doc, ["类别", "内容"], [
        ["建设目标", "在V2.0可信问数底座上实现综合问题理解、任务拆解、计划预览、DAG串并行、重试、取消、部分成功和证据化回答"],
        ["复用底座", "身份权限、配置发布、资产管理、AST SQL安全、运行事实、SSE、审计、准入、备份恢复"],
        ["非目标", "多域识别、跨域授权、跨域编排、开放式通用智能体、高风险写操作"],
        ["质量原则", "确定性代码裁决；不可变快照；事实与解释分离；关键失败显式披露；版本化可回放"],
    ])
    add_heading(doc, "二、总体组件架构", 1)
    add_code(doc, "前端对话/任务中心 → Java控制面(API、身份权限、计划版本、调度主记录、审计) → Python七层执行面(L2/L7受控模型、L3规划候选、L5查询计划、L6执行) → 单域数据库/Provider\n　　　　　　↘ SSE事件流 / 指标告警 / 运行事实库 / 配置与资产库")
    add_heading(doc, "三、核心领域对象", 1)
    add_table(doc, ["对象", "关键字段", "职责"], [
        ["TaskRequest", "requestId, sessionId, actor, question, command", "用户请求与控制命令"],
        ["TaskPlan", "planId, planVersion, status, completenessPolicy", "版本化语义计划"],
        ["TaskNode", "taskId, type, dependsOn, critical, inputRefs, retryPolicy", "最小可调度节点"],
        ["TaskAttempt", "attemptNo, status, startedAt, endedAt, errorCode", "一次执行尝试"],
        ["ExecutionFact", "factId, taskId, datasetHash, rows, dataAsOf", "不可变成功事实"],
        ["EvidenceAnswer", "answerId, status, claims, evidenceRefs, unverifiedItems", "证据化回答"],
        ["PermissionSnapshot", "subject, orgScope, metricScope, assetScope, version", "请求期间不可变授权事实"],
    ])
    add_heading(doc, "四、数据模型建议", 1)
    add_table(doc, ["表", "主键/核心字段", "约束与索引"], [
        ["task_plans", "plan_id, request_id, plan_version, status, plan_json, permission_snapshot_id", "UNIQUE(request_id,plan_version)；已确认版本不可覆盖"],
        ["task_nodes", "task_id, plan_id, node_type, critical, status, input_json", "INDEX(plan_id,status)"],
        ["task_dependencies", "plan_id, upstream_task_id, downstream_task_id", "复合主键；发布前无环校验"],
        ["task_attempts", "attempt_id, task_id, attempt_no, status, error_code", "UNIQUE(task_id,attempt_no)"],
        ["execution_facts", "fact_id, task_id, attempt_id, dataset_hash, payload_ref, data_as_of", "仅成功attempt写入；不可变"],
        ["task_events", "event_id, request_id, task_id, sequence_no, event_type, payload", "UNIQUE(request_id,sequence_no)，支持SSE续传"],
        ["answer_evidence", "answer_id, claim_id, fact_id", "所有关键结论至少关联一个fact"],
    ])
    add_heading(doc, "五、七层逐层技术详设", 1)
    layer_tech = {
        "L1": ["Vue任务计划卡、节点时间线、取消/重试按钮；Java REST+SSE入口", "校验命令与终态；生成幂等键；绑定会话、配置和权限快照", "POST /api/v2.1/requests；GET /events；POST /cancel；POST /tasks/{id}/retry"],
        "L2": ["Python受控LLM抽取+Java规则校验", "JSON Schema约束模型输出；字典精准映射；缺参澄清；指标/机构/资产权限预检", "UnderstandingResult包含候选目标、实体、上下文来源和permissionDecision"],
        "L3": ["语义规划器+能力注册表+DAG草案生成器", "将分析目标拆成只读任务；标记关键性；生成依赖；计算完整性策略；规则复核模型候选", "计划状态DRAFT→VALIDATED→WAITING_CONFIRMATION/CONFIRMED"],
        "L4": ["资产目录、指标字典、Schema注册表、权限决策服务", "逐节点绑定发布资产；冻结assetVersion；无权限资产FILTER或DENY；全部字段白名单", "AssetBindingSet包含taskId、数据源、表字段、口径、数据时效和权限证据"],
        "L5": ["SQL模板/AST门禁、计算节点注册表、DAG编译器", "模板渲染、范围注入、AST校验、无环/引用/类型校验、成本估算；确认后计划不可变", "ExecutableTaskDAG含拓扑序、并发组、超时、重试、补偿和输出引用"],
        "L6": ["Java调度主记录+Python执行客户端+公平准入+SSE事件", "按拓扑调度；节点CAS状态迁移；指数退避；取消传播；成功事实哈希；关键性裁决整体状态", "ExecutionFactBundle、TaskAttempt、TaskEvent、审计和监控指标"],
        "L7": ["受控LLM复述+事实一致性校验器", "只传成功facts；先规则生成claim/evidence骨架，再允许LLM润色；数值、机构、时间和完成度逐项核对", "EvidenceAnswer显式包含status、claims、charts、evidence、unverifiedItems和followUps"],
    }
    for lid, name, purpose, inp, out, boundary in LAYERS:
        add_heading(doc, f"{lid} {name}", 2)
        add_table(doc, ["设计项", "详细说明"], [
            ["职责", purpose], ["输入", inp], ["输出", out], ["技术组件", layer_tech[lid][0]],
            ["核心实现", layer_tech[lid][1]], ["接口/状态", layer_tech[lid][2]], ["安全边界", boundary],
        ])
        add_heading(doc, "处理流程", 3)
        flows = {
            "L1": "接收→认证→加载会话/配置/权限快照→幂等检查→创建Request→发布received事件→进入L2",
            "L2": "抽取候选→上下文补全→字典映射→必填校验→权限预检→澄清/拒绝/进入L3",
            "L3": "目标归一→能力匹配→拆分节点→定义依赖与关键性→完整性校验→生成Plan vN",
            "L4": "逐节点检索资产→权限过滤→口径/时效校验→冻结资产版本→形成绑定集",
            "L5": "生成SQL/计算节点→注入数据范围→AST安全→DAG无环/类型校验→成本校验→发布执行计划",
            "L6": "准入→拓扑就绪队列→并发执行→事件/心跳→重试或取消→事实落库→整体状态裁决",
            "L7": "筛选成功事实→生成结论骨架→模型润色→事实一致性/敏感校验→输出证据与未核实项",
        }[lid]
        add_code(doc, flows)
    add_heading(doc, "六、DAG调度与状态机", 1)
    add_code(doc, "DRAFT → VALIDATED → WAITING_CONFIRMATION → CONFIRMED → QUEUED → RUNNING → {SUCCEEDED | PARTIAL_SUCCESS | FAILED | CANCELLED}")
    add_bullets(doc, [
        "节点只有在全部上游满足依赖条件时进入READY；失败上游导致依赖节点SKIPPED。",
        "同一taskId任一时刻只允许一个活动attempt；重试通过CAS和幂等键防止重复执行。",
        "取消从Request向未完成节点传播；已提交数据源的查询使用executionId定向取消。",
        "关键节点全部成功且非关键节点有失败：PARTIAL_SUCCESS；任一必需关键节点失败：FAILED。",
        "服务重启后从数据库未终态Request恢复，而非依赖内存队列。",
    ])
    add_heading(doc, "七、权限与安全设计", 1)
    add_table(doc, ["门禁", "位置", "规则"], [
        ["身份与会话", "L1", "令牌主体与session主体一致；角色切换创建新session"],
        ["业务权限预检", "L2", "机构、指标、数据范围全量验证；无权目标不进入候选计划"],
        ["资产权限", "L4", "表、字段、数据源和API逐节点白名单"],
        ["SQL与范围", "L5", "AST只读门禁、参数绑定、行列范围强制注入"],
        ["执行安全", "L6", "短期内部令牌、幂等、限流、超时、审计和结果脱敏"],
        ["输出安全", "L7", "事实白名单、敏感词/实体过滤、权限范围复核"],
    ])
    add_heading(doc, "八、接口契约建议", 1)
    add_table(doc, ["方法", "路径", "用途", "关键响应"], [
        ["POST", "/api/v2.1/requests", "提交综合问题", "requestId,status,planVersion"],
        ["GET", "/api/v2.1/requests/{id}/plan", "查看计划", "nodes,edges,cost,permissionDecision"],
        ["PUT", "/api/v2.1/requests/{id}/plan", "调整计划", "newPlanVersion,diff"],
        ["POST", "/api/v2.1/requests/{id}/confirm", "确认执行", "QUEUED"],
        ["GET", "/api/v2.1/requests/{id}/events", "SSE进度/续传", "id,event,data"],
        ["POST", "/api/v2.1/requests/{id}/cancel", "幂等取消", "CANCEL_PENDING/CANCELLED"],
        ["POST", "/api/v2.1/tasks/{taskId}/retry", "定点重试", "attemptNo,status"],
        ["GET", "/api/v2.1/requests/{id}/answer", "证据化结果", "status,claims,evidence,unverifiedItems"],
    ])
    add_heading(doc, "九、可观测与审计", 1)
    add_bullets(doc, [
        "指标：请求吞吐、排队时间、DAG节点数、并行度、节点成功率、重试率、取消延迟、部分成功率、模型耗时与成本。",
        "日志：禁止记录密钥和原始敏感数据；统一traceId/requestId/planId/taskId/attemptId。",
        "审计：问题、权限快照、配置版本、计划差异、确认人、SQL摘要、执行事实哈希、回答证据链不可抵赖。",
        "告警：队列饱和、关键任务失败激增、取消超时、事实/回答不一致、Provider连续失败、成本超额。",
    ])
    add_heading(doc, "十、测试与验收矩阵", 1)
    add_table(doc, ["测试层级", "必测内容", "通过条件"], [
        ["单元", "拆解、无环、拓扑、关键性、状态裁决、取消、重试", "确定性边界全覆盖"],
        ["契约", "L1—L7 Schema、Java/Python内部契约、SSE续传", "向后兼容且版本明确"],
        ["安全", "越权节点、SQL绕过、提示注入、重试绕权、角色切换", "无越权SQL/数据/话术"],
        ["集成", "八场景×三角色×正常/失败分支", "结果、状态和审计一致"],
        ["性能", "30执行槽、50等待队列、突发、长任务、1300 SSE", "达到V2基线且无资源泄漏"],
        ["恢复", "服务重启、数据库恢复、发布回退", "未终态任务可恢复或明确终止"],
        ["Demo", "断网单文件、固定时间线、八场景", "无外链、结果可重复"],
        ["POC", "真实Provider、数据库、黄金问题", "无静默Fixture且对账通过"],
        ["Product", "安装升级、安全长稳、备份恢复", "发布门禁全部通过"],
    ])
    add_heading(doc, "十一、实施分解", 1)
    add_bullets(doc, [
        "M1 契约与数据模型：冻结TaskPlan/DAG/Fact/Answer Schema及迁移。",
        "M2 任务规划：实现L2/L3、计划预览调整、权限裁剪和版本化。",
        "M3 编排执行：实现L5/L6串并行、重试、取消、恢复和SSE。",
        "M4 用户体验：计划卡、任务中心、进度轨迹、部分成功和证据展示。",
        "M5 三状态同步：完成Demo Fixture、POC Adapter、Product Runtime与八场景矩阵。",
        "M6 发布关闭：回归V2.0，完成安全、容量、恢复、文档和制品发布。",
    ], numbered=True)
    add_heading(doc, "附录A｜八场景到技术能力映射", 1)
    add_table(doc, ["场景", "主要技术能力", "关键状态"], [[s["id"], s["goal"], s["failure"]] for s in SCENARIOS])
    add_footer(doc)
    path = OUT / "03-NLQ产品V2.1七层架构技术实现详设文件-完整落地版.docx"
    doc.save(path)
    return path


if __name__ == "__main__":
    for generated in (scenario_doc(), standard_io_doc(), technical_doc()):
        print(generated)
