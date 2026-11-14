"""确定性演示数据（seed 与干跑校验共用，不依赖 DB / 第三方库）。

规模契约：
  3 投件源 / 60 案件 / 210 附件（9 重复件 / 7 低置信待确认 / 4 无保单号未识别）/ 1 规则 v1 / 2 历史批次 / 3 账号

口径：
  - 25 个案件应收 4 类材料（医疗险 13 / 重疾险 12），35 个案件应收 3 类材料；
  - 其中 9 个 4 类案件的第 4 个文件是「重复投递」件（同内容、名字带 (1)），因此 205 件绑定案件 + 5 件未绑定 = 210；
  - 7 件低置信（文件名无关键词、内容只有弱特征）→ pending；
  - 4 件无任何材料特征、且未绑定案件 → unknown；
  - 全部数据由 random.Random(580) 生成，重复执行逐字节一致。
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

from src.constants.enums import EXPECTED_MATERIALS, InsuranceType, MaterialType

DEMO_PASSWORD = "Demo@2026"
DEMO_USERS: tuple[tuple[str, str, str], ...] = (
    ("admin@docflow.io", "周敏（受理主管）", "admin"),
    ("analyst@docflow.io", "林嘉（受理员）", "analyst"),
    ("auditor@docflow.io", "袁珂（稽核）", "auditor"),
)

SOURCES: tuple[dict, ...] = (
    {
        "code": "shared_drive",
        "name": "共享盘投件",
        "path": "\\\\fileserver\\claims-drop",
        "note": "受理组每日两次批量投件，按「案件号/客户名」建文件夹",
        "cycle": "每日 08:40 / 13:30",
    },
    {
        "code": "mailbox",
        "name": "理赔邮箱附件",
        "path": "claims@hangan-broker.cn",
        "note": "客户与代理人的邮件附件，命名最乱，常见 IMG_/微信图片",
        "cycle": "每小时拉取",
    },
    {
        "code": "portable",
        "name": "移动盘补件",
        "path": "E:\\补件-202611",
        "note": "外勤带回的移动盘，多为手机翻拍照片",
        "cycle": "按需手动挂载",
    },
)

ASSIGNEES = ("林嘉", "王倩", "周航", "陈曦")
CUSTOMERS = (
    "张伟", "李静", "王芳", "刘洋", "赵敏", "孙悦", "周强", "吴磊", "郑雯", "冯磊",
    "许静", "何骏", "高蕾", "马超", "罗宁", "梁宇", "宋佳", "唐锐", "邓婕", "韩松",
    "曹颖", "彭勇", "曾琪", "萧岩", "田甜", "董浩", "潘琳", "顾航", "严宁", "洪涛",
)

MATERIAL_ORDER: tuple[str, ...] = (
    MaterialType.INVOICE.value,
    MaterialType.DIAGNOSIS.value,
    MaterialType.ID_CARD.value,
    MaterialType.BANK_CARD.value,
    MaterialType.DISCHARGE.value,
)

MATERIAL_LABELS = {
    MaterialType.INVOICE.value: "发票",
    MaterialType.DIAGNOSIS.value: "诊断书",
    MaterialType.ID_CARD.value: "身份证",
    MaterialType.BANK_CARD.value: "银行卡",
    MaterialType.DISCHARGE.value: "出院小结",
    MaterialType.UNKNOWN.value: "未识别",
}

_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK = "10X98765432"


def id_number(prefix17: str) -> str:
    """按 GB 11643 生成带合法校验位的 18 位身份证号。"""
    total = sum(int(prefix17[i]) * _ID_WEIGHTS[i] for i in range(17))
    return prefix17 + _ID_CHECK[total % 11]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------- 内容模板 ----


def _amount(rng: random.Random, low: int, high: int) -> str:
    value = rng.randrange(low, high)
    return f"{value:,}.00"


def invoice_content(case: dict, doc_date: date, rng: random.Random, ci: int) -> str:
    code = f"0440019{ci:05d}"
    number = f"{rng.randrange(10**8):08d}"
    return (
        "增值税电子普通发票\n"
        f"发票代码：{code}\n"
        f"发票号码：{number}\n"
        f"开票日期：{doc_date.year}年{doc_date.month}月{doc_date.day}日\n"
        "购买方名称：恒安保险经纪有限公司\n"
        f"销售方名称：{case['hospital']}\n"
        f"价税合计（大写）：人民币壹仟贰佰元整  ￥{_amount(rng, 600, 9800)}\n"
        "备注：被保险人门诊医疗费用\n"
        f"保单号：{case['policy_no']}\n"
    )


def diagnosis_content(case: dict, doc_date: date, rng: random.Random) -> str:
    icd = f"J{18 + (rng.randrange(3))}.{rng.randrange(10)}"
    return (
        f"{case['hospital']} 门诊诊断证明书\n"
        f"姓名：{case['customer_name']}   性别：{case['gender']}   年龄：{case['age']}\n"
        "主诉：反复咳嗽两周，加重三天\n"
        f"现病史：两周前受凉后出现咳嗽、咳痰，自行服药未见好转。\n"
        f"诊断意见：社区获得性肺炎（ICD-10 {icd}）\n"
        "处理意见：抗感染治疗，两周后门诊复查。\n"
        f"报告医师：{case['doctor']}   日期：{doc_date.year}年{doc_date.month}月{doc_date.day}日\n"
        f"保单号：{case['policy_no']}\n"
    )


def id_card_content(case: dict, doc_date: date) -> str:
    number = id_number(case["id_prefix"])
    return (
        "中华人民共和国 居民身份证\n"
        f"姓名 {case['customer_name']}   性别 {case['gender']}   民族 汉\n"
        f"出生 {case['birth']}\n"
        "住址 某某省某某市某某区某某路 18 号 3 单元 502\n"
        f"公民身份号码 {number}\n"
        "签发机关 某某市公安局某某分局\n"
        "有效期限 2019.05.12-2039.05.12\n"
        f"保单号：{case['policy_no']}\n"
    )


def bank_card_content(case: dict, doc_date: date, rng: random.Random) -> str:
    card = f"6214 8300 {rng.randrange(1000, 9999)} {rng.randrange(1000, 9999)}"
    return (
        "招商银行 一卡通\n"
        f"账户名 {case['customer_name']}\n"
        f"卡号 {card}\n"
        "开户行 招商银行某某分行营业部\n"
        "银联 借记卡\n"
        f"保单号：{case['policy_no']}\n"
    )


def discharge_content(case: dict, doc_date: date, rng: random.Random) -> str:
    days = rng.randrange(3, 12)
    return (
        f"{case['hospital']} 出院小结\n"
        f"姓名：{case['customer_name']}   住院号：ZY{doc_date.strftime('%Y%m%d')}{rng.randrange(10, 99)}\n"
        f"入院日期：{doc_date.year}年{doc_date.month}月{doc_date.day}日\n"
        "出院日期：入院后数日\n"
        f"住院天数：{days} 天\n"
        "出院诊断：社区获得性肺炎（ICD10 J18.9）\n"
        "出院医嘱：继续口服抗生素一周，门诊复查；注意休息。\n"
        f"保单号：{case['policy_no']}\n"
    )


# --------------------------------------------------------------- 弱特征内容 ----


WEAK_CONTENTS: dict[str, tuple[str, str]] = {
    # kind -> (original_name, content)
    "IMG_2043": (
        "IMG_2043.jpg",
        "影像所见：左上肺陈旧性病灶，边界清晰。\n建议三个月后复查，报告医师：陈立。\n拍摄地点：某某市第一人民医院放射科\n",
    ),
    "scan_0012": (
        "扫描件_0012.pdf",
        "开票日期 2026年10月18日\n税额 84.00\n合计金额 1,284.00\n备注：门诊费用\n",
    ),
    "wechat_1030": (
        "微信图片_20261030144022.jpg",
        "住址 某某省某某市某某区某某路 18 号\n出生 1990 年 3 月\n性别 女\n",
    ),
    "newdoc": (
        "新建文档.pdf",
        "储蓄 借记 有效\n持卡人签名：\n开户 网点：某某支行\n",
    ),
    "camscanner": (
        "扫描全能王 2026-10-29 14.02.pdf",
        "门诊 复查 影像\n就诊科室：呼吸内科\n医师签名：\n",
    ),
    "file3": (
        "文件 (3).pdf",
        "销售方 某某医药有限公司\n开票日期 2026年10月21日\n税额 12.60\n",
    ),
    "img_2044": (
        "IMG_2044.jpg",
        "住址 某某省某某市\n性别 男\n出生 1987 年 11 月\n正面照片\n",
    ),
}

UNKNOWN_CONTENTS: tuple[tuple[str, str], ...] = (
    ("IMG_8891.jpg", "照片拍摄于2026年10月30日 14:22，光线不足，已重新拍摄。\n"),
    ("IMG_8892.jpg", "图片已压缩，原图见共享盘 2026-11 目录。\n"),
    ("扫描件_0007.pdf", "本页为空白扫描，请重新提供。\n"),
    ("附件_最终版.pdf", "见附件，如有疑问请联系理赔受理组。\n"),
)

PENDING_KINDS = ("IMG_2043", "scan_0012", "wechat_1030", "newdoc", "camscanner", "file3", "img_2044")

HOSPITALS = (
    "某某市第一人民医院",
    "某某市中心医院",
    "某某医科大学附属医院",
    "某某区人民医院",
)
DOCTORS = ("陈立", "何静", "赵鹏", "徐蕾", "刘敏")


# ------------------------------------------------------------------- 生成 ----


def _insurance_sequence(rng: random.Random) -> list[str]:
    pool = (
        [InsuranceType.MEDICAL.value] * 13
        + [InsuranceType.CRITICAL.value] * 12
        + [InsuranceType.ACCIDENT.value] * 12
        + [InsuranceType.AUTO.value] * 12
        + [InsuranceType.LIFE.value] * 11
    )
    rng.shuffle(pool)
    return pool


def build_case_specs() -> list[dict]:
    rng = random.Random(580)
    types = _insurance_sequence(rng)
    cases: list[dict] = []
    for index in range(60):
        insurance = types[index]
        # 保单号 = P + 12 位数字
        policy_no = "P" + f"2026{index + 1:08d}"
        incident = date(2026, 9, 1) + timedelta(days=index % 61)
        cases.append(
            {
                "index": index,
                "case_no": f"CLM-2026-{index + 1:04d}",
                "policy_no": policy_no,
                "customer_name": CUSTOMERS[index % len(CUSTOMERS)],
                "insurance_type": insurance,
                "channel": ("shared_drive", "mailbox", "portable")[index % 3],
                "assignee": ASSIGNEES[index % len(ASSIGNEES)],
                "incident_date": incident,
                "claim_amount": round(1260 + (index * 731) % 48000 + 0.5, 2),
                "note": "客户电话补充材料" if index % 11 == 5 else "",
                "slots": list(EXPECTED_MATERIALS[insurance]),
                "doctor": DOCTORS[index % len(DOCTORS)],
                "hospital": HOSPITALS[index % len(HOSPITALS)],
                "gender": "男" if index % 2 == 0 else "女",
                "age": 28 + (index * 3) % 45,
                "birth": f"19{70 + index % 28}年{(index % 12) + 1}月{(index % 27) + 1}日",
                "id_prefix": f"1101{index % 20:02d}19{70 + index % 28:02d}{(index % 12) + 1:02d}{(index % 27) + 1:02d}{100 + index % 400}",
            }
        )
    # 身份证前 17 位必须恰好 17 位数字
    for case in cases:
        prefix = case["id_prefix"][:17]
        case["id_prefix"] = prefix.ljust(17, "0")
    return cases


def _material_name(case: dict, material: str, doc_date: date, index: int) -> tuple[str, str]:
    """返回 (original_name, ext)。"""
    stamp = doc_date.strftime("%Y%m%d")
    customer = case["customer_name"]
    if material == MaterialType.INVOICE.value:
        return f"增值税电子普通发票_{case['policy_no']}_{stamp}.pdf", "pdf"
    if material == MaterialType.DIAGNOSIS.value:
        if index % 2 == 0:
            return f"诊断证明书_{customer}_{stamp}.pdf", "pdf"
        return f"诊断书_{customer}_{stamp}.jpg", "jpg"
    if material == MaterialType.ID_CARD.value:
        return f"身份证_{customer}_正面.jpg", "jpg"
    if material == MaterialType.BANK_CARD.value:
        return f"银行卡_{customer}_招行.jpg", "jpg"
    return f"出院小结_{customer}_{stamp}.pdf", "pdf"


def _content_for(case: dict, material: str, doc_date: date, rng: random.Random) -> str:
    if material == MaterialType.INVOICE.value:
        return invoice_content(case, doc_date, rng, case["index"])
    if material == MaterialType.DIAGNOSIS.value:
        return diagnosis_content(case, doc_date, rng)
    if material == MaterialType.ID_CARD.value:
        return id_card_content(case, doc_date)
    if material == MaterialType.BANK_CARD.value:
        return bank_card_content(case, doc_date, rng)
    return discharge_content(case, doc_date, rng)


def build_attachment_specs(cases: list[dict]) -> list[dict]:
    rng = random.Random(581)
    four_slot = [case for case in cases if len(case["slots"]) == 4]
    dup_cases = {four_slot[i]["index"] for i in (1, 4, 7, 10, 13, 16, 18, 21, 24)}

    # 6 件绑定案件的弱特征件：按材料类型在案件顺序里找第一个可用槽位
    pending_kinds = ("scan_0012", "wechat_1030", "newdoc", "camscanner", "file3", "img_2044")
    want_types = (
        MaterialType.INVOICE.value,
        MaterialType.ID_CARD.value,
        MaterialType.BANK_CARD.value,
        MaterialType.DIAGNOSIS.value,
        MaterialType.INVOICE.value,
        MaterialType.ID_CARD.value,
    )
    pending_slots: dict[tuple[int, int], str] = {}
    for order, (kind, want) in enumerate(zip(pending_kinds, want_types)):
        start = (order * 11 + 3) % 60  # 轮转起点，让待确认件散落在不同案件
        for offset in range(60):
            case = cases[(start + offset) % 60]
            if case["index"] in dup_cases:
                continue
            slot_index = next(
                (
                    index
                    for index, material in enumerate(case["slots"])
                    if material == want and (case["index"], index) not in pending_slots
                ),
                None,
            )
            if slot_index is None:
                continue
            pending_slots[(case["index"], slot_index)] = kind
            break

    specs: list[dict] = []
    seq = 0
    for case in cases:
        slots = case["slots"]
        for slot_index, material in enumerate(slots):
            seq += 1
            doc_date = case["incident_date"] + timedelta(days=slot_index * 2 + 1)
            dup_slot = case["index"] in dup_cases and slot_index == len(slots) - 1

            if dup_slot:
                primary_slot = 1
                primary = next(
                    spec for spec in specs if spec["case_index"] == case["index"] and spec["slot_index"] == primary_slot
                )
                ext = primary["ext"]
                stem = primary["original_name"].rsplit(".", 1)[0]
                name = f"{stem} (1).{ext}"
                content = primary["content_sample"]
                specs.append(
                    {
                        "case_index": case["index"],
                        "slot_index": slot_index,
                        "scan_seq": seq,
                        "source_code": case["channel"],
                        "original_name": name,
                        "ext": ext,
                        "size_bytes": primary["size_bytes"],
                        "content_sample": content,
                        "sha256": sha256_text(content),
                        "material_hint": primary["material_hint"],
                        "doc_date": primary["doc_date"],
                        "duplicate_of_seq": primary["scan_seq"],
                        "weak": False,
                        "note": "同一份材料重复投递（微信重发）",
                    }
                )
                continue

            kind = pending_slots.get((case["index"], slot_index))
            if kind:
                name, content = WEAK_CONTENTS[kind]
                ext = name.rsplit(".", 1)[-1].lower()
                specs.append(
                    {
                        "case_index": case["index"],
                        "slot_index": slot_index,
                        "scan_seq": seq,
                        "source_code": case["channel"],
                        "original_name": name,
                        "ext": ext,
                        "size_bytes": 180_000 + (seq * 977) % 900_000,
                        "content_sample": content,
                        "sha256": sha256_text(content),
                        "material_hint": material,
                        "doc_date": doc_date.isoformat(),
                        "duplicate_of_seq": None,
                        "weak": True,
                        "note": "低置信：文件名无关键词，内容仅弱特征",
                    }
                )
                continue

            name, ext = _material_name(case, material, doc_date, slot_index)
            content = _content_for(case, material, doc_date, rng)
            spec = {
                "case_index": case["index"],
                "slot_index": slot_index,
                "scan_seq": seq,
                "source_code": case["channel"],
                "original_name": name,
                "ext": ext,
                "size_bytes": 96_000 + (seq * 1777) % 2_400_000,
                "content_sample": content,
                "sha256": sha256_text(content),
                "material_hint": material,
                "doc_date": doc_date.isoformat(),
                "duplicate_of_seq": None,
                "weak": False,
                "note": "",
            }
            specs.append(spec)

    # 未绑定 + 无任何材料特征的 5 件（其中 1 件是 IMG_2043，待人工判类型并补保单号）
    img_name, img_content = WEAK_CONTENTS["IMG_2043"]
    seq += 1
    specs.append(
        {
            "case_index": None,
            "slot_index": None,
            "scan_seq": seq,
            "source_code": "shared_drive",
            "original_name": img_name,
            "ext": "jpg",
            "size_bytes": 742_318,
            "content_sample": img_content,
            "sha256": sha256_text(img_content),
            "material_hint": MaterialType.UNKNOWN.value,
            "doc_date": "2026-10-26",
            "duplicate_of_seq": None,
            "weak": True,
            "note": "投在共享盘根目录、未建案件文件夹；影像所见无定论",
        }
    )
    for name, content in UNKNOWN_CONTENTS:
        seq += 1
        specs.append(
            {
                "case_index": None,
                "slot_index": None,
                "scan_seq": seq,
                "source_code": "portable" if name.startswith("IMG") else "shared_drive",
                "original_name": name,
                "ext": name.rsplit(".", 1)[-1].lower(),
                "size_bytes": 120_000 + (seq * 331) % 640_000,
                "content_sample": content,
                "sha256": sha256_text(content),
                "material_hint": MaterialType.UNKNOWN.value,
                "doc_date": "2026-10-30",
                "duplicate_of_seq": None,
                "weak": False,
                "note": "无材料特征、无保单号",
            }
        )
    return specs


def build_all() -> tuple[list[dict], list[dict]]:
    cases = build_case_specs()
    return cases, build_attachment_specs(cases)


RULE_V1 = {
    "version": 1,
    "template": "{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}",
    "conflict_policy": "sha256_duplicate_first",
    "date_source": "filename>content>case",
    "note": "v1：受理组现行口径，重复件不落盘、冲突序号递增",
}
