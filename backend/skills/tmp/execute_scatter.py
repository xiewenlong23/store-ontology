import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

# 临期商品数据
products = [
    {"name": "蒙牛酸奶", "expiry": "2026-05-27", "stock": 50},
    {"name": "伊利纯牛奶", "expiry": "2026-05-30", "stock": 30},
    {"name": "盼盼小面包", "expiry": "2026-06-05", "stock": 100},
]

# 转换日期
dates = [datetime.strptime(p["expiry"], "%Y-%m-%d") for p in products]
stocks = [p["stock"] for p in products]
names = [p["name"] for p in products]

# 创建散点图
fig, ax = plt.subplots(figsize=(10, 6))

# 根据剩余天数设置颜色
colors = ['red' if s <= 50 else 'orange' for s in stocks]
sizes = [s * 2 for s in stocks]

scatter = ax.scatter(dates, stocks, c=colors, s=sizes, alpha=0.7, edgecolors='black', linewidth=1)

# 添加标签
for i, name in enumerate(names):
    ax.annotate(name, (dates[i], stocks[i]), xytext=(5, 5), 
                textcoords='offset points', fontsize=10, fontproperties=None)

# 格式化x轴日期
ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
ax.xaxis.set_major_locator(mdates.DayLocator())

# 设置标题和标签
ax.set_title('临期商品 - 过期日期与库存数量关系', fontsize=14, fontweight='bold')
ax.set_xlabel('过期日期', fontsize=12)
ax.set_ylabel('库存数量', fontsize=12)

# 添加网格
ax.grid(True, linestyle='--', alpha=0.6)

# 添加图例
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='red', alpha=0.7, label='库存 ≤ 50'),
    Patch(facecolor='orange', alpha=0.7, label='库存 > 50'),
]
ax.legend(handles=legend_elements, loc='upper right')

plt.tight_layout()
plt.savefig('/tmp/near_expiry_scatter.png', dpi=150)
print("散点图已保存到 /tmp/near_expiry_scatter.png")