import streamlit as st
import random
import re
import pandas as pd

# ---------- 固定颜色代码与名称映射 ----------
COLOR_NAMES = {
    'r': '红色', 'y': '黄色', 'b': '蓝色', 'g': '绿色',
    'k': '粉色', 'p': '紫色', 'z': '棕色', 's': '银色'
}
COLORS_LIST = ['r', 'y', 'b', 'g', 'k', 'p', 'z', 's']

# ---------- Session State 初始化 ----------
if 'color_counts' not in st.session_state:
    st.session_state.color_counts = {c: 0 for c in COLORS_LIST}
if 'non_std_weights' not in st.session_state:
    st.session_state.non_std_weights = {1: 0.25, 2: 0.25, 3: 0.25, 8: 0.25}
if 'seq_parsed' not in st.session_state:
    st.session_state.seq_parsed = False

# ---------- 默认参数 ----------
DEFAULT_UNLOCK = {
    'r': 0, 'y': 0, 'b': 0, 'g': 0,
    'k': 40, 'p': 50, 'z': 80, 's': 80
}
DEFAULT_INTERVALS = [
    (0, 39), (40, 49), (50, 79), (80, 100)
]
DEFAULT_RATIOS = [0.39, 0.10, 0.30, 0.21]
DEFAULT_STD_PROBS = [1.0, 0.8, 0.6, 0.4]
DEFAULT_STD_WEIGHTS = {4: 0.5, 6: 0.3, 10: 0.2}

# ---------- 辅助函数 ----------
def weighted_choice(choices, weights):
    return random.choices(choices, weights=weights, k=1)[0]

def split_color_total(total, std_prob, std_weights, non_std_weights):
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

def interleave_segments(segments_by_color, target_count, available_colors):
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
    return collected, segments_by_color

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
        target = interval_targets[idx]
        total_remain = sum(remaining_by_color[c] for c in available)
        if total_remain == 0:
            continue
        for c in available:
            if total_remain == 0:
                break
            alloc = int(round((remaining_by_color[c] / total_remain) * target))
            alloc = min(alloc, remaining_by_color[c])
            color_interval_plan[c][idx] = alloc
            remaining_by_color[c] -= alloc
            target -= alloc
            total_remain = sum(remaining_by_color[c] for c in available)
        if target > 0:
            for c in available:
                if remaining_by_color[c] > 0:
                    take = min(target, remaining_by_color[c])
                    color_interval_plan[c][idx] += take
                    remaining_by_color[c] -= take
                    target -= take
                    if target == 0:
                        break
    for c in COLORS_LIST:
        if remaining_by_color[c] > 0:
            color_interval_plan[c][-1] += remaining_by_color[c]

    segments_by_color = {c: [] for c in COLORS_LIST}
    for c in COLORS_LIST:
        for idx, (low, high) in enumerate(intervals):
            alloc = color_interval_plan[c][idx]
            if alloc <= 0 or unlock_progress[c] > low:
                continue
            std_prob = std_probs[idx]
            segs = split_color_total(alloc, std_prob, std_weights, non_std_weights)
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
st.markdown("在下方粘贴颜色序列（如 `r120y110g100b120`），调整参数后生成最终序列。")

# ---------- 左侧：序列输入 + 参数调整 ----------
col_input, col_params = st.columns([1, 2])

with col_input:
    st.header("📥 输入序列")
    seq_input = st.text_area(
        "粘贴总序列",
        placeholder="例如：r120y110g100b120",
        height=100,
        label_visibility="collapsed"
    )
    if st.button("🔍 解析序列", use_container_width=True):
        if seq_input.strip():
            parsed = parse_sequence_string(seq_input)
            if parsed:
                st.session_state.color_counts = parsed
                st.session_state.seq_parsed = True
                st.success("解析成功！")
            else:
                st.session_state.seq_parsed = False
                st.error("未能识别有效颜色组合。格式应为：颜色字母+数字，如 r120")
        else:
            st.warning("请输入序列。")
    
    if st.session_state.seq_parsed:
        st.markdown("### ✅ 已解析的颜色数量")
        for code, cnt in st.session_state.color_counts.items():
            if cnt > 0:
                st.write(f"**{COLOR_NAMES[code]} ({code})**：{cnt} 人")

