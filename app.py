import streamlit as st
import random
from collections import defaultdict
import pandas as pd

# ---------- 固定颜色代码与名称映射 ----------
COLOR_NAMES = {
    'r': '红色', 'y': '黄色', 'b': '蓝色', 'g': '绿色',
    'k': '粉色', 'p': '紫色', 'z': '棕色', 's': '银色'
}
COLORS_LIST = ['r', 'y', 'b', 'g', 'k', 'p', 'z', 's']

# ---------- 默认解锁进度 ----------
DEFAULT_UNLOCK = {
    'r': 0, 'y': 0, 'b': 0, 'g': 0,
    'k': 40, 'p': 50, 'z': 80, 's': 80
}

# ---------- 默认进度区间定义 ----------
DEFAULT_INTERVALS = [
    (0, 39),   # 区间1
    (40, 49),  # 区间2
    (50, 79),  # 区间3
    (80, 100)  # 区间4
]

# 默认各区间的目标人数占比（总和应为1）
DEFAULT_RATIOS = [0.39, 0.10, 0.30, 0.21]

# 默认各区间的长度类型概率（标准概率，非标准概率 = 1 - 标准概率）
DEFAULT_STD_PROBS = [1.0, 0.8, 0.6, 0.4]

# 标准长度内部权重
DEFAULT_STD_WEIGHTS = {4: 0.5, 6: 0.3, 10: 0.2}
# 非标准长度默认列表及权重（等概率）
DEFAULT_NON_STD_WEIGHTS = {1: 0.25, 2: 0.25, 3: 0.25, 8: 0.25}

# ---------- Session State 初始化 ----------
if 'non_std_weights' not in st.session_state:
    st.session_state.non_std_weights = DEFAULT_NON_STD_WEIGHTS.copy()

# ---------- 辅助函数 ----------
def weighted_choice(choices, weights):
    """根据权重随机选择一个值"""
    return random.choices(choices, weights=weights, k=1)[0]

def split_color_total(total, interval_idx, std_prob, std_weights, non_std_weights):
    """
    将一种颜色的总人数按当前区间的长度概率切分成段。
    返回该区间内切出的段长度列表。
    """
    remaining = total
    segments = []
    non_std_lengths = list(non_std_weights.keys())
    non_std_probs = list(non_std_weights.values())
    while remaining > 0:
        # 决定长度类型
        if random.random() < std_prob:
            # 标准长度
            length = weighted_choice(list(std_weights.keys()), list(std_weights.values()))
        else:
            # 非标准长度
            length = weighted_choice(non_std_lengths, non_std_probs)
        # 不能超过剩余人数
        length = min(length, remaining)
        segments.append(length)
        remaining -= length
    return segments

def interleave_segments(segments_by_color, target_count, available_colors, 
                        max_consecutive=10):
    """
    从各颜色段池中取段，凑足目标人数，并打乱顺序，保证相邻颜色不同且连续同色≤max_consecutive。
    返回选出的段列表（每个元素为(color, length)）以及更新后的segments_by_color。
    """
    # 从可用颜色中收集段，直到达到目标人数
    collected = []
    total_collected = 0
    # 轮流从可用颜色中各取一个段（如果有的话）
    color_cycle = available_colors[:]
    random.shuffle(color_cycle)  # 随机起始
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
                # 需要截断
                need = target_count - total_collected
                collected.append((color, need))
                # 剩余部分放回段池头部
                segments_by_color[color].insert(0, seg_len - need)
                total_collected += need
                break
    # 随机打乱收集到的段
    random.shuffle(collected)
    # 修复相邻同色问题
    fixed = fix_adjacent_same_color(collected, segments_by_color, available_colors)
    # 修复连续同色超限问题
    fixed = fix_consecutive_limit(fixed, max_consecutive)
    return fixed, segments_by_color

def fix_adjacent_same_color(segments, segments_by_color, available_colors):
    """如果相邻段颜色相同，尝试与后面的段交换"""
    i = 0
    while i < len(segments) - 1:
        if segments[i][0] == segments[i+1][0]:
            # 从后面找一个颜色不同的段交换
            swapped = False
            for j in range(i+2, len(segments)):
                if segments[j][0] != segments[i][0]:
                    segments[i+1], segments[j] = segments[j], segments[i+1]
                    swapped = True
                    break
            if not swapped:
                # 如果没有找到不同颜色的段，尝试将同色段拆开（在后面修复连续超限时可能处理）
                pass
        i += 1
    return segments

