"""
Sensitive word detection training dataset generator (v2.0 — multi-category).

Strategy: Uses statistical text features + TF-IDF on benign-vs-risk corpora
across multiple risk categories (phishing, fraud, spam, gambling-bait,
aggressive-marketing, contact-solicitation) to build a robust classifier.

The training samples here focus on universally recognized spam/risk STRUCTURAL
patterns. For domain-specific sensitive terms (pornographic, violent, gambling
keywords), users should supply an external rules config file — see
`sensitive_rules_config.example.json`.

Risk categories covered in training data:
  - PHISHING:   credential harvesting, fake notifications
  - FRAUD:      financial scams, advance-fee fraud
  - SPAM:       bulk unsolicited advertising
  - GAMBLING:   high-return lure, "guaranteed win" patterns
  - AGGRESSIVE:  clickbait, sensational claims, urgency manipulation
  - CONTACT:    soliciting private chat / social media contacts

Features extracted (expanded v2):
  - ent, punct, digit, special_char, repeated_char ratios
  - url_flag, contact_info_flag, emoji_ratio
  - exclamation_ratio, consecutive_repeat_max, homoglyph_flag
  - avg_sentence_len, text_length
"""

import json
import math
import re
from collections import Counter
from typing import Any

# ---------------------------------------------------------------------------
# Feature configuration
# ---------------------------------------------------------------------------

SENSITIVE_WORD_FEATURE_CONFIG = {
    "entropy_threshold": 3.5,
    "punctuation_max_ratio": 0.15,
    "digit_max_ratio": 0.30,
    "repeated_char_max_ratio": 0.20,
    "special_char_max_ratio": 0.10,
    "emoji_max_ratio": 0.15,
    "exclamation_max_ratio": 0.25,
    "min_text_length": 5,
    "max_avg_word_length": 15,
}

FEATURE_NAMES_V2 = [
    "entropy",
    "punctuation_ratio",
    "digit_ratio",
    "special_char_ratio",
    "repeated_char_ratio",
    "url_flag",
    "contact_info_flag",
    "emoji_ratio",
    "exclamation_ratio",
    "consecutive_repeat_max",
    "homoglyph_flag",
]

RISK_CATEGORIES = [
    "phishing",
    "fraud",
    "spam",
    "gambling",
    "aggressive",
    "contact",
]

# ---------------------------------------------------------------------------
# Benign samples (daily conversation, news, tech, business)
# ---------------------------------------------------------------------------

BENIGN_SAMPLES_CN: list[str] = [
    # Daily conversation
    "今天天气真不错，适合出去走走",
    "请问这个功能怎么使用呢",
    "谢谢你的帮助，问题已经解决了",
    "晚上一起吃饭吧，老地方见",
    "周末打算去爬山，你要一起吗",
    "最近工作太忙了，需要好好休息一下",
    "这款咖啡口感确实不错，值得推荐",
    "孩子的作业终于做完了，真不容易",
    "地铁上人真多，挤得喘不过气",
    "下个月打算去云南旅游，有推荐吗",
    # News / announcements
    "公司年度报告已经正式发布了",
    "技术团队正在优化系统性能",
    "明天下午两点开会讨论项目进展",
    "新版本软件修复了若干已知问题",
    "本周五团建活动请各位准时参加",
    "服务器例行维护计划在下周二进行",
    "年终总结需要包含业绩数据和规划",
    "新员工入职培训安排在下周一",
    "市场调研报告将在本周内完成",
    "合作伙伴对我们的方案很感兴趣",
    # Tech / professional
    "深度学习在自然语言处理中应用广泛",
    "数据分析显示用户增长趋势良好",
    "人工智能正在改变各行各业的运作方式",
    "开源社区贡献者数量持续增长",
    "用户体验优化是下一阶段的重点工作",
    "API接口文档已发布在开发者平台",
    "代码审查通过了所有测试用例",
    "数据库备份已完成，运行状态正常",
    "设备巡检一切正常，无异常告警",
    "新功能上线后用户活跃度提升了百分之二十",
    # Customer service
    "感谢您的反馈，我们会尽快处理",
    "请确认一下收货地址是否正确",
    "物流信息显示包裹已在配送途中",
    "您的问题已转交相关部门处理",
    "如需帮助请随时联系我们的客服",
    "系统升级不会影响您的正常使用",
    "文档已经更新到最新版本",
    "供应商报价已经收到，请查收邮件",
    "研发进度符合预期，可以按时交付",
    "财务报告已经提交给审计部门",
    # Health / lifestyle (benign)
    "每天坚持运动对身体很有好处",
    "蔬菜水果的摄入量要保证充足",
    "午休半小时能有效提高下午的工作效率",
    "阅读是一个很好的习惯，受益终身",
    "环保出行，尽量选择公共交通",
    "合理规划时间才能平衡好工作和生活",
    "这个季节正是赏花的好时节",
    "网购时记得货比三家，理性消费",
]