with col_params:
    st.header("⚙️ 生成参数")
    
    with st.expander("🎨 颜色解锁进度 (%)", expanded=True):
        unlock_progress = {}
        cols = st.columns(4)
        for i, code in enumerate(COLORS_LIST):
            with cols[i % 4]:
                unlock_progress[code] = st.slider(
                    f"{COLOR_NAMES[code]} ({code})",
                    0, 100, DEFAULT_UNLOCK[code], 5,
                    key=f"unlock_{code}"
                )

    with st.expander("📊 进度区间 & 人数占比", expanded=True):
        intervals = []
        interval_ratios = []
        cols = st.columns(4)
        for i in range(4):
            with cols[i]:
                st.markdown(f"**区间 {i+1}**")
                low = st.number_input("下限%", value=DEFAULT_INTERVALS[i][0], step=1, key=f"low_{i}")
                high = st.number_input("上限%", value=DEFAULT_INTERVALS[i][1], step=1, key=f"high_{i}")
                intervals.append((low, high))
                ratio = st.number_input("人数占比", value=DEFAULT_RATIOS[i], step=0.01, format="%.2f", key=f"ratio_{i}")
                interval_ratios.append(ratio)
        total_ratio = sum(interval_ratios)
        if abs(total_ratio - 1.0) > 0.001:
            st.warning(f"占比总和为 {total_ratio:.2f}，将自动归一化。")
            interval_ratios = [r / total_ratio for r in interval_ratios]

    with st.expander("🎲 长度类型概率", expanded=True):
        std_probs = []
        cols = st.columns(4)
        for i in range(4):
            with cols[i]:
                prob = st.slider(
                    f"区间{i+1} 标准概率",
                    0.0, 1.0, DEFAULT_STD_PROBS[i], 0.05,
                    key=f"std_prob_{i}"
                )
                std_probs.append(prob)
                st.caption(f"非标准 = {1-prob:.2f}")

    with st.expander("⚖️ 标准长度权重 (4/6/10)", expanded=False):
        std_weights = {}
        cols = st.columns(3)
        with cols[0]:
            w4 = st.slider("4", 0.0, 1.0, DEFAULT_STD_WEIGHTS[4], 0.05, key="w4")
        with cols[1]:
            w6 = st.slider("6", 0.0, 1.0, DEFAULT_STD_WEIGHTS[6], 0.05, key="w6")
        with cols[2]:
            w10 = st.slider("10", 0.0, 1.0, DEFAULT_STD_WEIGHTS[10], 0.05, key="w10")
        total_w = w4 + w6 + w10
        if total_w > 0:
            std_weights = {4: w4/total_w, 6: w6/total_w, 10: w10/total_w}
        else:
            std_weights = {4: 1/3, 6: 1/3, 10: 1/3}
        st.write("归一化后：", {k: f"{v:.2f}" for k, v in std_weights.items()})

    with st.expander("🔢 非标准长度（可自定义添加/删除，调节权重）", expanded=False):
        to_delete = None
        updated_weights = {}
        for length, weight in list(st.session_state.non_std_weights.items()):
            cols = st.columns([1, 2, 1])
            with cols[0]:
                st.markdown(f"**{length}**")
            with cols[1]:
                new_weight = st.slider(
                    f"权重", 0.0, 1.0, weight, 0.05,
                    key=f"ns_w_{length}"
                )
                updated_weights[length] = new_weight
            with cols[2]:
                if st.button("❌", key=f"del_{length}"):
                    to_delete = length
        if to_delete is not None:
            del st.session_state.non_std_weights[to_delete]
            st.experimental_rerun()
        total_ns = sum(updated_weights.values())
        if total_ns > 0:
            st.session_state.non_std_weights = {k: v/total_ns for k, v in updated_weights.items()}
        else:
            st.error("至少保留一个非标准长度且权重大于0。")
        st.write("归一化后：", {k: f"{v:.2f}" for k, v in st.session_state.non_std_weights.items()})
        
        st.markdown("---")
        new_len = st.number_input("新长度值（≤10）", 1, 10, 5, key="new_len")
        new_w = st.slider("初始权重", 0.0, 1.0, 0.1, 0.05, key="new_w")
        if st.button("➕ 添加非标准长度"):
            if new_len in st.session_state.non_std_weights:
                st.warning("已存在！")
            else:
                st.session_state.non_std_weights[new_len] = new_w
                total = sum(st.session_state.non_std_weights.values())
                st.session_state.non_std_weights = {k: v/total for k, v in st.session_state.non_std_weights.items()}
                st.experimental_rerun()

# ---------- 生成按钮 ----------
st.divider()
if st.button("🚀 生成序列", type="primary", use_container_width=True):
    if not st.session_state.seq_parsed or sum(st.session_state.color_counts.values()) == 0:
        st.error("请先输入有效的颜色序列并点击“解析序列”。")
    else:
        total_counts = st.session_state.color_counts.copy()
        with st.spinner("生成中..."):
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
        st.header("📋 最终序列")
        st.code(compressed, language="text")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("总人数", len(final_seq))
        with col2:
            st.metric("颜色种数", len(set(final_seq)))
        
        st.subheader("颜色人数核对")
        count_dict = {c: final_seq.count(c) for c in COLORS_LIST if final_seq.count(c) > 0}
        df = pd.DataFrame({
            "颜色": [COLOR_NAMES[c] for c in count_dict],
            "代码": list(count_dict.keys()),
            "实际": list(count_dict.values()),
            "目标": [total_counts[c] for c in count_dict]
        })
        st.dataframe(df, use_container_width=True)
        
        # 解锁进度检查
        all_ok = True
        for code in COLORS_LIST:
            if total_counts[code] > 0:
                first = final_seq.index(code) if code in final_seq else -1
                if first >= 0:
                    progress = first / len(final_seq) * 100
                    if progress < unlock_progress[code] - 0.1:
                        st.warning(f"{COLOR_NAMES[code]} 首次出现于 {progress:.1f}%，解锁要求 {unlock_progress[code]}%")
                        all_ok = False
        if all_ok:
            st.success("✅ 所有颜色解锁进度符合设置。")
        
        max_run = 0
        cur = 1
        for i in range(1, len(final_seq)):
            if final_seq[i] == final_seq[i-1]:
                cur += 1
            else:
                max_run = max(max_run, cur)
                cur = 1
        max_run = max(max_run, cur)
        if max_run <= 10:
            st.success(f"✅ 最大连续同色：{max_run}（≤10）")
        else:
            st.error(f"❌ 最大连续同色：{max_run}（超过10）")
        
        st.download_button("📥 下载序列", compressed, "sequence.txt")

st.markdown("---")
st.caption("使用说明：粘贴总序列 → 点击“解析” → 调整参数 → 生成最终序列")
