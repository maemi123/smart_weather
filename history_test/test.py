import pandas as pd

# 读取数据，注意分号和编码
df = pd.read_csv('58457.01.01.2008.29.12.2025.1.0.0.cn.utf8.00000000.csv', sep=';', encoding='utf-8', low_memory=False)
print(f"数据形状: {df.shape}")
print(f"列名: {df.columns.tolist()}")
print(df.head())