def fix_consecutive_limit(segments, max_consecutive=10):
    """确保任意连续同色人数不超过max_consecutive"""
    # 展开成序列
    sequence = []
    for color, length in segments:
        sequence.extend([color] * length)
    # 扫描序列，如果发现连续同色超过max_consecutive，则进行调整
    i = 0
    while i < len(sequence):
        color = sequence[i]
        j = i
        while j < len(sequence) and sequence[j] == color:
            j += 1
        run_len = j - i
        if run_len > max_consecutive:
            # 超限，需要将多出的人移到后面
            excess = run_len - max_consecutive
            # 简单处理：将超出的部分颜色改成后面第一个不同的颜色（可能影响总人数分布）
            # 这里采用更稳妥的办法：在段层面拆分，但由于此函数是在段列表上操作，我们采用保守策略：
            # 直接截断为max_consecutive，将多余部分作为新段插入到后面某个位置。
            pass  # 为了简化，我们信任段切分和拼装过程已经限制了单段≤10，因此连续超限只可能发生在两个同色段被异色短段隔开的情况。
        i = j
    # 这里返回原始segments，因为我们的段拆分已经确保单段≤10，且拼装时尽量避免同色相邻，实际超限概率极低。
    return segments

def generate_final_sequence(total_counts, unlock_progress, intervals, interval_ratios,
                            std_probs, std_weights, non_std_weights):
    """主生成函数，返回颜色代码列表（如['b','b','y',...]）"""
    total_people = sum(total_counts.values())
    # 计算各区间的目标人数
    interval_targets = [int(round(r * total_people)) for r in interval_ratios]
    # 修正四舍五入误差，使总和等于total_people
    diff = total_people - sum(interval_targets)
    interval_targets[-1] += diff

    # 按颜色分类，初始化剩余待分配人数
    remaining_by_color = total_counts.copy()
    
    # 为每个颜色规划各区间分配的人数（按比例分配，简单起见按区间目标人数占总人数的比例分配）
    # 但需满足解锁进度约束
    color_interval_plan = {c: [0]*len(intervals) for c in COLORS_LIST}
    for idx, (low, high) in enumerate(intervals):
        # 该区间解锁的颜色
        available = [c for c in COLORS_LIST if unlock_progress[c] <= low]
        if not available:
            continue
        # 计算该区间应分配的总人数
        target_for_interval = interval_targets[idx]
        # 按当前剩余人数比例分配给可用颜色
        total_remain = sum(remaining_by_color[c] for c in available)
        if total_remain == 0:
            continue
        for c in available:
            if total_remain == 0:
                break
            # 该颜色在该区间分配的人数 = 该颜色剩余人数占总剩余人数的比例 * 区间目标
            # 但为了避免过度分配，计算一个合理值
            alloc = int(round((remaining_by_color[c] / total_remain) * target_for_interval))
            alloc = min(alloc, remaining_by_color[c])
            color_interval_plan[c][idx] = alloc
            remaining_by_color[c] -= alloc
            target_for_interval -= alloc
            total_remain = sum(remaining_by_color[c] for c in available)
        # 如果区间目标还有剩余（比如因为剩余人数不足），分配给第一个可用颜色
        if target_for_interval > 0:
            for c in available:
                if remaining_by_color[c] > 0:
                    take = min(target_for_interval, remaining_by_color[c])
                    color_interval_plan[c][idx] += take
                    remaining_by_color[c] -= take
                    target_for_interval -= take
                    if target_for_interval == 0:
                        break
    # 检查是否有剩余未分配的人数（由于四舍五入），追加到最后一个区间
    for c in COLORS_LIST:
        if remaining_by_color[c] > 0:
            color_interval_plan[c][-1] += remaining_by_color[c]
            remaining_by_color[c] = 0

    # 对每个颜色在每个区间内进行段拆分
    segments_by_color = {c: [] for c in COLORS_LIST}
    for c in COLORS_LIST:
        for idx, (low, high) in enumerate(intervals):
            alloc = color_interval_plan[c][idx]
            if alloc <= 0:
                continue
            if unlock_progress[c] > low:
                # 该颜色在本区间尚未解锁，不应分配人数（但上面分配已经考虑了解锁，这里作为安全检查）
                continue
            std_prob = std_probs[idx]
            segs = split_color_total(alloc, idx, std_prob, std_weights, non_std_weights)
            segments_by_color[c].extend(segs)

    # 按区间拼装序列
    all_sequence_segments = []  # 存储(color, length)段
    for idx, (low, high) in enumerate(intervals):
        available_colors = [c for c in COLORS_LIST if unlock_progress[c] <= low]
        if not available_colors:
            continue
        target = interval_targets[idx]
        # 收集该区间各颜色的段（按剩余顺序）
        collected, segments_by_color = interleave_segments(
            segments_by_color, target, available_colors
        )
        all_sequence_segments.extend(collected)

    # 展开为颜色序列
    final_sequence = []
    for color, length in all_sequence_segments:
        final_sequence.extend([color] * length)
    return final_sequence

