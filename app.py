import streamlit as st
import random
import re
from collections import defaultdict
import pandas as pd

# ---------- 固定颜色代码与名称映射 ----------
COLOR_NAMES = {
    'r': '红色', 'y': '黄色', 'b': '蓝色', 'g': '绿色',
    'k': '粉色', 'p': '紫色', 'z': '棕色', 's': '银色'
}
COLORS_LIST = ['r', 'y', 'b', 'g', 'k', 'p', 'z', 's']

# ---------- 初始化 session state ----------
if 'color_counts' not in st.session_state:
    st.session_state.color_counts = {c: 0 for c in COLORS_LIST}
if 'non_std_weights' not in st.session_state:
    st.session_state.non_std_weights = {1: 0.25, 2: 0.25, 3: 0.25, 8: 0.25}

# ---------- 默认解锁进度 ----------
DEFAULT_UNLOCK = {
    'r': 0, 'y': 0, 'b': 0, 'g': 0,
    'k': 40, 'p': 50, 'z': 80, 's': 80
}

# ---------- 默认进度区间定义 ----------
DEFAULT_INTERVALS = [
    (0, 39),
    (40, 49),
    (50, 79),
    (80, 100)
]
DEFAULT_RATIOS = [0.39, 0.10, 0.30, 0.21]
DEFAULT_STD_PROBS = [1.0, 0.8, 0.6, 0.4]
DEFAULT_STD_WEIGHTS = {4: 0.5, 6: 0.3, 10: 0.2}

# ---------- 辅助函数 ----------
def weighted_choice(choices, weights):
    return random.choices(choices, weights=weights, k=1)[0]

def split_color_total(total, interval_idx, std_prob, std_weights, non_std_weights):
    remaining = total
    segments = []
    non_std_lengths = list(non_std_weights.keys())
    non_std_probs = list(non_std_weights.values())
    while remaining > 0:
        if random.random() < std_prob:
            length = weighted_choice(list(std_weights.keys()), list(std_weights.values()))
        else:
            length = weighted_choice(non_std_lengths, non_std_probs)
        length = min(length, remaining)
        segments.append(length)
        remaining -= length
    return segments

def interleave_segments(segments_by_color, target_count, available_colors, max_consecutive=10):
    collected = []
    total_collected = 0
    color_cycle = available_colors[:]
    random.shuffle(color_cycle)
    while total_collected < target_count and any(segments_by_color[c] for c in available_colors):
        for color in color_cycle:
            if total_collected >= target_count:
                break
            if not segments_by_color[color]:
                continue
            seg_len = segments_by_color[color].pop(0)
            if total_collected + seg_len <= target_count:
                collected.append((color, seg_len))
                total_collected += seg_len
            else:
                need = target_count - total_collected
                collected.append((color, need))
                segments_by_color[color].insert(0, seg_len - need)
                total_collected += need
                break
    random.shuffle(collected)
    fixed = fix_adjacent_same_color(collected, segments_by_color, available_colors)
    fixed = fix_consecutive_limit(fixed, max_consecutive)
    return fixed, segments_by_color

def fix_adjacent_same_color(segments, segments_by_color, available_colors):
    i = 0
    while i < len(segments) - 1:
        if segments[i][0] == segments[i+1][0]:
            swapped = False
            for j in range(i+2, len(segments)):
                if segments[j][0] != segments[i][0]:
                    segments[i+1], segments[j] = segments[j], segments[i+1]
                    swapped = True
                    break
            if not swapped:
                pass
        i += 1
    return segments

def fix_consecutive_limit(segments, max_consecutive=10):
    return segments

