import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# 临期商品数据
products = ['蒙牛酸奶', '伊利纯牛奶', '盼盼小面包']
days_left = [5, 8, 14]
stock = [50, 30, 100]

# 创建散点图
fig, ax = plt.subplots(figsize=(10, 7))

# 绘制散点，节点大小与库存成正比
sizes = [s * 3 for s in stock]
colors = ['#e74c3c', '#f39c12', '#27ae60']  # 红色=紧急, 橙色=警告, 绿色=正常

scatter = ax.scatter(days_left, stock, s=sizes, c=colors, alpha=0.7, edgecolors='black', linewidth=1.5)

# 添加标签
for i, (x, y, name) in enumerate(zip(days_left, stock, products)):
    ax.annotate(name, (x, y), fontsize=11, ha='center', va='bottom', 
                xytext=(0, 10), textcoords='offset points', fontweight='bold')

# 设置标题和轴标签
ax.set_title('临期商品剩余天数 vs 库存数量', fontsize=16, fontweight='bold', pad=15)
ax.set_xlabel('剩余天数（天）', fontsize=12)
ax.set_ylabel('库存数量', fontsize=12)

# 添加网格
ax.grid(True, linestyle='--', alpha=0.6)
ax.set_xlim(0, 18)
ax.set_ylim(0, 120)

# 添加图例说明
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='#e74c3c', label='紧急（≤7天）'),
    Patch(facecolor='#f39c12', label='警告（8-10天）'),
    Patch(facecolor='#27ae60', label='正常（>10天）')
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=10)

# 添加说明文字
ax.text(0.98, 0.02, '* 节点大小表示库存数量', transform=ax.transAxes, 
        fontsize=9, ha='right', va='bottom', style='italic', color='gray')

plt.tight_layout()
plt.savefig('/tmp/near_expiry_scatter.png', dpi=150, bbox_inches='tight')
print("散点图已保存")