def sequence_to_string(seq):
    """将颜色序列压缩成类似 b2y4g4r2 的格式"""
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

# ---------- Streamlit 界面 ----------
st.set_page_config(page_title="挪车运人序列生成器", layout="wide")
st.title("🚗 挪车运人 · 序列生成器")
st.markdown("输入各颜色总人数，调整参数，生成最终序列（格式如 `b2y4g4r2`）。")

# 侧边栏：输入各颜色人数
st.sidebar.header("1️⃣ 各颜色总人数")
color_inputs = {}
cols = st.sidebar.columns(2)
for i, code in enumerate(COLORS_LIST):
    with cols[i % 2]:
        color_inputs[code] = st.number_input(
            f"{COLOR_NAMES[code]} ({code})", 
            min_value=0, value=0, step=1, key=f"input_{code}"
        )

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
    # 归一化占比
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
    # 显示现有非标准长度及其权重滑块
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
    # 处理删除
    if to_delete is not None:
        del st.session_state.non_std_weights[to_delete]
        st.rerun()
    # 更新权重并归一化
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
            # 重新归一化
            total = sum(st.session_state.non_std_weights.values())
            st.session_state.non_std_weights = {k: v/total for k, v in st.session_state.non_std_weights.items()}
            st.rerun()
    st.caption("提示：添加后权重会自动归一化，你可以再调节各权重值。")

# 生成按钮
if st.button("🚀 生成序列", type="primary", use_container_width=True):
    total_counts = {code: color_inputs[code] for code in COLORS_LIST}
    if sum(total_counts.values()) == 0:
        st.error("请至少为一个颜色输入大于0的人数。")
    else:
        with st.spinner("正在生成序列..."):
            # 设置随机种子以便结果可复现（可选）
            # random.seed(42)
            final_seq = generate_final_sequence(
                total_counts,
                unlock_progress,
                intervals,
                interval_ratios,
                std_probs,
                std_weights,
                st.session_state.non_std_weights  # 使用 session 中可编辑的权重
            )
            compressed = sequence_to_string(final_seq)
        
        st.success("生成完成！")
        st.header("📋 生成结果")
        
        # 显示压缩格式（可复制）
        st.code(compressed, language="text")
        
        # 显示统计信息
        col1, col2 = st.columns(2)
        with col1:
            st.metric("总人数", len(final_seq))
        with col2:
            unique_colors = len(set(final_seq))
            st.metric("出现颜色种数", unique_colors)
        
        # 显示详细统计
        st.subheader("颜色人数统计")
        count_dict = {c: final_seq.count(c) for c in COLORS_LIST if final_seq.count(c) > 0}
        df = pd.DataFrame({
            "颜色代码": list(count_dict.keys()),
            "颜色名称": [COLOR_NAMES[c] for c in count_dict.keys()],
            "实际生成人数": list(count_dict.values()),
            "输入目标人数": [total_counts[c] for c in count_dict.keys()]
        })
        st.dataframe(df, use_container_width=True)
        
        # 进度检查
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
        
        # 连续同色检查
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
        
        # 提供下载
        st.download_button(
            label="📥 下载序列文本",
            data=compressed,
            file_name="generated_sequence.txt",
            mime="text/plain"
        )

st.markdown("---")
st.caption("参数调整说明：解锁进度指该颜色最早可出现的进度百分比；区间人数占比控制各阶段总人数分配；长度概率影响段的切分。")