def generate_final_sequence(total_counts, unlock_progress, intervals, interval_ratios,
                            std_probs, std_weights, non_std_weights):
    total_people = sum(total_counts.values())
    interval_targets = [int(round(r * total_people)) for r in interval_ratios]
    diff = total_people - sum(interval_targets)
    interval_targets[-1] += diff

    remaining_by_color = total_counts.copy()
    color_interval_plan = {c: [0]*len(intervals) for c in COLORS_LIST}
    for idx, (low, high) in enumerate(intervals):
        available = [c for c in COLORS_LIST if unlock_progress[c] <= low]
        if not available:
            continue
        target_for_interval = interval_targets[idx]
        total_remain = sum(remaining_by_color[c] for c in available)
        if total_remain == 0:
            continue
        for c in available:
            if total_remain == 0:
                break
            alloc = int(round((remaining_by_color[c] / total_remain) * target_for_interval))
            alloc = min(alloc, remaining_by_color[c])
            color_interval_plan[c][idx] = alloc
            remaining_by_color[c] -= alloc
            target_for_interval -= alloc
            total_remain = sum(remaining_by_color[c] for c in available)
        if target_for_interval > 0:
            for c in available:
                if remaining_by_color[c] > 0:
                    take = min(target_for_interval, remaining_by_color[c])
                    color_interval_plan[c][idx] += take
                    remaining_by_color[c] -= take
                    target_for_interval -= take
                    if target_for_interval == 0:
                        break
    for c in COLORS_LIST:
        if remaining_by_color[c] > 0:
            color_interval_plan[c][-1] += remaining_by_color[c]
            remaining_by_color[c] = 0

    segments_by_color = {c: [] for c in COLORS_LIST}
    for c in COLORS_LIST:
        for idx, (low, high) in enumerate(intervals):
            alloc = color_interval_plan[c][idx]
            if alloc <= 0:
                continue
            if unlock_progress[c] > low:
                continue
            std_prob = std_probs[idx]
            segs = split_color_total(alloc, idx, std_prob, std_weights, non_std_weights)
            segments_by_color[c].extend(segs)

    all_sequence_segments = []
    for idx, (low, high) in enumerate(intervals):
        available_colors = [c for c in COLORS_LIST if unlock_progress[c] <= low]
        if not available_colors:
            continue
        target = interval_targets[idx]
        collected, segments_by_color = interleave_segments(
            segments_by_color, target, available_colors
        )
        all_sequence_segments.extend(collected)

    final_sequence = []
    for color, length in all_sequence_segments:
        final_sequence.extend([color] * length)
    return final_sequence

def sequence_to_string(seq):
    if not seq:
        return ""
    result = []
    current_color = seq[0]
    count = 1
    for color in seq[1:]:
        if color == current_color:
            count += 1
        else:
            result.append(f"{current_color}{count}")
            current_color = color
            count = 1
    result.append(f"{current_color}{count}")
    return "".join(result)

def parse_sequence_string(s):
    """解析形如 'r120y110g100b120' 的字符串，返回颜色数量字典"""
    s = s.strip().lower()
    pattern = r'([a-z])(\d+)'
    matches = re.findall(pattern, s)
    counts = {}
    for code, num_str in matches:
        if code in COLOR_NAMES:
            counts[code] = counts.get(code, 0) + int(num_str)
    return counts

# ---------- Streamlit 界面 ----------
st.set_page_config(page_title="挪车运人序列生成器", layout="wide")
st.title("🚗 挪车运人 · 序列生成器")
st.markdown("输入各颜色总人数（可手动输入或粘贴序列），调整参数，生成最终序列（格式如 `b2y4g4r2`）。")

# 侧边栏
st.sidebar.header("1️⃣ 各颜色总人数")

# 新增：粘贴序列文本框
st.sidebar.subheader("📋 粘贴序列快速填充")
seq_input = st.sidebar.text_input("粘贴序列 (例如 r120y110g100b120)", key="seq_input")
if st.sidebar.button("解析并应用"):
    if seq_input.strip():
        parsed = parse_sequence_string(seq_input)
        if parsed:
            for code, cnt in parsed.items():
                st.session_state.color_counts[code] = cnt
            st.sidebar.success("已应用序列，下方数字已更新。")
        else:
            st.sidebar.error("未能解析到有效颜色，格式应为颜色字母+数字，如 r120")