# ---------------------------------------------------------------------------
# Risk samples — organised by category
# ---------------------------------------------------------------------------

# ---- PHISHING: credential harvesting, fake system alerts ----
PHISHING_SAMPLES: list[str] = [
    "系统检测到异常登录请立即验证身份信息",
    "您的账号存在安全风险请点击链接确认",
    "尊敬的用户请更新您的账户安全设置",
    "安全中心提醒您近期有异常设备登录",
    "系统升级需要重新验证您的手机号码",
    "您的支付密码已经过期请尽快更新",
    "身份认证信息已过期请重新提交资料",
    "邮箱账户需验证请在两小时内完成操作",
    "系统提醒您的账号绑定信息已被修改",
    "您的账号在其他设备登录如非本人请立即处理",
    "密码强度过低建议立即修改以保障安全",
    "验证码已发送请勿泄露给任何人",
    "账户注销申请已提交如非本人操作请取消",
    "您的账号因安全原因被临时限制请验证解锁",
]

# ---- FRAUD: financial scams, fake refunds, advance-fee ----
FRAUD_SAMPLES: list[str] = [
    "您有一笔退款待领取请提供银行卡信息",
    "系统检测到您的账户资金存在异常变动",
    "恭喜获得现金大奖请提交身份信息领取",
    "您的征信报告存在异常记录请尽快处理",
    "退税通知您有一笔税款可以申请退还",
    "您的贷款申请已通过请联系工作人员",
    "系统提醒您的账户即将被扣除年费",
    "您的银行卡存在风险请立即更新信息",
    "账户已被限制交易请致电客服解除",
    "通知您有一笔遗产待继承请提供证件",
    "您的信用卡积分即将失效请尽快兑换",
    "资金到账延迟请添加客服微信确认",
    "您的账户收到一笔异常转账请核实",
]

# ---- SPAM: bulk unsolicited ads, promotional flooding ----
SPAM_SAMPLES: list[str] = [
    "限时特惠全场五折错过等一年",
    "新品上市免费试用名额仅限今日",
    "会员日大促满减优惠送不停",
    "清仓大甩卖最后三天价格触底",
    "年中大促惊喜不断好货低至一折",
    "品牌日专属优惠券限时领取中",
    "全场包邮满两件再送一件",
    "新用户专享首单零元购机不可失",
    "店庆狂欢双倍积分还送礼品",
    "转发朋友圈集满五十个赞免费领好礼",
    "扫码下载App即送十元话费",
    "注册就送红包最高可领一百元",
]

# ---- GAMBLING-BAIT: high-return promises, "sure win" rhetoric ----
GAMBLING_BAIT_SAMPLES: list[str] = [
    "内部消息这只明天必涨速速入金",
    "稳赚不赔跟着老师操作月入过万",
    "天天涨停板跟着我操作保证收益",
    "零风险高回报轻松实现财务自由",
    "跟着导师做单日收益至少百分之五",
    "免费跟单一对一指导亏损全额赔付",
    "专业老师带单准确率高达九成以上",
    "足不出户日赚千元错过只能后悔",
    "一级市场原始股认购名额有限",
    "每天只需十分钟收益看得见",
    "投资一千回报一万不是梦",
    "稳赢策略跟着做就能赚",
]

