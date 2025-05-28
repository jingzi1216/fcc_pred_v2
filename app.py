import streamlit as st
import pandas as pd
import numpy as np
import joblib

# 加载训练好的模型
target_names = [
    '汽油收率wt%', '汽油芳烃含量vol %', '汽油烯烃含量vol%', '汽油RON', '汽油干点℃',
    '液化气收率wt%', '液化气丙烯含量wt%', '液化气C5体积比 vol%',
    '烟气中CO2排放量t/h', '柴油ASTM D8695% ℃'
]
rf_model = joblib.load('rf_model.pkl')
gb_model = joblib.load('gb_model.pkl')

# 特征变量名称，请与训练时保持一致
FEATURE_NAMES = [
    '原料质量流量t/h', '原料芳烃含量wt%', '原料镍含量ppmwt', '原料钒含量ppmwt',
    '原料残炭含量 wt%', '原料预热温度℃', '反应压力bar_g', '反应温度℃',
    '催化剂微反活性t%', '新鲜催化剂活性 wt%', '反应器密相催化剂藏量kg', '再生器床温℃',
    '原料比重g/cm3', '原料氮含量wt%', '原料硫含量wt%',
    '催化剂补充速率tonne/d', '提升蒸汽注入量tonne/hr', '雾化蒸汽注入量tonne/hr', '汽提蒸汽注入量tonne/hr'
]

# 目标变量范围，用于告警
TARGET_RANGES = {
    '汽油收率wt%': (35, 55), '汽油芳烃含量vol %': (0, 33), '汽油烯烃含量vol%': (0, 25),
    '汽油RON': (92, None), '汽油干点℃': (0, 215),
    '液化气收率wt%': (15, 35), '液化气丙烯含量wt%': (30, None), '液化气C5体积比 vol%': (0, 2.3),
    '柴油ASTM D8695% ℃': (0, 360)
}

st.set_page_config(
    page_title="模型预测与最优值计算",
    layout='wide'
)

st.title("催化裂化装置预测与最优值计算")
st.markdown("---")

# 上传Excel文件
st.sidebar.header("上传包含自变量的Excel文件")
uploaded_file = st.sidebar.file_uploader(
    "请选择一个Excel文件 (.xlsx, .xls)", type=['xlsx', 'xls']
)

if uploaded_file:
    # 读取用户上传数据
    input_df = pd.read_excel(uploaded_file)
    # 检查列是否齐全
    missing = [c for c in FEATURE_NAMES if c not in input_df.columns]
    if missing:
        st.sidebar.error(f"缺少以下特征列：{missing}")
        st.stop()
    # 只保留模型需要的特征列，并按顺序排列
    input_df = input_df[FEATURE_NAMES]

    # 显示上传的数据预览
    st.subheader("输入数据预览")
    st.dataframe(input_df)

    # 运行预测
    if st.sidebar.button("运行预测"):
        # 模型预测
        rf_preds = rf_model.predict(input_df)
        gb_preds = gb_model.predict(input_df)
        # 合并结果，并调整
        y_preds = rf_preds.copy()
        # 用gb_model的两项替换
        idx_co2 = target_names.index('烟气中CO2排放量t/h')
        idx_prop = target_names.index('液化气丙烯含量wt%')
        y_preds[:, idx_co2] = gb_preds[:, idx_co2]
        y_preds[:, idx_prop] = gb_preds[:, idx_prop]
        # 汽油收率调整
        idx_gas = target_names.index('汽油收率wt%')
        y_preds[:, idx_gas] *= 0.965

        # 构建结果DataFrame
        result_df = pd.DataFrame(y_preds, columns=target_names)

        # 检查超出范围
        warn_list = []
        for col, (rmin, rmax) in TARGET_RANGES.items():
            vals = result_df[col]
            if rmin is not None:
                warn_low = vals < rmin
                for i in result_df.index[warn_low]:
                    warn_list.append(f"行{i}: {col} = {vals[i]:.3f} < 最小值 {rmin}")
            if rmax is not None:
                warn_high = vals > rmax
                for i in result_df.index[warn_high]:
                    warn_list.append(f"行{i}: {col} = {vals[i]:.3f} > 最大值 {rmax}")


        # 计算价值与最优值（对每行）
        mass = input_df['原料质量流量t/h']
        gasoline_yield = result_df['汽油收率wt%'] / 100
        lpg_yield = result_df['液化气收率wt%'] / 100
        prop_ratio = result_df['液化气丙烯含量wt%'] / 100

        gasoline_prod = gasoline_yield * mass
        lpg_prod = lpg_yield * mass
        prop_prod = lpg_prod * prop_ratio

        value = gasoline_prod * 1.2 + (lpg_prod - prop_prod) * 1.0 + prop_prod * 1.5
        co2 = result_df['烟气中CO2排放量t/h']
        best_val = value / (co2 + 1e-8)

        # 合并指标到结果
        result_df['计算价值'] = value
        result_df['CO2排放t/h'] = co2
        result_df['最优值'] = best_val

        # 展示结果
        st.subheader("预测结果与最优值")
        st.dataframe(result_df)
        if warn_list:
            st.warning("检测到预测值超出预设范围：")
            for msg in warn_list:
                st.write(msg)
        else:
            st.success("所有预测值均在范围内。")
        st.info("提示：如需重新预测，可修改Excel后重新上传并点击运行预测。")

else:
    st.info("请在左侧上传包含自变量的Excel文件，然后点击‘运行预测’。")