st.sidebar.markdown("---")
st.sidebar.subheader("或手动调整各颜色人数")
cols = st.sidebar.columns(2)
for i, code in enumerate(COLORS_LIST):
    with cols[i % 2]:
        # 使用 session_state 中的值作为默认，并在修改时更新
        cnt = st.number_input(
            f"{COLOR_NAMES[code]} ({code})",
            min_value=0,
            value=st.session_state.color_counts[code],
            step=1,
            key=f"input_{code}"
        )
        st.session_state.color_counts[code] = cnt

# 主区域：参数调整
st.header("2️⃣ 调整生成参数")

with st.expander("🎨 颜色解锁进度 (%)", expanded=True):
    unlock_progress = {}
    cols = st.columns(4)
    for i, code in enumerate(COLORS_LIST):
        with cols[i % 4]:
            unlock_progress[code] = st.slider(
                f"{COLOR_NAMES[code]} ({code})",
                min_value=0, max_value=100, value=DEFAULT_UNLOCK[code], step=5,
                key=f"unlock_{code}"
            )

with st.expander("📊 进度区间 & 人数占比", expanded=True):
    st.markdown("定义四个进度区间（百分比），以及每个区间的人数占比（总和应为1）")
    intervals = []
    interval_ratios = []
    cols = st.columns(4)
    for i in range(4):
        with cols[i]:
            st.markdown(f"**区间 {i+1}**")
            low = st.number_input(f"下限%", value=DEFAULT_INTERVALS[i][0], step=1, key=f"low_{i}")
            high = st.number_input(f"上限%", value=DEFAULT_INTERVALS[i][1], step=1, key=f"high_{i}")
            intervals.append((low, high))
            ratio = st.number_input(f"人数占比", value=DEFAULT_RATIOS[i], step=0.01, format="%.2f", key=f"ratio_{i}")
            interval_ratios.append(ratio)
    total_ratio = sum(interval_ratios)
    if abs(total_ratio - 1.0) > 0.001:
        st.warning(f"⚠️ 人数占比总和为 {total_ratio:.2f}，将自动归一化。")
        interval_ratios = [r / total_ratio for r in interval_ratios]

with st.expander("🎲 长度类型概率（标准 vs 非标准）", expanded=True):
    std_probs = []
    cols = st.columns(4)
    for i in range(4):
        with cols[i]:
            prob = st.slider(
                f"区间{i+1} 标准长度概率",
                min_value=0.0, max_value=1.0, value=DEFAULT_STD_PROBS[i], step=0.05,
                key=f"std_prob_{i}"
            )
            std_probs.append(prob)
            st.caption(f"非标准概率 = {1-prob:.2f}")

with st.expander("⚖️ 标准长度内部权重", expanded=False):
    st.markdown("标准长度选项：4、6、10")
    std_weights = {}
    cols = st.columns(3)
    with cols[0]:
        w4 = st.slider("长度4权重", 0.0, 1.0, DEFAULT_STD_WEIGHTS[4], 0.05, key="w4")
    with cols[1]:
        w6 = st.slider("长度6权重", 0.0, 1.0, DEFAULT_STD_WEIGHTS[6], 0.05, key="w6")
    with cols[2]:
        w10 = st.slider("长度10权重", 0.0, 1.0, DEFAULT_STD_WEIGHTS[10], 0.05, key="w10")
    total_w = w4 + w6 + w10
    if total_w > 0:
        std_weights = {4: w4/total_w, 6: w6/total_w, 10: w10/total_w}
    else:
        std_weights = {4: 1/3, 6: 1/3, 10: 1/3}
    st.write("归一化后权重：", {k: f"{v:.2f}" for k, v in std_weights.items()})