# ---- AGGRESSIVE: sensational, urgency-manipulation, clickbait ----
AGGRESSIVE_SAMPLES: list[str] = [
    "紧急通知错过这条消息你将后悔一辈子",
    "惊爆消息全网疯传速速围观",
    "重大发现这个秘密百分之九十九的人不知道",
    "马上删除你手机里的这些东西太可怕了",
    "不看亏大了这是今年最重要的消息",
    "再不看就要被删除了速看",
    "一定要告诉你的家人看完吓一跳",
    "最新谣言揭秘真相竟然是这个",
    "今晚十二点前必须做的事情清单",
    "这种食物千万别吃央视已经曝光",
    "转了这条消息你今年会好运连连",
    "惊天秘密泄露速看即删",
]

# ---- CONTACT-SOLICITATION: private chat / social media lure ----
CONTACT_SOLICIT_SAMPLES: list[str] = [
    "加我为好友每天有惊喜分享",
    "扫码入群免费领取独家资料",
    "关注公众号每天获取精选内容",
    "加微信了解详情名额有限先到先得",
    "私信我领取专属福利大礼包",
    "添加客服微信即刻享受优惠",
    "进群交流认识更多志同道合的朋友",
    "添加导师微信一对一免费指导",
    "联系我获取完整版资料和教程",
    "加入我们的圈子发现更多精彩",
    "点击关注每天推送精品好文",
    "转发此条消息到三个群即可解锁",
    "联系QQ客服即刻办理相关手续",
]

# ---------------------------------------------------------------------------
# Combined risk samples (all categories)
# ---------------------------------------------------------------------------

RISK_SAMPLES_CN: list[str] = (
    PHISHING_SAMPLES
    + FRAUD_SAMPLES
    + SPAM_SAMPLES
    + GAMBLING_BAIT_SAMPLES
    + AGGRESSIVE_SAMPLES
    + CONTACT_SOLICIT_SAMPLES
)

# Category labels for each risk sample (for multi-class training)
RISK_CATEGORY_LABELS: list[str] = (
    ["phishing"] * len(PHISHING_SAMPLES)
    + ["fraud"] * len(FRAUD_SAMPLES)
    + ["spam"] * len(SPAM_SAMPLES)
    + ["gambling"] * len(GAMBLING_BAIT_SAMPLES)
    + ["aggressive"] * len(AGGRESSIVE_SAMPLES)
    + ["contact"] * len(CONTACT_SOLICIT_SAMPLES)
)

# ---------------------------------------------------------------------------
# Enhanced feature extraction (v2)
# ---------------------------------------------------------------------------

# Emoji Unicode ranges (common blocks)
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed characters
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols extended-A
    "\U00002600-\U000026FF"  # misc symbols
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"              # zero-width joiner
    "]+",
    re.UNICODE,
)

# Contact-info pattern: phone numbers, QQ, WeChat IDs, email
_CONTACT_PATTERN = re.compile(
    r"(?:"
    r"1[3-9]\d{9}"                     # Chinese mobile
    r"|\d{3,4}[-]?\d{7,8}"             # landline
    r"|[qQ]{2}\s*\d{5,}"               # QQ number
    r"|[vVxX]\s*\w{5,}"                 # WeChat ID pattern
    r"|微信\s*\w{2,}"                   # 微信 + id
    r"|加\s*(?:我|微信|QQ)"              # "加我/加微信/加QQ"
    r"|\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"  # email
    r")"
)

# Homoglyph / confusable Unicode blocks (common in filter evasion)
_HOMOGLYPH_PATTERN = re.compile(
    "[" 
    "\U00000400-\U000004FF"  # Cyrillic (look-alike Latin)
    "\U0000FF00-\U0000FFEF"  # fullwidth forms
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200B-\U0000200F"  # zero-width spaces
    "\U0000FEFF"             # BOM / zero-width no-break
    "\U00002061-\U00002064"  # invisible operators
    "]+",
    re.UNICODE,
)