with st.expander("🔢 非标准长度选项（可自定义添加/删除，调节权重）", expanded=False):
    st.markdown("### 当前非标准长度列表")
    to_delete = None
    updated_weights = {}
    for length, weight in list(st.session_state.non_std_weights.items()):
        cols = st.columns([1, 2, 1])
        with cols[0]:
            st.markdown(f"**{length}**")
        with cols[1]:
            new_weight = st.slider(
                f"权重", 0.0, 1.0, weight, 0.05,
                key=f"nonstd_w_{length}"
            )
            updated_weights[length] = new_weight
        with cols[2]:
            if st.button("❌ 删除", key=f"del_{length}"):
                to_delete = length
    if to_delete is not None:
        del st.session_state.non_std_weights[to_delete]
        st.rerun()
    total_nw = sum(updated_weights.values())
    if total_nw > 0:
        st.session_state.non_std_weights = {k: v/total_nw for k, v in updated_weights.items()}
    else:
        st.error("权重总和不能为0，请至少保留一个非标准长度且权重大于0。")
    st.write("归一化后权重：", {k: f"{v:.2f}" for k, v in st.session_state.non_std_weights.items()})
    
    st.markdown("---")
    st.markdown("### 添加新的非标准长度")
    new_len = st.number_input("新长度值（正整数，≤10）", min_value=1, max_value=10, value=5, step=1)
    new_weight = st.slider("初始权重", 0.0, 1.0, 0.1, 0.05, key="new_weight")
    if st.button("➕ 添加"):
        if new_len in st.session_state.non_std_weights:
            st.warning(f"长度 {new_len} 已存在！")
        else:
            st.session_state.non_std_weights[new_len] = new_weight
            total = sum(st.session_state.non_std_weights.values())
            st.session_state.non_std_weights = {k: v/total for k, v in st.session_state.non_std_weights.items()}
            st.rerun()
    st.caption("提示：添加后权重会自动归一化，你可以再调节各权重值。")

# 生成按钮
if st.button("🚀 生成序列", type="primary", use_container_width=True):
    total_counts = st.session_state.color_counts.copy()
    if sum(total_counts.values()) == 0:
        st.error("请至少为一个颜色输入大于0的人数。")
    else:
        with st.spinner("正在生成序列..."):
            final_seq = generate_final_sequence(
                total_counts,
                unlock_progress,
                intervals,
                interval_ratios,
                std_probs,
                std_weights,
                st.session_state.non_std_weights
            )
            compressed = sequence_to_string(final_seq)
        
        st.success("生成完成！")
        st.header("📋 生成结果")
        st.code(compressed, language="text")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("总人数", len(final_seq))
        with col2:
            unique_colors = len(set(final_seq))
            st.metric("出现颜色种数", unique_colors)
        
        st.subheader("颜色人数统计")
        count_dict = {c: final_seq.count(c) for c in COLORS_LIST if final_seq.count(c) > 0}
        df = pd.DataFrame({
            "颜色代码": list(count_dict.keys()),
            "颜色名称": [COLOR_NAMES[c] for c in count_dict.keys()],
            "实际生成人数": list(count_dict.values()),
            "输入目标人数": [total_counts[c] for c in count_dict.keys()]
        })
        st.dataframe(df, use_container_width=True)
        
        st.subheader("进度解锁检查")
        check_pass = True
        for code in COLORS_LIST:
            if total_counts[code] > 0:
                first_idx = final_seq.index(code) if code in final_seq else -1
                if first_idx >= 0:
                    progress_at_first = first_idx / len(final_seq) * 100
                    expected_unlock = unlock_progress[code]
                    if progress_at_first < expected_unlock - 0.1:
                        st.warning(f"⚠️ {COLOR_NAMES[code]}({code}) 首次出现在进度 {progress_at_first:.1f}%，但解锁要求是 {expected_unlock}%")
                        check_pass = False
        if check_pass:
            st.success("✅ 所有颜色均满足解锁进度约束。")
        
        max_run = 0
        current_run = 1
        for i in range(1, len(final_seq)):
            if final_seq[i] == final_seq[i-1]:
                current_run += 1
            else:
                max_run = max(max_run, current_run)
                current_run = 1
        max_run = max(max_run, current_run)
        if max_run <= 10:
            st.success(f"✅ 最大连续同色人数为 {max_run}，未超过10。")
        else:
            st.error(f"❌ 最大连续同色人数为 {max_run}，超过限制10！")
        
        st.download_button(
            label="📥 下载序列文本",
            data=compressed,
            file_name="generated_sequence.txt",
            mime="text/plain"
        )

st.markdown("---")
st.caption("参数调整说明：解锁进度指该颜色最早可出现的进度百分比；区间人数占比控制各阶段总人数分配；长度概率影响段的切分。")