def _compute_text_features(text: str) -> dict[str, float]:
    """Extract enhanced statistical features from text (v2)."""
    if not text:
        return {name: 0.0 for name in FEATURE_NAMES_V2}

    chars = list(text)
    n = len(chars)

    # ---- Character entropy ----
    char_counts = Counter(chars)
    entropy = -sum(
        (c / n) * math.log2(c / n) for c in char_counts.values() if c > 0
    )

    # ---- Density ratios ----
    punctuation_set = set(',.!?;:、，。！？；：""''（）【】《》…—～')
    punctuation = sum(1 for ch in chars if ch in punctuation_set)
    digits = sum(1 for ch in chars if ch.isdigit())
    special_chars = sum(1 for ch in chars if ch in '@#$%^&*+=|\\/<>[]{}~`')

    # ---- Repeated character ratio ----
    repeated = sum(
        1 for i in range(1, n) if chars[i] == chars[i - 1]
    ) / max(n, 1)

    # ---- Consecutive repeat max ----
    max_consecutive = 1
    current_run = 1
    for i in range(1, n):
        if chars[i] == chars[i - 1]:
            current_run += 1
            max_consecutive = max(max_consecutive, current_run)
        else:
            current_run = 1

    # ---- URL flag ----
    url_flag = 1 if any(
        m in text for m in ['http', 'www.', '.com', '.cn', '.net']
    ) else 0

    # ---- Contact info flag ----
    contact_flag = 1 if _CONTACT_PATTERN.search(text) else 0

    # ---- Emoji ratio ----
    emoji_matches = _EMOJI_PATTERN.findall(text)
    emoji_chars_total = sum(len(m) for m in emoji_matches)
    emoji_ratio = emoji_chars_total / max(n, 1)

    # ---- Exclamation ratio ----
    exclamation = sum(1 for ch in chars if ch in '!！')
    exclamation_ratio = exclamation / max(n, 1)

    # ---- Homoglyph flag (filter evasion) ----
    homoglyph_flag = 1 if _HOMOGLYPH_PATTERN.search(text) else 0

    # ---- Sentence analysis ----
    for_delimiters = ".!?！？。"
    tmp = text
    for d in for_delimiters:
        tmp = tmp.replace(d, "。")
    sentences = [s for s in tmp.split("。") if s.strip()]
    avg_sentence_len = (sum(len(s) for s in sentences) / max(len(sentences), 1))

    return {
        "entropy": round(entropy, 4),
        "punctuation_ratio": round(punctuation / max(n, 1), 4),
        "digit_ratio": round(digits / max(n, 1), 4),
        "special_char_ratio": round(special_chars / max(n, 1), 4),
        "repeated_char_ratio": round(repeated, 4),
        "url_flag": url_flag,
        "contact_info_flag": contact_flag,
        "emoji_ratio": round(emoji_ratio, 4),
        "exclamation_ratio": round(exclamation_ratio, 4),
        "consecutive_repeat_max": max_consecutive,
        "homoglyph_flag": homoglyph_flag,
        "avg_sentence_length": round(avg_sentence_len, 2),
        "length": n,
    }


# ---------------------------------------------------------------------------
# Dataset generation
# ---------------------------------------------------------------------------

def generate_sensitive_word_dataset() -> list[dict[str, Any]]:
    """
    Generate multi-category training dataset with enhanced statistical features.

    Returns list of {text, features, label, category}
    - label: 0 (benign) or 1 (risk)
    - category: risk category name (only for risk samples)
    """
    dataset: list[dict[str, Any]] = []

    # Benign
    for text in BENIGN_SAMPLES_CN:
        dataset.append({
            "text": text,
            "features": _compute_text_features(text),
            "label": 0,
            "category": "benign",
        })

    # Risk (multi-category)
    for text, cat in zip(RISK_SAMPLES_CN, RISK_CATEGORY_LABELS):
        dataset.append({
            "text": text,
            "features": _compute_text_features(text),
            "label": 1,
            "category": cat,
        })

    return dataset


def get_risk_samples_by_category() -> dict[str, list[str]]:
    """Return risk samples grouped by category name."""
    return {
        "phishing": PHISHING_SAMPLES,
        "fraud": FRAUD_SAMPLES,
        "spam": SPAM_SAMPLES,
        "gambling": GAMBLING_BAIT_SAMPLES,
        "aggressive": AGGRESSIVE_SAMPLES,
        "contact": CONTACT_SOLICIT_SAMPLES,
    }


def export_dataset_json(output_path: str | None = None) -> str:
    """Export the dataset as JSON. Returns JSON string if no path given."""
    dataset = generate_sensitive_word_dataset()
    json_str = json.dumps(dataset, ensure_ascii=False, indent=2)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
    return json_str
